"""HME-NN-3 accuracy-only evaluator; registered seeds run only after publication.

Cache the shared-position ranker's query-independent distance/field components.
This is a scoring-equivalent implementation, not an API latency benchmark.
Compare every public per-hit score/order on development fixtures and verify the
first query of every registered cell against each full HME API variant.
"""
from __future__ import annotations

import os
for _name in ("OPENBLAS_NUM_THREADS", "OMP_NUM_THREADS", "MKL_NUM_THREADS"):
    os.environ[_name] = "1"

import argparse
import copy
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import platform
import re
import subprocess
import sys
import traceback

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from hme_engine import HMEConfig, HMEEngine
from experiments.sign_ablation_v1.signed_variant import signed_module

PROTOCOL_COMMIT = "8a3f9420d74424d9bd4490292e60d1bc4adeee3c"
SEEDS = tuple(range(26092501, 26092531))
SIGMAS = (0.0, 0.25, 0.5, 1.0)
ARMS = ("raw_signed_nn", "raw_absolute_nn", "processed_signed_nn",
        "processed_symmetric_nn", "hme_default", "hme_symmetric",
        "hme_no_window", "hme_no_window_field_erased", "hme_no_window_signed")
FROZEN = ("hme_engine.py", "experiments/sign_ablation_v1/signed_variant.py",
          "experiments/raw_vector_baseline_v1/PROTOCOL.md",
          "experiments/raw_vector_baseline_v1/evaluate.py",
          "tests/test_raw_vector_baseline.py")
CONTRASTS = (
    ("hme_default", "raw_signed_nn"),
    ("hme_no_window", "hme_default"),
    ("hme_symmetric", "hme_default"),
    ("processed_signed_nn", "raw_signed_nn"),
    ("hme_no_window", "raw_signed_nn"),
    ("hme_no_window_signed", "raw_signed_nn"),
    ("raw_absolute_nn", "raw_signed_nn"),
    ("hme_no_window", "hme_no_window_field_erased"),
)
EPS = 1e-12


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def array_hash(array: np.ndarray) -> str:
    a = np.ascontiguousarray(array)
    return sha(str(a.dtype).encode() + b"|" + str(a.shape).encode() + b"|" + a.tobytes())


def cosine_scores(vectors: np.ndarray, query: np.ndarray, absolute=False) -> np.ndarray:
    v = np.asarray(vectors, dtype=np.complex128)
    q = np.asarray(query, dtype=np.complex128).copy()
    qnorm = float(np.linalg.norm(q))
    if qnorm > EPS:
        q /= qnorm
    denominator = np.linalg.norm(v, axis=1) * np.linalg.norm(q)
    dots = v.conj() @ q
    numerator = np.abs(dots) if absolute else dots.real
    return np.divide(numerator, denominator, out=np.zeros(len(v)), where=denominator > EPS)


def order(scores: np.ndarray) -> np.ndarray:
    return np.argsort(-scores, kind="stable")


class Snapshot:
    """Cache production per-candidate components; retain independent provenance."""
    def __init__(self, engine, position):
        self.position = position
        self.ids = list(engine.hme.records)
        self.lookup = {item: i for i, item in enumerate(self.ids)}
        self.vectors = np.stack(list(engine.hme._payloads.values())).copy()
        self.records = copy.deepcopy(list(engine.hme.records.values()))
        self.lineage = copy.deepcopy(engine.lineage.to_dict())
        hits = engine.retrieve_memory(position, query=np.zeros(self.vectors.shape[1]),
                                      top_k=len(self.ids)).hits
        assert len(hits) == len(self.ids)
        self.distance = np.zeros(len(self.ids))
        self.pattern = np.zeros(len(self.ids))
        for hit in hits:
            i = self.lookup[hit.artifact_id]
            self.distance[i], self.pattern[i] = hit.distance_score, hit.pattern_score

    def scores(self, query, *, signed=False):
        cosine = cosine_scores(self.vectors, query, absolute=not signed)
        return np.clip(.38 * self.distance + .42 * cosine + .20 * self.pattern, 0., 1.)

    def verify_api(self, engine, query, *, signed=False):
        scores = self.scores(query, signed=signed)
        hits = engine.retrieve_memory(self.position, query=query, top_k=len(self.ids)).hits
        actual = np.asarray([self.lookup[h.artifact_id] for h in hits])
        np.testing.assert_array_equal(order(scores), actual)
        np.testing.assert_allclose(scores[actual], [h.final_score for h in hits],
                                   rtol=0, atol=2e-14)
        return float(np.max(np.abs(scores[actual] - [h.final_score for h in hits])))


def build_engines(vectors, seed, memory_size=64, position=(32, 32)):
    engines = {}
    dimension = vectors.shape[1]
    for name, window, module in (("default", True, None), ("no_window", False, None),
                                  ("signed", False, signed_module())):
        cls = HMEEngine if module is None else module.HMEEngine
        cfg = HMEConfig if module is None else module.HMEConfig
        engine = cls(hme_config=cfg(memory_size=memory_size,
                         encoding_resolution=dimension, use_hann_window=window), seed=seed)
        for i, vector in enumerate(vectors):
            engine.encode_memory(vector, position, tag=f"raw-nn3:{i}",
                                 metadata={"item_index": i})
        engines[name] = engine
    engines["erased"] = copy.deepcopy(engines["no_window"])
    engines["erased"].hme.field.fill(0)
    return engines


def score_arms(raw, query, snapshots):
    tapered = query * np.hanning(query.size)
    native, unwindowed = snapshots["default"], snapshots["no_window"]
    return {
        "raw_signed_nn": cosine_scores(raw, query),
        "raw_absolute_nn": cosine_scores(raw, query, absolute=True),
        "processed_signed_nn": cosine_scores(native.vectors, query),
        "processed_symmetric_nn": cosine_scores(native.vectors, tapered),
        "hme_default": native.scores(query),
        "hme_symmetric": native.scores(tapered),
        "hme_no_window": unwindowed.scores(query),
        "hme_no_window_field_erased": snapshots["erased"].scores(query),
        "hme_no_window_signed": snapshots["signed"].scores(query, signed=True),
    }


def seed_cells(seed, n=128, dimension=16, memory_size=64, position=(32, 32), sigmas=SIGMAS):
    rng = np.random.default_rng(seed)
    raw = rng.standard_normal((n, dimension))
    engines = build_engines(raw, seed, memory_size, position)
    snapshots = {name: Snapshot(engine, position) for name, engine in engines.items()}
    # The raw baseline must retain untouched source coordinates, not ledger vectors.
    np.testing.assert_allclose(snapshots["no_window"].vectors.real,
                               raw / np.linalg.norm(raw, axis=1)[:, None], atol=1e-14)
    ledger_erased = copy.deepcopy(engines["default"])
    field_hash = array_hash(ledger_erased.hme.field)
    for name in ("records", "_payloads", "_patterns"):
        getattr(ledger_erased.hme, name).clear()
    assert not ledger_erased.retrieve_memory(position, query=raw[0], top_k=1).hits
    assert field_hash == array_hash(ledger_erased.hme.field)
    cells = []
    for sigma in sigmas:
        queries = raw + sigma * rng.standard_normal(raw.shape)
        probe = queries[0]
        errors = [snapshots[name].verify_api(engines[name], probe, signed=name == "signed")
                  for name in engines]
        errors.append(snapshots["default"].verify_api(engines["default"],
                                                      probe * np.hanning(dimension)))
        predictions = {name: [] for name in ARMS}
        for query in queries:
            scores = score_arms(raw, query, snapshots)
            # Shared-position, field-erased HME has exactly the abs-cosine ranking.
            np.testing.assert_array_equal(order(scores["hme_no_window_field_erased"]),
                                           order(scores["raw_absolute_nn"]))
            for name in ARMS:
                predictions[name].append(int(order(scores[name])[0]))
        correct = {name: int(np.sum(np.asarray(values) == np.arange(n)))
                   for name, values in predictions.items()}
        cells.append({"seed": seed, "sigma": sigma, "n": n, "dimension": dimension,
                      "item_sha256": array_hash(raw), "query_sha256": array_hash(queries),
                      "predictions": predictions, "correct": correct,
                      "max_api_score_error": max(errors), "ledger_erased_identity_hits": 0})
    return cells


def summarize(cells):
    seeds = sorted({c["seed"] for c in cells})
    draws = np.random.default_rng(26092500).integers(0, len(seeds), (10000, len(seeds)))
    summaries = []
    for sigma in sorted({c["sigma"] for c in cells}):
        group = sorted((c for c in cells if c["sigma"] == sigma), key=lambda c: c["seed"])
        if [c["seed"] for c in group] != seeds:
            raise ValueError("Incomplete or duplicate seed/sigma cells")
        values = {name: np.array([c["correct"][name] / c["n"] * 100 for c in group])
                  for name in ARMS}
        contrasts = {}
        for a, b in CONTRASTS:
            delta = values[a] - values[b]
            contrasts[f"{a} - {b}"] = {"mean_pp": float(delta.mean()),
                "ci95_pp": np.quantile(delta[draws].mean(axis=1), [.025, .975]).tolist(),
                "paired_seed_deltas_pp": delta.tolist()}
        gap = float((values["raw_signed_nn"] - values["hme_default"]).mean())
        improvement = float((values["hme_no_window"] - values["hme_default"]).mean())
        summaries.append({"sigma": sigma,
            "mean_accuracy_percent": {k: float(v.mean()) for k, v in values.items()},
            "mean_correct_count": {k: float(np.mean([c["correct"][k] for c in group])) for k in ARMS},
            "contrasts": contrasts,
            "descriptive_gap_reduction_fraction": improvement/gap if gap > 0 else None})
    return summaries


def verify_registration(commit):
    if not re.fullmatch(r"[0-9a-f]{40}", commit) or commit == PROTOCOL_COMMIT:
        raise ValueError("Supply the full, separate evaluator registration commit SHA")
    subprocess.run(["git", "merge-base", "--is-ancestor", PROTOCOL_COMMIT, commit],
                   cwd=ROOT, check=True, capture_output=True)
    hashes = {}
    for name in FROZEN:
        registered = subprocess.check_output(["git", "show", f"{commit}:{name}"], cwd=ROOT)
        current = (ROOT / name).read_bytes()
        if current != registered:
            raise RuntimeError(f"Frozen source mismatch: {name}")
        hashes[name] = sha(current)
    original = subprocess.check_output(["git", "show",
        f"{PROTOCOL_COMMIT}:experiments/raw_vector_baseline_v1/PROTOCOL.md"], cwd=ROOT)
    if original != (ROOT / "experiments/raw_vector_baseline_v1/PROTOCOL.md").read_bytes():
        raise RuntimeError("The prospective protocol was changed")
    return hashes


def render_report(result):
    lines = ["# HME-NN-3: raw-vector and Hann-window results", "",
        f"Protocol registration: `{PROTOCOL_COMMIT}`.",
        f"Evaluator registration: `{result['registration_commit']}`.", "",
        "Thirty fixed seeds, 128 Gaussian items, dimension 16, one shared position.",
        "Cells are mean top-1 accuracy (%). Original vectors are not normalized before noise.", "",
        "| Arm | sigma 0 | sigma .25 | sigma .5 | sigma 1 |",
        "|---|---:|---:|---:|---:|"]
    for arm in ARMS:
        cells = " | ".join(f"{s['mean_accuracy_percent'][arm]:.2f}" for s in result["summary"])
        lines.append(f"| {arm} | {cells} |")
    lines += ["", "## Primary and prespecified descriptive contrasts", "",
              "Differences are percentage points, not correct-item counts.", "",
              "| Contrast at sigma 1 | Mean difference | Paired 95% interval |",
              "|---|---:|---:|"]
    primary = next(s for s in result["summary"] if s["sigma"] == 1.0)
    for name, stat in primary["contrasts"].items():
        lo, hi = stat["ci95_pp"]
        lines.append(f"| {name} | {stat['mean_pp']:+.2f} | [{lo:+.2f}, {hi:+.2f}] |")
    fraction = primary["descriptive_gap_reduction_fraction"]
    if fraction is not None:
        lines += ["", f"No-window gap reduction at sigma 1: {100*fraction:.1f}% (descriptive ratio, not causal attribution)."]
    lines += ["", "## Interpretation and boundaries", "",
        "Raw-input NN and matched-processed NN answer different questions. The latter",
        "remains the registered HME-NN-1 baseline; its old report is not overwritten.",
        "The no-window control separates tapering from the sign and field terms.",
        "Symmetric tapering is a separate condition; it does not restore coordinates",
        "discarded or attenuated by the taper. Secondary contrasts are descriptive.",
        "No default-engine change, field retrieval advantage, equivalence, calibrated",
        "confidence, semantic-memory benefit, or speed/storage claim follows from this study.", "",
        "The evaluator caches query-independent components of the frozen ranker.",
        "All registered cells pass full-API score/order probes for each HME variant",
        "and symmetric queries; development tests compare every score and rank on",
        "small fixtures. The field-erased ranking equals absolute cosine on every",
        "evaluated query. Ledger-erased engines return no identity hits with fields preserved.",
        "All 120 registered seed/noise cells completed. No protocol deviations.", "",
        "Raw predictions, counts, dataset/source hashes, runtime versions, and all",
        "secondary intervals are in [results.json](results.json).", "",
        "## Reproduce", "", "```bash",
        "OPENBLAS_NUM_THREADS=1 python experiments/raw_vector_baseline_v1/evaluate.py \\",
        f"  --registration-commit {result['registration_commit']} \\",
        "  --output outputs/raw_vector_baseline_v1", "```", "",
        "Use a fresh output directory. The evaluator rejects changed frozen sources",
        "and records technical failures rather than publishing a partial success.", ""]
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--registration-commit", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=False)
    try:
        hashes = verify_registration(args.registration_commit)
        cells = []
        for seed in SEEDS:
            cells.extend(seed_cells(seed))
        assert len(cells) == len(SEEDS) * len(SIGMAS)
        result = {"study": "HME-NN-3", "status": "complete", "deviations": [],
            "protocol_commit": PROTOCOL_COMMIT, "registration_commit": args.registration_commit,
            "source_sha256": hashes, "python": platform.python_version(), "numpy": np.__version__,
            "finished_utc": datetime.now(timezone.utc).isoformat(),
            "configuration": {"memory_size": 64, "dimension": 16, "items": 128,
                "position": [32, 32], "strength": 1.0, "seeds": SEEDS, "sigmas": SIGMAS,
                "bootstrap_draws": 10000, "bootstrap_seed": 26092500,
                "implementation": "cached production components; accuracy only; API probes per cell"},
            "cells": cells, "summary": summarize(cells)}
        (args.output / "results.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
        (args.output / "REPORT.md").write_text(render_report(result), encoding="utf-8")
        (args.output / "RESULTS.sha256").write_text("".join(
            f"{sha((args.output/name).read_bytes())}  {name}\n" for name in ("results.json", "REPORT.md")), encoding="utf-8")
        print(render_report(result))
    except Exception:
        (args.output / "FAILED.json").write_text(json.dumps({"status": "failed",
            "registration_commit": args.registration_commit, "traceback": traceback.format_exc()}, indent=2) + "\n")
        raise


if __name__ == "__main__":
    main()
