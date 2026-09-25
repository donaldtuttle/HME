"""Matched semantic inputs with a full-dimensional NN safeguard."""
from __future__ import annotations

import numpy as np

from hme_engine import HMEConfig, HMEEngine
from experiments.field_retrieval_v1.retrieval import FieldRetrieval, unit_rows


ARMS = ("summary_recent", "nn_full", "nn_projected", "hme_hybrid")


def word_count(text):
    return len(text.split())


def pack(messages, order, budget):
    """Complete messages only. Same deterministic cap and ordering in all arms."""
    selected, used = [], 0
    for index in order:
        record = messages[int(index)]
        cost = word_count(record.render())
        if used + cost <= budget:
            selected.append(record)
            used += cost
    # Show chronological order to every reader after choosing candidates.
    return sorted(selected, key=lambda m: m.sequence)


class RetrievalMemory:
    def __init__(self, messages, embeddings, cfg, seed):
        self.messages = messages
        raw = np.asarray(embeddings, dtype=np.float64)
        if raw.ndim != 2 or len(raw) != len(messages) or not np.all(np.isfinite(raw)):
            raise ValueError("Embeddings must match the message ledger")
        if np.any(np.linalg.norm(raw, axis=1) <= 1e-12):
            raise ValueError("Zero message embedding")
        self.full = unit_rows(raw).real
        d = cfg["projection_dimension"]
        rng = np.random.default_rng(cfg["projection_seed"])
        self.projection = rng.normal(size=(raw.shape[1], d)) / np.sqrt(d)
        projected = self.full @ self.projection
        if np.any(np.linalg.norm(projected, axis=1) <= 1e-12):
            raise ValueError("Degenerate shared projection")
        self.projected = unit_rows(projected).real
        side = cfg["field_size"]
        spacing = cfg["spacing"]
        rows, cols = cfg["grid_shape"]
        if len(messages) != rows * cols or max(rows, cols) * spacing + d > side:
            raise ValueError("Registered layout cannot contain the ledger")
        positions = [(d // 2 + r * spacing, d // 2 + c * spacing)
                     for r in range(rows) for c in range(cols)]
        order = np.random.default_rng(np.random.SeedSequence([seed, 17])).permutation(len(messages))
        engine = HMEEngine(hme_config=HMEConfig(memory_size=side, encoding_resolution=d,
                           max_records=len(messages), use_hann_window=False))
        for i, message in enumerate(messages):
            engine.encode_memory(self.projected[i], positions[int(order[i])], tag=message.id,
                                 t=message.sequence, metadata={"message": message.text})
        self.hybrid = FieldRetrieval(engine, hybrid=True, a=cfg["a"], b=cfg["b"])
        self.hybrid.prepare_cache()
        self.cfg = cfg

    def rank(self, query):
        raw = np.asarray(query, dtype=np.float64).reshape(1, -1)
        if raw.shape[1] != self.full.shape[1] or not np.all(np.isfinite(raw)) or np.linalg.norm(raw) <= 1e-12:
            raise ValueError("Invalid query embedding")
        q = unit_rows(raw).real
        projected_raw = q @ self.projection
        if np.linalg.norm(projected_raw) <= 1e-12:
            raise ValueError("Degenerate projected query")
        projected = unit_rows(projected_raw).real
        scores = {"nn_full": (q @ self.full.T)[0],
                  "nn_projected": (projected @ self.projected.T)[0],
                  "hme_hybrid": self.hybrid.scores(projected)[0]}
        return {arm: {"order": np.argsort(-value, kind="stable").tolist(),
                      "scores": value.tolist()} for arm, value in scores.items()}

    def numeric_bytes(self):
        # Shared corpus text and Python overhead are excluded explicitly. These
        # are separate conceptual arm snapshots, not this harness's peak RSS.
        projection = self.projection.nbytes
        return {"nn_full": self.full.nbytes,
                "nn_projected": self.projected.nbytes + projection,
                "hme_hybrid": projection + self.hybrid.vectors.nbytes +
                              self.hybrid._field.nbytes + self.hybrid._cache.nbytes}
