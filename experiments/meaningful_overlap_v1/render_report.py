"""Static evaluator-side plots for exposed development/validation observations."""
import argparse
import gzip
import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle
import numpy as np

from .evaluate import LAYOUTS


def render(source, output, cost_source=None):
    source, output = Path(source), Path(output)
    manifest = json.loads((source/"RUN_MANIFEST.json").read_text())
    if manifest["phase"] not in ("development", "validation"):
        raise ValueError("This renderer labels only development/validation observations")
    if (source/"FAILURE.json").exists():
        raise ValueError("Incomplete run: do not plot successful subset")
    summary = json.loads((source/"summary.json").read_text())
    runs = [json.loads(gzip.decompress(f.read_bytes())) for f in sorted(source.glob("corpus_*.json.gz"))]
    if len(runs) != len(manifest["planned_namespaces"]):
        raise ValueError("Missing corpus output")
    if cost_source:
        cost_source = Path(cost_source)
        completion = json.loads((cost_source/"COMPLETION.json").read_text())
        if completion["completed_corpora"] != len(runs) or completion["failures"]:
            raise ValueError("Incomplete replacement cost pass")
        for i, run in enumerate(runs):
            measured = json.loads((cost_source/f"corpus_{i:03d}.json").read_text())
            if measured["namespace"] != run["namespace"] or not measured["primary_metrics_and_rank_records_unchanged"]:
                raise ValueError("Mismatched cost corpus")
            run["costs"] = measured["costs"]
    output.mkdir(parents=True, exist_ok=False)
    p = manifest["protocol"]
    shared = p["primary"]["r"]
    first = runs[0]
    families = first["data_hashes"][str(shared)]["families_evaluator_only"]
    layouts = [next(v for v in first["layouts"] if v["r"] == shared and v["layout"] == kind) for kind in LAYOUTS[:3]]
    colors = plt.get_cmap("tab20")
    fig, axes = plt.subplots(1, 3, figsize=(12, 4), constrained_layout=True)
    for ax, layout in zip(axes, layouts):
        for index, (x, y) in enumerate(layout["positions"]):
            ax.add_patch(Rectangle((y-8, x-8), 16, 16, facecolor=colors(families[index]),
                                   edgecolor="black", linewidth=.25, alpha=.45))
        ax.set(xlim=(0, 256), ylim=(256, 0), aspect="equal", title=layout["layout"].replace("_", " "))
        ax.set_xlabel("Field column")
        ax.set_ylabel("Field row")
    fig.suptitle("Validation example: identical patch sizes; colors added by evaluator only")
    fig.savefig(output/"layouts.png", dpi=160)
    plt.close(fig)

    names = ["RANDOM_MATCHED/HYBRID", "SIMILARITY_PLACED/HYBRID", "SEPARATED/HYBRID", "SIGNED_NN", "RAW_SIGNED_NN", "VECTOR_AGGREGATE", "SIMILARITY_PLACED/FIELD_ONLY"]
    labels = ["Random hybrid", "Similarity hybrid", "Separated hybrid", "Matched signed NN", "Raw signed NN", "Vector aggregate", "Similarity field only"]
    fig, axes = plt.subplots(1, 2, figsize=(12, 5), constrained_layout=True)
    for ax, metric, title in zip(axes, ["sibling_precision_at_5", "exact_top1_accuracy"], ["Sibling precision at 5", "Exact identity top-1"]):
        values = [100*summary["primary_means"][name][metric] for name in names]
        ax.barh(labels, values, color=["#8899aa", "#b57927", "#8899aa", "#667788", "#345b78", "#398572", "#c6a26a"])
        for i, v in enumerate(values):
            ax.text(v+.5, i, f"{v:.2f}%", va="center", fontsize=9)
        ax.invert_yaxis()
        ax.set(xlim=(0, max(values)*1.22), xlabel="Percent", title=title)
    fig.suptitle(f"Development observations: {len(runs)} validation corpora, r=.50, sigma=1, symmetric")
    fig.savefig(output/"accuracy.png", dpi=160)
    plt.close(fig)

    fig, axes = plt.subplots(1, 3, figsize=(12, 4), constrained_layout=True)
    geometry_keys = [("weighted_signed_similarity", "Overlapping vector cosine"),
                     ("weighted_family_enrichment", "Overlapping pairs in same family"),
                     ("weighted_offset_pattern_agreement", "Pattern agreement at actual offsets")]
    for ax, (key, title) in zip(axes, geometry_keys):
        kinds = ["RANDOM_MATCHED", "SIMILARITY_PLACED", "CONTENT_SHUFFLE"]
        vals = [np.mean([next(v for v in r["layouts"] if v["r"] == shared and v["layout"] == kind)["geometry"][key] for r in runs]) for kind in kinds]
        ax.bar(["Random", "Similarity", "Shuffle"], vals, color=["#8899aa", "#b57927", "#8899aa"])
        ax.axhline(0, color="black", linewidth=.5)
        ax.set_title(title, fontsize=10)
    fig.suptitle("Measured overlap relationships, validation only")
    fig.savefig(output/"overlap.png", dpi=160)
    plt.close(fig)

    cnames = ["RAW_SIGNED_NN", "VECTOR_AGGREGATE", "SIMILARITY_PLACED/HYBRID", "SIMILARITY_PLACED/FIELD_ONLY"]
    clabels = ["Raw NN", "Aggregate", "Hybrid", "Field only"]
    fig, axes = plt.subplots(1, 3, figsize=(12, 4), constrained_layout=True)
    fields = [("storage", "persistent_bytes", 1/1048576, "Retained state (MiB)"),
              ("latency", "median_ns", 1/1e6, "Median query latency (ms)"),
              ("latency", "p95_ns", 1/1e6, "p95 query latency (ms)")]
    for ax, (group, key, scale, title) in zip(axes, fields):
        vals = [float(np.median([r["costs"][group][n][key] for r in runs]))*scale for n in cnames]
        ax.bar(clabels, vals, color=["#345b78", "#398572", "#b57927", "#c6a26a"])
        ax.set_title(title, fontsize=10)
        ax.tick_params(axis="x", labelrotation=20)
    fig.suptitle("Measured host costs: cached snapshots, median across validation corpora")
    fig.savefig(output/"costs.png", dpi=160)
    plt.close(fig)
    return [str(p) for p in sorted(output.glob("*.png"))]


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source")
    parser.add_argument("--output", required=True)
    parser.add_argument("--cost-source")
    args = parser.parse_args()
    for name in render(args.source, args.output, args.cost_source):
        print(name)
