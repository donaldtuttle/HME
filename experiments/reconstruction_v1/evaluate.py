"""HME-REC-1: frozen, remote-gated partial-observation reconstruction study."""
from __future__ import annotations

import os
for _name in ("OPENBLAS_NUM_THREADS", "OMP_NUM_THREADS", "MKL_NUM_THREADS"):
    os.environ[_name] = "1"

import argparse
import copy
from dataclasses import fields, is_dataclass
from datetime import datetime, timezone
import gzip
import hashlib
import itertools
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
ARMS = ("nn_copy", "weighted_blend", "field_ridge", "direct_moment",
        "diagonal_field", "zero_fill")
FROZEN = ("hme_engine.py", "experiments/sign_ablation_v1/signed_variant.py",
          "experiments/reconstruction_v1/protocol.json",
          "experiments/reconstruction_v1/PROTOCOL.md",
          "experiments/reconstruction_v1/evaluate.py", "tests/test_reconstruction.py")
ORIGINS = ("https://github.com/donaldtuttle/HME.git", "https://github.com/donaldtuttle/HME",
           "git@github.com:donaldtuttle/HME.git")


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def array_hash(a: np.ndarray) -> str:
    a = np.ascontiguousarray(a)
    return sha(str(a.dtype).encode() + str(a.shape).encode() + a.tobytes())


def git(*args: str) -> str:
    return subprocess.check_output(["git", *args], cwd=ROOT, text=True,
                                   stderr=subprocess.PIPE).strip()


def verify_registration(commit: str, runner=git) -> dict:
    """Fresh canonical remote visibility, local ancestry, and exact source freeze."""
    if not re.fullmatch(r"[0-9a-f]{40}", commit):
        raise ValueError("Use a full immutable registration SHA")
    runner("merge-base", "--is-ancestor", commit, "HEAD")
    hashes = {}
    for path in FROZEN:
        frozen = runner("show", f"{commit}:{path}")
        # runner strips a final newline; compare without changing internal bytes.
        actual = (ROOT / path).read_text(encoding="utf-8")
        if frozen != actual.strip():
            raise RuntimeError(f"Frozen file differs: {path}")
        hashes[path] = sha((ROOT / path).read_bytes())
        # Git blob hashing supplies a second, byte-exact check including newlines.
        if runner("rev-parse", f"{commit}:{path}") != runner("hash-object", path):
            raise RuntimeError(f"Frozen file bytes differ: {path}")
    origin = runner("remote", "get-url", "origin")
    if origin not in ORIGINS:
        raise RuntimeError("origin must be the canonical donaldtuttle/HME repository")
    runner("fetch", "--no-tags", "--prune", "origin",
           "+refs/heads/*:refs/remotes/origin/*")
    refs = runner("for-each-ref", "--contains", commit,
                  "--format=%(refname) %(objectname)", "refs/remotes/origin/")
    containing = [line for line in refs.splitlines()
                  if line.startswith("refs/remotes/origin/")
                  and not line.startswith("refs/remotes/origin/HEAD ")]
    if not containing:
        raise RuntimeError("Registration is not contained in a freshly fetched origin branch")
    return {"commit": commit, "origin": origin, "containing_remote_refs": containing,
            "verified_at_utc": datetime.now(timezone.utc).isoformat(), "frozen_sha256": hashes}


def server_run_record() -> dict | None:
    """Retain GitHub's server timestamps for the official run, not commit dates."""
    run_id = os.environ.get("GITHUB_RUN_ID")
    if not run_id:
        return None
    url = f"https://api.github.com/repos/donaldtuttle/HME/actions/runs/{int(run_id)}"
    headers = {"Accept": "application/vnd.github+json", "User-Agent": "HME-REC-1"}
    token = os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN")
    if token:
        headers["Authorization"] = f"Bearer {token}"
    with urllib.request.urlopen(urllib.request.Request(url, headers=headers), timeout=30) as r:
        record = json.load(r)
        server_date = r.headers.get("Date")
    return {**{k: record[k] for k in ("id", "head_sha", "event", "created_at",
                                     "run_started_at", "html_url")},
            "server_response_date": server_date}


def dataset(seed: int, rank: int, n: int, q: int, d: int) -> tuple[np.ndarray, np.ndarray]:
    rng = np.random.default_rng(np.random.SeedSequence([seed, rank, 1]))
    basis = np.linalg.qr(rng.standard_normal((d, d)))[0][:, :rank]
    z = rng.standard_normal((n + q, rank))
    noise = rng.standard_normal((n + q, d))
    x = z @ basis.T / np.sqrt(rank) + P["residual_sigma"] * noise / np.sqrt(d)
    x /= np.linalg.norm(x, axis=1)[:, None]
    return x[:n].copy(), x[n:].copy()


def observations(targets, seed, rank, fraction, sigma, mask_type):
    d = targets.shape[1]
    rng = np.random.default_rng(np.random.SeedSequence(
        [seed, rank, int(fraction * 100), int(sigma * 100), int(mask_type == "block"), 2]))
    masks = np.zeros(targets.shape, dtype=bool)
    count = int(d * fraction)
    for mask in masks:
        idx = (rng.choice(d, count, replace=False) if mask_type == "random" else
               (rng.integers(d) + np.arange(count)) % d)
        mask[idx] = True
    noisy = targets + sigma / np.sqrt(d) * rng.standard_normal(targets.shape)
    return np.where(masks, noisy, np.nan), masks


def build_engine(vectors, *, signed=False):
    mod = signed_module() if signed else None
    cls = HMEEngine if mod is None else mod.HMEEngine
    cfg = HMEConfig if mod is None else mod.HMEConfig
    engine = cls(hme_config=cfg(memory_size=64, encoding_resolution=vectors.shape[1],
                              use_hann_window=False, max_records=len(vectors)))
    for i, v in enumerate(vectors):
        engine.encode_memory(v, (32, 32), strength=1., tag=f"rec1:{i}",
                             metadata={"index": i})
    return engine


def field_moment(field, dimension, count):
    """Recover the uncentered second moment from a co-located FFT-pattern field."""
    if count < 1 or dimension < 2 or field.ndim != 2:
        raise ValueError("Invalid field readout dimensions or write count")
    start = 32 - dimension // 2
    patch = field[start:start + dimension, start:start + dimension]
    if patch.shape != (dimension, dimension):
        raise ValueError("Field patch must be complete and unclipped")
    c = patch[:, (-np.arange(dimension)) % dimension] / count
    if np.max(np.abs(c.imag)) > 1e-12:
        raise ValueError("This reconstruction study supports real signals only")
    return c.real.copy()


def masked_cosine(vectors, y, mask):
    v, q = vectors[:, mask], y[mask]
    denom = np.linalg.norm(v, axis=1) * np.linalg.norm(q)
    return np.divide(v @ q, denom, out=np.zeros(len(vectors)), where=denom > 1e-12)


def reconstruct(arm, model, y, mask):
    """Use only revealed coordinates; never normalize by a hidden target norm."""
    y, mask = np.asarray(y), np.asarray(mask)
    if y.ndim != 1 or mask.shape != y.shape or mask.dtype != np.bool_:
        raise ValueError("Expected a vector and equal-shaped Boolean observation mask")
    if not 0 < np.sum(mask) < len(y) or not np.all(np.isfinite(y[mask])):
        raise ValueError("Require finite observations and both observed/missing coordinates")
    out = np.zeros(len(y))
    out[mask] = y[mask]
    missing = ~mask
    if arm in ("nn_copy", "weighted_blend"):
        scores = masked_cosine(model, y, mask)
        order = np.argsort(-scores, kind="stable")
        if arm == "nn_copy":
            out[missing] = model[order[0], missing]
        else:
            keep = order[:min(P["blend_k"], len(model))]
            w = np.exp((scores[keep] - scores[keep[0]]) / P["blend_temperature"])
            w /= w.sum()
            out[missing] = w @ model[keep][:, missing]
    elif arm in ("field_ridge", "direct_moment", "diagonal_field"):
        c = model if arm == "direct_moment" else field_moment(*model)
        if arm == "diagonal_field":
            c = np.diag(np.diag(c))
        lam = P["ridge_fraction"] * float(np.trace(c)) / len(y)
        if lam > 0:
            coo = c[np.ix_(mask, mask)] + lam * np.eye(np.sum(mask))
            out[missing] = c[np.ix_(missing, mask)] @ np.linalg.solve(coo, y[mask])
    elif arm != "zero_fill":
        raise ValueError(f"Unknown arm: {arm}")
    if not np.all(np.isfinite(out)):
        raise FloatingPointError("Non-finite reconstruction")
    return out


def persistent_bytes(value):
    """Reachable owned arrays and Python objects; no modules or query workspace."""
    seen = set()
    def walk(x):
        if id(x) in seen:
            return 0
        seen.add(id(x))
        total = sys.getsizeof(x)
        if isinstance(x, np.ndarray):
            return total + (walk(x.base) if x.base is not None else 0)
        if isinstance(x, dict):
            return total + sum(walk(k) + walk(v) for k, v in x.items())
        if isinstance(x, (list, tuple, set)):
            return total + sum(walk(v) for v in x)
        if is_dataclass(x) and not isinstance(x, type):
            return total + sum(walk(getattr(x, f.name)) for f in fields(x))
        if hasattr(x, "__dict__") and not isinstance(x, type):
            return total + walk(vars(x))
        return total
    return walk(value)


def prepare(vectors):
    begin = time.perf_counter_ns()
    engine = build_engine(vectors)
    hme_ns = time.perf_counter_ns() - begin
    begin = time.perf_counter_ns()
    provenance = copy.deepcopy({"records": [r.to_dict() for r in engine.hme.records.values()],
                               "lineage": engine.lineage.to_dict()})
    provenance_ns = time.perf_counter_ns() - begin
    begin = time.perf_counter_ns()
    ledger = vectors.copy()
    ledger_ns = time.perf_counter_ns() - begin
    begin = time.perf_counter_ns()
    c = vectors.T @ vectors / len(vectors)
    moment_ns = time.perf_counter_ns() - begin
    field = (engine.hme.field, vectors.shape[1], len(vectors))
    error = float(np.max(np.abs(field_moment(*field) - c)))
    if error > 1e-12:
        raise AssertionError("FFT/moment algebra failed")
    models = {"nn_copy": ledger, "weighted_blend": ledger, "field_ridge": field,
              "direct_moment": c, "diagonal_field": field, "zero_fill": None}
    bundles = {"nn_copy": (ledger, provenance), "weighted_blend": (ledger, provenance),
               "field_ridge": engine, "direct_moment": (c, ledger, provenance)}
    costs = {"build_ns": {"hme_engine": hme_ns, "provenance_copy": provenance_ns,
                          "ledger_copy": ledger_ns, "direct_moment": moment_ns},
             "bundle_bytes": {k: persistent_bytes(v) for k, v in bundles.items()},
             "compact_state_bytes": {k: persistent_bytes(v) for k, v in models.items()},
             "moment_max_error": error}
    return engine, models, costs


def cell(seed, rank, fraction, sigma, mask_type, targets, models, raw):
    ys, masks = observations(targets, seed, rank, fraction, sigma, mask_type)
    energy = np.sum(np.where(masks, 0, targets ** 2), axis=1)
    errors = {a: [] for a in ARMS}
    maximum = 0.
    for i, (y, mask) in enumerate(zip(ys, masks)):
        preds = {a: reconstruct(a, models[a], y, mask) for a in ARMS}
        err = float(np.max(np.abs(preds["field_ridge"] - preds["direct_moment"])))
        maximum = max(maximum, err)
        if err > 1e-10 or not np.array_equal(preds["diagonal_field"], preds["zero_fill"]):
            raise AssertionError("Readout/ablation control failed")
        for a in ARMS:
            errors[a].append(float(np.sum((preds[a][~mask] - targets[i, ~mask]) ** 2)))
        if raw is not None:
            raw.write(json.dumps({"seed":seed, "rank":rank, "fraction":fraction,
                "sigma":sigma, "mask_type":mask_type, "query":i,
                "observed_indices":np.flatnonzero(mask).tolist(),
                "observations":y[mask].tolist(), "target":targets[i].tolist(),
                "predictions":{a: v.tolist() for a, v in preds.items()},
                "hidden_energy":float(energy[i]), "sse":{a: errors[a][-1] for a in ARMS}},
                separators=(",", ":"), allow_nan=False) + "\n")
    return {"seed":seed, "rank":rank, "fraction":fraction, "sigma":sigma,
            "mask_type":mask_type, "nmse":{a:float(np.sum(e)/np.sum(energy)) for a,e in errors.items()},
            "target_hash":array_hash(targets), "observation_hash":array_hash(ys),
            "mask_hash":array_hash(masks), "field_direct_max_error":maximum}


def timing(models, ys, masks):
    samples = {a: [] for a in ARMS}
    for a in ARMS:
        for i in range(8):
            reconstruct(a, models[a], ys[i % len(ys)], masks[i % len(ys)])
    for repeat in range(P["timing_repeats"]):
        for i, (y, mask) in enumerate(zip(ys, masks)):
            shift = (i + repeat) % len(ARMS)
            for a in ARMS[shift:] + ARMS[:shift]:
                start = time.perf_counter_ns()
                reconstruct(a, models[a], y, mask)
                samples[a].append(time.perf_counter_ns() - start)
    return {a:{"ns":s, "median_ns":float(np.median(s)), "p95_ns":float(np.quantile(s,.95))}
            for a,s in samples.items()}


def identity_guardrail(seed, n=128, d=16):
    rng = np.random.default_rng(np.random.SeedSequence([seed, 3]))
    vectors = rng.standard_normal((n, d))
    queries = vectors + rng.standard_normal((n, d))
    e = build_engine(vectors, signed=True)
    ids = list(e.hme.records)
    lookup = {ident:i for i, ident in enumerate(ids)}
    def predictions():
        return [lookup[e.retrieve_memory((32,32), query=q, top_k=1).hits[0].artifact_id]
                for q in queries]
    before = predictions()
    fingerprint = array_hash(e.hme.field)
    for q in queries:
        mask = np.arange(d) % 2 == 0
        reconstruct("field_ridge", (e.hme.field,d,n), np.where(mask,q,np.nan), mask)
    after = predictions()
    if before != after or fingerprint != array_hash(e.hme.field):
        raise AssertionError("Reconstruction changed identity state")
    denom = np.linalg.norm(vectors,axis=1)
    nn = [int(np.argmax(vectors @ q / denom)) for q in queries]
    expected = np.arange(n)
    return {"seed":seed, "hme_predictions":before, "nn_predictions":nn,
            "hme_correct":int(np.sum(np.asarray(before)==expected)),
            "nn_correct":int(np.sum(np.asarray(nn)==expected)), "n":n,
            "unchanged":True, "vectors_hash":array_hash(vectors), "queries_hash":array_hash(queries)}


def interval(values):
    values = np.asarray(values, dtype=float)
    rng = np.random.default_rng(P["bootstrap_seed"])
    samples = values[rng.integers(len(values),size=(P["bootstrap_draws"],len(values)))].mean(axis=1)
    return {"mean":float(values.mean()), "ci95":np.quantile(samples,[.025,.975]).tolist()}


def summarize(cells, costs, guards):
    expected = set(itertools.product(P["seeds"],P["ranks"],P["observed_fractions"],
                                      P["noise_sigmas"],P["mask_types"]))
    found = [(c["seed"],c["rank"],c["fraction"],c["sigma"],c["mask_type"]) for c in cells]
    if set(found) != expected or len(found) != len(expected):
        raise ValueError("Missing or duplicate registered cells")
    if sorted(c["seed"] for c in costs) != P["seeds"] or sorted(g["seed"] for g in guards)!=P["seeds"]:
        raise ValueError("Missing cost/identity seeds")
    summaries = []
    for rank,fraction,sigma,mask_type in itertools.product(P["ranks"],P["observed_fractions"],
                                                          P["noise_sigmas"],P["mask_types"]):
        group = sorted([c for c in cells if (c["rank"],c["fraction"],c["sigma"],c["mask_type"]) ==
                        (rank,fraction,sigma,mask_type)],key=lambda c:c["seed"])
        summaries.append({"rank":rank,"fraction":fraction,"sigma":sigma,"mask_type":mask_type,
            "mean_nmse":{a:float(np.mean([c["nmse"][a] for c in group])) for a in ARMS},
            "relative_reductions":{a:interval([1-c["nmse"]["field_ridge"]/c["nmse"][a] for c in group])
                                   for a in ("nn_copy","weighted_blend")}})
    primary = next(c for c in summaries if all(c[k]==v for k,v in P["primary"].items()))
    ident = interval([100*(g["hme_correct"]-g["nn_correct"])/g["n"] for g in guards])
    cost_summary = {"median_bundle_bytes":{a:float(np.median([c["bundle_bytes"][a] for c in costs]))
                                          for a in ("nn_copy","weighted_blend","field_ridge","direct_moment")},
        "median_latency_ns":{a:float(np.median([c["timing"][a]["median_ns"] for c in costs])) for a in ARMS},
        "median_p95_ns":{a:float(np.median([c["timing"][a]["p95_ns"] for c in costs])) for a in ARMS},
        "field_over_blend_median_ratio":float(np.median([c["timing"]["field_ridge"]["median_ns"] /
                                                  c["timing"]["weighted_blend"]["median_ns"] for c in costs]))}
    gates = {"reconstruction":all(v["ci95"][0]>P["primary_min_relative_error_reduction"]
                                  for v in primary["relative_reductions"].values()),
             "identity":ident["ci95"][0]>-P["identity_noninferiority_margin_pp"] and all(g["unchanged"] for g in guards),
             "cost":all(c["bundle_bytes"]["field_ridge"]<=P["memory_cap_bytes"] for c in costs)
                 and cost_summary["median_p95_ns"]["field_ridge"]<=P["max_primary_p95_latency_ns"]
                 and cost_summary["field_over_blend_median_ratio"]<=P["max_latency_ratio_to_blend"]}
    gates["overall"] = all(gates.values())
    return {"primary":primary,"all_conditions":summaries,"identity_delta_pp":ident,
            "costs":cost_summary,"gates":gates,
            "maximum_field_direct_coordinate_error":max(c["field_direct_max_error"] for c in cells)}


def report(result):
    s = result["summary"]
    lines = ["# HME-REC-1: partial-observation reconstruction results", "",
        f"Registration: `{result['registration']['commit']}`.", "",
        "30 seeds; 128 complete training records; 64 unseen queries per seed; dimension 32.",
        "All 1,080 registered cells completed. Primary: rank 4, 50% random observations, sigma 0.1.",
        "Missing-coordinate normalized squared error (lower is better):", "",
        "| Arm | Primary mean NMSE | Median query time (microseconds) |",
        "|---|---:|---:|"]
    for a in ARMS:
        lines.append(f"| {a} | {s['primary']['mean_nmse'][a]:.6f} | {s['costs']['median_latency_ns'][a]/1000:.2f} |")
    lines += ["", "## Prespecified contrasts and gates", ""]
    for a,v in s["primary"]["relative_reductions"].items():
        lines.append(f"Field relative error reduction versus {a}: {100*v['mean']:.2f}% "
                     f"(paired 95% interval [{100*v['ci95'][0]:.2f}, {100*v['ci95'][1]:.2f}]%).")
    ident=s['identity_delta_pp']
    lines += ["", f"Separate identity path minus raw signed cosine: {ident['mean']:+.3f} percentage points "
              f"(95% interval [{ident['ci95'][0]:+.3f}, {ident['ci95'][1]:+.3f}]).",
              "Public identity predictions and field bytes were unchanged by reconstruction.", "",
              "| Gate | Passed |", "|---|---|"]
    lines += [f"| {k} | {v} |" for k,v in s['gates'].items()]
    lines += ["", "## Costs", "", "| Deployment bundle | Median accounted bytes |", "|---|---:|"]
    lines += [f"| {a} | {v:.0f} |" for a,v in s['costs']['median_bundle_bytes'].items()]
    lines += ["",f"Median paired field/blend query-time ratio: {s['costs']['field_over_blend_median_ratio']:.3f}.",
        f"Median field p95: {s['costs']['median_p95_ns']['field_ridge']/1e6:.3f} ms.", "",
        "HME bytes include the actual field, payload/pattern caches, records and lineage.",
        "Other bundles retain the same provenance and identity vectors. Compact-state bytes,",
        "construction times and raw timing samples are in results.json. Transient query",
        "workspace and interpreter/module overhead are not included. These timings are host-specific.",
        "", "## Interpretation", "",
        "The direct second-moment readout is algebraically equivalent in this co-located setup.",
        f"Maximum field/direct reconstructed-coordinate difference: {s['maximum_field_direct_coordinate_error']:.3g}.",
        "A reconstruction improvement over copying/blending is a useful field operation,",
        "not evidence of an FFT-specific advantage over the direct-matrix control.",
        "The low-rank generative design favors learning shared linear structure; isotropic",
        "and block-mask controls, all noise levels and all observation fractions are reported.",
        "No claim about arbitrary images, semantic memory, missing training records, nonlinear",
        "data, field-only identity recovery, or production deployment follows from this study.",
        "The identity guardrail protects the existing separate experimental signed path,",
        "not a new policy that identifies records after field completion. Engine source is unchanged.",
        "", "## Provenance and reproduction", "",
        "Fresh canonical-origin fetch and containing refs were checked before data generation.",
        "The registration record includes source hashes and any GitHub server run timestamps.",
        "This establishes public availability before this run, not absence of undisclosed private runs.",
        "No protocol deviations. Retained raw_records.jsonl.gz contains all query predictions,",
        "targets, observations and losses. results.json contains hashes, every cell, costs and guards.", "",
        "```bash", "OPENBLAS_NUM_THREADS=1 python experiments/reconstruction_v1/evaluate.py \\",
        f"  --registration-commit {result['registration']['commit']} \\",
        "  --output outputs/reconstruction_v1_reproduction", "```", "",
        "Use a fresh output directory and a full clone with network access to canonical origin.", ""]
    return "\n".join(lines)


def run(commit, output):
    if output.exists():
        raise FileExistsError("Use a fresh output directory")
    registration = verify_registration(commit)
    registration["github_run"] = server_run_record()
    output.mkdir(parents=True)
    (output/"registration.json").write_text(json.dumps(registration,indent=2)+"\n")
    cells, costs, guards = [], [], []
    try:
        with gzip.open(output/"raw_records.jsonl.gz", "wt", encoding="utf-8") as raw:
            for seed in P["seeds"]:
                for rank in P["ranks"]:
                    x,t = dataset(seed,rank,P["train_count"],P["query_count"],P["dimension"])
                    engine, models, cost = prepare(x)
                    field_hash = array_hash(engine.hme.field)
                    # Retain a field-only copy and erase all ledger data in the control.
                    erased = copy.deepcopy(engine)
                    for name in ("records","_payloads","_patterns"):
                        getattr(erased.hme,name).clear()
                    probe_mask=np.arange(P["dimension"])%2==0
                    probe=np.where(probe_mask,t[0],np.nan)
                    np.testing.assert_array_equal(
                        reconstruct("field_ridge",models["field_ridge"],probe,probe_mask),
                        reconstruct("field_ridge",(erased.hme.field,P["dimension"],len(x)),probe,probe_mask))
                    np.testing.assert_array_equal(
                        reconstruct("field_ridge",(np.zeros_like(engine.hme.field),P["dimension"],len(x)),probe,probe_mask),
                        reconstruct("zero_fill",None,probe,probe_mask))
                    del erased
                    for fraction,sigma,mask_type in itertools.product(P["observed_fractions"],P["noise_sigmas"],P["mask_types"]):
                        c=cell(seed,rank,fraction,sigma,mask_type,t,models,raw)
                        c["training_hash"]=array_hash(x)
                        cells.append(c)
                    if rank==P["primary"]["rank"]:
                        ys,masks=observations(t,seed,rank,P["primary"]["fraction"],P["primary"]["sigma"],P["primary"]["mask_type"])
                        cost.update(seed=seed,timing=timing(models,ys,masks))
                        costs.append(cost)
                    if array_hash(engine.hme.field)!=field_hash:
                        raise AssertionError("Readout mutated the field")
                guards.append(identity_guardrail(seed))
                print(f"Completed seed {seed}",flush=True)
        result={"id":P["id"],"registration":registration,"protocol":P,
                "runtime":{"python":platform.python_version(),"numpy":np.__version__,
                           "platform":platform.platform(),"processor":platform.processor()},
                "finished_at_utc":datetime.now(timezone.utc).isoformat(),
                "cells":cells,"costs":costs,"identity":guards,"summary":summarize(cells,costs,guards)}
        (output/"results.json").write_text(json.dumps(result,indent=2,allow_nan=False)+"\n")
        (output/"REPORT.md").write_text(report(result))
        names=("results.json","REPORT.md","registration.json","raw_records.jsonl.gz")
        (output/"RESULTS.sha256").write_text("".join(f"{sha((output/n).read_bytes())}  {n}\n" for n in names))
    except Exception:
        (output/"FAILURE.json").write_text(json.dumps({"traceback":traceback.format_exc(),
            "completed_cells":len(cells),"completed_guardrails":len(guards)},indent=2)+"\n")
        raise


if __name__ == "__main__":
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--registration-commit",required=True)
    parser.add_argument("--output",type=Path,required=True)
    args=parser.parse_args()
    run(args.registration_commit,args.output)
