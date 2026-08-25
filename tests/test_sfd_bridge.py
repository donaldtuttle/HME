from __future__ import annotations

from integrations.sfd_to_hme_bridge import EXPECTED_RECEIPT, run_bridge


def test_verified_sfd_to_hme_bridge() -> None:
    report = run_bridge()
    expected = EXPECTED_RECEIPT
    assert report["engine_sha256"] == expected["engine_sha256"]
    assert report["signature_hash"] == expected["signature_hash"]
    assert report["trajectory_hash"] == expected["trajectory_hash"]
    assert report["artifact"]["artifact_id"] == expected["artifact_id"]
    assert report["artifact"]["payload_hash"] == expected["payload_hash"]
    assert report["artifact"]["pattern_hash"] == expected["pattern_hash"]
    assert report["artifact"]["glyph"] == "Σ◯"
    assert report["checks"]["top_is_artifact"] is True
    assert abs(report["retrieval"]["confidence"] - expected["confidence"]) < 1.0e-12
