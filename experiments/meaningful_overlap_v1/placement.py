"""Label-blind assignment to fixed slots; whole patches only."""
import numpy as np
from .dataset import rng
from experiments.field_retrieval_v1.retrieval import unit_rows


def slots(canvas, dimension, grid_shape, spacing):
    rows, cols = grid_shape
    span = (np.array([rows, cols])-1)*spacing + dimension
    if np.any(span > canvas) or spacing < 0:
        raise ValueError("Layout would clip a patch")
    first = (canvas-span)//2 + dimension//2
    return np.array([first+[r*spacing, c*spacing]
                     for r in range(rows) for c in range(cols)], dtype=np.int64)


def overlap_matrix(positions, dimension):
    p = np.asarray(positions)
    widths = np.maximum(0, dimension-np.abs(p[:, None]-p[None, :]))
    result = np.prod(widths, axis=2).astype(float)/(dimension*dimension)
    np.fill_diagonal(result, 0)
    return result


def objective(assignment, weights, similarities):
    total = weights.sum()
    return float(np.sum(weights*similarities[np.ix_(assignment, assignment)])/total) if total else 0.0


def assign(processed, namespace, cfg, kind, canvas=None, spacing=None, permit=None):
    n = len(processed)
    canvas = canvas or cfg["canvas"]
    spacing = spacing if spacing is not None else (cfg["separated_spacing"] if kind == "SEPARATED" else cfg["overlap_spacing"])
    locations = slots(canvas, cfg["dimension"], cfg["grid_shape"], spacing)
    if len(locations) != n:
        raise ValueError("Slot count does not match corpus")
    weights = overlap_matrix(locations, cfg["dimension"])
    vectors = unit_rows(processed)
    sim = (vectors.conj() @ vectors.T).real
    initial = rng(namespace, "layout/initial", permit).permutation(n)
    assignment, initial_j = initial.copy(), objective(initial, weights, sim)
    best_j = initial_j
    accepted = 0
    weight_sum = weights.sum()
    if kind in ("SIMILARITY_PLACED", "CONTENT_SHUFFLE"):
        for restart in range(cfg["search_restarts"]):
            a = initial.copy() if restart == 0 else rng(namespace, f"layout/restart/{restart}", permit).permutation(n)
            proposals = rng(namespace, f"layout/proposals/{restart}", permit).integers(0, n, (cfg["swap_proposals"], 2))
            for left, right in proposals:
                if left == right:
                    continue
                # Undirected weighted objective delta. The swapped pair is unchanged.
                delta = (weights[left]-weights[right])*(sim[a[right], a]-sim[a[left], a])
                delta[left] = delta[right] = 0
                if weight_sum and 2*delta.sum()/weight_sum > cfg["swap_tolerance"]:
                    a[left], a[right] = a[right], a[left]
                    accepted += 1
            j = objective(a, weights, sim)
            if j > best_j+cfg["swap_tolerance"] or (abs(j-best_j) <= cfg["swap_tolerance"] and tuple(a) < tuple(assignment)):
                assignment, best_j = a.copy(), j
        if kind == "CONTENT_SHUFFLE":
            assignment = assignment[rng(namespace, "layout/content_shuffle", permit).permutation(n)]
    elif kind not in ("RANDOM_MATCHED", "SEPARATED"):
        raise ValueError(kind)
    positions = np.empty_like(locations)
    positions[assignment] = locations
    return positions, {"slot_to_item": assignment.tolist(), "slots": locations.tolist(),
                       "initial_objective": initial_j, "objective": objective(assignment, weights, sim),
                       "accepted_swaps_all_restarts": accepted}


def geometry(positions, processed, patterns, field, labels):
    """Evaluator-only diagnostics, never passed back to assignment/search."""
    d = patterns.shape[1]
    w = overlap_matrix(positions, d)
    sim = (unit_rows(processed).conj() @ unit_rows(processed).T).real
    occupancy = np.zeros(field.shape, dtype=np.int16)
    starts = positions-d//2
    for x, y in starts:
        occupancy[x:x+d, y:y+d] += 1
    pairs = []
    for i, j in zip(*np.where(np.triu(w, 1) > 0)):
        lo, hi = np.maximum(starts[i], starts[j]), np.minimum(starts[i]+d, starts[j]+d)
        ai, aj, size = lo-starts[i], lo-starts[j], hi-lo
        p = patterns[i, ai[0]:ai[0]+size[0], ai[1]:ai[1]+size[1]].ravel()
        q = patterns[j, aj[0]:aj[0]+size[0], aj[1]:aj[1]+size[1]].ravel()
        denom = np.linalg.norm(p)*np.linalg.norm(q)
        agreement = float(np.vdot(p, q).real/denom) if denom > 1e-12 else 0.0
        pairs.append({"i": int(i), "j": int(j), "fraction": w[i, j], "signed_cosine": sim[i, j],
                      "same_family": bool(labels[i] == labels[j]), "offset_pattern_agreement": agreement,
                      "offset_inner_product_real": float(np.vdot(p, q).real)})
    mass = sum(p["fraction"] for p in pairs)
    mean = lambda key: sum(p["fraction"]*p[key] for p in pairs)/mass if mass else None
    return {"pairs": pairs, "pair_count": len(pairs), "overlap_weight": mass,
            "weighted_signed_similarity": mean("signed_cosine"),
            "weighted_family_enrichment": mean("same_family"),
            "weighted_offset_pattern_agreement": mean("offset_pattern_agreement"),
            "occupancy_histogram": {str(v): int(np.sum(occupancy == v)) for v in np.unique(occupancy)},
            "max_occupancy": int(occupancy.max()), "field_norm": float(np.linalg.norm(field)),
            "field_energy": float(np.vdot(field.ravel(), field.ravel()).real)}
