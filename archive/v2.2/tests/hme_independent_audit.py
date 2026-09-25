#!/usr/bin/env python3
"""
hme_independent_audit.py
========================
Independent audit harness for the current QOSMOS HME typed realization.

This script does not redefine HME and does not amend QOFT canon. It imports
qosmos_hme_engine.py and tests the implementation as written.

Tests
-----
1. Deterministic encoding and field generation.
2. Linear superposition of stored HME patterns.
3. Top-1 numerical retrieval under increasing Gaussian noise.
4. Retrieval with the complex field erased but artifact records preserved.
5. Retrieval with artifact records erased but the complex field preserved.
6. Exact and partial string-query behavior.
7. Confidence returned for an unrelated numerical query.

Expected layout
---------------
Option A:
    qosmos_hme_engine.py
    hme_independent_audit.py

Option B:
    core/qosmos_hme_engine.py
    hme_independent_audit.py

Run
---
    python hme_independent_audit.py

Or point directly to the engine file:
    python hme_independent_audit.py --engine ./core/qosmos_hme_engine.py

Save a JSON report:
    python hme_independent_audit.py --output hme_audit_report.json

Required dependency: numpy
"""

from __future__ import annotations

import argparse
import copy
import importlib
import importlib.util
import json
import platform
import sys
from pathlib import Path
from types import ModuleType
from typing import Any, Sequence

import numpy as np


DEFAULT_SEED = 7_312_026
DEFAULT_MEMORY_COUNT = 128
DEFAULT_VECTOR_DIMENSION = 16
DEFAULT_MEMORY_SIZE = 64
DEFAULT_POSITION = (32, 32)
DEFAULT_NOISE_LEVELS = (0.0, 0.05, 0.10, 0.25, 0.50, 1.00)


def load_engine_module(engine_path: str | None) -> ModuleType:
    """Load qosmos_hme_engine from a path or from normal Python imports."""
    if engine_path:
        path = Path(engine_path).expanduser().resolve()
        if not path.is_file():
            raise FileNotFoundError(f"HME engine not found: {path}")

        spec = importlib.util.spec_from_file_location("qosmos_hme_engine_audit", path)
        if spec is None or spec.loader is None:
            raise ImportError(f"Could not create an import spec for: {path}")

        module = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = module
        spec.loader.exec_module(module)
        return module

    errors: list[str] = []
    for module_name in ("core.qosmos_hme_engine", "qosmos_hme_engine"):
        try:
            return importlib.import_module(module_name)
        except Exception as exc:  # Preserve both failure paths for diagnosis.
            errors.append(f"{module_name}: {exc}")

    joined = "\n  ".join(errors)
    raise ImportError(
        "Could not import qosmos_hme_engine. Put this script beside the engine, "
        "run it from the repository root, or pass --engine PATH.\n"
        f"Import attempts:\n  {joined}"
    )


def build_numeric_engine(
    engine_module: ModuleType,
    *,
    vectors: np.ndarray,
    seed: int,
    memory_size: int,
    vector_dimension: int,
    position: tuple[int, int],
    recursive_factor: float,
) -> tuple[Any, list[str]]:
    """Create one engine and encode every vector at the same location."""
    engine_class = getattr(engine_module, "QOSMOSHMEEngine", None)
    if engine_class is None:
        raise AttributeError("Engine module has no QOSMOSHMEEngine class")

    engine = engine_class(
        memory_size=memory_size,
        encoding_resolution=vector_dimension,
        seed=seed,
    )

    artifact_ids: list[str] = []
    for index, vector in enumerate(vectors):
        artifact = engine.encode_memory(
            vector,
            position,
            recursive_factor=recursive_factor,
            tag=f"audit:numeric:{index:04d}",
            glyph="Σ◯",
            metadata={"audit_index": index, "audit_kind": "numeric"},
            t=index,
        )
        artifact_ids.append(artifact.artifact_id)

    return engine, artifact_ids


def top1_accuracy(
    engine: Any,
    *,
    source_vectors: np.ndarray,
    artifact_ids: Sequence[str],
    position: tuple[int, int],
    noise_sigma: float,
    noise_seed: int,
) -> dict[str, Any]:
    """Measure top-1 artifact identification for one noise level."""
    rng = np.random.default_rng(noise_seed)
    correct = 0
    misses: list[dict[str, Any]] = []

    for index, vector in enumerate(source_vectors):
        if noise_sigma == 0.0:
            query = vector.copy()
        else:
            query = vector + rng.normal(0.0, noise_sigma, size=vector.shape)

        retrieval = engine.retrieve_memory(position, query=query, top_k=1)
        returned_id = retrieval.hits[0].artifact_id if retrieval.hits else None
        expected_id = artifact_ids[index]

        if returned_id == expected_id:
            correct += 1
        elif len(misses) < 12:
            misses.append(
                {
                    "index": index,
                    "expected_artifact_id": expected_id,
                    "returned_artifact_id": returned_id,
                    "confidence": float(retrieval.confidence),
                }
            )

    total = len(source_vectors)
    return {
        "noise_sigma": float(noise_sigma),
        "correct": int(correct),
        "total": int(total),
        "accuracy": float(correct / total if total else 0.0),
        "sample_misses": misses,
    }


def deterministic_checks(
    engine_module: ModuleType,
    *,
    vectors: np.ndarray,
    seed: int,
    memory_size: int,
    vector_dimension: int,
    position: tuple[int, int],
    recursive_factor: float,
) -> tuple[Any, list[str], dict[str, Any]]:
    """Encode the same dataset twice and compare artifacts and fields."""
    engine_a, ids_a = build_numeric_engine(
        engine_module,
        vectors=vectors,
        seed=seed,
        memory_size=memory_size,
        vector_dimension=vector_dimension,
        position=position,
        recursive_factor=recursive_factor,
    )
    engine_b, ids_b = build_numeric_engine(
        engine_module,
        vectors=vectors,
        seed=seed,
        memory_size=memory_size,
        vector_dimension=vector_dimension,
        position=position,
        recursive_factor=recursive_factor,
    )

    payload_hashes_a = [
        artifact.payload_hash for artifact in engine_a.hme.records.values()
    ]
    payload_hashes_b = [
        artifact.payload_hash for artifact in engine_b.hme.records.values()
    ]
    pattern_hashes_a = [
        artifact.pattern_hash for artifact in engine_a.hme.records.values()
    ]
    pattern_hashes_b = [
        artifact.pattern_hash for artifact in engine_b.hme.records.values()
    ]

    field_delta = np.asarray(engine_a.hme.field) - np.asarray(engine_b.hme.field)
    max_field_difference = float(np.max(np.abs(field_delta)))

    report = {
        "artifact_ids_identical": ids_a == ids_b,
        "payload_hashes_identical": payload_hashes_a == payload_hashes_b,
        "pattern_hashes_identical": pattern_hashes_a == pattern_hashes_b,
        "fields_allclose": bool(np.allclose(engine_a.hme.field, engine_b.hme.field)),
        "max_field_difference": max_field_difference,
    }
    return engine_a, ids_a, report


def linear_superposition_check(engine: Any) -> dict[str, Any]:
    """
    Rebuild the HME field from each retained pattern and compare it to the
    engine's accumulated field.

    This intentionally reads private audit surfaces (_patterns and
    _patch_slices). It does not modify them.
    """
    hme = engine.hme
    required = ("_patterns", "_patch_slices")
    missing = [name for name in required if not hasattr(hme, name)]
    if missing:
        return {
            "supported": False,
            "reason": f"Engine lacks audit surfaces: {', '.join(missing)}",
        }

    reconstructed = np.zeros_like(hme.field, dtype=np.complex128)
    for artifact_id, artifact in hme.records.items():
        pattern = hme._patterns[artifact_id]
        grid_slice, pattern_slice = hme._patch_slices(
            artifact.position, pattern.shape
        )
        reconstructed[grid_slice] += artifact.gain * pattern[pattern_slice]

    difference = np.asarray(hme.field) - reconstructed
    max_error = float(np.max(np.abs(difference)))
    return {
        "supported": True,
        "allclose": bool(np.allclose(hme.field, reconstructed)),
        "max_absolute_error": max_error,
    }


def field_vs_ledger_ablation(
    engine: Any,
    *,
    vectors: np.ndarray,
    artifact_ids: Sequence[str],
    position: tuple[int, int],
    seed: int,
) -> dict[str, Any]:
    """Separate the field contribution from the retained artifact ledger."""
    normal = top1_accuracy(
        engine,
        source_vectors=vectors,
        artifact_ids=artifact_ids,
        position=position,
        noise_sigma=0.0,
        noise_seed=seed + 20_000,
    )

    field_erased_engine = copy.deepcopy(engine)
    field_erased_engine.hme.field.fill(0.0)
    field_erased = top1_accuracy(
        field_erased_engine,
        source_vectors=vectors,
        artifact_ids=artifact_ids,
        position=position,
        noise_sigma=0.0,
        noise_seed=seed + 20_001,
    )

    ledger_erased_engine = copy.deepcopy(engine)
    retained_field_norm = float(np.linalg.norm(ledger_erased_engine.hme.field))
    ledger_erased_engine.hme.records.clear()
    ledger_erased_engine.hme._payloads.clear()
    ledger_erased_engine.hme._patterns.clear()

    retrieval = ledger_erased_engine.retrieve_memory(
        position,
        query=vectors[0],
        top_k=1,
    )

    return {
        "normal_exact_query": normal,
        "field_erased_records_preserved": field_erased,
        "ledger_erased_field_preserved": {
            "retained_field_norm": retained_field_norm,
            "hit_count": len(retrieval.hits),
            "confidence": float(retrieval.confidence),
            "decoded_surface_norm": float(np.linalg.norm(retrieval.decoded_surface)),
            "decoded_vector_norm": float(np.linalg.norm(retrieval.decoded_vector)),
        },
    }


def symbol_probe(
    engine_module: ModuleType,
    *,
    seed: int,
    memory_size: int,
    vector_dimension: int,
    position: tuple[int, int],
) -> dict[str, Any]:
    """Show exact-symbol retrieval and the behavior of partial text cues."""
    engine_class = getattr(engine_module, "QOSMOSHMEEngine")
    engine = engine_class(
        memory_size=memory_size,
        encoding_resolution=vector_dimension,
        seed=seed,
    )

    symbols = ("recursive_self", "red_cube", "blue_sphere", "glass_badge")
    id_to_symbol: dict[str, str] = {}
    for index, symbol in enumerate(symbols):
        artifact = engine.encode_memory(
            symbol,
            position,
            recursive_factor=0.15,
            glyph="Σ◯",
            metadata={"audit_index": index, "audit_kind": "symbol"},
            t=index,
        )
        id_to_symbol[artifact.artifact_id] = symbol

    queries = (
        "recursive_self",
        "red_cube",
        "recursive",
        "recursive self",
        "red cub",
    )
    results: list[dict[str, Any]] = []
    for query in queries:
        retrieval = engine.retrieve_memory(position, query=query, top_k=1)
        hit = retrieval.hits[0] if retrieval.hits else None
        returned_symbol = id_to_symbol.get(hit.artifact_id) if hit else None
        results.append(
            {
                "query": query,
                "returned_symbol": returned_symbol,
                "correct_exact_match": returned_symbol == query,
                "confidence": float(retrieval.confidence),
                "score_breakdown": (
                    {
                        "distance": float(hit.distance_score),
                        "query": float(hit.query_score),
                        "pattern": float(hit.pattern_score),
                        "combined": float(hit.score),
                    }
                    if hit is not None
                    else None
                ),
            }
        )

    return {"stored_symbols": list(symbols), "queries": results}


def unrelated_query_probe(
    engine: Any,
    *,
    position: tuple[int, int],
    vector_dimension: int,
    seed: int,
) -> dict[str, Any]:
    """Measure the best available score for a random, unrelated query."""
    rng = np.random.default_rng(seed + 90_001)
    query = rng.standard_normal(vector_dimension)
    retrieval = engine.retrieve_memory(position, query=query, top_k=1)
    hit = retrieval.hits[0] if retrieval.hits else None
    return {
        "hit_count": len(retrieval.hits),
        "confidence": float(retrieval.confidence),
        "top_hit": (
            {
                "artifact_id": hit.artifact_id,
                "distance_score": float(hit.distance_score),
                "query_score": float(hit.query_score),
                "pattern_score": float(hit.pattern_score),
                "combined_score": float(hit.score),
            }
            if hit is not None
            else None
        ),
        "interpretation": (
            "The current confidence is the highest available combined score; "
            "this probe does not treat it as a calibrated probability."
        ),
    }


def run_audit(args: argparse.Namespace) -> dict[str, Any]:
    engine_module = load_engine_module(args.engine)

    rng = np.random.default_rng(args.seed)
    vectors = rng.standard_normal((args.memories, args.dimension))
    position = (args.position_x, args.position_y)

    engine, artifact_ids, deterministic = deterministic_checks(
        engine_module,
        vectors=vectors,
        seed=args.seed,
        memory_size=args.memory_size,
        vector_dimension=args.dimension,
        position=position,
        recursive_factor=args.gain,
    )

    retrieval_results = []
    for index, sigma in enumerate(args.noise):
        retrieval_results.append(
            top1_accuracy(
                engine,
                source_vectors=vectors,
                artifact_ids=artifact_ids,
                position=position,
                noise_sigma=float(sigma),
                # Each noise level gets its own stable stream so adding a new
                # level does not alter earlier results.
                noise_seed=args.seed + 1_000 + index,
            )
        )

    module_path = getattr(engine_module, "__file__", None)
    report = {
        "audit": "QOSMOS HME independent retrieval and ablation harness",
        "status": "DEVELOP typed-realization test; not a canon or physics test",
        "environment": {
            "python": platform.python_version(),
            "numpy": np.__version__,
            "engine_module": engine_module.__name__,
            "engine_path": str(module_path) if module_path else None,
        },
        "configuration": {
            "seed": args.seed,
            "memories": args.memories,
            "vector_dimension": args.dimension,
            "memory_size": args.memory_size,
            "position": list(position),
            "recursive_factor": args.gain,
            "noise_levels": [float(value) for value in args.noise],
        },
        "determinism": deterministic,
        "linear_superposition": linear_superposition_check(engine),
        "numeric_top1_retrieval": retrieval_results,
        "field_vs_ledger_ablation": field_vs_ledger_ablation(
            engine,
            vectors=vectors,
            artifact_ids=artifact_ids,
            position=position,
            seed=args.seed,
        ),
        "symbol_probe": symbol_probe(
            engine_module,
            seed=args.seed,
            memory_size=args.memory_size,
            vector_dimension=args.dimension,
            position=position,
        ),
        "unrelated_query_probe": unrelated_query_probe(
            engine,
            position=position,
            vector_dimension=args.dimension,
            seed=args.seed,
        ),
    }
    return report


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Independent audit harness for qosmos_hme_engine.py"
    )
    parser.add_argument(
        "--engine",
        help="Path to qosmos_hme_engine.py. Optional if importable normally.",
    )
    parser.add_argument("--output", help="Optional JSON report path")
    parser.add_argument("--seed", type=int, default=DEFAULT_SEED)
    parser.add_argument("--memories", type=int, default=DEFAULT_MEMORY_COUNT)
    parser.add_argument("--dimension", type=int, default=DEFAULT_VECTOR_DIMENSION)
    parser.add_argument("--memory-size", type=int, default=DEFAULT_MEMORY_SIZE)
    parser.add_argument("--position-x", type=int, default=DEFAULT_POSITION[0])
    parser.add_argument("--position-y", type=int, default=DEFAULT_POSITION[1])
    parser.add_argument("--gain", type=float, default=0.1)
    parser.add_argument(
        "--noise",
        type=float,
        nargs="+",
        default=list(DEFAULT_NOISE_LEVELS),
        help="Gaussian noise sigma values",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.memories < 1:
        parser.error("--memories must be positive")
    if args.dimension < 2:
        parser.error("--dimension must be at least 2")
    if args.memory_size < args.dimension:
        parser.error("--memory-size must be >= --dimension")
    if not (0 <= args.position_x < args.memory_size):
        parser.error("--position-x is outside the memory field")
    if not (0 <= args.position_y < args.memory_size):
        parser.error("--position-y is outside the memory field")
    if any(value < 0.0 for value in args.noise):
        parser.error("noise sigma values cannot be negative")

    report = run_audit(args)
    rendered = json.dumps(report, indent=2, ensure_ascii=False)
    print(rendered)

    if args.output:
        output_path = Path(args.output).expanduser().resolve()
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(rendered + "\n", encoding="utf-8")
        print(f"\nSaved report: {output_path}", file=sys.stderr)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
