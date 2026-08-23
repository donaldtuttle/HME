from __future__ import annotations

from integrations.sfd_to_hme_bridge import run_bridge


EXPECTED = {
    "signature_hash": "7fef693477ffaf55104f12f25be9b91b72a8ab8e4aed8d13c4c3604fa5719ce9",
    "trajectory_hash": "e90921fbd2fd990efab3b684249de68a28e7186e8fc226d2f3ca3a4038e8f5db",
    "artifact_id": "d902825c52772941b345",
    "payload_hash": "d363f67bdd7ac2d963c7884cd1750211872314cac8b198fb8c43681c46d80b4b",
    "pattern_hash": "f28f0fa635dd31ad745d096fa948791ab0e5a7bddbe3e142a414c4ed97f754b3",
    "confidence": 0.9307851800354882,
}


def test_verified_sfd_to_hme_bridge() -> None:
    report = run_bridge()
    assert report["signature_hash"] == EXPECTED["signature_hash"]
    assert report["trajectory_hash"] == EXPECTED["trajectory_hash"]
    assert report["artifact"]["artifact_id"] == EXPECTED["artifact_id"]
    assert report["artifact"]["payload_hash"] == EXPECTED["payload_hash"]
    assert report["artifact"]["pattern_hash"] == EXPECTED["pattern_hash"]
    assert report["artifact"]["glyph"] == "Σ◯"
    assert report["checks"]["top_is_artifact"] is True
    assert abs(report["retrieval"]["confidence"] - EXPECTED["confidence"]) < 1.0e-12
