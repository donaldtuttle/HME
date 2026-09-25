# C0–C7 Ablation Protocol — C(ψ) Salience Mechanisms

**Status:** Preregistered experimental protocol  
**Classification:** Typed Realization / DEVELOP  
**Canonical weight:** none  
**Engine pin:** `1caff9577e8a4bdaa2b0510c79673035081a967a25f15067bfa8ce99ccca6d11`  
**Required before any efficacy claim** for write-gain, retrieval salience, or inscription rejection.

This document is the experimental governance companion to the runtime contract in `SKILL.md`. It does not alter HME semantics.

---

## 1. Factorial design

Three independent binary switches:

| Switch | Meaning |
|--------|---------|
| W | `influence_write_gain` |
| R | `influence_retrieval` |
| I | `enable_inscription_rejection` |

| ID | W | R | I | Description |
|----|---|---|---|-------------|
| C0 | – | – | – | Baseline (all off) |
| C1 | ✓ | – | – | Write-gain alone |
| C2 | – | ✓ | – | Retrieval salience alone |
| C3 | – | – | ✓ | Inscription rejection alone |
| C4 | ✓ | ✓ | – | Write + retrieval |
| C5 | ✓ | – | ✓ | Write + rejection |
| C6 | – | ✓ | ✓ | Retrieval + rejection |
| C7 | ✓ | ✓ | ✓ | All three |

All other parameters fixed to the current realization defaults documented in `SKILL.md`.

---

## 2. Ground truth requirement

**Do not use `base_score` eligibility as ground truth.**

For every query the harness must supply an externally frozen answer key:

```text
Query Q17
Relevant artifacts:   [A04, A11]
Irrelevant artifacts: [A01, A02, A03, …]
```

All precision, recall, MRR, and top-1 metrics are computed against this frozen label set. Using the engine’s own relevance function as both the tested mechanism and the ground truth is forbidden.

---

## 3. Primary efficacy metrics (retrieval)

Computed against the frozen ground-truth labels:

- Top-1 target accuracy
- Precision@k (k = 1, 3, 5)
- Recall@k (k = 1, 3, 5)
- Mean Reciprocal Rank (MRR)

These are the decisive measures of whether rank movement actually helps.

---

## 4. Mechanistic metrics (retrieval topology)

- base-rank → final-rank displacement (Spearman ρ / Kendall τ on the eligible set)
- Percentage of relevance-eligible hits reordered by salience
- final_score − base_score delta on the selected hit (mean, median)
- score = 1.0 tie frequency
- Fraction of queries whose selected artifact changes relative to C0

These answer “is the mechanism doing anything?” They are not by themselves evidence of improvement.

---

## 5. Rejection metrics

- `LOW_INSCRIPTION_SALIENCE` rate
- False-rejection rate (relevant ground-truth artifacts rejected by policy)
- Correct-rejection rate (irrelevant or low-value artifacts rejected)
- Precision after rejection (on the surviving set)

Rejection is **not** required to improve recall. Its purpose is a policy decision about inscription strength, not discovery of additional memories.

---

## 6. Write-gain metrics

- Ledger gain distribution (mean, median, p95, max)
- Field-write amplitude (‖Δfield‖ after each modulated write)
- Fraction of writes that received scale > 1.0

**Consequence tests (required for write-gain conditions):**

- Later retrieval accuracy / precision for the amplified artifacts
- Cross-artifact interference (degradation of neighboring or unrelated targets)
- Field reconstruction quality under increasing ledger density

Stronger field writes are not inherently desirable. Amplification that raises interference or lowers later accuracy is a negative result.

---

## 7. Stability & diagnostic coupling

- Rank stability across repeated identical queries (fixed seed)
- Artifact identity hit rate under Gaussian query noise (σ = 0.00, 0.25, 0.50, 1.00) — reuse existing audit protocol
- Correlation of C(ψ) margin with final rank, applied gain, and rejection decision (report effect size + CI)

---

## 8. Falsifiers (preregistered)

**Retrieval salience (C2, C4, C6, C7):**  
If the condition produces statistically detectable rank displacement or reordering **but** yields no reproducible improvement in Precision@k, Recall@k, MRR, or Top-1 accuracy against the frozen ground truth, the retrieval-salience channel has not earned inclusion.

**Write-gain (C1, C4, C5, C7):**  
If amplification occurs but later retrieval accuracy does not improve (or interference rises), write-gain has not earned inclusion as a default.

**Inscription rejection (C3, C5, C6, C7):**  
If false-rejection rate is high enough to degrade overall precision, the current threshold/policy has not earned inclusion.

---

## 9. Reporting requirements

For each condition:

- n queries / n artifacts
- mean ± 95 % CI (or bootstrap) for every metric
- main-effect and interaction summary (three two-way + three-way contrasts vs C0)
- explicit statement of which metrics improved, degraded, or were neutral
- confirmation that:
  - `confidence` remained `base_score`
  - `NO_MATCH` never used C(ψ)
  - query-dependent scores were never written to artifacts
  - engine-generated `c_psi` ownership was preserved

---

## 10. Claim boundary after ablation

- Positive result on a metric → “under this realization and this test distribution, switch X moved metric Y”
- No result → switch remains available experimental machinery but unearned
- Never promote any switch to default-on or to an HME invariant without a new typed-realization decision

Efficacy is **not claimed** by the existence of this protocol or by the presence of the switches in the engine.

---

## 11. Relationship to SKILL.md

`SKILL.md` owns the runtime contract and the requirement to run C0–C7 before any efficacy claim.  
This file owns the detailed experimental design.  
Do not merge the full metric list into the skill; keep the skill lean.
