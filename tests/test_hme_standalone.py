from __future__ import annotations

import hashlib
import importlib.util
import itertools
import json
from pathlib import Path
import subprocess
import sys

import numpy as np
import pytest

import hme_engine as hme

ROOT = Path(__file__).resolve().parents[1]
ARCHIVE = ROOT / "archive/v2.2"
OLD_PIN = "1caff9577e8a4bdaa2b0510c79673035081a967a25f15067bfa8ce99ccca6d11"


@pytest.fixture(scope="module")
def prior():
    path = ARCHIVE / "qosmos_hme_engine.py"
    assert hashlib.sha256(path.read_bytes()).hexdigest() == OLD_PIN
    spec = importlib.util.spec_from_file_location("hme_v2_reference", path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


@pytest.mark.parametrize("switches", list(itertools.product((False, True), repeat=3)))
def test_memory_core_matches_prior_version(prior, switches):
    """Compare state and ranked outputs across the API/schema boundary."""
    write, rerank, reject = switches
    common = dict(memory_size=24, encoding_resolution=8, seed=17)
    salience = dict(influence_write_gain=write, influence_retrieval=rerank,
                    retrieval_weight=0.5, rejection_threshold=0.5)
    old = prior.QOSMOSHMEEngine(**common, collapse_config=prior.CollapseConfig(
        **salience, enable_inscription_rejection=reject))
    new = hme.HMEEngine(**common, salience_config=hme.SalienceConfig(
        **salience, enable_salience_rejection=reject))
    rng = np.random.default_rng(23)
    payloads = [rng.normal(size=5), rng.normal(size=8),
                rng.normal(size=13) + 1j*rng.normal(size=13), "alpha", "beta"]
    positions = [(0, 0), (12, 12), (23, 23), (12, 12), (12, 12)]
    id_map = {}
    for i, (payload, position) in enumerate(zip(payloads, positions)):
        sal = [0.1, 2.0, -1.0, None, 8.0][i]
        a = old.encode_memory(payload, position, recursive_factor=0.2, observer_weight=1.25,
                             metadata={"c_psi": sal}, t=i)
        b = new.encode_memory(payload, position, strength=0.2, write_weight=1.25,
                             metadata={"write_salience": sal}, t=i)
        id_map[a.artifact_id] = b.artifact_id
        assert a.artifact_id != b.artifact_id
        assert (a.payload_hash, a.pattern_hash, a.gain) == (b.payload_hash, b.pattern_hash, b.gain)
        np.testing.assert_array_equal(old.hme.field, new.hme.field)
        np.testing.assert_array_equal(old.hme._payloads[a.artifact_id], new.hme._payloads[b.artifact_id])
        np.testing.assert_array_equal(old.hme._patterns[a.artifact_id], new.hme._patterns[b.artifact_id])

    queries = list(zip(positions, payloads)) + [((12, 12), None), ((5, 6), "unknown"), ((12, 12), rng.normal(size=8))]
    for position, query in queries:
        a = old.retrieve_memory(position, query=query, top_k=3)
        b = new.retrieve_memory(position, query=query, top_k=3)
        assert [id_map[h.artifact_id] for h in a.hits] == [h.artifact_id for h in b.hits]
        assert a.confidence == b.relevance_score
        assert a.rejected == b.rejected
        assert a.outcome.replace("LOW_INSCRIPTION_SALIENCE", "LOW_WRITE_SALIENCE") == b.outcome
        for ah, bh in zip(a.hits, b.hits):
            for attr in ("base_score", "final_score", "distance_score", "query_score", "pattern_score"):
                assert getattr(ah, attr) == getattr(bh, attr)
            assert ah.collapse_salience == bh.salience
        for attr in ("window", "decoded_surface", "decoded_vector"):
            np.testing.assert_array_equal(getattr(a, attr), getattr(b, attr))


def test_plain_schema_and_insertion_lineage():
    engine = hme.HMEEngine(memory_size=24, encoding_resolution=8)
    first = engine.encode_memory("alpha", (12, 12))
    second = engine.encode_memory("beta", (12, 12))
    assert first.operation == "write"
    assert "glyph" not in first.to_dict()
    assert "observer_weight" not in first.to_dict()
    edge = engine.lineage.edges[0]
    assert (edge.relation, edge.source, edge.target) == (
        "next_memory", f"memory:{first.artifact_id}", f"memory:{second.artifact_id}")
    result = engine.retrieve_memory((12, 12), query="beta").to_dict()
    assert result["schema_id"] == "hme-v3"
    assert "relevance_score" in result and "confidence" not in result
    assert "salience" in result["hits"][0]
    assert engine.hme.snapshot()["schema_id"] == "hme-v3"


def test_relevance_gate_precedes_salience_and_does_not_mutate_metadata():
    engine = hme.HMEEngine(
        hme_config=hme.HMEConfig(memory_size=24, encoding_resolution=8, relevance_threshold=0.99),
        salience_config=hme.SalienceConfig(influence_retrieval=True, retrieval_weight=1.0))
    artifact = engine.encode_memory("alpha", (12, 12), metadata={"write_salience": 1e6})
    before = dict(artifact.metadata)
    result = engine.retrieve_memory((0, 0), query="unrelated")
    assert result.outcome == "NO_MATCH" and not result.hits
    assert artifact.metadata == before


def test_salience_rejection_keeps_hits_and_base_score():
    engine = hme.HMEEngine(salience_config=hme.SalienceConfig(
        influence_retrieval=True, enable_salience_rejection=True, rejection_threshold=0.5))
    artifact = engine.encode_memory("alpha", (32, 32), metadata={"write_salience": 0.1})
    result = engine.retrieve_memory((32, 32), query="alpha")
    assert result.hits[0].artifact_id == artifact.artifact_id
    assert result.outcome == "LOW_WRITE_SALIENCE" and result.rejected
    assert result.relevance_score == result.hits[0].base_score
    assert result.hits[0].final_score > result.relevance_score


def test_field_only_retains_surface_but_cannot_identify_item():
    engine = hme.HMEEngine()
    engine.encode_memory("alpha", (32, 32))
    engine.hme.records.clear()
    engine.hme._payloads.clear()
    engine.hme._patterns.clear()
    result = engine.retrieve_memory((32, 32), query="alpha")
    assert np.linalg.norm(result.decoded_surface) > 0
    assert not result.hits and result.outcome == "NO_MATCH"
    assert not np.any(result.decoded_vector)


def test_merge_decay_and_eviction_preserve_numerics(prior):
    old = prior.HME(config=prior.HMEConfig(memory_size=24, encoding_resolution=8, max_records=2, field_decay=0.1))
    new = hme.HME(config=hme.HMEConfig(memory_size=24, encoding_resolution=8, max_records=2, field_decay=0.1))
    for i in range(4):
        payload = np.arange(8) + i
        old.encode(payload, (i*6, i*6))
        new.encode(payload, (i*6, i*6))
    assert len(old.records) == len(new.records) == 2
    old.decay(0.2)
    new.decay(0.2)
    old.merge(np.ones((12, 12)), weight=0.3)
    new.merge(np.ones((12, 12)), weight=0.3)
    np.testing.assert_array_equal(old.field, new.field)


def test_cli_and_import_require_no_framework_modules():
    code = "import sys, hme_engine; assert not any(n.startswith(('qosmos', 'core.', 'archive.')) for n in sys.modules); assert hme_engine._self_test()['status'] == 'PASS'"
    subprocess.run([sys.executable, "-c", code], cwd=ROOT, check=True)
    output = subprocess.check_output([sys.executable, str(ROOT / "hme_engine.py"), "--self-test"], text=True)
    assert json.loads(output)["status"] == "PASS"


def test_source_provenance_matches_both_implementations():
    provenance = json.loads((ROOT / "SOURCE_PROVENANCE.json").read_text())
    for key in ("active_engine", "previous_engine"):
        entry = provenance[key]
        assert hashlib.sha256((ROOT / entry["path"]).read_bytes()).hexdigest() == entry["sha256"]


@pytest.mark.parametrize("data", [[], [np.nan], [np.inf]])
def test_invalid_payloads_are_rejected(data):
    with pytest.raises(ValueError):
        hme.HMEEngine().encode_memory(data, (32, 32))


@pytest.mark.parametrize("operation", ["", " ", 5])
def test_invalid_operation_is_rejected_without_a_write(operation):
    engine = hme.HMEEngine()
    with pytest.raises(ValueError):
        engine.encode_memory("alpha", (32, 32), operation=operation)
    assert not engine.hme.records and not np.any(engine.hme.field)
