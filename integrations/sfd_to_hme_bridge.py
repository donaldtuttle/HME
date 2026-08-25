#!/usr/bin/env python3
"""Deterministic Symbolic Field Dynamics → HME bridge reproduction."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Sequence

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
EXPECTED_RECEIPT = {
    "engine_sha256": ACTIVE_ENGINE_SHA256,
    "signature_hash": "7fef693477ffaf55104f12f25be9b91b72a8ab8e4aed8d13c4c3604fa5719ce9",
    "trajectory_hash": "e90921fbd2fd990efab3b684249de68a28e7186e8fc226d2f3ca3a4038e8f5db",
    "artifact_id": "7264c7cc7b27aceb15f1",
    "payload_hash": "cae26ced8c2e11a484d0a5abeb7da26959c93633a44b169499957b1da20e2ea8",
    "pattern_hash": "3381e092455f79f3e72816fa6e31eba39929264fa7b4986e58faa8227cab2d67",
    "confidence": 0.9307851800354883,
}


def _file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


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
    return report


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", help="Optional JSON report path")
    args = parser.parse_args(argv)

    report = run_bridge()
    rendered = json.dumps(report, indent=2, ensure_ascii=False)
    print(rendered)

    if args.output:
        path = Path(args.output)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(rendered + "\n", encoding="utf-8")

    expected = EXPECTED_RECEIPT
    checks = [
        report["engine_sha256"] == expected["engine_sha256"],
        report["signature_hash"] == expected["signature_hash"],
        report["trajectory_hash"] == expected["trajectory_hash"],
        report["artifact"]["artifact_id"] == expected["artifact_id"],
        report["artifact"]["payload_hash"] == expected["payload_hash"],
        report["artifact"]["pattern_hash"] == expected["pattern_hash"],
        report["artifact"]["glyph"] == "Σ◯",
        report["checks"]["top_is_artifact"],
        abs(report["retrieval"]["confidence"] - expected["confidence"]) < 1.0e-12,
    ]
    return 0 if all(checks) else 2


if __name__ == "__main__":
    raise SystemExit(main())
