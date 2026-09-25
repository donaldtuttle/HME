from pathlib import Path
import json


def replace_once(path, old, new):
    p = Path(path)
    text = p.read_text(encoding="utf-8")
    if text.count(old) != 1:
        raise RuntimeError(f"Expected one anchor in {path}: {old!r}")
    p.write_text(text.replace(old, new, 1), encoding="utf-8")


section = '''## Raw-input retrieval check

The [HME-NN-3 follow-up](experiments/raw_vector_baseline_v1/REPORT.md) separates
raw cosine NN from the earlier matched-processed-vector baseline. Its protocol
and evaluator were published before thirty fixed evaluation seeds were run.
All 120 seed/noise cells completed, using 128 Gaussian items of dimension 16
at one shared position.

| Method | Top-1 at noise sigma 0.5 | Top-1 at noise sigma 1.0 |
|---|---:|---:|
| Raw signed-cosine NN | 99.43% | 74.11% |
| Default HME | 92.14% | 42.21% |
| HME with Hann window disabled | 99.01% | 65.65% |
| Experimental no-window, signed HME | 99.32% | 73.93% |

Disabling the window recovered 73.5% of the default-to-raw-NN high-noise gap
(a descriptive ratio, not a causal attribution). Applying the window to queries
too made HME worse: 28.78% at sigma 1.0. The no-window signed variant differed
from raw NN by -0.18 percentage points (95% interval [-0.57, +0.21]); this study
does not establish equivalence or superiority. The field-erased no-window arm
exactly reproduced absolute-cosine rankings for every evaluated query.

For numeric-vector experiments, the existing opt-out is explicit:

```python
from hme_engine import HMEConfig, HMEEngine
memory = HMEEngine(hme_config=HMEConfig(use_hann_window=False))
```

This does not switch to signed retrieval. The signed variant is an experimental
scoring ablation, not the production API. **The pinned storage component and its
Hann-on default remain unchanged** to preserve earlier results and compatibility;
a default change needs a versioned migration. For this tested identity-retrieval
workload, raw signed-cosine NN remains the reference choice. See the
[review response](docs/REVIEW_2026_09_25.md) for fixes and decision boundaries.

'''
replace_once("README.md", "## Evidence and limitations\n", section + "## Evidence and limitations\n")
replace_once("README.md", "The latest experiment, [HME-NN-2B]", "The earlier field experiment, [HME-NN-2B]")
replace_once("README.md", "The first **preregistered nearest-neighbor comparison found a negative result**.", "The first **preregistered matched-processed-vector comparison found a negative result**.")
replace_once("README.md", "The active suite now has **128** after conversation-harness development\nchecks.", "The active suite had **128** after conversation-harness development\nchecks and now has **138** after raw-baseline and direct-checkout regression tests.")
replace_once("CHANGELOG.md", "## 3.1.0 — restore optional field dynamics\n", '''## 3.1.0 — restore optional field dynamics

- Publish HME-NN-3: thirty preregistered seeds separating raw-input NN, processed-vector NN, Hann/query preprocessing, sign and field ablations. Retain all prior reports and unchanged pinned engine/default bytes.
- Fix direct-checkout execution of the independent audit and runtime example without an editable install; add isolated-interpreter regression tests. NumPy remains required.
- Document the explicit no-window numeric configuration and the negative symmetric-taper result. The active suite now has 138 tests; the archived suite remains 11 tests.
- Add guarded v3.1.0 release publication after version, integrity, self-test and active/historical test gates. Existing tags and releases are not replaced.
''')
replace_once("docs/EVIDENCE.md", "|---|---|---|\n", '''|---|---|---|
| [Raw-vector and Hann ablation](../experiments/raw_vector_baseline_v1/REPORT.md) | Unchanged pinned core; evaluator frozen at `7ef2789` after protocol `8a3f942` | Thirty seeds; default HME 42.21%, no-window HME 65.65%, experimental no-window signed HME 73.93%, raw signed NN 74.11% at sigma 1; all cells and raw predictions published |
| [Public-API cross-check](../evidence/review_crosscheck_2026_09_25.json) | Registered HME-NN-3 first seed, verified after publication in a separate Python/NumPy environment | All 640 direct HME predictions and 128 scalar raw-cosine predictions match the published first-seed high-noise data; verification, not a new efficacy study |
''')
replace_once("docs/EVIDENCE.md", "## Preregistered baseline comparison\n", '''## Raw inputs versus matched processed inputs

HME-NN-1 and HME-NN-2A compared methods using the same Hann-processed stored
vectors. Their results answer that registered question, not how HME compares
with raw-input NN. [HME-NN-3](../experiments/raw_vector_baseline_v1/REPORT.md)
adds the missing raw-input baseline without rewriting those reports. At sigma
1.0, default HME minus raw signed NN is -31.90 percentage points (95% interval
[-33.26, -30.44]). Turning Hann off improves HME by 23.44 points; tapering queries
too worsens it by 13.44 points. These decomposition contrasts are descriptive.
The no-window signed variant is close to raw NN, but the study does not register
an equivalence claim or demonstrate a field advantage. No speed or storage
claim is made. Ten regression tests bring the active suite to 138; earlier
counts in this index describe their original runs and remain unchanged.

## Preregistered baseline comparison
''')
replace_once("docs/KNOWN_LIMITATIONS.md", "- The encoder and query path apply different preprocessing, and absolute similarity cannot distinguish sign/global phase reversal.\n", "- The frozen default encoder Hann-tapers stored vectors but not numeric queries; absolute similarity cannot distinguish sign/global phase reversal. [HME-NN-3](../experiments/raw_vector_baseline_v1/REPORT.md) finds large losses versus raw signed-cosine NN. Explicit `HMEConfig(use_hann_window=False)` recovers much of this gap but does not change the absolute score. Tapering queries too made the tested workload worse; it is not a general repair. The default remains frozen for compatibility.\n")
with Path("docs/REPRODUCIBILITY.md").open("a", encoding="utf-8") as f:
    f.write('''
## Direct-checkout scripts and raw-baseline follow-up

With NumPy installed, `python tests/hme_independent_audit.py` and
`python examples/runtime_demo.py` now resolve the checkout without an editable
installation or `PYTHONPATH`. Explicit audit `--engine PATH` remains supported.
Isolated-interpreter tests run both scripts from unrelated working directories.
The audit harness changed for source discovery, not its numerical calculations;
old saved audit reports retain their original harness hashes.

[HME-NN-3](../experiments/raw_vector_baseline_v1/REPORT.md) records the protocol
commit, evaluator registration, source and dataset hashes, all 120 seed/noise
cells and per-query predictions. Its reproduction command verifies frozen
sources against the public evaluator registration. Use a complete Git checkout
and a fresh output directory. Core, runtime, dynamics and archived source pins
are unchanged. A [post-publication check](../evidence/review_crosscheck_2026_09_25.json)
compared all queries in one registered high-noise seed with the public HME API
and an independent scalar raw-cosine calculation in a second environment.
''')
Path("docs/REVIEW_2026_09_25.md").write_text('''# Response to the independent HME review

The owner supplied an external code-evaluation summary on 2026-09-25. Its
five-seed cross-check source and seeds were not provided, so the new study is
a separately preregistered follow-up, not a reproduction of its exact counts.

## What changed

The independent audit and runtime example now run directly from a NumPy-equipped
checkout, without `pip install -e` or `PYTHONPATH`. The audit prefers its adjacent
checkout engine; an explicit `--engine PATH` still takes priority. Regression tests
copy the scripts and source into an isolated checkout, disable user/import-path
shortcuts, and execute from an unrelated working directory.

[HME-NN-3](../experiments/raw_vector_baseline_v1/REPORT.md) adds raw signed and
absolute cosine, the previous processed-vector baseline, symmetric tapering,
no-window HME, field erasure and a scoring-only signed variant. Protocol commit
`8a3f9420d74424d9bd4490292e60d1bc4adeee3c` preceded implementation and evaluation;
evaluator commit `7ef2789f2ce58ab67e2778a9c1fefb26f99b982d` was pushed before the
registered seeds ran. Results were published separately at `5347423`.
Thirty fixed seeds and all 120 seed/noise cells completed without deviations.
The active test suite is 138 tests, with 11 separately labelled archived tests.

The README and evidence index now distinguish raw-input retrieval from the
previous matched-processed-vector comparison. Old experiments remain unchanged.
The v3.1.0 release workflow validates version, manifests, source pins, self-test
and both test suites before publishing. It never overwrites an existing tag
or release; publication targets the exact tested main commit.

## What the evidence says

At high noise (sigma 1.0), raw signed NN achieved 74.11%, default HME 42.21%,
no-window HME 65.65%, and experimental no-window signed HME 73.93%.
No-window recovered 73.5% of the default-to-raw gap (descriptive ratio).
Applying Hann to queries as well reduced HME to 28.78%; symmetry alone did not
repair information attenuated or discarded by the taper.
The signed no-window difference versus raw NN was -0.18 percentage points,
95% interval [-0.57, +0.21]. Numerical closeness is not a superiority or
registered equivalence claim. This study measures accuracy, not latency or bytes.

The field-erased no-window arm matched absolute-cosine rankings on every query.
Erasing the ledger still left no identity hits. HME-NN-2A had already tested
sign before this review, and HME-NN-2B had already found no practical benefit
from its candidate-specific field readout. Those separate scopes are preserved.

## Configuration and compatibility decision

For numeric-vector experiments, opt out explicitly:

```python
from hme_engine import HMEConfig, HMEEngine
memory = HMEEngine(hme_config=HMEConfig(use_hann_window=False))
```

The production API still uses absolute similarity; the signed arm lives only
in experimental code. No pinned engine, runtime or dynamics source changed.
The historical Hann-on default remains intact because v3.1 preserves the v3.0
storage component byte-for-byte. Silently changing it would invalidate that
contract, payload hashes and historical reproduction. A future default change
must be separately versioned with a migration decision. The review therefore
produced a tested explicit configuration and new evidence, not a silent rewrite.
For this tested synthetic identity-retrieval workload, raw signed-cosine NN
remains the practical reference. No semantic conversation-memory efficacy,
calibrated confidence or field-only identity capability is established here.
''', encoding="utf-8")
Path("docs/releases").mkdir(exist_ok=True)
Path("docs/releases/v3.1.0.md").write_text('''# HME v3.1.0

HME is a standalone, source-available experimental memory engine using NumPy.
This release packages the restored optional field runtime and spatial dynamics,
the unchanged v3.0 storage component, reproducible evaluations and checkout fixes.
It supersedes the old v2.2.0 download without replacing the historical archive.
Status remains alpha; the existing proprietary evaluation license is unchanged.

## Included

- Optional field/agent runtimes, state-derived salience, events, telemetry,
  lineage, spatial diffusion and field-signature bridges.
- Direct-checkout audit and runtime example that work with NumPy installed,
  without an editable package install or `PYTHONPATH`.
- HME-NN-1, HME-NN-2A, HME-NN-2B and the new preregistered HME-NN-3 raw-input
  baseline, with protocols, raw observations, source pins and limitations.
- Conversation-memory evaluation harness for local Ollama; no real-model
  conversation outcomes have been established.

## Retrieval evidence

In HME-NN-3's thirty-seed, 128-item, dimension-16 high-noise condition:

| Method | Mean top-1 accuracy |
|---|---:|
| Raw signed-cosine NN | 74.11% |
| Default HME | 42.21% |
| HME without Hann window | 65.65% |
| Experimental no-window signed HME | 73.93% |

Disabling Hann recovered 73.5% of the default-to-raw-NN gap, descriptively.
Tapering queries too made retrieval worse. The signed no-window arm's difference
from raw NN was -0.18 points, with a 95% interval [-0.57, +0.21]; no superiority,
equivalence, field advantage, semantic-memory benefit or performance claim follows.
All 120 registered seed/noise cells completed without deviations.

The Hann-on default and all pinned storage/runtime/dynamics bytes remain unchanged.
Use `HMEEngine(hme_config=HMEConfig(use_hann_window=False))` to opt out explicitly;
this does not enable experimental signed retrieval. Raw cosine NN remains the
reference for the tested identity task. Scores are not calibrated confidence.

## Validation and reproduction

The release is gated on version consistency, payload/source/archive SHA-256
checks, license parity, the deterministic self-test, 138 active tests and
11 separately labelled historical tests. Earlier reports retain their original
source hashes and test counts. The main README, docs/EVIDENCE.md and
experiments/raw_vector_baseline_v1/REPORT.md contain reproduction instructions.
The release tag points to the exact tested main commit. No existing tag is moved.
''', encoding="utf-8")
crosscheck = json.loads(Path(".github/review-crosscheck.json").read_text())
Path("evidence/review_crosscheck_2026_09_25.json").write_text(json.dumps(crosscheck, indent=2) + "\n", encoding="utf-8")
for name in (".github/review-finalize.py", ".github/review-crosscheck.json", ".github/workflows/review-finalize.yml"):
    Path(name).unlink(missing_ok=True)
