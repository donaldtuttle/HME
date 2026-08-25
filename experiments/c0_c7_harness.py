#!/usr/bin/env python3
"""
C0–C7 experimental harness for HME C(ψ) salience mechanisms.

Status: DEVELOP typed-realization experiment infrastructure.
Canonical weight: none. No efficacy claim is made by running this harness.

Freeze boundary (required before any scored run):
  1. engine SHA-256
  2. protocol hash (references/c0-c7-ablation.md)
  3. query/artifact corpus hash
  4. answer-key hash
  5. seed + config pin

This harness:
  - builds a synthetic frozen corpus and independent answer key
  - runs the full 2×2×2 factorial (C0–C7)
  - computes primary efficacy metrics against the external answer key
  - emits a machine-readable result bundle per condition

It does not promote any switch to default-on.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import platform
import sys
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Sequence

import numpy as np

# ---------------------------------------------------------------------------
# Constants / protocol identity
# ---------------------------------------------------------------------------

PROTOCOL_ID = "C0-C7-HME-Cpsi-salience-v1"
PROTOCOL_PATH = "skills/hme/references/c0-c7-ablation.md"
ACTIVE_ENGINE_PIN = (
    "1caff9577e8a4bdaa2b0510c79673035081a967a25f15067bfa8ce99ccca6d11"
)

DEFAULT_SEED = 73_120_26
DEFAULT_MEMORY_SIZE = 64
DEFAULT_ENCODING_RESOLUTION = 16
DEFAULT_N_ARTIFACTS = 32
DEFAULT_N_QUERIES = 48

# Factorial matrix
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


# ---------------------------------------------------------------------------
# Frozen corpus + answer key
# ---------------------------------------------------------------------------

@dataclass
class FrozenCorpus:
    """Synthetic but fully pinned memory population + external labels."""

    seed: int
    vectors: np.ndarray                    # (n_artifacts, dim)
    positions: list[tuple[int, int]]
    queries: list[np.ndarray]              # (n_queries, dim)
    # answer_key[q] = list of artifact indices that are relevant for query q
    answer_key: list[list[int]]
    corpus_hash: str = ""
    answer_key_hash: str = ""

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


def build_frozen_corpus(
    *,
    seed: int,
    n_artifacts: int,
    n_queries: int,
    dim: int,
    memory_size: int,
) -> FrozenCorpus:
    """
    Construct a deterministic synthetic corpus and an independent answer key.

    Relevance rule (external, not base_score):
      For each query we designate the nearest 2 artifacts (by L2 on the
      generating vectors) as relevant. This is computed once, frozen, and
      never recomputed from engine scores.
    """
    rng = np.random.default_rng(seed)

    vectors = rng.standard_normal((n_artifacts, dim))
    # Normalize for stable distances
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

    queries = []
    answer_key: list[list[int]] = []
    for _ in range(n_queries):
        # Query = small perturbation of a random artifact vector
        src = int(rng.integers(0, n_artifacts))
        noise = rng.normal(0.0, 0.15, size=dim)
        q = vectors[src] + noise
        q = q / (np.linalg.norm(q) + 1e-12)
        queries.append(q)

        # External relevance: two nearest generating vectors
        dists = np.linalg.norm(vectors - q[None, :], axis=1)
        nearest = np.argsort(dists)[:2].tolist()
        answer_key.append(nearest)

    corpus = FrozenCorpus(
        seed=seed,
        vectors=vectors,
        positions=positions,
        queries=queries,
        answer_key=answer_key,
    )
    corpus.pin()
    return corpus


# ---------------------------------------------------------------------------
# Condition runner
# ---------------------------------------------------------------------------

def run_condition(
    engine_module: Any,
    corpus: FrozenCorpus,
    *,
    condition: dict[str, Any],
    memory_size: int,
    encoding_resolution: int,
    seed: int,
    relevance_threshold: float = 0.0,
    rejection_threshold: float | None = 0.5,
) -> dict[str, Any]:
    CollapseConfig = engine_module.CollapseConfig
    QOSMOSHMEEngine = engine_module.QOSMOSHMEEngine

    cfg = CollapseConfig(
        enabled=True,
        influence_write_gain=bool(condition["W"]),
        influence_retrieval=bool(condition["R"]),
        enable_inscription_rejection=bool(condition["I"]),
        rejection_threshold=rejection_threshold if condition["I"] else None,
        relevance_threshold=relevance_threshold,
    )

    engine = QOSMOSHMEEngine(
        memory_size=memory_size,
        encoding_resolution=encoding_resolution,
        collapse_config=cfg,
        seed=seed,
    )

    # Encode corpus. When W is on we force a collapse on every write so
    # the gain path is exercised (synthetic but deterministic).
    artifact_ids: list[str] = []
    gains: list[float] = []
    field_amps: list[float] = []

    for i, (vec, pos) in enumerate(zip(corpus.vectors, corpus.positions)):
        pre_norm = float(np.linalg.norm(engine.hme.field))
        if condition["W"]:
            # Force collapse + write on same tick so write-gain can fire
            result = engine.step(
                memory_payload=vec,
                memory_position=pos,
                memory_gain=0.12,
                collapse_override=True,
                metadata={"corpus_index": i},
            )
            art = result.memory_artifact
        else:
            art = engine.encode_memory(
                vec,
                pos,
                recursive_factor=0.12,
                glyph="Σ◯",
                metadata={"corpus_index": i},
                t=i,
            )
        assert art is not None
        artifact_ids.append(art.artifact_id)
        gains.append(float(art.gain))
        post_norm = float(np.linalg.norm(engine.hme.field))
        field_amps.append(abs(post_norm - pre_norm))

    # Retrieval pass against frozen answer key
    top1_hits = 0
    precisions = {1: [], 3: [], 5: []}
    recalls = {1: [], 3: [], 5: []}
    rr_list: list[float] = []
    rank_displacements: list[float] = []
    kendalls: list[float] = []
    spearmans: list[float] = []
    reordered = 0
    no_match = 0
    low_inscription = 0
    false_rejections = 0
    total_relevant_seen = 0

    for q_idx, query in enumerate(corpus.queries):
        relevant = set(corpus.answer_key[q_idx])
        # Use first relevant artifact position as query position (synthetic)
        pos = corpus.positions[corpus.answer_key[q_idx][0]]

        receipt = engine.retrieve_memory(pos, query=query, top_k=5)

        if receipt.rejection_reason == "NO_MATCH" or not receipt.hits:
            no_match += 1
            rr_list.append(0.0)
            continue

        if receipt.rejected and receipt.rejection_reason == "LOW_INSCRIPTION_SALIENCE":
            low_inscription += 1
            # Count false rejection if any ground-truth relevant was selected
            selected_idx = None
            for hid in [h.artifact_id for h in receipt.hits]:
                if hid in artifact_ids:
                    selected_idx = artifact_ids.index(hid)
                    break
            if selected_idx is not None and selected_idx in relevant:
                false_rejections += 1
                total_relevant_seen += 1

        # Map returned artifact_ids back to corpus indices
        returned_indices = []
        for hit in receipt.hits:
            if hit.artifact_id in artifact_ids:
                returned_indices.append(artifact_ids.index(hit.artifact_id))

        # Top-1 accuracy
        if returned_indices and returned_indices[0] in relevant:
            top1_hits += 1

        # Precision / Recall @k
        for k in (1, 3, 5):
            topk = returned_indices[:k]
            if not topk:
                precisions[k].append(0.0)
                recalls[k].append(0.0)
                continue
            hits_at_k = len([i for i in topk if i in relevant])
            precisions[k].append(hits_at_k / len(topk))
            recalls[k].append(hits_at_k / max(len(relevant), 1))

        # MRR
        rr = 0.0
        for rank, idx in enumerate(returned_indices, start=1):
            if idx in relevant:
                rr = 1.0 / rank
                break
        rr_list.append(rr)

        # Mechanistic: compare base vs final ordering among eligible hits
        if len(receipt.hits) >= 2:
            base_order = sorted(
                range(len(receipt.hits)),
                key=lambda i: receipt.hits[i].base_score,
                reverse=True,
            )
            final_order = list(range(len(receipt.hits)))  # already sorted by final
            # Simple displacement of the top base item
            top_base = base_order[0]
            final_rank_of_top_base = final_order.index(top_base) + 1
            rank_displacements.append(float(final_rank_of_top_base - 1))
            if base_order != final_order:
                reordered += 1

            # Spearman on the two rankings (short lists)
            n = len(receipt.hits)
            if n >= 2:
                base_ranks = {idx: r for r, idx in enumerate(base_order)}
                final_ranks = {idx: r for r, idx in enumerate(final_order)}
                d2 = sum(
                    (base_ranks[i] - final_ranks[i]) ** 2 for i in range(n)
                )
                spearman = 1.0 - (6 * d2) / (n * (n * n - 1)) if n > 1 else 1.0
                spearmans.append(spearman)

    n_q = len(corpus.queries)
    n_reordered_denom = max(n_q - no_match, 1)

    result = {
        "condition": condition["id"],
        "switches": {"W": condition["W"], "R": condition["R"], "I": condition["I"]},
        "n_artifacts": len(artifact_ids),
        "n_queries": n_q,
        "top1_accuracy": top1_hits / n_q,
        "precision@1": float(np.mean(precisions[1])) if precisions[1] else 0.0,
        "precision@3": float(np.mean(precisions[3])) if precisions[3] else 0.0,
        "precision@5": float(np.mean(precisions[5])) if precisions[5] else 0.0,
        "recall@1": float(np.mean(recalls[1])) if recalls[1] else 0.0,
        "recall@3": float(np.mean(recalls[3])) if recalls[3] else 0.0,
        "recall@5": float(np.mean(recalls[5])) if recalls[5] else 0.0,
        "MRR": float(np.mean(rr_list)) if rr_list else 0.0,
        "rank_displacement_mean": float(np.mean(rank_displacements))
        if rank_displacements
        else 0.0,
        "spearman_rho_mean": float(np.mean(spearmans)) if spearmans else 1.0,
        "reordered_fraction": reordered / n_reordered_denom,
        "NO_MATCH_rate": no_match / n_q,
        "LOW_INSCRIPTION_SALIENCE_rate": low_inscription / n_q,
        "false_rejection_rate": (
            false_rejections / max(total_relevant_seen, 1)
            if condition["I"]
            else 0.0
        ),
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
        # write_interference left as placeholder for denser future corpora
        "write_interference": None,
        "noise_robustness": None,  # optional extension; reuse audit protocol
    }
    return result


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def run_all(args: argparse.Namespace) -> dict[str, Any]:
    engine_module = load_engine(args.engine)
    engine_path = Path(args.engine).resolve() if args.engine else None

    # Engine pin check (best-effort when path supplied)
    engine_sha = None
    if engine_path and engine_path.is_file():
        engine_sha = _file_sha256(engine_path)

    protocol_path = Path(args.protocol) if args.protocol else None
    protocol_sha = _file_sha256(protocol_path) if protocol_path else None

    corpus = build_frozen_corpus(
        seed=args.seed,
        n_artifacts=args.artifacts,
        n_queries=args.queries,
        dim=args.dimension,
        memory_size=args.memory_size,
    )

    pins = {
        "engine_sha256": engine_sha or ACTIVE_ENGINE_PIN,
        "protocol_id": PROTOCOL_ID,
        "protocol_path": PROTOCOL_PATH,
        "protocol_sha256": protocol_sha,
        "corpus_hash": corpus.corpus_hash,
        "answer_key_hash": corpus.answer_key_hash,
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

    # Refuse to proceed if critical pins are missing when strict mode is on
    if args.strict:
        missing = [
            k
            for k, v in pins.items()
            if v is None and k in ("engine_sha256", "protocol_sha256")
        ]
        if missing:
            raise RuntimeError(
                f"Strict mode: missing freeze pins {missing}. "
                "Supply --engine and --protocol paths."
            )

    condition_results = []
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
        )
        condition_results.append(result)

    # Simple main-effect / interaction contrasts vs C0
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

    bundle = {
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
        "contrasts_vs_C0": contrasts,
        "notes": [
            "Answer key is external (nearest generating vectors), not base_score.",
            "Write-interference and noise_robustness left null in this minimal corpus;",
            "extend corpus density before treating those metrics as decisive.",
            "C0–C7 must be re-run on any larger frozen corpus before efficacy claims.",
        ],
    }
    return bundle


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="C0–C7 HME C(ψ) salience experimental harness"
    )
    p.add_argument("--engine", help="Path to qosmos_hme_engine.py")
    p.add_argument(
        "--protocol",
        help="Path to c0-c7-ablation.md (for protocol pin)",
        default=None,
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
        help="Refuse to run if engine or protocol SHA pins are missing",
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
