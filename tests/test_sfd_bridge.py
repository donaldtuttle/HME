from __future__ import annotations

from integrations.sfd_to_hme_bridge import (
    RECEIPT_VARIANTS,
    STABLE_EXPECTATIONS,
    classify_receipt,
    run_bridge,
    validate_bridge_report,
)


def test_verified_sfd_to_hme_bridge() -> None:
    report = run_bridge()
    expected = STABLE_EXPECTATIONS

    assert validate_bridge_report(report) == []
    assert report["engine_sha256"] == expected["engine_sha256"]
    assert report["signature_hash"] == expected["signature_hash"]
    assert report["trajectory_hash"] == expected["trajectory_hash"]
    assert report["artifact"]["glyph"] == "Σ◯"
    assert report["checks"]["top_is_artifact"] is True
    assert report["checks"]["known_receipt_variant"] is True
    assert abs(report["retrieval"]["confidence"] - expected["confidence"]) < 1.0e-12

    variant = classify_receipt(report)
    assert variant == report["receipt_variant"]
    assert variant in RECEIPT_VARIANTS
    observed = {
        "artifact_id": report["artifact"]["artifact_id"],
        "payload_hash": report["artifact"]["payload_hash"],
        "pattern_hash": report["artifact"]["pattern_hash"],
    }
    assert observed == RECEIPT_VARIANTS[variant]
