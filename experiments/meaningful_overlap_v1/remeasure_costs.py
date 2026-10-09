"""Serial cost pass over exposed validation corpora, with exact score checks.

Never selects a layout, baseline, condition or outcome. Preserves the original
validation records; separately identifies measurement-source amendments.
"""
import os
os.environ.update({k: "1" for k in ("OPENBLAS_NUM_THREADS", "OMP_NUM_THREADS", "MKL_NUM_THREADS",
                                   "VECLIB_MAXIMUM_THREADS", "NUMEXPR_NUM_THREADS")})
import argparse
from datetime import datetime, timezone
import gzip
import json
from pathlib import Path
import resource
import traceback

import numpy as np
from . import dataset, placement, retrieval, statistics, costs, integrity
from .evaluate import config, write_json, invariant


def run(source, output):
    source, output = Path(source), Path(output)
    if output.exists():
        raise FileExistsError("Refusing existing output directory")
    output.mkdir(parents=True)
    try:
        manifest = json.loads((source/"RUN_MANIFEST.json").read_text())
        invariant(manifest["phase"] == "validation" and not (source/"FAILURE.json").exists(), "Need completed validation")
        completion = json.loads((source/"COMPLETION.json").read_text())
        invariant(completion["completed_corpora"] == 12 and not completion["failures"], "Incomplete validation")
        p = config()
        invariant(p == manifest["protocol"], "Protocol changed after validation")
        rule = json.loads((integrity.HERE/"FROZEN_BASELINE.json").read_text())["rule"]
        invariant(rule == manifest["baseline_rule"], "Frozen baseline changed")
        write_json(output/"RUN_MANIFEST.json", {"phase": "validation_cost_remeasurement",
            "reason": "Independent uncached snapshots and serial host measurement; original records preserved",
            "validation_manifest_sha256": integrity.digest(source/"RUN_MANIFEST.json"),
            "source_sha256": integrity.source_hashes(), "head": integrity.git("rev-parse", "HEAD"),
            "started_utc": datetime.now(timezone.utc).isoformat(), "planned_namespaces": manifest["planned_namespaces"]})
        for index, namespace in enumerate(manifest["planned_namespaces"]):
            old = json.loads(gzip.decompress((source/f"corpus_{index:03d}.json.gz").read_bytes()))
            corpus, truth = dataset.generate(namespace, p["dataset"], p["primary"]["r"])
            processed = retrieval.preprocess(corpus.vectors, "symmetric")
            invariant(dataset.array_hash(corpus.vectors) == old["data_hashes"][str(p["primary"]["r"])]["vectors"], "Reconstructed corpus differs")
            variants = {"RAW_SIGNED_NN": retrieval.RawNN(corpus), "VECTOR_AGGREGATE": retrieval.VectorAggregate(corpus, rule)}
            for kind in ("RANDOM_MATCHED", "SIMILARITY_PLACED", "SEPARATED"):
                pos, _ = placement.assign(processed, namespace, p["dataset"], kind)
                _, arms, _ = retrieval.build(corpus, pos, p["dataset"])
                variants.update({kind+"/"+name: arms[name] for name in ("HYBRID", "FIELD_ONLY")})
                if kind == "SIMILARITY_PLACED":
                    variants.update({name: arms[name] for name in ("SIGNED_NN", "ABSOLUTE_NN")})
            large_pos, _ = placement.assign(processed, namespace, p["dataset"], "SIMILARITY_PLACED",
                canvas=p["descriptive"]["larger_canvas"], spacing=p["descriptive"]["larger_spacing"])
            _, large_arms, _ = retrieval.build(corpus, large_pos, p["dataset"], p["descriptive"]["larger_canvas"])
            q, targets = dataset.queries(namespace, corpus, p["primary"]["sigma"], p["primary"]["repeats"])
            invariant(dataset.array_hash(q) == old["data_hashes"][str(p["primary"]["r"])]["queries"][str(p["primary"]["sigma"])] , "Queries differ")
            cell = next(c for c in old["cells"] if all(c[k] == p["primary"][k] for k in ("r", "sigma", "mode")))
            for name, arm in variants.items():
                observed = statistics.observe(arm.scores(q, p["primary"]["mode"]), targets, truth.families)
                invariant(observed == cell["arms"][name], f"Primary scores/ranks changed for {name}")
            for name, arm in large_arms.items():
                observed = statistics.observe(arm.scores(q, p["primary"]["mode"]), targets, truth.families)
                invariant(observed == old["larger_canvas"]["arms"][name], f"Large-canvas scores changed for {name}")
            ordinary = costs.measure(variants, q, p["costs"])
            large = costs.measure({"RAW_SIGNED_NN": variants["RAW_SIGNED_NN"], **large_arms}, q, p["costs"])
            invariant(all(v["persistent_bytes"] <= p["integrity"]["persistent_bytes_cap"]
                          for c in (ordinary, large) for v in c["storage"].values()), "Memory cap exceeded")
            write_json(output/f"corpus_{index:03d}.json", {"namespace": namespace, "costs": ordinary,
                "large_costs": large, "primary_metrics_and_rank_records_unchanged": True})
            print(f"costs completed {namespace}", flush=True)
        write_json(output/"COMPLETION.json", {"completed_corpora": 12, "failures": [],
            "completed_utc": datetime.now(timezone.utc).isoformat(),
            "peak_process_rss_bytes": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*1024})
    except Exception as exc:
        write_json(output/"FAILURE.json", {"error": repr(exc), "traceback": traceback.format_exc()})
        raise


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source")
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    run(args.source, args.output)
