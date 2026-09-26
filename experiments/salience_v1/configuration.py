"""Fixed SAL-1 development policy. This is not a complete preregistration.

Capacities and policy values are inputs, never inferred from runtime object sizes.
Every construction asserts the common byte cap; a failing build must abort rather
than resizing an arm. The complete registration must pin this file and its JSON.
"""
from __future__ import annotations

import json
from pathlib import Path

from experiments.salience_v1.memory import (
    DirectMoment, FieldPredictor, ForgettingRLS, SurpriseMemory,
)

POLICY_PATH = Path(__file__).with_name("POLICY_CONSTANTS.json")


def policy_constants() -> dict:
    """Read a fresh policy object; retain no stream data or mutable policy cache."""
    return json.loads(POLICY_PATH.read_text(encoding="utf-8"))


def build_fixed_memory(backend: str, *, comparison: str = "budget") -> SurpriseMemory:
    """Construct literal-capacity arms; do not use fit_budget in this path.

    `matched_nonbinding` fixes k=4 for all backends. Its eventual corpus must also
    ensure capacity does not bind; a constructor cannot establish that property.
    Fixed backend settings here are for development, not validation-selected
    gain/decay settings for the as-yet unimplemented performance evaluator.
    """
    factories = {"field": FieldPredictor, "direct_moment": DirectMoment, "rls": ForgettingRLS}
    if backend not in factories:
        raise ValueError("unknown backend")
    if comparison not in ("budget", "matched_nonbinding"):
        raise ValueError("unknown comparison")
    p = policy_constants()
    if p["schema"] != "sal1-policy-v2":
        raise ValueError("unsupported fixed policy schema")
    capacity = (p["capacities"][backend] if comparison == "budget"
                else p["nonbinding_matched_capacity"])
    settings = p["development_backend_settings"]
    base = factories[backend](p["cue_dimension"], p["outcome_dimension"],
                              decay=settings["decay"], ridge=settings["ridge"])
    return SurpriseMemory(base, capacity=capacity, threshold=p["threshold_nmse"],
                          radius=p["recall_and_revision_radius"],
                          byte_budget=p["instance_owned_byte_cap"])
