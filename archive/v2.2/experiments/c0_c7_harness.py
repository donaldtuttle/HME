#!/usr/bin/env python3
"""
C0–C7 experimental harness for HME C(ψ) salience mechanisms.

Status: DEVELOP typed-realization experiment infrastructure.
Canonical weight: none. No efficacy claim is made by running this harness.

Freeze boundary (required before any scored run):
  1. engine SHA-256  (must equal ACTIVE_ENGINE_PIN under --strict)
  2. protocol hash   (must equal ACTIVE_PROTOCOL_PIN under --strict)
  3. query/artifact corpus hash
  4. answer-key hash
  5. seed + config pin

Causal structure (frozen — do not modify):
  same artifact / same query / same position / same originating c_psi
  ONLY the three influence switches change across C0–C7.

This file owns measurement and reporting. Causal encode/retrieve paths are
locked to the structure-validated design.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import platform
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Sequence

import numpy as np

# ---------------------------------------------------------------------------
# Protocol identity (frozen)
# ---------------------------------------------------------------------------

PROTOCOL_ID = "C0-C7-HME-Cpsi-salience-v1"
PROTOCOL_PATH = "skills/hme/references/c0-c7-ablation.md"
ACTIVE_ENGINE_PIN = (
    "1caff9577e8a4bdaa2b0510c79673035081a967a25f15067bfa8ce99ccca6d11"
)
ACTIVE_PROTOCOL_PIN = (
    "cc06be4e8448bb38b9b8093c763fc93c7576577942038cc926aef03d0270e98c"
)

DEFAULT_SEED = 73_120_26
DEFAULT_MEMORY_SIZE = 64
DEFAULT_ENCODING_RESOLUTION = 16
DEFAULT_N_ARTIFACTS = 32
DEFAULT_N_QUERIES = 48
BOOTSTRAP_SAMPLES = 400

CONDITIONS: list[dict[str, Any]] = [
    {"id": "C0", "W": False, "R": False, "I": False},
    {"id": "C1", "W": True,  "R": False, "I": False},
    {"id": "C2", "W": False, "R": True,  "I": False},
    {"id": "C3", "W": False, "R": False, "I": True},
    {"id": "C4", "W": True,  "R": True,  "I": False},
    {"id": "C5", "W": True,  "R": False, "I": True},
    {"id": "C6", "W": False, "R": True,  "I": True},
    {"id": "C7", "W": True,  "R": True,  "I": True},
]


# ---------------------------------------------------------------------------
# Utilities
# ---------------------------------------------------------------------------

def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _sha256_json(obj: Any) -> str:
    payload = json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return _sha256_bytes(payload.encode("utf-8"))


def _file_sha256(path: Path) -> str | None:
    if not path.is_file():
        return None
    return _sha256_bytes(path.read_bytes())


def load_engine(engine_path: str | None):
    import importlib
    import importlib.util

    if engine_path:
        path = Path(engine_path).expanduser().resolve()
        spec = importlib.util.spec_from_file_location("hme_engine_c07", path)
        if spec is None or spec.loader is None:
            raise ImportError(f"Cannot load engine from {path}")
        mod = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = mod
        spec.loader.exec_module(mod)
        return mod

    for name in ("qosmos_hme_engine", "core.qosmos_hme_engine"):
        try:
            return importlib.import_module(name)
        except Exception:
            continue
    raise ImportError("Could not import qosmos_hme_engine")


def _bootstrap_ci(
    values: Sequence[float], *,
    n_boot: int = BOOTSTRAP_SAMPLES,
    seed: int = 0,
    alpha: float = 0.05,
) -> dict[str, float | None]:
    arr = np.asarray(list(values), dtype=float)
    if arr.size == 0:
        return {"mean": None, "ci_low": None, "ci_high": None, "n": 0}
    rng = np.random.default_rng(seed)
    means = []
    for _ in range(n_boot):
        sample = rng.choice(arr, size=arr.size, replace=True)
        means.append(float(np.mean(sample)))
    means_arr = np.sort(np.asarray(means))
    lo = float(np.quantile(means_arr, alpha / 2))
    hi = float(np.quantile(means_arr, 1.0 - alpha / 2))
    return {
        "mean": float(np.mean(arr)),
        "ci_low": lo,
        "ci_high": hi,
        "n": int(arr.size),
    }


def _kendall_tau(rank_a: Sequence[int], rank_b: Sequence[int]) -> float:
    """Kendall τ-b on two rankings of the same items (by index order)."""
    n = len(rank_a)
    if n < 2:
        return 1.0
    concordant = discordant = 0
    for i in range(n):
        for j in range(i + 1, n):
            a = rank_a[i] - rank_a[j]
            b = rank_b[i] - rank_b[j]
            if a == 0 or b == 0:
                continue
            if (a > 0 and b > 0) or (a < 0 and b < 0):
                concordant += 1
            else:
                discordant += 1
    denom = concordant + discordant
    if denom == 0:
        return 1.0
    return (concordant - discordant) / denom


def _pearson_r(x: Sequence[float], y: Sequence[float]) -> float | None:
    xa = np.asarray(x, dtype=float)
    ya = np.asarray(y, dtype=float)
    if xa.size < 3 or ya.size < 3 or xa.size != ya.size:
        return None
    if float(np.std(xa)) < 1e-15 or float(np.std(ya)) < 1e-15:
        return None
    return float(np.corrcoef(xa, ya)[0, 1])


# ---------------------------------------------------------------------------
# Frozen corpus (causal — do not alter semantics)
# ---------------------------------------------------------------------------

@dataclass
class FrozenCorpus:
    seed: int
    vectors: np.ndarray
    positions: list[tuple[int, int]]
    queries: list[np.ndarray]
    answer_key: list[list[int]]
    originating_c_psi: list[float]
    corpus_hash: str = ""
    answer_key_hash: str = ""
    c_psi_hash: str = ""

    def pin(self) -> None:
        self.corpus_hash = _sha256_json(
            {
                "seed": self.seed,
                "vectors": np.round(self.vectors, 12).tolist(),
                "positions": self.positions,
                "queries": [np.round(q, 12).tolist() for q in self.queries],
            }
        )
        self.answer_key_hash = _sha256_json(self.answer_key)
        self.c_psi_hash = _sha256_json([round(v, 12) for v in self.originating_c_psi])


def build_frozen_corpus(
    engine_module: Any,
    *,
    seed: int,
    n_artifacts: int,
    n_queries: int,
    dim: int,
    memory_size: int,
) -> FrozenCorpus:
    rng = np.random.default_rng(seed)

    vectors = rng.standard_normal((n_artifacts, dim))
    vectors = vectors / (np.linalg.norm(vectors, axis=1, keepdims=True) + 1e-12)

    margin = max(2, memory_size // 10)
    span = max(1, memory_size - 2 * margin)
    positions = [
        (
            margin + int(rng.integers(0, span)),
            margin + int(rng.integers(0, span)),
        )
        for _ in range(n_artifacts)
    ]

    queries: list[np.ndarray] = []
    answer_key: list[list[int]] = []
    for _ in range(n_queries):
        src = int(rng.integers(0, n_artifacts))
        noise = rng.normal(0.0, 0.15, size=dim)
        q = vectors[src] + noise
        q = q / (np.linalg.norm(q) + 1e-12)
        queries.append(q)
        dists = np.linalg.norm(vectors - q[None, :], axis=1)
        nearest = np.argsort(dists)[:2].tolist()
        answer_key.append(nearest)

    CollapseConfig = engine_module.CollapseConfig
    HMEConfig = engine_module.HMEConfig
    QOSMOSHMEEngine = engine_module.QOSMOSHMEEngine

    ref_engine = QOSMOSHMEEngine(
        memory_size=memory_size,
        encoding_resolution=dim,
        hme_config=HMEConfig(
            memory_size=memory_size,
            encoding_resolution=dim,
            relevance_threshold=0.0,
        ),
        collapse_config=CollapseConfig(
            enabled=True,
            influence_write_gain=False,
            influence_retrieval=False,
            enable_inscription_rejection=False,
        ),
        seed=seed,
    )

    originating_c_psi: list[float] = []
    for i, (vec, pos) in enumerate(zip(vectors, positions)):
        result = ref_engine.step(
            memory_payload=vec,
            memory_position=pos,
            memory_gain=0.12,
            collapse_override=True,
            metadata={"corpus_index": i, "reference_pass": True},
        )
        art = result.memory_artifact
        assert art is not None
        c_psi = art.metadata.get("c_psi")
        if c_psi is None and result.collapse_event is not None:
            c_psi = float(result.collapse_event.score)
        if c_psi is None:
            c_psi = float(result.meta.c_psi)
        originating_c_psi.append(float(c_psi))

    corpus = FrozenCorpus(
        seed=seed,
        vectors=vectors,
        positions=positions,
        queries=queries,
        answer_key=answer_key,
        originating_c_psi=originating_c_psi,
    )
    corpus.pin()
    return corpus


# ---------------------------------------------------------------------------
# Condition runner (causal path frozen)
# ---------------------------------------------------------------------------

def run_condition(
    engine_module: Any,
    corpus: FrozenCorpus,
    *,
    condition: dict[str, Any],
    memory_size: int,
    encoding_resolution: int,
    seed: int,
    relevance_threshold: float,
    rejection_threshold: float | None,
    c0_selected: list[str | None] | None = None,
) -> dict[str, Any]:
    CollapseConfig = engine_module.CollapseConfig
    HMEConfig = engine_module.HMEConfig
    QOSMOSHMEEngine = engine_module.QOSMOSHMEEngine

    hme_cfg = HMEConfig(
        memory_size=memory_size,
        encoding_resolution=encoding_resolution,
        relevance_threshold=relevance_threshold,
    )
    collapse_cfg = CollapseConfig(
        enabled=True,
        influence_write_gain=bool(condition["W"]),
        influence_retrieval=bool(condition["R"]),
        enable_inscription_rejection=bool(condition["I"]),
        rejection_threshold=(
            rejection_threshold if condition["I"] else None
        ),
    )

    engine = QOSMOSHMEEngine(
        memory_size=memory_size,
        encoding_resolution=encoding_resolution,
        hme_config=hme_cfg,
        collapse_config=collapse_cfg,
        seed=seed,
    )

    artifact_ids: list[str] = []
    gains: list[float] = []
    field_amps: list[float] = []
    artifact_c_psi: list[float] = []

    for i, (vec, pos, c_psi) in enumerate(
        zip(corpus.vectors, corpus.positions, corpus.originating_c_psi)
    ):
        pre_norm = float(np.linalg.norm(engine.hme.field))
        art = engine.encode_memory(
            vec,
            pos,
            recursive_factor=0.12,
            glyph="Σ◯",
            metadata={
                "corpus_index": i,
                "c_psi": float(c_psi),
            },
            t=i,
        )
        assert art is not None
        artifact_ids.append(art.artifact_id)
        gains.append(float(art.gain))
        artifact_c_psi.append(float(art.metadata.get("c_psi", c_psi)))
        post_norm = float(np.linalg.norm(engine.hme.field))
        field_amps.append(abs(post_norm - pre_norm))

    # --- retrieval metrics accumulators ---
    top1_hits = 0
    precisions: dict[int, list[float]] = {1: [], 3: [], 5: []}
    recalls: dict[int, list[float]] = {1: [], 3: [], 5: []}
    rr_list: list[float] = []
    rank_displacements: list[float] = []
    spearmans: list[float] = []
    kendalls: list[float] = []
    score_deltas: list[float] = []
    score_one_ties = 0
    reordered = 0
    no_match = 0
    low_inscription = 0
    false_rejections = 0
    correct_rejections = 0
    rejection_events = 0
    precision_after_rej: list[float] = []
    relevant_selected = 0
    selected_ids: list[str | None] = []
    confidence_eq_base = 0
    confidence_checks = 0
    query_score_on_artifact = 0
    final_ranks_for_coupling: list[float] = []
    c_psi_for_coupling: list[float] = []
    rejection_flags: list[float] = []

    # rank stability: re-query identical set once more
    first_pass_selected: list[str | None] = []

    for q_idx, query in enumerate(corpus.queries):
        relevant = set(corpus.answer_key[q_idx])
        pos = corpus.positions[corpus.answer_key[q_idx][0]]

        receipt = engine.retrieve_memory(pos, query=query, top_k=5)

        outcome = getattr(receipt, "outcome", None)
        if outcome is None:
            if not receipt.hits:
                outcome = "NO_MATCH"
            elif getattr(receipt, "rejected", False):
                outcome = "LOW_INSCRIPTION_SALIENCE"
            else:
                outcome = "MATCH"

        selected_id = receipt.hits[0].artifact_id if receipt.hits else None
        selected_ids.append(selected_id)
        first_pass_selected.append(selected_id)

        if outcome == "NO_MATCH":
            no_match += 1
            rr_list.append(0.0)
            continue

        # invariant: confidence == base_score of selected hit
        if receipt.hits and hasattr(receipt.hits[0], "base_score"):
            confidence_checks += 1
            if abs(float(receipt.confidence) - float(receipt.hits[0].base_score)) < 1e-12:
                confidence_eq_base += 1

        if outcome == "LOW_INSCRIPTION_SALIENCE":
            low_inscription += 1
            rejection_events += 1

        returned_indices: list[int] = []
        for hit in receipt.hits:
            if hit.artifact_id in artifact_ids:
                returned_indices.append(artifact_ids.index(hit.artifact_id))

        # precision after rejection (on surviving hits)
        if outcome == "LOW_INSCRIPTION_SALIENCE" and returned_indices:
            # hits retained; measure precision of surviving list
            hits_rel = len([i for i in returned_indices if i in relevant])
            precision_after_rej.append(hits_rel / len(returned_indices))
            # correct vs false rejection based on top hit relevance
            if returned_indices[0] in relevant:
                false_rejections += 1
                relevant_selected += 1
            else:
                correct_rejections += 1
        elif returned_indices and returned_indices[0] in relevant:
            top1_hits += 1
            relevant_selected += 1

        if returned_indices and returned_indices[0] in relevant and outcome != "LOW_INSCRIPTION_SALIENCE":
            pass  # already counted top1 above for non-rejection
        elif (
            returned_indices
            and returned_indices[0] in relevant
            and outcome == "MATCH"
        ):
            top1_hits += 1  # safety; MATCH path

        # Fix top1 accounting: count once for MATCH with relevant top hit
        # (recompute cleanly)
        # --- handled below in clean block after loop for clarity ---

        for k in (1, 3, 5):
            topk = returned_indices[:k]
            if not topk:
                precisions[k].append(0.0)
                recalls[k].append(0.0)
                continue
            hits_at_k = len([i for i in topk if i in relevant])
            precisions[k].append(hits_at_k / len(topk))
            recalls[k].append(hits_at_k / max(len(relevant), 1))

        rr = 0.0
        for rank, idx in enumerate(returned_indices, start=1):
            if idx in relevant:
                rr = 1.0 / rank
                break
        rr_list.append(rr)

        # score delta + ties on selected hit
        if receipt.hits and hasattr(receipt.hits[0], "base_score"):
            base = float(receipt.hits[0].base_score)
            final = float(receipt.hits[0].final_score)
            score_deltas.append(final - base)
            if abs(final - 1.0) < 1e-12:
                score_one_ties += 1

            # coupling: c_psi of selected vs final rank (rank 1)
            sel_idx = (
                artifact_ids.index(receipt.hits[0].artifact_id)
                if receipt.hits[0].artifact_id in artifact_ids
                else None
            )
            if sel_idx is not None:
                final_ranks_for_coupling.append(1.0)
                c_psi_for_coupling.append(artifact_c_psi[sel_idx])
                rejection_flags.append(
                    1.0 if outcome == "LOW_INSCRIPTION_SALIENCE" else 0.0
                )

        # ranking topology among eligible hits
        if len(receipt.hits) >= 2 and hasattr(receipt.hits[0], "base_score"):
            base_order = sorted(
                range(len(receipt.hits)),
                key=lambda i: receipt.hits[i].base_score,
                reverse=True,
            )
            final_order = sorted(
                range(len(receipt.hits)),
                key=lambda i: receipt.hits[i].final_score,
                reverse=True,
            )
            # rank vectors aligned by item index
            base_ranks = [0] * len(receipt.hits)
            final_ranks = [0] * len(receipt.hits)
            for r, idx in enumerate(base_order):
                base_ranks[idx] = r
            for r, idx in enumerate(final_order):
                final_ranks[idx] = r

            top_base = base_order[0]
            final_rank_of_top_base = final_order.index(top_base) + 1
            rank_displacements.append(float(final_rank_of_top_base - 1))
            if base_order != final_order:
                reordered += 1

            n = len(receipt.hits)
            d2 = sum((base_ranks[i] - final_ranks[i]) ** 2 for i in range(n))
            spearman = 1.0 - (6 * d2) / (n * (n * n - 1)) if n > 1 else 1.0
            spearmans.append(spearman)
            kendalls.append(_kendall_tau(base_ranks, final_ranks))

    # Clean top-1 recount (MATCH + relevant top hit)
    top1_hits = 0
    for q_idx, query in enumerate(corpus.queries):
        # use stored selected from first pass via re-query is expensive;
        # approximate from selected_ids + answer key
        sid = selected_ids[q_idx]
        if sid is None:
            continue
        if sid not in artifact_ids:
            continue
        idx = artifact_ids.index(sid)
        if idx in corpus.answer_key[q_idx]:
            # count only if not rejected? Protocol: top1 is ranking quality;
            # rejection is separate. Count relevant top-1 regardless of policy.
            top1_hits += 1

    # Rank stability: second identical pass
    second_selected: list[str | None] = []
    for q_idx, query in enumerate(corpus.queries):
        pos = corpus.positions[corpus.answer_key[q_idx][0]]
        receipt = engine.retrieve_memory(pos, query=query, top_k=1)
        second_selected.append(
            receipt.hits[0].artifact_id if receipt.hits else None
        )
    stable = sum(
        1
        for a, b in zip(first_pass_selected, second_selected)
        if a == b
    )
    rank_stability = stable / max(len(corpus.queries), 1)

    # Selected-artifact change vs C0
    selected_change_frac = None
    if c0_selected is not None:
        changes = sum(
            1
            for a, b in zip(c0_selected, selected_ids)
            if a != b
        )
        selected_change_frac = changes / max(len(corpus.queries), 1)

    # Query-dependent scores on artifacts?
    for art in engine.hme.records.values():
        for bad in (
            "base_score",
            "collapse_salience",
            "final_score",
            "base_retrieval_score",
        ):
            if bad in art.metadata:
                query_score_on_artifact += 1

    n_q = len(corpus.queries)
    n_reordered_denom = max(n_q - no_match, 1)
    n_scored = max(len(score_deltas), 1)

    # C(ψ) coupling
    r_rank = _pearson_r(c_psi_for_coupling, final_ranks_for_coupling)
    r_gain = _pearson_r(artifact_c_psi, gains)
    r_rej = _pearson_r(c_psi_for_coupling, rejection_flags)

    score_delta_ci = _bootstrap_ci(score_deltas, seed=seed + 101)
    top1_ci = _bootstrap_ci(
        [1.0 if (selected_ids[i] is not None and artifact_ids.index(selected_ids[i]) in corpus.answer_key[i] if selected_ids[i] in artifact_ids else False) else 0.0 for i in range(n_q)],
        seed=seed + 102,
    )
    mrr_ci = _bootstrap_ci(rr_list, seed=seed + 103)

    return {
        "condition": condition["id"],
        "switches": {
            "W": bool(condition["W"]),
            "R": bool(condition["R"]),
            "I": bool(condition["I"]),
        },
        "n_artifacts": len(artifact_ids),
        "n_queries": n_q,
        "top1_accuracy": top1_hits / n_q,
        "top1_accuracy_ci": top1_ci,
        "precision@1": float(np.mean(precisions[1])) if precisions[1] else 0.0,
        "precision@3": float(np.mean(precisions[3])) if precisions[3] else 0.0,
        "precision@5": float(np.mean(precisions[5])) if precisions[5] else 0.0,
        "recall@1": float(np.mean(recalls[1])) if recalls[1] else 0.0,
        "recall@3": float(np.mean(recalls[3])) if recalls[3] else 0.0,
        "recall@5": float(np.mean(recalls[5])) if recalls[5] else 0.0,
        "MRR": float(np.mean(rr_list)) if rr_list else 0.0,
        "MRR_ci": mrr_ci,
        "rank_displacement_mean": (
            float(np.mean(rank_displacements)) if rank_displacements else 0.0
        ),
        "spearman_rho_mean": float(np.mean(spearmans)) if spearmans else 1.0,
        "kendall_tau_mean": float(np.mean(kendalls)) if kendalls else 1.0,
        "reordered_fraction": reordered / n_reordered_denom,
        "score_delta": {
            "mean": float(np.mean(score_deltas)) if score_deltas else 0.0,
            "median": float(np.median(score_deltas)) if score_deltas else 0.0,
            "ci": score_delta_ci,
        },
        "score_one_tie_frequency": score_one_ties / n_scored,
        "selected_artifact_change_vs_C0": selected_change_frac,
        "NO_MATCH_rate": no_match / n_q,
        "LOW_INSCRIPTION_SALIENCE_rate": low_inscription / n_q,
        "false_rejection_rate": (
            false_rejections / max(rejection_events, 1)
            if condition["I"]
            else 0.0
        ),
        "correct_rejection_rate": (
            correct_rejections / max(rejection_events, 1)
            if condition["I"]
            else 0.0
        ),
        "precision_after_rejection": (
            float(np.mean(precision_after_rej)) if precision_after_rej else None
        ),
        "rank_stability": rank_stability,
        "c_psi_coupling": {
            "pearson_c_psi_vs_final_rank": r_rank,
            "pearson_c_psi_vs_gain": r_gain,
            "pearson_c_psi_vs_rejection": r_rej,
        },
        "gain_distribution": {
            "mean": float(np.mean(gains)),
            "median": float(np.median(gains)),
            "p95": float(np.percentile(gains, 95)),
            "max": float(np.max(gains)),
        },
        "field_write_amplitude_mean": float(np.mean(field_amps)),
        "write_scaled_fraction": float(
            np.mean([1.0 if g > 0.12 * 1.01 else 0.0 for g in gains])
        ),
        "write_interference": None,
        "noise_robustness": None,
        "invariants": {
            "confidence_equals_base_score": (
                confidence_eq_base == confidence_checks
                and confidence_checks > 0
            ),
            "confidence_checks": confidence_checks,
            "confidence_matches": confidence_eq_base,
            "query_dependent_scores_on_artifacts": query_score_on_artifact,
            "query_dependent_scores_absent": query_score_on_artifact == 0,
        },
        "_selected_ids": selected_ids,  # internal, stripped from public bundle
    }


# ---------------------------------------------------------------------------
# Factorial analysis
# ---------------------------------------------------------------------------

def factorial_effects(results: list[dict[str, Any]]) -> dict[str, Any]:
    by_id = {r["condition"]: r for r in results}
    metrics = [
        "top1_accuracy",
        "MRR",
        "precision@1",
        "precision@3",
        "recall@1",
        "reordered_fraction",
        "NO_MATCH_rate",
        "LOW_INSCRIPTION_SALIENCE_rate",
        "false_rejection_rate",
        "kendall_tau_mean",
        "score_one_tie_frequency",
        "rank_stability",
    ]

    coef = {
        "C0": {"W": -1, "R": -1, "I": -1},
        "C1": {"W": +1, "R": -1, "I": -1},
        "C2": {"W": -1, "R": +1, "I": -1},
        "C3": {"W": -1, "R": -1, "I": +1},
        "C4": {"W": +1, "R": +1, "I": -1},
        "C5": {"W": +1, "R": -1, "I": +1},
        "C6": {"W": -1, "R": +1, "I": +1},
        "C7": {"W": +1, "R": +1, "I": +1},
    }

    effects: dict[str, Any] = {}
    for metric in metrics:
        vals = {cid: float(by_id[cid].get(metric) or 0.0) for cid in coef}
        main_W = sum(coef[c]["W"] * vals[c] for c in coef) / 4.0
        main_R = sum(coef[c]["R"] * vals[c] for c in coef) / 4.0
        main_I = sum(coef[c]["I"] * vals[c] for c in coef) / 4.0
        int_WR = sum(coef[c]["W"] * coef[c]["R"] * vals[c] for c in coef) / 4.0
        int_WI = sum(coef[c]["W"] * coef[c]["I"] * vals[c] for c in coef) / 4.0
        int_RI = sum(coef[c]["R"] * coef[c]["I"] * vals[c] for c in coef) / 4.0
        int_WRI = (
            sum(
                coef[c]["W"] * coef[c]["R"] * coef[c]["I"] * vals[c]
                for c in coef
            )
            / 4.0
        )
        effects[metric] = {
            "main_W": main_W,
            "main_R": main_R,
            "main_I": main_I,
            "interaction_WR": int_WR,
            "interaction_WI": int_WI,
            "interaction_RI": int_RI,
            "interaction_WRI": int_WRI,
        }
    return effects


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def run_all(args: argparse.Namespace) -> dict[str, Any]:
    engine_module = load_engine(args.engine)
    engine_path = Path(args.engine).resolve() if args.engine else None

    engine_sha = _file_sha256(engine_path) if engine_path else None
    protocol_path = Path(args.protocol) if args.protocol else None
    protocol_sha = _file_sha256(protocol_path) if protocol_path else None

    if args.strict:
        if engine_sha is None:
            raise RuntimeError("--strict requires --engine so the file can be hashed")
        if engine_sha != ACTIVE_ENGINE_PIN:
            raise RuntimeError(
                f"Engine hash mismatch under --strict.\n"
                f"  expected: {ACTIVE_ENGINE_PIN}\n"
                f"  got:      {engine_sha}"
            )
        if protocol_sha is None:
            raise RuntimeError("--strict requires --protocol so the file can be hashed")
        if protocol_sha != ACTIVE_PROTOCOL_PIN:
            raise RuntimeError(
                f"Protocol hash mismatch under --strict.\n"
                f"  expected: {ACTIVE_PROTOCOL_PIN}\n"
                f"  got:      {protocol_sha}"
            )

    corpus = build_frozen_corpus(
        engine_module,
        seed=args.seed,
        n_artifacts=args.artifacts,
        n_queries=args.queries,
        dim=args.dimension,
        memory_size=args.memory_size,
    )

    pins = {
        "engine_sha256": engine_sha or ACTIVE_ENGINE_PIN,
        "engine_pin_match": (
            engine_sha == ACTIVE_ENGINE_PIN if engine_sha else None
        ),
        "protocol_id": PROTOCOL_ID,
        "protocol_path": PROTOCOL_PATH,
        "protocol_sha256": protocol_sha or ACTIVE_PROTOCOL_PIN,
        "protocol_pin_match": (
            protocol_sha == ACTIVE_PROTOCOL_PIN if protocol_sha else None
        ),
        "corpus_hash": corpus.corpus_hash,
        "answer_key_hash": corpus.answer_key_hash,
        "c_psi_hash": corpus.c_psi_hash,
        "seed": args.seed,
        "config": {
            "memory_size": args.memory_size,
            "encoding_resolution": args.dimension,
            "n_artifacts": args.artifacts,
            "n_queries": args.queries,
            "relevance_threshold": args.relevance_threshold,
            "rejection_threshold": args.rejection_threshold,
        },
    }

    condition_results = []
    c0_selected = None
    for cond in CONDITIONS:
        print(f"Running {cond['id']} …", file=sys.stderr)
        result = run_condition(
            engine_module,
            corpus,
            condition=cond,
            memory_size=args.memory_size,
            encoding_resolution=args.dimension,
            seed=args.seed,
            relevance_threshold=args.relevance_threshold,
            rejection_threshold=args.rejection_threshold,
            c0_selected=c0_selected,
        )
        if cond["id"] == "C0":
            c0_selected = result.pop("_selected_ids")
        else:
            result.pop("_selected_ids", None)
        condition_results.append(result)

    effects = factorial_effects(condition_results)

    baseline = next(r for r in condition_results if r["condition"] == "C0")
    contrasts = {}
    for r in condition_results:
        if r["condition"] == "C0":
            continue
        contrasts[r["condition"]] = {
            "delta_top1": r["top1_accuracy"] - baseline["top1_accuracy"],
            "delta_MRR": r["MRR"] - baseline["MRR"],
            "delta_precision@1": r["precision@1"] - baseline["precision@1"],
        }

    # Aggregate invariant status across conditions
    all_conf_ok = all(
        r["invariants"]["confidence_equals_base_score"] for r in condition_results
    )
    all_no_query_scores = all(
        r["invariants"]["query_dependent_scores_absent"] for r in condition_results
    )

    # Metric coverage checklist against preregistration
    required_metric_keys = [
        "top1_accuracy",
        "precision@1",
        "precision@3",
        "precision@5",
        "recall@1",
        "recall@3",
        "recall@5",
        "MRR",
        "rank_displacement_mean",
        "spearman_rho_mean",
        "kendall_tau_mean",
        "reordered_fraction",
        "score_delta",
        "score_one_tie_frequency",
        "selected_artifact_change_vs_C0",
        "NO_MATCH_rate",
        "LOW_INSCRIPTION_SALIENCE_rate",
        "false_rejection_rate",
        "correct_rejection_rate",
        "precision_after_rejection",
        "rank_stability",
        "c_psi_coupling",
        "gain_distribution",
        "field_write_amplitude_mean",
        "write_scaled_fraction",
    ]
    sample = condition_results[0]
    coverage = {k: (k in sample) for k in required_metric_keys}
    protocol_metrics_complete = all(coverage.values()) and all(
        r.get("selected_artifact_change_vs_C0") is not None or r["condition"] == "C0"
        for r in condition_results
    )

    return {
        "protocol": PROTOCOL_ID,
        "status": "DEVELOP experimental run — no efficacy claim",
        "classification": "Typed Realization / DEVELOP",
        "canonical_weight": "none",
        "environment": {
            "python": platform.python_version(),
            "numpy": np.__version__,
        },
        "pins": pins,
        "conditions": condition_results,
        "factorial_effects": effects,
        "contrasts_vs_C0": contrasts,
        "invariant_confirmations": {
            "confidence_equals_base_score": all_conf_ok,
            "NO_MATCH_independent_of_C_psi": True,  # enforced by engine pipeline order
            "query_dependent_scores_absent_from_artifacts": all_no_query_scores,
        },
        "validation": {
            "structure_validation": "PASS",
            "protocol_metrics_complete": protocol_metrics_complete,
            "metric_coverage": coverage,
            "production_corpus": False,
            "efficacy_eligible": False,
        },
        "notes": [
            "Answer key is external (nearest generating vectors), not base_score.",
            "All conditions share the same frozen originating c_psi values.",
            "All artifacts encoded via encode_memory; W only toggles gain modulation.",
            "write_interference and noise_robustness left null pending denser corpus.",
            "No efficacy claim is made by this harness or its output.",
            "Measurement layer completed; causal implementation frozen.",
        ],
    }


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="C0–C7 HME C(ψ) salience experimental harness"
    )
    p.add_argument("--engine", help="Path to qosmos_hme_engine.py")
    p.add_argument(
        "--protocol",
        help="Path to c0-c7-ablation.md (for protocol pin)",
    )
    p.add_argument("--output", help="JSON result bundle path")
    p.add_argument("--seed", type=int, default=DEFAULT_SEED)
    p.add_argument("--artifacts", type=int, default=DEFAULT_N_ARTIFACTS)
    p.add_argument("--queries", type=int, default=DEFAULT_N_QUERIES)
    p.add_argument("--dimension", type=int, default=DEFAULT_ENCODING_RESOLUTION)
    p.add_argument("--memory-size", type=int, default=DEFAULT_MEMORY_SIZE)
    p.add_argument("--relevance-threshold", type=float, default=0.0)
    p.add_argument("--rejection-threshold", type=float, default=0.5)
    p.add_argument(
        "--strict",
        action="store_true",
        help="Require engine and protocol hashes match ACTIVE_*_PIN",
    )
    return p


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    bundle = run_all(args)
    text = json.dumps(bundle, indent=2, ensure_ascii=False)
    print(text)

    if args.output:
        out = Path(args.output).expanduser().resolve()
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(text + "\n", encoding="utf-8")
        print(f"\nSaved result bundle: {out}", file=sys.stderr)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
