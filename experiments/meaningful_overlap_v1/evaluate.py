"""Development and validation runner; confirmatory execution is separately gated."""
from __future__ import annotations
import os
THREADS = {key: "1" for key in ("OPENBLAS_NUM_THREADS", "OMP_NUM_THREADS", "MKL_NUM_THREADS",
                                "VECLIB_MAXIMUM_THREADS", "NUMEXPR_NUM_THREADS")}
os.environ.update(THREADS)

import argparse
from datetime import datetime, timezone
import gzip
import json
from pathlib import Path
import platform
import resource
import time
import traceback

import numpy as np
from . import dataset, placement, retrieval, statistics, costs, integrity

HERE, ROOT = integrity.HERE, integrity.ROOT
LAYOUTS = ("RANDOM_MATCHED", "SIMILARITY_PLACED", "SEPARATED", "CONTENT_SHUFFLE")


def write_json(path, value):
    Path(path).write_text(json.dumps(value, indent=2, sort_keys=True, allow_nan=False)+"\n")


def write_gzip(path, value):
    data = json.dumps(value, separators=(",", ":"), allow_nan=False).encode()
    Path(path).write_bytes(gzip.compress(data, mtime=0))


def config():
    return json.loads((HERE/"protocol.json").read_text())


def invariant(condition, message):
    if not condition:
        raise RuntimeError(message)


def baseline_grid(p):
    grid = p["vector_grid"]
    return [{"representation": rep, "k": k, "lambda": lam}
            for rep in grid["representations"] for k in grid["k"] for lam in grid["lambda"]]


def tune_one(namespace, p):
    corpus, truth = dataset.generate(namespace, p["dataset"], p["primary"]["r"])
    q, targets = dataset.queries(namespace, corpus, p["primary"]["sigma"], p["primary"]["repeats"])
    raw = statistics.observe(retrieval.RawNN(corpus).scores(q), targets, truth.families)["metrics"]
    candidates = []
    for rule in baseline_grid(p):
        arm = retrieval.VectorAggregate(corpus, rule)
        observed = statistics.observe(arm.scores(q), targets, truth.families)
        candidates.append({"rule": rule, **observed})
    return {"namespace": namespace, "raw": raw, "candidates": candidates,
            "data_hash": dataset.array_hash(corpus.vectors), "query_hash": dataset.array_hash(q)}


def select_baseline(runs, p):
    raw = np.mean([r["raw"]["exact_top1_accuracy"] for r in runs])
    table = []
    for i, rule in enumerate(baseline_grid(p)):
        sibling = np.mean([r["candidates"][i]["metrics"]["sibling_precision_at_5"] for r in runs])
        exact = np.mean([r["candidates"][i]["metrics"]["exact_top1_accuracy"] for r in runs])
        table.append({"rule": rule, "sibling_precision_at_5": float(sibling),
                      "exact_top1_accuracy": float(exact), "eligible": bool(exact >= raw-.01)})
    feasible = [v for v in table if v["eligible"]]
    best = max(v["sibling_precision_at_5"] for v in feasible)
    tied = [v for v in feasible if best-v["sibling_precision_at_5"] <= 1e-12]
    chosen = min(tied, key=lambda v: (v["rule"]["lambda"], v["rule"]["k"], v["rule"]["representation"] != "raw"))
    return {"status": "FROZEN_AFTER_VALIDATION_TUNING", "rule": chosen["rule"],
            "source_namespaces": [r["namespace"] for r in runs], "raw_exact_mean": float(raw),
            "selection_table": table, "tuning_protocol_sha256": integrity.digest(HERE/"protocol.json")}


def reconstruction(engine):
    d = engine.hme.encoding_resolution
    errors, correlations = [], []
    for artifact_id, record in engine.hme.records.items():
        x, y = np.asarray(record.position)-d//2
        patch = engine.hme.field[x:x+d, y:y+d]
        own = record.gain*engine.hme._patterns[artifact_id]
        denom = np.linalg.norm(own)
        errors.append(float(np.linalg.norm(patch-own)/denom) if denom > 1e-12 else 0.0)
        product = np.linalg.norm(patch)*denom
        correlations.append(float(abs(np.vdot(patch, own))/product) if product > 1e-12 else 0.0)
    return {"relative_error_per_item": errors, "pattern_correlation_per_item": correlations,
            "mean_relative_error": float(np.mean(errors)), "mean_correlation": float(np.mean(correlations)),
            "scope": "Accumulated patch versus known isolated contribution, not recovery of original vectors"}


def layout_controls(arms, engine, q, cfg):
    checks = {}
    for name in ("HYBRID", "FIELD_ONLY"):
        arm = arms[name]
        cached, uncached = arm.scores(q[:8], "symmetric"), arm.scores(q[:8], "symmetric", cached=False)
        delta = float(np.max(np.abs(cached-uncached)))
        invariant(delta <= cfg["cache_atol"], "Cache score mismatch")
        invariant(np.array_equal(retrieval.ranks(cached), retrieval.ranks(uncached)), "Cache rank mismatch")
        checks[name+"_cache_max_error"] = delta
    zero = retrieval.FieldRetrieval(engine, hybrid=True)
    zero.replace_field(np.zeros_like(engine.hme.field))
    invariant(np.array_equal(zero.scores(q, "symmetric"), arms["SIGNED_NN"].scores(q, "symmetric")), "Zero-field control failed")
    checks["zero_field"] = True
    return checks


def one_corpus(namespace, p, rule, development=False, permit=None):
    cfg, primary = p["dataset"], p["primary"]
    shared_values = [primary["r"]] if development else p["descriptive"]["shared_variances"]
    cells, layouts, data_hashes = [], [], {}
    primary_scores = None
    costs_result, large_result = None, None
    for shared in shared_values:
        corpus, truth = dataset.generate(namespace, cfg, shared, permit)
        processed = retrieval.preprocess(corpus.vectors, "symmetric")
        # All layouts are built before this corpus's evaluation queries arrive.
        arranged = {}
        for kind in LAYOUTS:
            start = time.perf_counter_ns()
            pos, detail = placement.assign(processed, namespace, cfg, kind, permit=permit)
            layout_ns = time.perf_counter_ns()-start
            start = time.perf_counter_ns()
            engine, arms, mapping = retrieval.build(corpus, pos, cfg)
            write_build_ns = time.perf_counter_ns()-start
            arranged[kind] = (engine, arms, pos, detail, mapping, layout_ns, write_build_ns)
        larger = None
        if shared == primary["r"]:
            start = time.perf_counter_ns()
            large_pos, large_detail = placement.assign(processed, namespace, cfg, "SIMILARITY_PLACED",
                canvas=p["descriptive"]["larger_canvas"], spacing=p["descriptive"]["larger_spacing"], permit=permit)
            large_placement_ns = time.perf_counter_ns()-start
            large_engine, large_arms, _ = retrieval.build(corpus, large_pos, cfg, p["descriptive"]["larger_canvas"])
            larger = (large_engine, large_arms, large_pos, large_detail, large_placement_ns)
        raw_arm = retrieval.RawNN(corpus)
        start = time.perf_counter_ns()
        aggregate_arm = retrieval.VectorAggregate(corpus, rule)
        graph_build_ns = time.perf_counter_ns()-start
        query_data = {sigma: dataset.queries(namespace, corpus, sigma, primary["repeats"], permit)
                      for sigma in ([primary["sigma"]] if development else p["descriptive"]["noise_sigmas"])}
        data_hashes[str(shared)] = {"vectors": dataset.array_hash(corpus.vectors),
            "ids": list(corpus.ids), "families_evaluator_only": truth.families.tolist(),
            "queries": {str(s): dataset.array_hash(q) for s, (q, _) in query_data.items()}}
        primary_q, _ = query_data[primary["sigma"]]
        group_cells = {}
        for sigma, (q, targets) in query_data.items():
            for mode in ([primary["mode"]] if development else p["descriptive"]["query_modes"]):
                observations = {name: statistics.observe(arm.scores(q, mode), targets, truth.families)
                    for name, arm in {"RAW_SIGNED_NN": raw_arm, "VECTOR_AGGREGATE": aggregate_arm}.items()}
                group_cells[(sigma, mode)] = {"r": shared, "sigma": sigma, "mode": mode,
                    "targets_evaluator_only": targets.tolist(), "arms": observations}
        all_cost_arms = {"RAW_SIGNED_NN": raw_arm, "VECTOR_AGGREGATE": aggregate_arm}
        for kind, (engine, arms, pos, detail, mapping, layout_ns, write_ns) in arranged.items():
            checks = layout_controls(arms, engine, primary_q, p["integrity"])
            offset = int(dataset.rng(namespace, "readout/association_permutation", permit).integers(1, len(corpus.ids)))
            permutation = np.roll(np.arange(len(corpus.ids)), offset)
            permuted = retrieval.FieldRetrieval(engine, hybrid=True, a=cfg["hybrid_a"], b=cfg["hybrid_b"], permutation=permutation)
            if kind == "SIMILARITY_PLACED":
                arms["ASSOCIATION_PERMUTED"] = permuted
            for (sigma, mode), cell in group_cells.items():
                q, targets = query_data[sigma]
                values = {name: arm.scores(q, mode) for name, arm in arms.items()}
                if kind == "SEPARATED":
                    invariant(np.allclose(values["FIELD_ONLY"], values["SIGNED_NN"]**2, atol=p["integrity"]["atol"], rtol=0), "Isolated field identity failed")
                    invariant(np.array_equal(retrieval.ranks(values["HYBRID"]), retrieval.ranks(values["SIGNED_NN"])), "Isolated hybrid rank identity failed")
                for name in ("SIGNED_NN", "ABSOLUTE_NN"):
                    obs = statistics.observe(values[name], targets, truth.families)
                    if name in cell["arms"]:
                        invariant(obs == cell["arms"][name], "NN depends on layout")
                    cell["arms"][name] = obs
                for name in ("HYBRID", "FIELD_ONLY", "ASSOCIATION_PERMUTED"):
                    if name in values:
                        cell["arms"][kind+"/"+name] = statistics.observe(values[name], targets, truth.families)
            pats = np.stack(list(engine.hme._patterns.values()))
            geometry = placement.geometry(pos, processed, pats, engine.hme.field, truth.families)
            layouts.append({"r": shared, "layout": kind, "positions": pos.tolist(), "assignment": detail,
                "external_to_artifact": mapping, "geometry": geometry, "controls": checks,
                "field_sha256": dataset.array_hash(engine.hme.field), "reconstruction": reconstruction(engine),
                "placement_ns": layout_ns, "writer_and_snapshot_build_ns": write_ns,
                "construction_costs": engine.mo_construction_costs,
                "writer_build_state": costs.persistent_size(engine), "association_permutation": permutation.tolist()})
            if shared == primary["r"] and kind in LAYOUTS[:3]:
                all_cost_arms.update({kind+"/"+name: arms[name] for name in ("HYBRID", "FIELD_ONLY")})
                if kind == "SIMILARITY_PLACED":
                    all_cost_arms.update({name: arms[name] for name in ("SIGNED_NN", "ABSOLUTE_NN")})
        if shared == primary["r"]:
            primary_scores = {name: x["metrics"] for name, x in group_cells[(primary["sigma"], primary["mode"])]["arms"].items()}
            costs_result = costs.measure(all_cost_arms, primary_q, p["costs"])
            costs_result["vector_graph_build_ns"] = graph_build_ns
            costs_result["within_cap"] = all(s["persistent_bytes"] <= p["integrity"]["persistent_bytes_cap"] for s in costs_result["storage"].values())
            invariant(costs_result["within_cap"], "Retained memory cap exceeded")
            # Canvas-only correctness: same relative arrangement and patch values.
            canvas_errors = {}
            for kind in LAYOUTS[:3]:
                _, small_arms, pos, *_ = arranged[kind]
                translation = (p["descriptive"]["larger_canvas"]-cfg["canvas"])//2
                _, translated, _ = retrieval.build(corpus, pos+translation, cfg, p["descriptive"]["larger_canvas"])
                for method in ("FIELD_ONLY", "HYBRID"):
                    a, b = small_arms[method].scores(primary_q, primary["mode"]), translated[method].scores(primary_q, primary["mode"])
                    err = float(np.max(np.abs(a-b)))
                    invariant(err <= p["integrity"]["atol"] and np.array_equal(retrieval.ranks(a), retrieval.ranks(b)), "Canvas-only invariance failed")
                    canvas_errors[kind+"/"+method] = err
            large_engine, large_arms, large_pos, large_detail, large_placement_ns = larger
            _, targets = query_data[primary["sigma"]]
            large_metrics = {name: statistics.observe(arm.scores(primary_q, primary["mode"]), targets, truth.families)
                             for name, arm in large_arms.items()}
            large_cost = costs.measure({"RAW_SIGNED_NN": raw_arm, **large_arms}, primary_q, p["costs"])
            invariant(all(s["persistent_bytes"] <= p["integrity"]["persistent_bytes_cap"] for s in large_cost["storage"].values()), "512 cap exceeded")
            large_result = {"canvas_only_max_errors": canvas_errors, "canvas": p["descriptive"]["larger_canvas"],
                "spacing": p["descriptive"]["larger_spacing"], "assignment": large_detail, "positions": large_pos.tolist(),
                "geometry": placement.geometry(large_pos, processed, np.stack(list(large_engine.hme._patterns.values())), large_engine.hme.field, truth.families),
                "arms": large_metrics, "costs": large_cost, "placement_ns": large_placement_ns}
        cells.extend(group_cells.values())
    primary_layouts = {v["layout"]: v for v in layouts if v["r"] == primary["r"]}
    achieved_delta = primary_layouts["SIMILARITY_PLACED"]["assignment"]["objective"]-primary_layouts["RANDOM_MATCHED"]["assignment"]["objective"]
    return {"namespace": namespace, "cells": cells, "layouts": layouts, "primary": primary_scores,
            "data_hashes": data_hashes, "costs": costs_result, "larger_canvas": large_result,
            "placement_delta": achieved_delta, "placement_achieved": bool(achieved_delta > p["integrity"]["placement_delta_min"]),
            "integrity_passed": True}


def summarize(runs, p, phase):
    deltas = statistics.paired_deltas([r["primary"] for r in runs])
    analysis = statistics.decision(deltas, p["statistics"],
        integrity=all(r["integrity_passed"] for r in runs),
        placement_achieved=all(r["placement_achieved"] for r in runs))
    return {"phase": phase, "status": "DEVELOPMENT_OBSERVATIONS" if phase != "confirmatory" else "REGISTERED_EVALUATION",
        "analysis": analysis, "primary_means": {name: {metric: float(np.mean([r["primary"][name][metric] for r in runs]))
            for metric in runs[0]["primary"][name]} for name in runs[0]["primary"]},
        "planning_for_50": {"paired_sd": np.std(deltas, axis=0, ddof=1).tolist(),
            "approx_bonferroni_halfwidth": (2.394*np.std(deltas, axis=0, ddof=1)/np.sqrt(50)).tolist(),
            "note": "Validation-only normal approximation for precision; not a power guarantee or a test result."},
        "all_integrity_passed": all(r["integrity_passed"] for r in runs),
        "all_placement_achieved": all(r["placement_achieved"] for r in runs)}


def run(phase, output, registration_commit=None, approval=None):
    p = config()
    out = Path(output)
    if out.exists():
        raise FileExistsError("Refusing existing output directory")
    out.mkdir(parents=True)
    runs, failures = [], []
    try:
        integrity.verify_imports()
        permit, registration = None, None
        if phase == "confirmatory":
            permit, registration = integrity.verify_registration(registration_commit, approval)
        phase_split = {"development": "development", "tune": "validation_tune",
                       "validation": "validation_check", "confirmatory": "reserved_test"}[phase]
        count = 2 if phase == "development" else p["namespaces"][phase_split]
        if phase in ("validation", "confirmatory"):
            frozen = json.loads((HERE/"FROZEN_BASELINE.json").read_text())
            invariant(frozen["status"] == "FROZEN_AFTER_VALIDATION_TUNING", "Baseline not frozen")
            rule = frozen["rule"]
        else:
            rule = {"representation": "raw", "k": 4, "lambda": 0.0}
        write_json(out/"RUN_MANIFEST.json", {"phase": phase, "started_utc": datetime.now(timezone.utc).isoformat(),
            "source_sha256": integrity.source_hashes(), "head": integrity.git("rev-parse", "HEAD"),
            "worktree_status": integrity.git("status", "--porcelain"), "registration": registration,
            "protocol": p, "baseline_rule": rule, "python": platform.python_version(), "numpy": np.__version__,
            "platform": platform.platform(), "machine": platform.machine(), "processor": platform.processor(),
            "threads": THREADS, "planned_namespaces": [f"HME-MO-1/{phase_split}/{i:03d}" for i in range(count)]})
        for index in range(count):
            namespace = f"HME-MO-1/{phase_split}/{index:03d}"
            try:
                value = tune_one(namespace, p) if phase == "tune" else one_corpus(namespace, p, rule, phase == "development", permit)
                write_gzip(out/f"corpus_{index:03d}.json.gz", value)
                runs.append(value)
                print(f"completed {namespace}", flush=True)
            except Exception as exc:
                failure = {"namespace": namespace, "error": repr(exc), "traceback": traceback.format_exc()}
                failures.append(failure)
                write_json(out/f"FAILURE_{index:03d}.json", failure)
                print(f"FAILED {namespace}: {exc}", flush=True)
        if failures:
            raise RuntimeError(f"{len(failures)} corpus failures; no seed replacement or partial analysis")
        result = select_baseline(runs, p) if phase == "tune" else summarize(runs, p, phase)
        write_json(out/("FROZEN_BASELINE.json" if phase == "tune" else "summary.json"), result)
        write_json(out/"COMPLETION.json", {"completed_utc": datetime.now(timezone.utc).isoformat(),
            "completed_corpora": len(runs), "failures": failures,
            "peak_process_rss_bytes": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*1024,
            "rss_scope": "Linux whole runner high-water mark including evaluator arrays, build states, output accumulation and all arms; not per-arm retained bytes."})
        return result
    except Exception as exc:
        write_json(out/"FAILURE.json", {"phase": phase, "error": repr(exc), "traceback": traceback.format_exc(),
                   "completed_corpora": len(runs), "failures": failures})
        raise


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("phase", choices=("development", "tune", "validation", "confirmatory"))
    parser.add_argument("--output", required=True)
    parser.add_argument("--registration-commit")
    parser.add_argument("--approval")
    args = parser.parse_args()
    run(args.phase, args.output, args.registration_commit, args.approval)


if __name__ == "__main__":
    main()
