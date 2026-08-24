from __future__ import annotations

import hashlib
from pathlib import Path

import numpy as np

import qosmos_hme_engine as hme


def test_built_in_self_test_passes() -> None:
    report = hme._self_test()
    assert report["status"] == "PASS"
    assert report["artifact_hash_deterministic"] is True
    assert report["field_deterministic"] is True


def test_default_write_operator_is_sigma_ring() -> None:
    engine = hme.QOSMOSHMEEngine(memory_size=24, encoding_resolution=8, seed=11)
    artifact = engine.encode_memory([0.1, 0.2, 0.3, 0.4], (12, 12))
    assert artifact.glyph == "Σ◯"


def test_field_and_ledger_have_distinct_roles() -> None:
    engine = hme.QOSMOSHMEEngine(memory_size=32, encoding_resolution=8, seed=9)
    payload = np.linspace(-1.0, 1.0, 8)
    artifact = engine.encode_memory(payload, (16, 16), glyph="Σ◯")
    retrieval = engine.retrieve_memory((16, 16), query=payload)
    assert retrieval.hits
    assert retrieval.hits[0].artifact_id == artifact.artifact_id
    assert np.linalg.norm(retrieval.decoded_vector) > 0.0


def test_active_source_pin() -> None:
    source = Path(hme.__file__).resolve()
    digest = hashlib.sha256(source.read_bytes()).hexdigest()
    assert digest == "1caff9577e8a4bdaa2b0510c79673035081a967a25f15067bfa8ce99ccca6d11"


def test_collapse_write_emits_sigma_lineage() -> None:
    engine = hme.QOSMOSHMEEngine(
        memory_size=24,
        encoding_resolution=8,
        collapse_config=hme.CollapseConfig(
            enabled=True,
            lambda_c=0.1,
            cooldown_steps=0,
        ),
        seed=42,
    )
    result = engine.step(
        np.ones((24, 24), dtype=np.complex128),
        input_blend=1.0,
        memory_payload="collapse_commit",
        memory_position=(12, 12),
        collapse_override=True,
    )

    assert result.meta.collapse_triggered is True
    assert result.collapse_event is not None
    assert result.memory_artifact is not None
    assert result.memory_artifact.glyph == "Σ◯"
    relations = {edge.relation for edge in engine.qmesh.edges}
    assert "Λψ→Σ◯:consolidate" in relations


def test_no_match_gate_precedes_cpsi_salience() -> None:
    engine = hme.QOSMOSHMEEngine(
        memory_size=24,
        encoding_resolution=8,
        hme_config=hme.HMEConfig(memory_size=24, encoding_resolution=8, relevance_threshold=0.99),
        collapse_config=hme.CollapseConfig(influence_retrieval=True, retrieval_weight=1.0),
        seed=1,
    )
    artifact = engine.encode_memory(
        "alpha", (12, 12), metadata={"c_psi": 1.0e6}
    )
    result = engine.retrieve_memory((0, 0), query="unrelated")
    assert result.outcome == "NO_MATCH"
    assert result.hits == []
    assert "base_score" not in artifact.metadata
    assert "collapse_salience" not in artifact.metadata
    assert "final_score" not in artifact.metadata


def test_retrieval_salience_uses_headroom_after_eligibility() -> None:
    engine = hme.QOSMOSHMEEngine(
        memory_size=24,
        encoding_resolution=8,
        collapse_config=hme.CollapseConfig(influence_retrieval=True, retrieval_weight=0.5),
        seed=2,
    )
    artifact = engine.encode_memory("alpha", (12, 12), metadata={"c_psi": 2.0})
    result = engine.retrieve_memory((12, 12), query="alpha")
    hit = next(hit for hit in result.hits if hit.artifact_id == artifact.artifact_id)
    expected_salience = 2.0 / 3.0
    expected = hit.base_score + 0.5 * expected_salience * (1.0 - hit.base_score)
    assert np.isclose(hit.collapse_salience, expected_salience)
    assert np.isclose(hit.final_score, expected)
    assert hit.final_score >= hit.base_score
    assert np.isclose(result.confidence, hit.base_score)


def test_low_inscription_salience_retains_relevant_hits() -> None:
    engine = hme.QOSMOSHMEEngine(
        memory_size=24,
        encoding_resolution=8,
        collapse_config=hme.CollapseConfig(
            enable_inscription_rejection=True,
            rejection_threshold=0.5,
        ),
        seed=3,
    )
    artifact = engine.encode_memory("alpha", (12, 12), metadata={"c_psi": 0.1})
    result = engine.retrieve_memory((12, 12), query="alpha")
    assert result.outcome == "LOW_INSCRIPTION_SALIENCE"
    assert result.rejected is True
    assert result.rejection_reason
    assert result.hits
    assert result.hits[0].artifact_id == artifact.artifact_id


def test_write_gain_is_optional_bounded_and_cpsi_is_durable() -> None:
    base = hme.QOSMOSHMEEngine(memory_size=24, encoding_resolution=8, seed=4)
    influenced = hme.QOSMOSHMEEngine(
        memory_size=24,
        encoding_resolution=8,
        collapse_config=hme.CollapseConfig(
            influence_write_gain=True,
            write_gain_scale=0.25,
            write_gain_floor=0.05,
            write_gain_ceiling=1.5,
        ),
        seed=4,
    )
    a = base.encode_memory("alpha", (12, 12), recursive_factor=0.2, metadata={"c_psi": 4.0})
    b = influenced.encode_memory("alpha", (12, 12), recursive_factor=0.2, metadata={"c_psi": 4.0})
    assert np.isclose(a.gain, 0.2)
    assert np.isclose(b.gain, 0.3)
    assert b.metadata["c_psi"] == 4.0


def test_step_persists_lowercase_cpsi_only_for_new_salience_contract() -> None:
    engine = hme.QOSMOSHMEEngine(memory_size=24, encoding_resolution=8, seed=5)
    result = engine.step(
        np.ones((24, 24), dtype=np.complex128),
        memory_payload="tick-memory",
        memory_position=(12, 12),
        collapse_override=False,
    )
    assert result.memory_artifact is not None
    assert "c_psi" in result.memory_artifact.metadata
    assert "C_psi" not in result.memory_artifact.metadata

    override = engine.step(
        np.ones((24, 24), dtype=np.complex128),
        memory_payload="tick-memory-2",
        memory_position=(12, 12),
        collapse_override=False,
        metadata={"c_psi": -999.0},
    )
    assert override.memory_artifact is not None
    assert override.memory_artifact.metadata["c_psi"] == override.meta.c_psi
