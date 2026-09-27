"""Practical routine-error margin and validation-only base contamination screen.

No stream generation, gain search or inferential PASS is performed here. Callers
must establish real split provenance; hashes only bind the supplied record.
"""
from __future__ import annotations

import hashlib
import json
import math
from numbers import Real, Integral

from experiments.salience_v1.configuration import policy_constants


def digest(value) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"),
                                     allow_nan=False).encode()).hexdigest()


def nonnegative(value, name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, Real):
        raise ValueError(f"{name} must be a finite nonnegative number")
    value = float(value)
    if not math.isfinite(value) or value < 0:
        raise ValueError(f"{name} must be a finite nonnegative number")
    return value


def routine_gate(error: float, reference: float) -> dict:
    """One-sided practical margin, not floating-point closeness or a CI.

    The exact same signed excess can be aggregated by independent seed for the
    future inferential gate. No division by, clipping of, or floor on reference.
    """
    error = nonnegative(error, "routine error")
    reference = nonnegative(reference, "reference error")
    policy = policy_constants()["routine_retention_gate"]
    relative = nonnegative(policy["relative_allowance"], "relative allowance")
    absolute = nonnegative(policy["absolute_allowance_nmse"], "absolute allowance")
    allowance = relative * reference + absolute
    limit = reference + allowance
    if not math.isfinite(limit):
        raise ValueError("routine gate overflow")
    return {"routine_error": error, "routine_reference_error": reference,
            "absolute_change": error-reference, "allowed_increase": allowance,
            "limit": limit, "excess": error-limit, "feasible": error <= limit}


def checked_configuration(configuration: dict) -> dict:
    """Bind upstream choices and corpus conditions without claiming a full freeze."""
    expected = {"gain", "decay", "ridge", "observation_noise_std", "routine_writes",
                "correction_writes", "conflicting_corrections", "corpus_id"}
    if not isinstance(configuration, dict) or set(configuration) != expected:
        raise ValueError("complete base/corpus configuration required")
    c = {key: nonnegative(configuration[key], key) for key in
         ("gain", "decay", "ridge", "observation_noise_std")}
    if c["decay"] >= 1 or c["ridge"] <= 0:
        raise ValueError("decay must be below one and ridge positive")
    for key in ("routine_writes", "correction_writes", "conflicting_corrections"):
        v = configuration[key]
        if isinstance(v, bool) or not isinstance(v, Integral) or v < 0:
            raise ValueError(f"{key} must be a nonnegative integer")
        c[key] = int(v)
    if c["routine_writes"] < 1 or c["conflicting_corrections"] > c["correction_writes"]:
        raise ValueError("invalid routine/correction counts")
    if not isinstance(configuration["corpus_id"], str) or not configuration["corpus_id"].strip():
        raise ValueError("nonempty corpus_id required")
    c["corpus_id"] = configuration["corpus_id"]
    return c


def base_contamination_precheck(rows, *, backend: str, noise_std: float,
                                configuration: dict, expected_stream_ids,
                                comparison: str = "budget", split: str = "validation") -> dict:
    """Screen ONE upstream gain/decay/ridge setting before any radius search.

    Rejection means this design's base-preservation requirement failed, not that
    every possible hybrid must fail. Call for each prespecified candidate, retain
    all failures, and freeze the upstream winner before testing radii. This module
    does not implement the not-yet-registered gain/decay search or corpus.
    """
    p = policy_constants()
    if split != "validation":
        raise ValueError("base screen requires validation input")
    if backend not in p["capacities"] or comparison not in ("budget", "matched_nonbinding"):
        raise ValueError("unknown backend or comparison")
    if comparison == "matched_nonbinding" and backend == "field":
        raise ValueError("matched field/direct arms share the direct-moment screen")
    noise = nonnegative(noise_std, "cue noise")
    if noise not in p["required_cue_noise"]["standard_deviations"]:
        raise ValueError("undeclared cue noise")
    c = checked_configuration(configuration)
    ids = list(expected_stream_ids)
    if (not ids or any(not isinstance(s, str) or not s for s in ids)
            or len(set(ids)) != len(ids)):
        raise ValueError("unique expected validation stream ids required")
    ids = sorted(ids)
    clean = {}
    for row in rows:
        stream = row["stream_id"]
        if stream not in ids or stream in clean:
            raise ValueError("duplicate or unexpected base-screen stream")
        clean[stream] = {"stream_id": stream,
            "base_routine_error": nonnegative(row["base_routine_error"], "base error"),
            "routine_reference_error": nonnegative(row["routine_reference_error"], "reference")}
    if set(clean) != set(ids):
        raise ValueError("incomplete base-screen stream set")
    er, ref = [math.fsum(clean[s][k] / len(ids) for s in ids) for k in
               ("base_routine_error", "routine_reference_error")]
    check = routine_gate(er, ref)
    return {"schema": "sal1-base-screen-v1", "policy_sha256": digest(p),
            "backend": backend, "noise_std": noise, "comparison": comparison, "split": split,
            "configuration": c, "configuration_sha256": digest(c),
            "conflicting_fraction": c["conflicting_corrections"] /
                                    (c["routine_writes"]+c["correction_writes"]),
            "validation_stream_ids": ids, "rows": [clean[s] for s in ids],
            "gate": check,
            "status": "eligible" if check["feasible"] else "base_contamination",
            "interpretation": "design_screen_not_universal_hybrid_infeasibility"}


def checked_base_precheck(record: dict, *, backend: str, noise_std: float,
                          comparison: str) -> dict:
    if not isinstance(record, dict):
        raise ValueError("a base contamination precheck is required")
    try:
        rebuilt = base_contamination_precheck(record["rows"], backend=backend,
            noise_std=noise_std, comparison=comparison, configuration=record["configuration"],
            expected_stream_ids=record["validation_stream_ids"])
    except (KeyError, TypeError) as exc:
        raise ValueError("incomplete base contamination precheck") from exc
    if record != rebuilt:
        raise ValueError("base precheck does not match policy, configuration or group")
    return rebuilt
