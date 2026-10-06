"""Absolute retained/serialized costs and matched-output online latency."""
import io
import copy
import json
import time
import tracemalloc
from dataclasses import asdict, is_dataclass

import numpy as np
from experiments.nn_baseline_v1.evaluate import persistent_size


def serialized_size(arm):
    """Uncompressed arrays plus deterministic JSON metadata, not an engine export."""
    arrays = {}

    def encode(x, path="state"):
        if isinstance(x, np.ndarray):
            arrays[path] = x
            return {"array": path}
        if isinstance(x, np.generic):
            return x.item()
        if is_dataclass(x):
            return encode(asdict(x), path)
        if isinstance(x, dict):
            return {str(k): encode(v, path+"/"+str(k)) for k, v in x.items()}
        if isinstance(x, (list, tuple)):
            return [encode(v, path+f"/{i}") for i, v in enumerate(x)]
        if hasattr(x, "__dict__"):
            return encode(vars(x), path)
        return x

    metadata = json.dumps(encode(arm), sort_keys=True, separators=(",", ":")).encode()
    buf = io.BytesIO()
    np.savez(buf, **arrays)
    return {"npz_bytes": buf.tell(), "metadata_json_bytes": len(metadata),
            "serialized_total_bytes": buf.tell()+len(metadata)}


def storage(arm):
    component_arrays = {k: v.nbytes for k, v in vars(arm).items() if isinstance(v, np.ndarray)}
    return {**persistent_size(arm), **serialized_size(arm),
            "array_components_bytes": component_arrays,
            "metadata_and_python_overhead_bytes": persistent_size(arm)["persistent_bytes"]-persistent_size(arm)["numeric_array_bytes"]}


def measure(arms, q, cfg):
    variants = {name: (arm, {}) for name, arm in arms.items()}
    for name, arm in arms.items():
        if hasattr(arm, "field_scores"):
            uncached = copy.deepcopy(arm)
            uncached.invalidate_cache()
            variants[name+"/uncached"] = (uncached, {"cached": False})
    names = list(variants)
    cache = {}
    for name, arm in arms.items():
        if not hasattr(arm, "prepare_cache"):
            continue
        builds, invalidations = [], []
        for _ in range(cfg["cache_cycles"]):
            start = time.perf_counter_ns()
            arm.invalidate_cache()
            invalidations.append(time.perf_counter_ns()-start)
            start = time.perf_counter_ns()
            arm.prepare_cache()
            builds.append(time.perf_counter_ns()-start)
        cache[name] = {"build_median_ns": float(np.median(builds)),
                       "invalidate_median_ns": float(np.median(invalidations))}
    stored = {}
    for name, (arm, kwargs) in variants.items():
        if kwargs:
            arm.invalidate_cache()
        elif hasattr(arm, "prepare_cache"):
            arm.prepare_cache()
        stored[name] = storage(arm)
    for arm in arms.values():
        if hasattr(arm, "prepare_cache"):
            arm.prepare_cache()
    for arm, kwargs in variants.values():
        for query in q[:cfg["warmups"]]:
            arm.search(query, mode="symmetric", top_k=cfg["output_top_k"], **kwargs)
    samples = {name: [] for name in names}
    for repeat in range(cfg["repetitions"]):
        for index, query in enumerate(q[:cfg["query_count"]]):
            shift = (index+repeat) % len(names)
            for name in names[shift:]+names[:shift]:
                arm, kwargs = variants[name]
                start = time.perf_counter_ns()
                arm.search(query, mode="symmetric", top_k=cfg["output_top_k"], **kwargs)
                samples[name].append(time.perf_counter_ns()-start)
    latency = {name: {"median_ns": float(np.median(values)), "p95_ns": float(np.quantile(values, .95)),
                       "samples_ns": values} for name, values in samples.items()}
    baseline = latency["RAW_SIGNED_NN"]["median_ns"]
    for entry in latency.values():
        entry["median_ratio_to_raw_nn"] = entry["median_ns"]/baseline
    transient = {}
    # Separate instrumentation pass: these are not timed samples or peak RSS.
    for name, (arm, kwargs) in variants.items():
        tracemalloc.start()
        before, _ = tracemalloc.get_traced_memory()
        arm.search(q[0], mode="symmetric", top_k=cfg["output_top_k"], **kwargs)
        current, peak = tracemalloc.get_traced_memory()
        tracemalloc.stop()
        transient[name] = {"traced_peak_above_start_bytes": peak-before,
                           "traced_remaining_bytes": current-before}
    return {"storage": stored, "latency": latency, "cache": cache, "query_workspace": transient}
