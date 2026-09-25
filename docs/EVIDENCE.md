# Which engine does each result describe?

| Report | Tested implementation | Meaning |
|---|---|---|
| [Candidate-specific field retrieval](../experiments/field_retrieval_v1/REPORT.md) | Pinned default encoder/writer and new experimental readout; frozen at `6d83732` | Thirty fresh seeds and five layouts; primary hybrid 50.29% versus signed NN 52.03%; controls pass, practical gain and Stage 3 gate fail |
| [Preregistered sign ablation](../experiments/sign_ablation_v1/REPORT.md) | Default core and one-expression experimental signed variant; protocol frozen at `ca25cc3` | Thirty fresh seeds; sign change adds 9.79 points; signed HME versus NN +0.83 points; noninferiority supported, equivalence and superiority not established |
| [Preregistered NN comparison](../experiments/nn_baseline_v1/REPORT.md) | Unchanged v3.1 memory core; protocol/evaluator frozen at `88520eb` before execution | Ten seeds; HME 47.73% versus signed-cosine NN 57.27% in the primary high-noise condition; all conditions, paired intervals, costs and raw observations published |
| [Current release](../evidence/current_release_v3_1.json) | v3.1 engine files at `935b0d0`, hash-checked against that commit | Fresh 94-test active run; five-seed memory retrieval experiment; 20 current-runtime traces; separate 11-test historical check |
| [Runtime restoration](../evidence/runtime_restoration_validation.json) | v3.1 controllers/dynamics, pinned by source hashes | Numerical comparisons with the archived implementation, event integrity, bridge and packaging checks |
| [Standalone validation](../evidence/standalone_validation.json) | v3.0 extraction, pinned by source hashes | Original 21-test standalone run, separate archived tests, and extraction checks |
| [Earlier v3 retrieval audit](../evidence/hme_audit_v3.json) | `hme_engine.py` from v3.0 | Actual single-seed execution of the extracted core; not copied v2.2 measurements |
| [Archived evidence](../archive/v2.2/evidence/) | v2.2 and its pinned historical protocols | Historical results, retained unchanged |

The package and optional runtime are version 3.1.0. The memory component's
`ENGINE_ID` still says `hme-3.0.0` because its source is byte-identical to 3.0.
The fresh report records both identities explicitly. New runs can reproduce old
numbers when the numerical code, inputs and environment are unchanged.

## Preregistered baseline comparison

[HME-NN-1](../experiments/nn_baseline_v1/REPORT.md) is the first default-engine
comparison. It uses new seeds rather than relabelling the earlier HME-only sweep.
The primary accuracy difference is -9.53 percentage points, with a paired-seed
95% bootstrap interval of [-10.70, -8.28]. The frozen +2-point practical-advantage
criterion was not met. Actual accounted storage and measured online API latency
also favored exact NN at this task size. The baseline retains the same artifact
records and lineage, so retaining provenance is not exclusive to the HME arm.

The field's primary top-1 contribution relative to an absolute-cosine/field-erased
control was +0.70 points, interval [-1.02, +2.34]; it does not establish a reliable
benefit. The comparison covers synthetic vectors at one load, dimension and
shared position. All ten seeds and all registered conditions are available in
the report; no protocol deviations occurred. The nine added correctness tests
brought the active suite to 103 at that stage. Earlier test counts below describe their original
runs and remain unchanged.

## Preregistered sign ablation

[HME-NN-2A](../experiments/sign_ablation_v1/REPORT.md) follows with thirty new
seeds and a one-point equivalence margin fixed before execution. It changes
only absolute to signed item/query similarity, retaining the original field
bias and all other scoring behavior. The default package engine is unchanged.

Primary top-1 accuracies were current HME 44.01%, signed HME 53.80% and signed
NN 52.97%. The sign change added 9.79 points (95% interval [8.85, 10.73]).
Signed HME minus NN was +0.83 points: the 90% interval [0.08, 1.56] supports
noninferiority within one point, but extends outside the equivalence band.
The 95% interval [-0.05, 1.69] does not establish superiority. Under the
secondary symmetric-preprocessing, high-noise condition, signed HME trailed
NN by 1.33 points (descriptive 95% interval [0.70, 2.01]).

All seeds, conditions and costs are published without deviations. The six new
correctness tests brought the active suite to 109 at that stage. This is evidence for a
specific experimental sign change, not for a query-dependent field readout or
an encoder redesign. Those require separate registration and evaluation.

## Candidate-specific field retrieval

[HME-NN-2B](../experiments/field_retrieval_v1/REPORT.md) uses thirty fresh seeds,
five overlap layouts and a query-dependent field patch at each candidate's
independently assigned position. All searches scan every candidate without the
target address. The encoder/writer is unchanged, and every arm retains the
same provenance and address map.

The registered primary hybrid scored 50.29% versus signed NN's 52.03%, a paired
difference of -1.74 points (95% interval [-2.42, -1.09]); field-only scored 24.04%.
The +2-point practical-gain criterion failed. At zero overlap the hybrid exactly
reproduced signed NN and field-only reproduced absolute NN, as predicted. At
the shared position, hybrid ranks again matched NN and field-only tied all
identities. All cached/uncached and antipodal-ceiling checks passed.

Costs were measured for compact experimental snapshots with the same ranked-output
contract: cached hybrid used 9.34 times NN's accounted storage and 4.21 times its
query latency at the primary layout. These ratios describe different readout
implementations and outputs from the earlier default-API experiments, so they
must not be presented as directly comparable speedups over those reports.

All forty ordinary-data conditions, ten polarity-stress conditions, per-query
outcomes, reconstruction diagnostics and costs are published without deviations.
The eight new correctness tests bring the active suite to 117. The registered
Stage 3 accuracy gate did not pass; no encoder redesign was performed.

## Fresh v3.1 retrieval data

Five seeds were specified in the collector before execution: 7312026 through
7312030. Each run stores 128 independent Gaussian vectors of dimension 16 at
position (32, 32) in a 64-by-64 memory field. Query noise is additive Gaussian
noise with the reported sigma. Scores use the current default memory policy.

| Sigma | Correct per seed, out of 128 | Pooled accuracy | Approximate 95% interval for mean across seeds |
|---|---|---:|---|
| 0, 0.05, 0.10, 0.25 (each) | 128, 128, 128, 128, 128 | 100% | All five runs correct; no population guarantee |
| 0.50 | 119, 117, 120, 122, 118 | 93.1% | 91.3–95.0% |
| 1.00 | 59, 60, 49, 60, 54 | 44.1% | 39.4–48.7% |

The intervals use a Student-t estimate over five per-seed accuracies, with four
degrees of freedom. Five seeds provide limited precision; items sharing a field
are not treated as independent experiment replicates. Zero observed seed
variance at low noise produces a zero-width computed interval, not proof of
perfect population accuracy. Full audit outputs retain determinism checks,
field/ledger ablations, exact-string probes and unrelated-query probes.

These results are for synthetic numeric inputs at one load and position. They
do not demonstrate semantic retrieval, field-only identification, or superiority
to nearest-neighbor retrieval. The scores remain uncalibrated, so no Brier/ECE
result is presented as if they were correctness probabilities.

## Fresh runtime observations

Both `FieldRuntime` and `AgentRuntime` execute 16-write sequences for every seed,
with write weighting off and on: 20 runs and 320 observed ticks. Every run records
salience at measurement and write time, gain, event flags, event pre/post hashes,
state/memory hashes and final exact-query identification counts.

Each run produces one automatically triggered field event. Weighting changes the
total stored gain from 1.6 to 2.4 under this input drive; all enabled writes reach
the gain ceiling. Exact-query recall after the sequence is 16, 16, 14, 15 and 16
out of 16 across the five seeds for each controller/weight setting. Even clean
queries are not guaranteed to identify the originating record at this dimension
and preprocessing. This probe confirms execution and wiring, not a retrieval
improvement or selective prioritization effect. The conditions have different
stored gains and are not an equal-budget efficacy comparison.

## Reproduce and inspect

```bash
python -m pip install -e ".[test,legacy-test,visualization]"
python scripts/collect_current_evidence.py --output outputs/current_release_v3_1.json
```

The collector runs the active and archived suites separately, records the tested
commit and exact engine/harness hashes, and saves raw observations. It does not
rewrite previous evidence. Source changes must be committed and source pins
updated before release evidence is collected.

Every CI run also retains its own JUnit reports, single-seed retrieval audit,
runtime example output and historical bridge output as `hme-results-*` artifacts.
CI success establishes that the checks completed; quantitative outcomes belong
to the associated result files and source commit.
