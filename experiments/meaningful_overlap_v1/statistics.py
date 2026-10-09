"""Paired corpus bootstrap. Approximate coverage, no query pseudoreplication."""
import numpy as np
from .retrieval import ranks

CONTRASTS = (
    ("placement", "sibling_precision_at_5", "RANDOM_MATCHED/HYBRID", .02),
    ("separated", "sibling_precision_at_5", "SEPARATED/HYBRID", .02),
    ("raw_association", "sibling_precision_at_5", "RAW_SIGNED_NN", .02),
    ("aggregate", "sibling_precision_at_5", "VECTOR_AGGREGATE", .02),
    ("matched_identity", "exact_top1_accuracy", "SIGNED_NN", -.01),
    ("raw_identity", "exact_top1_accuracy", "RAW_SIGNED_NN", -.01),
)


def observe(scores, targets, families):
    order = ranks(scores)
    targets, families = np.asarray(targets), np.asarray(families)
    if len(targets) != len(order) or len(families) != order.shape[1] or order.shape[1] < 6:
        raise ValueError("Invalid evaluator truth")
    target_ranks = np.argmax(order == targets[:, None], axis=1)+1
    without = order[order != targets[:, None]].reshape(len(order), -1)[:, :5]
    sibling = np.mean(families[without] == families[targets, None], axis=1)
    top_family = families[order[:, 0]] == families[targets]
    exact = target_ranks == 1
    per_query = {"target_rank": target_ranks.tolist(), "top6": order[:, :6].tolist(),
                 "sibling_precision_at_5": sibling.tolist()}
    metrics = {"sibling_precision_at_5": float(sibling.mean()),
               "exact_top1_accuracy": float(exact.mean()),
               "exact_top5_accuracy": float(np.mean(target_ranks <= 5)),
               "mean_reciprocal_rank": float(np.mean(1/target_ranks)),
               "wrong_member_within_family": float(np.mean(top_family & ~exact)),
               "wrong_family": float(np.mean(~top_family)),
               "family_top1_including_target": float(top_family.mean()),
               "family_precision_at_5_including_target": float(np.mean(families[order[:, :5]] == families[targets, None])),
               "queries_with_exact_score_ties": int(np.sum(np.any(np.diff(np.sort(scores, axis=1), axis=1) == 0, axis=1)))}
    return {"metrics": metrics, "per_query": per_query}


def decision(deltas, cfg, integrity=True, placement_achieved=True):
    x = np.asarray(deltas, dtype=float)
    if x.ndim != 2 or x.shape[1] != 6 or len(x) < 2 or not np.all(np.isfinite(x)):
        raise ValueError("Need at least two complete finite paired corpora and six contrasts")
    indices = np.random.default_rng(cfg["analysis_seed"]).integers(0, len(x), (cfg["resamples"], len(x)))
    boot = x[indices].mean(axis=1)
    # Exact constant fixtures must not clear a strict margin through summation
    # roundoff (e.g. averaging fifty copies of .02 can yield .02000000000000001).
    constant = np.all(x == x[:1], axis=0)
    boot[:, constant] = x[0, constant]
    lower_q = cfg["family_alpha"]/6
    details = []
    for j, (name, metric, comparator, margin) in enumerate(CONTRASTS):
        low = float(np.quantile(boot[:, j], lower_q, method="linear"))
        upper = float(np.quantile(boot[:, j], 1-lower_q, method="linear"))
        details.append({"name": name, "metric": metric, "comparator": comparator,
                        "margin": margin, "mean": float(x[0, j] if constant[j] else x[:, j].mean()),
                        "values_by_corpus": x[:, j].tolist(), "decision_lower_bound": low,
                        "descriptive_upper_same_tail": upper,
                        "ci95": np.quantile(boot[:, j], [.025, .975], method="linear").tolist(),
                        "clears_margin": bool(low > margin)})
    valid = bool(integrity and placement_achieved)
    passed = [c["clears_margin"] for c in details]
    placement = valid and passed[0]
    identity = valid and all(passed[4:])
    full = valid and all(passed)
    conclusion = ("MECHANISM_NOT_TESTED" if not valid else "FULL_PROPOSED_SUCCESS" if full
                  else "TRADEOFF" if placement and not identity else "ADVANTAGE_NOT_ESTABLISHED")
    return {"contrasts": details, "placement_benefit": placement,
            "associative_benefit_over_tested_baselines": valid and all(passed[1:4]),
            "identity_preservation": identity, "full_proposed_success": full,
            "conclusion": conclusion, "integrity": bool(integrity),
            "placement_achieved": bool(placement_achieved),
            "tradeoff_meaning": "Association criterion passes, identity safeguard not established; not automatically evidence of inferiority.",
            "coverage": "Approximate percentile bootstrap; one-sided Bonferroni across six, alpha/6",
            "corpora": len(x), "resamples": cfg["resamples"], "lower_quantile": lower_q}


def paired_deltas(primary_cells):
    return np.array([[cell["SIMILARITY_PLACED/HYBRID"][metric]-cell[other][metric]
                      for _, metric, other, _ in CONTRASTS] for cell in primary_cells])
