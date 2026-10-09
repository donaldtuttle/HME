"""Frozen writer/readout adapters and conventional vector aggregation."""
import numpy as np
import time
from hme_engine import HMEConfig, HMEEngine, SalienceConfig
from experiments.field_retrieval_v1.retrieval import (
    ExactNN, FieldRetrieval, preprocess, patterns, unit_rows)


def ranks(scores):
    values = np.asarray(scores)
    if values.ndim != 2 or not np.all(np.isfinite(values)):
        raise ValueError("Expected a finite query-by-candidate score matrix")
    # Columns follow randomized insertion order, common across all layouts.
    return np.argsort(-values, axis=1, kind="stable")


class VectorAggregate:
    def __init__(self, corpus, rule):
        self.ids = list(corpus.ids)
        self.rule = dict(rule)
        if rule["representation"] not in ("raw", "processed") or not 0 <= rule["lambda"] <= 1:
            raise ValueError("Invalid aggregation rule")
        self.vectors = preprocess(corpus.vectors, "native" if rule["representation"] == "raw" else "symmetric")
        n = len(self.vectors)
        if not 1 <= rule["k"] < n:
            raise ValueError("Invalid neighbor count")
        similarities = (self.vectors.conj() @ self.vectors.T).real
        np.fill_diagonal(similarities, -np.inf)
        self.neighbors = ranks(np.where(np.isfinite(similarities), similarities, -2))[:, :rule["k"]].copy()
        positive = np.maximum(0, np.take_along_axis(similarities, self.neighbors, axis=1))
        totals = positive.sum(axis=1, keepdims=True)
        self.weights = np.divide(positive, totals, out=np.zeros_like(positive), where=totals > 1e-12)
        self.empty = totals[:, 0] <= 1e-12

    def scores(self, queries, mode="symmetric"):
        query_mode = "native" if self.rule["representation"] == "raw" else mode
        signed = (preprocess(queries, query_mode).conj() @ self.vectors.T).real
        neighbor = (signed[:, self.neighbors]*self.weights[None]).sum(axis=2)
        neighbor[:, self.empty] = signed[:, self.empty]
        lam = self.rule["lambda"]
        return (1-lam)*signed + lam*neighbor

    def search(self, query, mode="symmetric", top_k=5):
        values = self.scores(query, mode)[0]
        order = ranks(values[None])[0, :top_k]
        return order, values[order]


class RawNN:
    def __init__(self, corpus):
        self.ids = list(corpus.ids)
        self.vectors = unit_rows(corpus.vectors)

    def scores(self, queries, mode="symmetric"):
        return (preprocess(queries, "native").conj() @ self.vectors.T).real

    def search(self, query, mode="symmetric", top_k=5):
        values = self.scores(query, mode)[0]
        order = ranks(values[None])[0, :top_k]
        return order, values[order]


def build(corpus, positions, cfg, canvas=None):
    n, d = corpus.vectors.shape
    size = canvas or cfg["canvas"]
    pos = np.asarray(positions, dtype=np.int64)
    if pos.shape != (n, 2) or np.any(pos-d//2 < 0) or np.any(pos-d//2+d > size):
        raise ValueError("Clipping prohibited")
    engine = HMEEngine(hme_config=HMEConfig(memory_size=size, encoding_resolution=d,
        field_decay=0.0, max_records=n, use_hann_window=True, normalize_patterns=True),
        salience_config=SalienceConfig(influence_write_gain=False, influence_retrieval=False,
                                      enable_salience_rejection=False))
    mapping = {}
    write_start = time.perf_counter_ns()
    for tick, (vector, address, external_id) in enumerate(zip(corpus.vectors, pos, corpus.ids)):
        record = engine.encode_memory(vector, tuple(address), strength=cfg["write_strength"],
                                      write_weight=cfg["write_weight"], tag=external_id, t=tick)
        mapping[external_id] = record.artifact_id
    if len(engine.hme.records) != n or len(mapping) != n:
        raise RuntimeError("Eviction or duplicate external identity")
    write_ns = time.perf_counter_ns()-write_start
    snapshot_start = time.perf_counter_ns()
    args = {"a": cfg["hybrid_a"], "b": cfg["hybrid_b"]}
    arms = {"SIGNED_NN": ExactNN(engine), "ABSOLUTE_NN": ExactNN(engine, absolute=True),
            "FIELD_ONLY": FieldRetrieval(engine), "HYBRID": FieldRetrieval(engine, hybrid=True, **args)}
    # Artifact IDs remain available; external IDs only identify candidates, never families.
    for arm in arms.values():
        arm.external_ids = list(corpus.ids)
        arm.external_to_artifact = dict(mapping)
    engine.mo_construction_costs = {"insertion_ns": write_ns, "writes": n,
        "writes_per_second": n*1e9/write_ns,
        "snapshot_construction_ns": time.perf_counter_ns()-snapshot_start,
        "rewrite_throughput": "not measured; this experiment builds immutable search snapshots"}
    return engine, arms, mapping
