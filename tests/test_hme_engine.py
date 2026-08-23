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
    assert digest == "f81fb49e265d83f5206220584dfc6cabf28aeee5266aca33654182be1549c080"


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
