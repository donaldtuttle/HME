"""SAL-1 development prototype. No registered performance outcomes.

Real cue/outcome vectors only. Surprise is measured against caller-supplied
feedback, not inferred truth. All baselines receive the same observations.
"""
from __future__ import annotations

import math
from typing import Callable

import numpy as np
from numpy.typing import ArrayLike

from hme_consolidation import ConsolidatingMemory, _owned_bytes

_MAX_CLOCK = np.iinfo(np.uint64).max
_POLICY = np.dtype([("threshold", "<f8"), ("radius", "<f8"),
                    ("clock", "<u8"), ("admissions", "<u8"),
                    ("flags", "u1")])
_ALWAYS_ADMIT = 1
_REFRESH_ON_CONFIRMATION = 2


def _config(cue_dim: int, outcome_dim: int, decay: float, ridge: float) -> np.ndarray:
    for value in (cue_dim, outcome_dim):
        if isinstance(value, (bool, np.bool_)) or not isinstance(value, (int, np.integer)):
            raise TypeError("dimensions must be integers")
        if value < 1:
            raise ValueError("dimensions must be positive")
    if not math.isfinite(decay) or not 0 <= decay < 1:
        raise ValueError("decay must be finite and in [0, 1)")
    if not math.isfinite(ridge) or ridge <= 0:
        raise ValueError("ridge must be finite and positive")
    return np.array([cue_dim, outcome_dim, decay, ridge, 0.0], dtype=np.float64)


def _vector(value: ArrayLike, size: int) -> np.ndarray:
    raw = np.asarray(value)
    if np.iscomplexobj(raw):
        raise TypeError("this prototype supports real vectors only")
    out = np.asarray(raw, dtype=np.float64)
    if out.shape != (size,) or not np.isfinite(out).all():
        raise ValueError("expected a finite, dimension-matched vector")
    if not np.isfinite(np.linalg.norm(out)):
        raise ValueError("vector norm must be finite")
    return out


def _sample(base, cue: ArrayLike, outcome: ArrayLike, gain: float):
    """Gain weights a unit joint row, not the unnormalized observation.

    For raw z=[cue,outcome], the second-moment contribution is
    (gain / ||z||^2) zz^T. Larger targets change that effective raw-space weight.
    The observed outcome is used at learning time only, never to normalize a query.
    """
    cue = _vector(cue, base.cue_dim)
    outcome = _vector(outcome, base.outcome_dim)
    if np.linalg.norm(cue) <= 0:
        raise ValueError("cue must be nonzero")
    gain = float(gain)
    if not math.isfinite(gain) or gain < 0 or not math.isfinite(gain * gain):
        raise ValueError("gain and its square must be finite and nonnegative")
    z = np.concatenate((cue, outcome))
    norm = float(np.linalg.norm(z))
    if not math.isfinite(norm) or norm <= 0:
        raise ValueError("joint observation must have a finite nonzero norm")
    return cue, outcome, gain, z / norm


class _Dimensions:
    __slots__ = ()

    @property
    def cue_dim(self) -> int:
        return int(self._cfg[0])

    @property
    def outcome_dim(self) -> int:
        return int(self._cfg[1])


class FieldPredictor(_Dimensions):
    """The existing consolidated FFT patch; no episodic records retained."""
    __slots__ = ("_cfg", "state")

    def __init__(self, cue_dim=8, outcome_dim=8, *, decay=0.0, ridge=0.01):
        self._cfg = _config(cue_dim, outcome_dim, decay, ridge)
        d = cue_dim + outcome_dim
        self.state = ConsolidatingMemory(dimension=d, memory_size=max(4, d),
                                         use_hann_window=False, decay=decay)
        self.state.consolidate()

    def predict(self, cue: ArrayLike) -> np.ndarray:
        x = _vector(cue, self.cue_dim)
        if self.state.weight_mass <= 0:
            return np.zeros(self.outcome_dim)
        observed = np.concatenate((x, np.full(self.outcome_dim, np.nan)))
        mask = np.arange(observed.size) < self.cue_dim
        return self.state.reconstruct(observed, mask, ridge=float(self._cfg[3]))[~mask].real

    def update(self, cue, outcome, *, gain=1.0) -> None:
        x, y, g, _ = _sample(self, cue, outcome, gain)
        self.state.write(np.concatenate((x, y)), gain=g)

    def retained_arrays(self):
        return (self._cfg, self.state._field, self.state._control)


class DirectMoment(_Dimensions):
    """Matched weighted/decayed direct statistic and identical ridge rule."""
    __slots__ = ("_cfg", "_sum")

    def __init__(self, cue_dim=8, outcome_dim=8, *, decay=0.0, ridge=0.01):
        self._cfg = _config(cue_dim, outcome_dim, decay, ridge)
        self._sum = np.zeros((cue_dim + outcome_dim,) * 2)

    def update(self, cue, outcome, *, gain=1.0) -> None:
        _, _, g, z = _sample(self, cue, outcome, gain)
        keep = 1.0 - self._cfg[2]
        with np.errstate(over="raise", invalid="raise"):
            total = keep * self._sum + g * np.outer(z, z)
            mass = keep * self._cfg[4] + g
        if not np.isfinite(total).all() or not math.isfinite(mass):
            raise OverflowError("moment update overflow")
        self._sum[:] = total
        self._cfg[4] = mass

    def predict(self, cue: ArrayLike) -> np.ndarray:
        x = _vector(cue, self.cue_dim)
        if self._cfg[4] <= 0:
            return np.zeros(self.outcome_dim)
        p = self.cue_dim
        c = self._sum / self._cfg[4]
        reg = self._cfg[3] * np.trace(c) / c.shape[0]
        return c[p:, :p] @ np.linalg.solve(c[:p, :p] + reg * np.eye(p), x)

    def retained_arrays(self):
        return (self._cfg, self._sum)


class ForgettingRLS(_Dimensions):
    """Multioutput RLS with exponential forgetting and a decaying ridge prior.

    Uses the same normalized joint training rows as FieldPredictor. Its initial
    prior is ridge*I; unlike the field's mass-scaled ridge, that prior decays.
    No claim that these two different regularizers yield identical predictors.
    """
    __slots__ = ("_cfg", "_inverse", "_coef")

    def __init__(self, cue_dim=8, outcome_dim=8, *, decay=0.0, ridge=0.01):
        self._cfg = _config(cue_dim, outcome_dim, decay, ridge)
        self._inverse = np.eye(cue_dim) / ridge
        self._coef = np.zeros((outcome_dim, cue_dim))

    def update(self, cue, outcome, *, gain=1.0) -> None:
        _, _, g, z = _sample(self, cue, outcome, gain)
        x, y = z[:self.cue_dim], z[self.cue_dim:]
        with np.errstate(over="raise", invalid="raise", divide="raise"):
            prior = self._inverse / (1.0 - self._cfg[2])
            v = prior @ x
            denom = 1.0 + g * float(x @ v)
            if denom <= 0 or not math.isfinite(denom):
                raise FloatingPointError("RLS precision update is not positive")
            k = g * v / denom
            coeff = self._coef + np.outer(y - self._coef @ x, k)
            precision_inverse = prior - np.outer(k, x @ prior)
            precision_inverse = (precision_inverse + precision_inverse.T) / 2.0
        if not np.isfinite(coeff).all() or not np.isfinite(precision_inverse).all():
            raise FloatingPointError("nonfinite RLS state")
        self._coef[:] = coeff
        self._inverse[:] = precision_inverse

    def predict(self, cue: ArrayLike) -> np.ndarray:
        return self._coef @ _vector(cue, self.cue_dim)

    def retained_arrays(self):
        return (self._cfg, self._inverse, self._coef)


class SurpriseMemory:
    """Bounded numeric exception store, shared unchanged by all three bases.

    Admission uses the pre-update HYBRID prediction, including any routed
    exception. Revision/removal uses the same nearest-within-radius match as
    recall, with newest-entry ties. An existing anchor stays fixed on revision
    to avoid chains of small cue changes walking it into a different region.

    If the base already predicts eligible feedback adequately, remove the matched
    exception. If the hybrid is adequate but the base is not, KEEP the exception
    without a new admission. FIFO does not refresh its age; the confirmation
    ablation refreshes eviction age on eligible trusted feedback. Otherwise revise or
    admit a new entry, evicting the oldest accepted entry when full. Admit-all is
    an explicit ablation using the same matching and anchor rules. Nearby distinct
    scopes can still collide: this is not semantic scope inference or a truth test.

    Slots are compacted in acceptance order, independently of eviction timestamps.
    This preserves newest-accepted recall ties when confirmation updates an age.
    The mode bit shares the existing policy byte; neither arm adds retained arrays.
    predict() never refreshes: an unlabelled recall cannot establish correctness.
    """
    __slots__ = ("base", "_cues", "_targets", "_ages", "_valid", "_policy")

    def __init__(self, base, *, capacity=4, threshold=0.1, radius=0.1,
                 always_admit=False, byte_budget=None, refresh_on_confirmation=False):
        if isinstance(capacity, (bool, np.bool_)) or not isinstance(capacity, (int, np.integer)):
            raise TypeError("capacity must be an integer")
        if capacity < 0:
            raise ValueError("capacity cannot be negative")
        if not math.isfinite(threshold) or threshold < 0:
            raise ValueError("threshold must be finite and nonnegative")
        if not math.isfinite(radius) or radius < 0 or not math.isfinite(radius * radius):
            raise ValueError("radius and its square must be finite and nonnegative")
        if not isinstance(always_admit, (bool, np.bool_)):
            raise TypeError("always_admit must be boolean")
        if not isinstance(refresh_on_confirmation, (bool, np.bool_)):
            raise TypeError("refresh_on_confirmation must be boolean")
        self.base = base
        self._cues = np.zeros((capacity, base.cue_dim))
        self._targets = np.zeros((capacity, base.outcome_dim))
        self._ages = np.zeros(capacity, dtype=np.uint64)
        self._valid = np.zeros(capacity, dtype=np.bool_)
        self._policy = np.zeros(1, dtype=_POLICY)
        flags = int(always_admit) * _ALWAYS_ADMIT | int(refresh_on_confirmation) * _REFRESH_ON_CONFIRMATION
        self._policy[0] = (threshold, radius, 0, 0, flags)
        if byte_budget is not None:
            if isinstance(byte_budget, bool) or not isinstance(byte_budget, (int, np.integer)):
                raise TypeError("byte_budget must be an integer")
            if self.storage_report()["instance_owned_bytes"] > byte_budget:
                raise ValueError("model and buffer exceed the instance-owned byte budget")

    def _match(self, cue: np.ndarray):
        candidates = np.flatnonzero(self._valid)
        if not candidates.size:
            return None
        with np.errstate(over="ignore"):
            dist = np.sum((self._cues[candidates] - cue) ** 2, axis=1)
        nearest = float(dist.min())
        if nearest > float(self._policy["radius"][0]) ** 2:
            return None
        ties = candidates[dist == nearest]
        # Valid slots are ordered oldest to newest acceptance, not confirmation.
        return int(ties[-1])

    def _discard_entry(self, index: int) -> None:
        """Remove a logical entry, preserving acceptance order without extra state."""
        size = int(self._valid.sum())
        for array in (self._cues, self._targets, self._ages, self._valid):
            array[index:size-1] = array[index+1:size].copy()
            array[size-1] = 0

    def predict(self, cue: ArrayLike) -> np.ndarray:
        x = _vector(cue, self.base.cue_dim)
        i = self._match(x)
        return self._targets[i].copy() if i is not None else self.base.predict(x)

    def observe(self, cue, outcome, *, gain=1.0, trusted=True, eligible=True) -> dict:
        """Update with feedback; flags are external, identically available to arms.

        trusted=False ignores feedback entirely. eligible=False still updates
        the base, but does not create or revise exception entries (e.g. warm-up).
        Eligibility must be scheduled independently of hidden evaluation labels.
        Invalid inputs and clock exhaustion are rejected before either update.
        """
        if not isinstance(trusted, (bool, np.bool_)) or not isinstance(eligible, (bool, np.bool_)):
            raise TypeError("trusted and eligible must be boolean")
        x, y, g, _ = _sample(self.base, cue, outcome, gain)
        if not trusted:
            return {"ignored": True, "admitted": False}
        clock = int(self._policy["clock"][0])
        if clock == _MAX_CLOCK:
            raise OverflowError("fixed-width event clock exhausted")
        match = self._match(x)
        base_prediction = self.base.predict(x)
        hybrid_prediction = self._targets[match] if match is not None else base_prediction
        with np.errstate(over="raise", invalid="raise"):
            denominator = max(float(y @ y), 1e-12)
            base_loss = float(np.sum((base_prediction - y) ** 2) / denominator)
            hybrid_loss = float(np.sum((hybrid_prediction - y) ** 2) / denominator)
        if not math.isfinite(base_loss) or not math.isfinite(hybrid_loss):
            raise FloatingPointError("nonfinite surprise score")
        threshold = float(self._policy["threshold"][0])
        flags = int(self._policy["flags"][0])
        always = bool(flags & _ALWAYS_ADMIT)
        enabled = bool(eligible and self._valid.size)
        # The base check is for safe retirement, NOT admission surprise.
        remove = enabled and match is not None and not always and base_loss <= threshold
        admit = enabled and not remove and (always or hybrid_loss > threshold)
        if admit and int(self._policy["admissions"][0]) == _MAX_CLOCK:
            raise OverflowError("fixed-width admission counter exhausted")
        # No buffer mutation if the base rejects its numerical update.
        self.base.update(x, y, gain=g)
        self._policy["clock"][0] = clock + 1
        admitted = removed = revised = refreshed = False
        if remove:
            self._discard_entry(match)
            removed = True
        elif admit:
            # Preserve the first cue anchor while moving a revision to newest
            # acceptance order. Confirmation alone never reorders these slots.
            anchor = self._cues[match].copy() if match is not None else x
            if match is not None:
                self._discard_entry(match)
            elif self._valid.all():
                self._discard_entry(int(np.argmin(self._ages)))
            i = int(self._valid.sum())
            self._cues[i], self._targets[i] = anchor, y
            self._ages[i], self._valid[i] = clock + 1, True
            self._policy["admissions"][0] += 1
            admitted, revised = True, match is not None
        elif (enabled and match is not None and
              flags & _REFRESH_ON_CONFIRMATION and hybrid_loss <= threshold):
            # Reached only when retirement and admission are both unnecessary.
            # Supplied trusted eligible feedback confirms a still-needed entry.
            self._ages[match] = clock + 1
            refreshed = True
        return {"ignored": False, "admitted": admitted, "removed": removed,
                "revised": revised, "refreshed": refreshed, "pre_update_base_nmse": base_loss,
                "pre_update_hybrid_nmse": hybrid_loss}

    def storage_report(self) -> dict:
        arrays = (*self.base.retained_arrays(), self._cues, self._targets,
                  self._ages, self._valid, self._policy)
        return {"capacity": len(self._valid), "occupied": int(self._valid.sum()),
                "retained_array_bytes": sum(a.nbytes for a in arrays),
                "instance_owned_bytes": _owned_bytes(self),
                "admissions": int(self._policy["admissions"][0])}


def fit_budget(factory: Callable, byte_budget: int, **policy) -> SurpriseMemory:
    """Development sizing helper only; never choose capacity during evaluation.

    Use the largest whole buffer capacity under the same owned-byte ceiling.

    Measured bytes depend on runtime. This is not exact equal consumption: unused
    remainders are reported, not padded. Code, temporary workspace and RSS are
    excluded; every instance-reachable object is included by the shared counter.
    """
    if "capacity" in policy or "byte_budget" in policy:
        raise ValueError("capacity and budget are selected by fit_budget")
    base = factory()
    empty = SurpriseMemory(base, capacity=0, byte_budget=byte_budget, **policy)
    available = byte_budget - empty.storage_report()["instance_owned_bytes"]
    per_entry = 8 * (base.cue_dim + base.outcome_dim) + 8 + 1
    capacity = max(0, available // per_entry)
    return SurpriseMemory(base, capacity=capacity, byte_budget=byte_budget, **policy)
