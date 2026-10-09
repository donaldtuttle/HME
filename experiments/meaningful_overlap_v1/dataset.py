"""Numeric corpora and evaluator truth. No semantic string embeddings."""
from dataclasses import dataclass
import hashlib
import re

import numpy as np


@dataclass(frozen=True)
class Corpus:
    vectors: np.ndarray
    ids: tuple[str, ...]


@dataclass(frozen=True)
class Truth:
    families: np.ndarray


class _TestPermit:
    """Created by registration verification, not by CLI configuration."""
    def __init__(self, registration_commit):
        self.registration_commit = registration_commit


def check_namespace(namespace, permit=None):
    limits = {"development": 4, "validation_tune": 12,
              "validation_check": 12, "reserved_test": 50}
    match = re.fullmatch(r"HME-MO-1/(development|validation_tune|validation_check|reserved_test)/(\d{3})", namespace)
    if match is None or not 0 <= int(match[2]) < limits[match[1]]:
        raise ValueError("Unknown or out-of-plan corpus namespace")
    if match[1] == "reserved_test" and not isinstance(permit, _TestPermit):
        raise PermissionError("Reserved corpora require verified approval and registration")


def rng(namespace, stream, permit=None):
    check_namespace(namespace, permit)
    digest = hashlib.sha256(f"{namespace}/{stream}".encode()).digest()
    entropy = np.frombuffer(digest, dtype="<u4").tolist()
    return np.random.default_rng(np.random.SeedSequence(entropy))


def generate(namespace, cfg, r=0.5, permit=None):
    check_namespace(namespace, permit)
    if not 0 <= r <= 1:
        raise ValueError("Shared variance must lie in [0,1]")
    g, m, d = cfg["families"], cfg["members_per_family"], cfg["dimension"]
    if g * m != cfg["items"]:
        raise ValueError("Family sizes must match item count")
    # Independent streams, reused across r as a paired descriptive intervention.
    proto = rng(namespace, "prototypes", permit).standard_normal((g, d))
    residual = rng(namespace, "identity", permit).standard_normal((g*m, d))
    labels = np.repeat(np.arange(g), m)
    vectors = np.sqrt(r)*proto[labels] + np.sqrt(1-r)*residual
    ids_rng = rng(namespace, "opaque_ids", permit)
    ids = [ids_rng.bytes(16).hex() for _ in range(g*m)]
    order = rng(namespace, "insertion", permit).permutation(g*m)
    corpus = Corpus(vectors[order].copy(), tuple(ids[i] for i in order))
    return corpus, Truth(labels[order].copy())


def queries(namespace, corpus, sigma, repeats=4, permit=None):
    if not np.isfinite(sigma) or sigma < 0 or repeats < 1:
        raise ValueError("Invalid query condition")
    targets = np.repeat(np.arange(len(corpus.ids)), repeats)
    noise = rng(namespace, f"query_noise/{float(sigma).hex()}", permit).standard_normal(
        (len(targets), corpus.vectors.shape[1]))
    q = corpus.vectors[targets] + sigma*noise
    order = rng(namespace, f"query_order/{float(sigma).hex()}", permit).permutation(len(q))
    return q[order], targets[order]


def array_hash(value):
    x = np.ascontiguousarray(value)
    return hashlib.sha256(str(x.dtype).encode()+str(x.shape).encode()+x.tobytes()).hexdigest()
