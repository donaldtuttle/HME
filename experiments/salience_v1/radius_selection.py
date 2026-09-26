"""Deterministic reduction of validation-only score tables, not an evaluator.

No streams or evaluation seeds are generated here. The future registered harness
must establish split provenance; a string saying 'validation' is not proof of it.
Every radius must have every validation stream. No partial-success selection.
"""
from __future__ import annotations

import hashlib
import json
import math

from experiments.salience_v1.configuration import policy_constants
from experiments.salience_v1.routine_gate import routine_gate, checked_base_precheck


def _digest(value) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"),
                                     allow_nan=False).encode()).hexdigest()


def select_validation_radius(rows, *, backend: str, noise_std: float,
                             comparison: str = "budget", split: str = "validation",
                             eviction: str = "fifo", base_precheck: dict | None = None) -> dict:
    """Minimize stream-balanced joint error among routine-feasible radii.

    Requires a checked upstream base screen. A rejected screen returns a distinct
    result without consuming rows, so the future harness can supply a lazy search.
    Ties use the smaller radius. An infeasible table returns radius=None with all
    candidate scores retained; constructors reject it. This procedure is fixed in
    the draft, not a claim that a complete SAL-1 protocol has been registered.
    """
    p = policy_constants()
    if split != "validation" or eviction != "fifo":
        raise ValueError("radius selection requires validation-only FIFO scores")
    if backend not in p["capacities"] or comparison not in ("budget", "matched_nonbinding"):
        raise ValueError("unknown backend or comparison")
    if comparison == "matched_nonbinding" and backend == "field":
        raise ValueError("matched field/direct arms must share the direct-moment selection")
    if isinstance(noise_std, bool) or noise_std not in p["required_cue_noise"]["standard_deviations"]:
        raise ValueError("noise level is not in the declared design")
    precheck = checked_base_precheck(base_precheck, backend=backend, noise_std=noise_std,
                                     comparison=comparison)
    common = {"schema": "sal1-radius-selection-v2", "split": split, "eviction": eviction,
              "backend": backend, "comparison": comparison, "noise_std": float(noise_std),
              "policy_sha256": _digest(p), "base_precheck": precheck}
    if precheck["status"] == "base_contamination":
        # Do not touch/consume a lazy radius table when the upstream setting fails.
        return {**common, "status": "base_contamination", "radius": None, "scores": [],
                "validation_stream_ids": precheck["validation_stream_ids"], "rows": []}
    candidates = p["radius_selection"]["candidate_radii"]
    grouped = {r: {} for r in candidates}
    rows = list(rows)
    if not rows:
        raise ValueError("empty validation table")
    cleaned = []
    for row in rows:
        stream = row["stream_id"]
        r = row["radius"]
        if not isinstance(stream, str) or not stream or isinstance(r, bool) or r not in grouped:
            raise ValueError("invalid stream id or candidate radius")
        if stream in grouped[r]:
            raise ValueError("duplicate radius/stream observation")
        item = {"stream_id": stream, "radius": float(r)}
        for key in ("correction_error", "routine_error", "routine_reference_error"):
            if isinstance(row[key], bool):
                raise ValueError("errors must be finite nonnegative numbers")
            v = float(row[key])
            if not math.isfinite(v) or v < 0:
                raise ValueError("errors must be finite nonnegative numbers")
            item[key] = v
        grouped[r][stream] = item
        cleaned.append(item)
    stream_ids = sorted(grouped[candidates[0]])
    if not stream_ids or any(set(g) != set(stream_ids) for g in grouped.values()):
        raise ValueError("all candidate radii require the same complete validation streams")
    if stream_ids != precheck["validation_stream_ids"]:
        raise ValueError("radius streams must match the base screen exactly")
    references = {v["stream_id"]: v["routine_reference_error"] for v in precheck["rows"]}
    for stream in stream_ids:
        if len({grouped[r][stream]["routine_reference_error"] for r in candidates}) != 1:
            raise ValueError("routine reference must not change with radius")
        if grouped[candidates[0]][stream]["routine_reference_error"] != references[stream]:
            raise ValueError("radius reference must match the base screen")
    table = []
    for r in candidates:
        records = [grouped[r][s] for s in stream_ids]
        ec, er, ref = [math.fsum(v[k] / len(records) for v in records) for k in
                       ("correction_error", "routine_error", "routine_reference_error")]
        table.append({"radius": r, "correction_error": ec, "routine_error": er,
                      "routine_reference_error": ref, "joint_error": ec/2+er/2,
                      "routine_gate": routine_gate(er, ref),
                      "feasible": routine_gate(er, ref)["feasible"]})
    feasible = [v for v in table if v["feasible"]]
    winner = min(feasible, key=lambda v: (v["joint_error"], v["radius"])) if feasible else None
    return {**common, "status": "selected" if winner else "infeasible",
            "radius": winner["radius"] if winner else None, "scores": table,
            "validation_stream_ids": stream_ids,
            "rows": sorted(cleaned, key=lambda v: (v["radius"], v["stream_id"]))}


def checked_radius(selection: dict, *, backend: str, noise_std: float,
                   comparison: str) -> float:
    """Recompute a selection and check policy/group binding before construction.

    This detects accidental edits/mismatched use, not fabricated provenance.
    Registration must freeze the table and selected values before test generation.
    """
    source = "direct_moment" if comparison == "matched_nonbinding" and backend == "field" else backend
    rebuilt = select_validation_radius(selection["rows"], backend=source,
                                        noise_std=noise_std, comparison=comparison,
                                        base_precheck=selection.get("base_precheck"))
    if selection != rebuilt:
        raise ValueError("selection does not match policy, noise, backend or validation table")
    if rebuilt["status"] == "base_contamination":
        raise ValueError("base contamination screen failed; radius search skipped")
    if rebuilt["status"] != "selected":
        raise ValueError("no feasible validation radius; no fallback permitted")
    return float(rebuilt["radius"])
