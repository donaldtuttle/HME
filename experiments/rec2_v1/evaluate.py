"""HME-REC-2: frozen, remote-gated aligned-bank and shift-pool study."""
from __future__ import annotations

import os
for _name in ("OPENBLAS_NUM_THREADS", "OMP_NUM_THREADS", "MKL_NUM_THREADS"):
    os.environ[_name] = "1"

import argparse
from datetime import datetime, timezone
import gzip
import hashlib
import json
from pathlib import Path
import platform
import re
import subprocess
import sys
import time
import traceback
import urllib.request

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from hme_engine import HMEConfig, HMEEngine
from experiments.sign_ablation_v1.signed_variant import signed_module

HERE = Path(__file__).resolve().parent
P = json.loads((HERE / "protocol.json").read_text())
FROZEN = (
    "hme_engine.py",
    "experiments/sign_ablation_v1/signed_variant.py",
    "experiments/rec2_v1/protocol.json",
    "experiments/rec2_v1/PROTOCOL.md",
    "experiments/rec2_v1/evaluate.py",
    "tests/test_rec2.py",
    ".github/workflows/rec2-study.yml",
)
ORIGINS = (
    "https://github.com/donaldtuttle/HME.git",
    "https://github.com/donaldtuttle/HME",
    "git@github.com:donaldtuttle/HME.git",
)


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def array_hash(a: np.ndarray) -> str:
    a = np.ascontiguousarray(a)
    return sha(str(a.dtype).encode() + str(a.shape).encode() + a.tobytes())


def git(*args: str) -> str:
    return subprocess.check_output(
        ["git", *args], cwd=ROOT, text=True, stderr=subprocess.PIPE
    ).strip()


def verify_registration(commit: str, runner=git) -> dict:
    """Fresh canonical remote visibility, local ancestry, and exact source freeze."""
    if not re.fullmatch(r"[0-9a-f]{40}", commit):
        raise ValueError("Use a full immutable registration SHA")
    if P["development_seed"] in P["seeds"]:
        raise RuntimeError("Development seed leaked into the registered list")
    runner("merge-base", "--is-ancestor", commit, "HEAD")
    hashes = {}
    for path in FROZEN:
        frozen = runner("show", f"{commit}:{path}")
        actual = (ROOT / path).read_text(encoding="utf-8")
        if frozen != actual.strip():
            raise RuntimeError(f"Frozen file differs: {path}")
        hashes[path] = sha((ROOT / path).read_bytes())
        if runner("rev-parse", f"{commit}:{path}") != runner("hash-object", path):
            raise RuntimeError(f"Frozen file bytes differ: {path}")
    origin = runner("remote", "get-url", "origin")
    if origin not in ORIGINS:
        raise RuntimeError("origin must be the canonical donaldtuttle/HME repository")
    runner("fetch", "--no-tags", "--prune", "origin", "+refs/heads/*:refs/remotes/origin/*")
    refs = runner(
        "for-each-ref", "--contains", commit,
        "--format=%(refname) %(objectname)", "refs/remotes/origin/",
    )
    containing = [
        line for line in refs.splitlines()
        if line.startswith("refs/remotes/origin/")
        and not line.startswith("refs/remotes/origin/HEAD ")
    ]
    if not containing:
        raise RuntimeError("Registration is not contained in a freshly fetched origin branch")
    return {
        "commit": commit,
        "origin": origin,
        "containing_remote_refs": containing,
        "verified_at_utc": datetime.now(timezone.utc).isoformat(),
        "frozen_sha256": hashes,
    }


def server_run_record() -> dict | None:
    run_id = os.environ.get("GITHUB_RUN_ID")
    if not run_id:
        return None
    url = f"https://api.github.com/repos/donaldtuttle/HME/actions/runs/{int(run_id)}"
    headers = {"Accept": "application/vnd.github+json", "User-Agent": "HME-REC-2"}
    token = os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN")
    if token:
        headers["Authorization"] = f"Bearer {token}"
    with urllib.request.urlopen(urllib.request.Request(url, headers=headers), timeout=30) as response:
        record = json.load(response)
        server_date = response.headers.get("Date")
    return {
        **{key: record[key] for key in (
            "id", "head_sha", "event", "created_at", "run_started_at", "html_url")},
        "server_response_date": server_date,
    }


def geometry():
    d = int(P["dimension"])
    sites = int(P["sites"])
    half = d // 2
    memory = sites * d
    centers = [(k * d + half, half) for k in range(sites)]
    return memory, centers


def normalize_rows(x: np.ndarray) -> np.ndarray:
    return x / np.linalg.norm(x, axis=1)[:, None]


def site_split(seed: int, site: int) -> tuple[np.ndarray, np.ndarray]:
    """Development seed is allowed. Registered seeds are for the official run only."""
    d = int(P["dimension"])
    rank = int(P["latent_rank"])
    n = int(P["train_per_site"])
    q = int(P["queries_per_site"])
    rng = np.random.default_rng(np.random.SeedSequence([int(seed), int(site), 11]))
    basis = np.linalg.qr(rng.standard_normal((d, d)))[0][:, :rank]
    z = rng.standard_normal((n + q, rank))
    noise = rng.standard_normal((n + q, d))
    x = z @ basis.T / np.sqrt(rank) + P["residual_sigma"] * noise / np.sqrt(d)
    x = normalize_rows(x)
    return x[:n].copy(), x[n:].copy()


def observations(targets: np.ndarray, seed: int, site: int, sigma: float):
    d = targets.shape[1]
    count = int(d * P["observed_fraction"])
    rng = np.random.default_rng(np.random.SeedSequence(
        [int(seed), int(site), int(sigma * 100), 2]))
    masks = np.zeros(targets.shape, dtype=bool)
    for mask in masks:
        mask[rng.choice(d, count, replace=False)] = True
    noisy = targets + sigma / np.sqrt(d) * rng.standard_normal(targets.shape)
    return np.where(masks, noisy, np.nan), masks


def build_banks(seed: int):
    memory, centers = geometry()
    d = int(P["dimension"])
    trains, tests = [], []
    engine = HMEEngine(hme_config=HMEConfig(
        memory_size=memory,
        encoding_resolution=d,
        use_hann_window=False,
        normalize_patterns=True,
        field_decay=0.0,
        max_records=int(P["sites"]) * int(P["train_per_site"]),
    ))
    for site in range(int(P["sites"])):
        train, test = site_split(seed, site)
        trains.append(train)
        tests.append(test)
        for i, vector in enumerate(train):
            engine.encode_memory(
                vector, centers[site], strength=1.0,
                tag=f"rec2:{seed}:{site}:{i}", metadata={"site": site, "index": i},
            )
    return trains, tests, engine, centers


def block_moment(field: np.ndarray, center: tuple[int, int], count: int) -> np.ndarray:
    d = int(P["dimension"])
    half = d // 2
    r0, c0 = center[0] - half, center[1] - half
    patch = np.asarray(field)[r0:r0 + d, c0:c0 + d]
    if patch.shape != (d, d):
        raise ValueError("Block was clipped by the grid")
    moment = patch[:, (-np.arange(d)) % d] / count
    if np.max(np.abs(moment.imag)) > 1e-10:
        raise ValueError("Aligned-bank study supports real signals only")
    return moment.real.copy()


def direct_moment(vectors: np.ndarray) -> np.ndarray:
    return vectors.T @ vectors / len(vectors)


def reconstruct(moment: np.ndarray, y: np.ndarray, mask: np.ndarray) -> np.ndarray:
    y = np.asarray(y, dtype=float)
    mask = np.asarray(mask)
    if y.ndim != 1 or mask.shape != y.shape or mask.dtype != np.bool_:
        raise ValueError("Expected a vector and an equal-shaped Boolean mask")
    if not 0 < int(np.sum(mask)) < len(y) or not np.all(np.isfinite(y[mask])):
        raise ValueError("Require finite observations and both observed and missing coordinates")
    out = np.zeros(len(y))
    out[mask] = y[mask]
    missing = ~mask
    lam = P["ridge_fraction"] * float(np.trace(moment)) / len(y)
    gram = moment[np.ix_(mask, mask)] + lam * np.eye(int(np.sum(mask)))
    out[missing] = moment[np.ix_(missing, mask)] @ np.linalg.solve(gram, y[mask])
    if not np.all(np.isfinite(out)):
        raise FloatingPointError("Non-finite reconstruction")
    return out


def fit_oracle_ppca(vectors: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Rank is the generator rank and is an oracle. Covariance uses / n."""
    rank = int(P["ppca_rank"])
    mu = vectors.mean(axis=0)
    centered = vectors - mu
    cov = centered.T @ centered / len(vectors)
    evals, evecs = np.linalg.eigh(cov)
    order = np.argsort(evals)[::-1]
    evals = np.clip(evals[order], 0.0, None)
    evecs = evecs[:, order]
    sigma2 = float(np.mean(evals[rank:])) if rank < len(evals) else 0.0
    scales = np.sqrt(np.clip(evals[:rank] - sigma2, 0.0, None))
    weights = evecs[:, :rank] * scales
    moment = weights @ weights.T + sigma2 * np.eye(vectors.shape[1])
    return mu, moment


def reconstruct_ppca(mu: np.ndarray, moment: np.ndarray, y: np.ndarray, mask: np.ndarray):
    out = np.array(mu, dtype=float, copy=True)
    out[mask] = y[mask]
    missing = ~mask
    gram = moment[np.ix_(mask, mask)]
    # The PPCA covariance is positive definite when discarded eigenvalues remain.
    # A singular observed block falls back to a least-squares solve and is counted.
    try:
        coef = np.linalg.solve(gram, y[mask] - mu[mask])
        singular = False
    except np.linalg.LinAlgError:
        coef = np.linalg.lstsq(gram, y[mask] - mu[mask], rcond=None)[0]
        singular = True
    out[missing] = mu[missing] + moment[np.ix_(missing, mask)] @ coef
    if not np.all(np.isfinite(out)):
        raise FloatingPointError("Non-finite PPCA reconstruction")
    return out, singular


def shift_sum(records: np.ndarray) -> np.ndarray:
    """Sum of zero-padded shifted outer products. Not the shipped J-pattern writer."""
    records = np.asarray(records, dtype=float)
    n, d = records.shape
    field = np.zeros((d, d))
    for x in records:
        for shift in range(-(d - 1), d):
            z = np.zeros(d)
            if shift >= 0:
                z[shift:] = x[:d - shift]
            else:
                z[:d + shift] = x[-shift:]
            field += np.outer(z, z)
    return field


def lag_sum(records: np.ndarray) -> np.ndarray:
    """Unnormalized aperiodic autocorrelation sum. x is zero outside the record."""
    records = np.asarray(records, dtype=float)
    d = records.shape[1]
    moment = np.zeros((d, d))
    for x in records:
        for m in range(d):
            for n in range(d):
                ell = n - m
                if ell >= 0:
                    moment[m, n] += float(np.dot(x[:d - ell], x[ell:]))
                else:
                    moment[m, n] += float(np.dot(x[-ell:], x[:d + ell]))
    return moment


def shift_records(seed: int) -> np.ndarray:
    d = int(P["shift_dimension"])
    n = int(P["shift_records"])
    rng = np.random.default_rng(np.random.SeedSequence([int(seed), 19]))
    return rng.standard_normal((n, d))


def check_shifts(seed: int) -> dict:
    records = shift_records(seed)
    pooled = shift_sum(records)
    lags = lag_sum(records)
    scale = records.shape[0] * records.shape[1]
    gap = float(np.max(np.abs(pooled - lags)))
    biased_gap = float(np.max(np.abs(pooled / scale - lags / scale)))
    # Toeplitz: every lag diagonal is constant.
    d = records.shape[1]
    toeplitz_gap = 0.0
    for ell in range(-(d - 1), d):
        diag = np.diag(pooled, k=ell)
        toeplitz_gap = max(toeplitz_gap, float(np.max(diag) - np.min(diag)))
    smallest = float(np.min(np.linalg.eigvalsh(pooled)))
    return {
        "seed": int(seed),
        "unnormalized_gap": gap,
        "biased_gap": biased_gap,
        "toeplitz_gap": toeplitz_gap,
        "min_eigenvalue": smallest,
        "records_hash": array_hash(records),
    }


def colocated_moment(field: np.ndarray, d: int, count: int, origin: int = 32) -> np.ndarray:
    start = origin - d // 2
    patch = np.asarray(field)[start:start + d, start:start + d]
    moment = patch[:, (-np.arange(d)) % d] / count
    return moment.real.copy()


def identity_guardrail(seed: int, n: int | None = None, d: int | None = None) -> dict:
    n = int(P["identity_items"] if n is None else n)
    d = int(P["identity_dimension"] if d is None else d)
    rng = np.random.default_rng(np.random.SeedSequence([int(seed), 3]))
    vectors = rng.standard_normal((n, d))
    queries = vectors + rng.standard_normal((n, d))
    mod = signed_module()
    engine = mod.HMEEngine(hme_config=mod.HMEConfig(
        memory_size=64, encoding_resolution=d, use_hann_window=False, max_records=n,
    ))
    for i, vector in enumerate(vectors):
        engine.encode_memory(vector, (32, 32), strength=1.0, tag=f"rec2-id:{seed}:{i}")
    ids = list(engine.hme.records)
    lookup = {ident: i for i, ident in enumerate(ids)}

    def predictions():
        found = []
        for query in queries:
            hit = engine.retrieve_memory((32, 32), query=query, top_k=1).hits[0]
            found.append(lookup[hit.artifact_id])
        return found

    before = predictions()
    fingerprint = array_hash(engine.hme.field)
    probe_mask = np.arange(d) % 2 == 0
    probe = np.where(probe_mask, queries[0], np.nan)
    moment = colocated_moment(engine.hme.field, d, n)
    reconstruct(moment, probe, probe_mask)
    after = predictions()
    unchanged = before == after and fingerprint == array_hash(engine.hme.field)
    if not unchanged:
        raise AssertionError("Identity readout changed stored answers or field bytes")
    vnorm = np.linalg.norm(vectors, axis=1)
    nn = []
    for query in queries:
        qnorm = float(np.linalg.norm(query))
        nn.append(int(np.argmax(vectors @ query / (vnorm * qnorm))))
    expected = np.arange(n)
    return {
        "seed": int(seed),
        "hme_correct": int(np.sum(np.asarray(before) == expected)),
        "nn_correct": int(np.sum(np.asarray(nn) == expected)),
        "n": n,
        "unchanged": True,
        "vectors_hash": array_hash(vectors),
        "queries_hash": array_hash(queries),
    }


def interval(values) -> dict:
    values = np.asarray(values, dtype=float)
    rng = np.random.default_rng(P["bootstrap_seed"])
    draws = rng.integers(len(values), size=(int(P["bootstrap_draws"]), len(values)))
    means = values[draws].mean(axis=1)
    low, high = np.quantile(means, [0.025, 0.975])
    return {"mean": float(values.mean()), "ci95": [float(low), float(high)]}


def score_seed(seed: int, raw):
    trains, tests, engine, centers = build_banks(seed)
    count = int(P["train_per_site"])
    field_moments, direct_moments, ppca_models = [], [], []
    matrix_gap = 0.0
    for site, (train, center) in enumerate(zip(trains, centers)):
        got = block_moment(engine.hme.field, center, count)
        want = direct_moment(train)
        matrix_gap = max(matrix_gap, float(np.max(np.abs(got - want))))
        field_moments.append(got)
        direct_moments.append(want)
        ppca_models.append(fit_oracle_ppca(train))
    cells = []
    singular = 0
    primary_queries = None
    for sigma in P["noise_sigmas"]:
        coord_gap = 0.0
        sse = {"field_ridge": 0.0, "direct_moment": 0.0, "oracle_ppca": 0.0}
        energy = 0.0
        packed = []
        for site, test in enumerate(tests):
            ys, masks = observations(test, seed, site, float(sigma))
            for i, (y, mask) in enumerate(zip(ys, masks)):
                field_hat = reconstruct(field_moments[site], y, mask)
                direct_hat = reconstruct(direct_moments[site], y, mask)
                ppca_hat, was_singular = reconstruct_ppca(*ppca_models[site], y, mask)
                singular += int(was_singular)
                coord_gap = max(coord_gap, float(np.max(np.abs(field_hat - direct_hat))))
                hidden = ~mask
                energy += float(np.sum(test[i, hidden] ** 2))
                for name, hat in (
                    ("field_ridge", field_hat),
                    ("direct_moment", direct_hat),
                    ("oracle_ppca", ppca_hat),
                ):
                    sse[name] += float(np.sum((hat[hidden] - test[i, hidden]) ** 2))
                packed.append((y, mask, field_hat, direct_hat, ppca_hat, test[i]))
                if raw is not None:
                    raw.write(json.dumps({
                        "seed": int(seed), "site": site, "sigma": float(sigma), "query": i,
                        "observed_indices": np.flatnonzero(mask).tolist(),
                        "observations": y[mask].tolist(),
                        "target": test[i].tolist(),
                        "field_ridge": field_hat.tolist(),
                        "direct_moment": direct_hat.tolist(),
                        "oracle_ppca": ppca_hat.tolist(),
                    }, separators=(",", ":"), allow_nan=False) + "\n")
        if energy <= 0:
            raise RuntimeError("Hidden-coordinate energy was zero")
        cell = {
            "seed": int(seed),
            "sigma": float(sigma),
            "matrix_max_abs": matrix_gap,
            "coordinate_max_abs": coord_gap,
            "nmse": {name: sse[name] / energy for name in sse},
            "training_hash": array_hash(np.concatenate(trains)),
            "test_hash": array_hash(np.concatenate(tests)),
        }
        cells.append(cell)
        if float(sigma) == float(P["primary_sigma"]):
            primary_queries = packed
    if primary_queries is None:
        raise RuntimeError("Primary sigma produced no queries")
    timing = time_queries(field_moments, direct_moments, primary_queries)
    return cells, {
        "seed": int(seed),
        "matrix_max_abs": matrix_gap,
        "timing": timing,
        "ppca_singular_solves": singular,
        "bundle_bytes": {
            "field_ridge": int(engine.hme.field.nbytes + sum(
                np.asarray(v).nbytes for v in engine.hme._payloads.values()
            )),
            "direct_moment": int(sum(m.nbytes for m in direct_moments)),
            "allocated_field": int(engine.hme.field.nbytes),
            "active_patches": int(P["sites"] * P["dimension"] ** 2 * 16),
        },
        "full_bundle_bytes": _bundle_bytes(engine, direct_moments),
    }, check_shifts(seed)


def _bundle_bytes(engine, direct_moments) -> dict:
    """Array payloads only, plus a full object walk matching the REC-1 idea."""
    field_arrays = int(engine.hme.field.nbytes)
    field_arrays += int(sum(np.asarray(v).nbytes for v in engine.hme._payloads.values()))
    field_arrays += int(sum(np.asarray(v).nbytes for v in engine.hme._patterns.values()))
    direct_arrays = int(sum(m.nbytes for m in direct_moments))
    return {
        "field_array_bytes": field_arrays,
        "direct_array_bytes": direct_arrays,
        "field_object_bytes": _object_bytes(engine),
        "direct_object_bytes": _object_bytes(direct_moments),
    }


def _object_bytes(value) -> int:
    seen = set()

    def walk(item):
        if id(item) in seen:
            return 0
        seen.add(id(item))
        total = sys.getsizeof(item)
        if isinstance(item, np.ndarray):
            return total + (walk(item.base) if item.base is not None else 0)
        if isinstance(item, dict):
            return total + sum(walk(k) + walk(v) for k, v in item.items())
        if isinstance(item, (list, tuple, set)):
            return total + sum(walk(v) for v in item)
        if hasattr(item, "__dict__") and not isinstance(item, type):
            return total + walk(vars(item))
        return total

    return int(walk(value))


def time_queries(field_moments, direct_moments, packed) -> dict:
    arms = ("field_ridge", "direct_moment")

    def once(arm, item):
        y, mask = item[0], item[1]
        # The site is recovered from which moment we were going to use: items are
        # grouped, so the caller passes (moment_index) as item[6] if present.
        site = item[6]
        moment = field_moments[site] if arm == "field_ridge" else direct_moments[site]
        reconstruct(moment, y, mask)

    # Repack with site index. score_seed stored site-major order.
    per_site = int(P["queries_per_site"])
    items = []
    for i, item in enumerate(packed):
        items.append((*item, i // per_site))
    for arm in arms:
        for i in range(int(P["timing_warmups"])):
            once(arm, items[i % len(items)])
    samples = {arm: [] for arm in arms}
    for repeat in range(int(P["timing_repeats"])):
        for i, item in enumerate(items):
            order = arms[(i + repeat) % 2:] + arms[:(i + repeat) % 2]
            for arm in order:
                start = time.perf_counter_ns()
                once(arm, item)
                samples[arm].append(time.perf_counter_ns() - start)
    return {
        arm: {
            "median_ns": float(np.median(samples[arm])),
            "p95_ns": float(np.quantile(samples[arm], 0.95)),
        }
        for arm in arms
    }


def summarize(cells, costs, shifts, guards) -> dict:
    expected = {(seed, float(sigma)) for seed in P["seeds"] for sigma in P["noise_sigmas"]}
    found = {(c["seed"], float(c["sigma"])) for c in cells}
    if found != expected:
        raise ValueError("Missing or duplicate registered cells")
    if [c["seed"] for c in costs] != list(P["seeds"]):
        raise ValueError("Cost rows are not one per seed in order")
    identity_ok = all(
        c["matrix_max_abs"] <= P["matrix_abs_tolerance"]
        and c["coordinate_max_abs"] <= P["coordinate_abs_tolerance"]
        for c in cells
    )
    shift_ok = all(
        s["biased_gap"] <= P["shift_abs_tolerance"]
        and s["toeplitz_gap"] <= P["shift_abs_tolerance"]
        and s["min_eigenvalue"] >= -1e-8
        for s in shifts
    )
    ident = interval([
        100.0 * (g["hme_correct"] - g["nn_correct"]) / g["n"] for g in guards
    ])
    identity_path_ok = (
        ident["ci95"][0] > -P["identity_noninferiority_margin_pp"]
        and all(g["unchanged"] for g in guards)
    )
    p95 = np.array([c["timing"]["field_ridge"]["p95_ns"] for c in costs])
    cost_ok = (
        all(c["full_bundle_bytes"]["field_object_bytes"] <= P["memory_cap_bytes"] for c in costs)
        and float(np.median(p95)) <= P["max_primary_p95_latency_ns"]
    )
    primary_cells = [c for c in cells if float(c["sigma"]) == float(P["primary_sigma"])]
    primary_cells.sort(key=lambda c: c["seed"])
    ratios = np.array([
        c["timing"]["field_ridge"]["median_ns"] / c["timing"]["direct_moment"]["median_ns"]
        for c in costs
    ])
    byte_ratios = np.array([
        c["full_bundle_bytes"]["field_object_bytes"] / c["full_bundle_bytes"]["direct_object_bytes"]
        for c in costs
    ])
    nmse_gap = np.array([
        c["nmse"]["direct_moment"] - c["nmse"]["oracle_ppca"] for c in primary_cells
    ])
    gates = {
        "primary_identity": bool(identity_ok),
        "shift_control": bool(shift_ok),
        "identity_path": bool(identity_path_ok),
        "cost": bool(cost_ok),
    }
    gates["overall"] = all(gates.values())
    return {
        "gates": gates,
        "worst_matrix_abs": max(c["matrix_max_abs"] for c in cells),
        "worst_coordinate_abs": max(c["coordinate_max_abs"] for c in cells),
        "worst_shift_gap": max(s["biased_gap"] for s in shifts),
        "primary_mean_nmse": {
            arm: float(np.mean([c["nmse"][arm] for c in primary_cells]))
            for arm in ("field_ridge", "direct_moment", "oracle_ppca")
        },
        "ppca_minus_direct_nmse": interval(-nmse_gap),
        "identity_delta_pp": ident,
        "latency_ratio_field_over_direct": interval(ratios),
        "object_byte_ratio_field_over_direct": interval(byte_ratios),
        "median_field_p95_ns": float(np.median(p95)),
        "median_bundle_object_bytes": {
            "field_ridge": float(np.median([c["full_bundle_bytes"]["field_object_bytes"] for c in costs])),
            "direct_moment": float(np.median([c["full_bundle_bytes"]["direct_object_bytes"] for c in costs])),
        },
        "median_array_bytes": {
            "field_arrays": float(np.median([c["full_bundle_bytes"]["field_array_bytes"] for c in costs])),
            "direct_arrays": float(np.median([c["full_bundle_bytes"]["direct_array_bytes"] for c in costs])),
            "allocated_field": float(np.median([c["bundle_bytes"]["allocated_field"] for c in costs])),
            "active_patches": float(np.median([c["bundle_bytes"]["active_patches"] for c in costs])),
        },
    }


def report(result: dict) -> str:
    s = result["summary"]
    g = s["gates"]
    lines = [
        "# HME-REC-2: aligned banks and full-shift pooling",
        "",
        f"Registration: `{result['registration']['commit']}`.",
        "",
        "30 seeds. Four disjoint length-8 blocks. 32 training vectors and 16 held-out",
        "vectors per block. Primary cell: random 50% observed, sigma 0.1.",
        "Every arm was given the true block number. This is matched routing.",
        "",
        "The primary comparison is whether the unchanged engine matches ordinary",
        "per-block matrices. It is not a contest the field can win on accuracy.",
        "",
        "| Check | Result |",
        "|---|---|",
        f"| Matrices agree within 1e-10 | {g['primary_identity']} |",
        f"| Reconstructions agree within 1e-8 | {g['primary_identity']} |",
        f"| Shift writer matches biased autocorrelation within 1e-10 | {g['shift_control']} |",
        f"| Old identity path stays within 1 point | {g['identity_path']} |",
        f"| Field bundle under 64 MiB and p95 under 20 ms | {g['cost']} |",
        f"| Overall | {g['overall']} |",
        "",
        f"Worst matrix gap: {s['worst_matrix_abs']:.3g}.",
        f"Worst reconstructed-coordinate gap: {s['worst_coordinate_abs']:.3g}.",
        f"Worst biased-autocorrelation gap: {s['worst_shift_gap']:.3g}.",
        "",
        "Primary missing-coordinate error, lower is better. Field and direct should match.",
        "PPCA uses the true rank and is descriptive only.",
        "",
        "| Arm | Primary mean NMSE |",
        "|---|---:|",
    ]
    for arm in ("field_ridge", "direct_moment", "oracle_ppca"):
        lines.append(f"| {arm} | {s['primary_mean_nmse'][arm]:.6f} |")
    ppca = s["ppca_minus_direct_nmse"]
    ident = s["identity_delta_pp"]
    ratio = s["latency_ratio_field_over_direct"]
    bytes_ratio = s["object_byte_ratio_field_over_direct"]
    lines += [
        "",
        f"Oracle PPCA minus direct NMSE: {ppca['mean']:.6f} "
        f"(95% interval [{ppca['ci95'][0]:.6f}, {ppca['ci95'][1]:.6f}]). Not a gate.",
        f"Signed identity path minus raw cosine: {ident['mean']:+.3f} percentage points "
        f"(95% interval [{ident['ci95'][0]:+.3f}, {ident['ci95'][1]:+.3f}]).",
        f"Median field query p95: {s['median_field_p95_ns'] / 1e6:.3f} ms.",
        f"Field/direct median-time ratio: {ratio['mean']:.3f} "
        f"(95% interval [{ratio['ci95'][0]:.3f}, {ratio['ci95'][1]:.3f}]).",
        f"Field/direct object-byte ratio: {bytes_ratio['mean']:.3f} "
        f"(95% interval [{bytes_ratio['ci95'][0]:.3f}, {bytes_ratio['ci95'][1]:.3f}]).",
        "",
        "| Store | Median object bytes |",
        "|---|---:|",
        f"| field bundle | {s['median_bundle_object_bytes']['field_ridge']:.0f} |",
        f"| direct matrices | {s['median_bundle_object_bytes']['direct_moment']:.0f} |",
        "",
        f"Allocated field grid: {s['median_array_bytes']['allocated_field']:.0f} bytes.",
        f"Active complex patches: {s['median_array_bytes']['active_patches']:.0f} bytes.",
        f"Direct matrix arrays: {s['median_array_bytes']['direct_arrays']:.0f} bytes.",
        "",
        "A pass means the bookkeeping matches and the bundles fit the ceilings.",
        "It does not mean the field is more accurate, smaller, or faster than storing",
        "the matrices, and it does not say anything about unlabeled routing.",
        "The shift writer is experimental code in this study, not a change to the engine.",
        "",
        "No protocol deviations. Raw predictions are in raw_records.jsonl.gz.",
        "Fresh canonical-origin visibility was checked before the draws.",
        "That shows this protocol was public before this run, not that no private run existed.",
        "",
        "```bash",
        "OPENBLAS_NUM_THREADS=1 python experiments/rec2_v1/evaluate.py \\",
        f"  --registration-commit {result['registration']['commit']} \\",
        "  --output outputs/rec2_v1_reproduction",
        "```",
        "",
    ]
    return "\n".join(lines)


def run(commit: str, output: Path) -> None:
    if output.exists():
        raise FileExistsError("Use a fresh output directory")
    registration = verify_registration(commit)
    registration["github_run"] = server_run_record()
    output.mkdir(parents=True)
    (output / "registration.json").write_text(json.dumps(registration, indent=2) + "\n")
    cells, costs, shifts, guards = [], [], [], []
    try:
        with gzip.open(output / "raw_records.jsonl.gz", "wt", encoding="utf-8") as raw:
            for seed in P["seeds"]:
                seed_cells, cost, shift = score_seed(seed, raw)
                cells.extend(seed_cells)
                costs.append(cost)
                shifts.append(shift)
                guards.append(identity_guardrail(seed))
                print(f"Completed seed {seed}", flush=True)
        result = {
            "id": P["id"],
            "registration": registration,
            "protocol": P,
            "runtime": {
                "python": platform.python_version(),
                "numpy": np.__version__,
                "platform": platform.platform(),
            },
            "finished_at_utc": datetime.now(timezone.utc).isoformat(),
            "cells": cells,
            "costs": costs,
            "shifts": shifts,
            "identity": guards,
            "summary": summarize(cells, costs, shifts, guards),
        }
        (output / "results.json").write_text(json.dumps(result, indent=2, allow_nan=False) + "\n")
        (output / "REPORT.md").write_text(report(result))
        names = ("results.json", "REPORT.md", "registration.json", "raw_records.jsonl.gz")
        (output / "RESULTS.sha256").write_text(
            "".join(f"{sha((output / name).read_bytes())}  {name}\n" for name in names)
        )
    except Exception:
        (output / "FAILURE.json").write_text(json.dumps({
            "traceback": traceback.format_exc(),
            "completed_cells": len(cells),
            "completed_guardrails": len(guards),
        }, indent=2) + "\n")
        raise


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--registration-commit", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    run(args.registration_commit, args.output)
