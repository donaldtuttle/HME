#!/usr/bin/env python3
"""Deterministic Symbolic Field Dynamics → HME bridge reproduction."""

from __future__ import annotations

import argparse
import hashlib
import json
import platform
import sys
from pathlib import Path
from typing import Mapping, Sequence

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(Path(__file__).resolve().parent) not in sys.path:
    sys.path.insert(0, str(Path(__file__).resolve().parent))

from qosmos_hme_engine import QOSMOSCoreHME  # noqa: E402
from symbolic_field_dynamics import (  # noqa: E402
    SymbolicFieldConfig,
    SymbolicFieldDynamicsEngine,
)

ACTIVE_ENGINE_SHA256 = (
    "1caff9577e8a4bdaa2b0510c79673035081a967a25f15067bfa8ce99ccca6d11"
)
STABLE_EXPECTATIONS = {
    "engine_sha256": ACTIVE_ENGINE_SHA256,
    "signature_hash": "7fef693477ffaf55104f12f25be9b91b72a8ab8e4aed8d13c4c3604fa5719ce9",
    "trajectory_hash": "e90921fbd2fd990efab3b684249de68a28e7186e8fc226d2f3ca3a4038e8f5db",
    "confidence": 0.9307851800354883,
}

# The bridge's exact artifact identity includes SHA-256 hashes of floating-point
# payload and FFT-derived pattern bytes. Heterogeneous GitHub runners have
# produced two complete, internally consistent byte receipts while preserving
# the source hash, symbolic-field hashes, glyph, ranking result, and score.
# Keep variants tuple-locked so components from different receipts cannot mix.
RECEIPT_VARIANTS: dict[str, dict[str, str]] = {
    "numeric_bytes_7264": {
        "artifact_id": "7264c7cc7b27aceb15f1",
        "payload_hash": "cae26ced8c2e11a484d0a5abeb7da26959c93633a44b169499957b1da20e2ea8",
        "pattern_hash": "3381e092455f79f3e72816fa6e31eba39929264fa7b4986e58faa8227cab2d67",
    },
    "numeric_bytes_d902": {
        "artifact_id": "d902825c52772941b345",
        "payload_hash": "d363f67bdd7ac2d963c7884cd1750211872314cac8b198fb8c43681c46d80b4b",
        "pattern_hash": "f28f0fa635dd31ad745d096fa948791ab0e5a7bddbe3e142a414c4ed97f754b3",
    },
}


def _file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def classify_receipt(report: Mapping[str, object]) -> str | None:
    artifact = report.get("artifact")
    if not isinstance(artifact, Mapping):
        return None
    observed = {
        "artifact_id": artifact.get("artifact_id"),
        "payload_hash": artifact.get("payload_hash"),
        "pattern_hash": artifact.get("pattern_hash"),
    }
    for name, expected in RECEIPT_VARIANTS.items():
        if observed == expected:
            return name
    return None


def validate_bridge_report(report: Mapping[str, object]) -> list[str]:
    failures: list[str] = []
    expected = STABLE_EXPECTATIONS

    for field in ("engine_sha256", "signature_hash", "trajectory_hash"):
        if report.get(field) != expected[field]:
            failures.append(field)

    artifact = report.get("artifact")
    retrieval = report.get("retrieval")
    checks = report.get("checks")
    if not isinstance(artifact, Mapping) or artifact.get("glyph") != "Σ◯":
        failures.append("artifact.glyph")
    if not isinstance(checks, Mapping) or checks.get("top_is_artifact") is not True:
        failures.append("checks.top_is_artifact")
    if report.get("receipt_variant") not in RECEIPT_VARIANTS:
        failures.append("receipt_variant")

    confidence = retrieval.get("confidence") if isinstance(retrieval, Mapping) else None
    try:
        confidence_ok = abs(float(confidence) - float(expected["confidence"])) < 1.0e-12
    except (TypeError, ValueError):
        confidence_ok = False
    if not confidence_ok:
        failures.append("retrieval.confidence")

    return failures


def run_bridge() -> dict:
    field_engine = SymbolicFieldDynamicsEngine(
        SymbolicFieldConfig(
            grid_size=96,
            num_steps=120,
            lattice_size=6,
            seed=7312026,
            signature_size=24,
        )
    )
    result = field_engine.run(glyph="Ξ")

    hme = QOSMOSCoreHME(memory_size=64, encoding_resolution=16, seed=7)
    artifact = field_engine.commit_to_hme(
        hme,
        result,
        position=(32, 32),
        recursive_factor=0.15,
        commit_glyph="Σ◯",
    )
    payload = field_engine.to_hme_payload(result, dimensions=16)
    retrieval = hme.retrieve_memory((32, 32), query=payload, top_k=3)

    top_id = retrieval.hits[0].artifact_id if retrieval.hits else None
    report = {
        "environment": {
            "python": platform.python_version(),
            "numpy": np.__version__,
            "machine": platform.machine(),
            "platform": platform.platform(),
        },
        "engine_sha256": _file_sha256(ROOT / "qosmos_hme_engine.py"),
        "signature_hash": result.signature_hash,
        "trajectory_hash": result.trajectory_hash,
        "artifact": artifact.to_dict(),
        "retrieval": retrieval.to_dict(),
        "checks": {
            "top_hit": top_id,
            "top_is_artifact": top_id == artifact.artifact_id,
            "glyph": artifact.glyph,
        },
    }
    report["receipt_variant"] = classify_receipt(report)
    report["checks"]["known_receipt_variant"] = report["receipt_variant"] is not None
    return report


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", help="Optional JSON report path")
    args = parser.parse_args(argv)

    report = run_bridge()
    failures = validate_bridge_report(report)
    report["validation"] = {
        "status": "PASS" if not failures else "FAIL",
        "failures": failures,
    }
    rendered = json.dumps(report, indent=2, ensure_ascii=False)
    print(rendered)

    if args.output:
        path = Path(args.output)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(rendered + "\n", encoding="utf-8")

    return 0 if not failures else 2


if __name__ == "__main__":
    raise SystemExit(main())
