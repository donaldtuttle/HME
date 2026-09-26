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


def build_fixed_memory(backend: str, *, comparison: str = "budget",
                       eviction: str = "fifo", radius_profile: str = "fixed_development",
                       noise_std: float | None = None, selection: dict | None = None) -> SurpriseMemory:
    """Construct literal-capacity arms; do not use fit_budget in this path.

    `matched_nonbinding` fixes k=4 for all backends. Its eventual corpus must also
    ensure capacity does not bind; a constructor cannot establish that property.
    Fixed backend settings here are for development, not validation-selected
    gain/decay settings for the as-yet unimplemented performance evaluator.
    The default fixed_development radius is NOT a primary efficacy configuration.
    Selected profiles use the screened decay/ridge, not development defaults.
    The future stream runner must also use the bound observation gain and corpus.
    Selected profiles require a checked validation table. The isolated eviction
    ablation reuses that same FIFO-selected radius; it is never retuned here.
    """
    factories = {"field": FieldPredictor, "direct_moment": DirectMoment, "rls": ForgettingRLS}
    if backend not in factories:
        raise ValueError("unknown backend")
    if comparison not in ("budget", "matched_nonbinding"):
        raise ValueError("unknown comparison")
    p = policy_constants()
    if p["schema"] != "sal1-policy-v4":
        raise ValueError("unsupported fixed policy schema")
    if eviction not in p["eviction_arms"]:
        raise ValueError("unknown eviction arm")
    if radius_profile == "validation_selected":
        from experiments.salience_v1.radius_selection import checked_radius
        if selection is None or noise_std is None:
            raise ValueError("selected-radius construction requires a validation selection")
        radius = checked_radius(selection, backend=backend, noise_std=noise_std,
                                comparison=comparison)
    elif radius_profile in ("fixed_development", "fixed_stress"):
        if selection is not None:
            raise ValueError("fixed-radius profiles cannot consume a tuned selection")
        if radius_profile == "fixed_stress" and noise_std != p["noise_designations"]["declared_stress"]["sigma"]:
            raise ValueError("fixed-radius stress is explicitly sigma=0.05")
        radius = p["recall_and_revision_radius"]
    else:
        raise ValueError("unknown radius profile")
    capacity = (p["capacities"][backend] if comparison == "budget"
                else p["nonbinding_matched_capacity"])
    settings = (selection["base_precheck"]["configuration"]
                if radius_profile == "validation_selected" else p["development_backend_settings"])
    base = factories[backend](p["cue_dimension"], p["outcome_dimension"],
                              decay=settings["decay"], ridge=settings["ridge"])
    return SurpriseMemory(base, capacity=capacity, threshold=p["threshold_nmse"],
                          radius=radius, refresh_on_confirmation=(eviction == "confirmation_refresh"),
                          byte_budget=p["instance_owned_byte_cap"])
