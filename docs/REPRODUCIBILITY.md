# Reproducibility

The storage module is `hme_engine.py`; optional controllers and dynamics live in `hme_runtime.py` and `hme_dynamics.py`. Their source pins and the prior source pins are recorded in `SOURCE_PINS.sha256` and `SOURCE_PROVENANCE.json`. The storage source stays byte-identical to 3.0 (including its component engine ID); the package/runtime version is 3.1.0.

```bash
sha256sum --check MANIFEST.sha256
sha256sum --check SOURCE_PINS.sha256
python hme_engine.py --self-test
python -m pytest -q
python tests/hme_independent_audit.py --engine ./hme_engine.py --output outputs/hme_audit.json
python examples/runtime_demo.py
python scripts/collect_current_evidence.py --output outputs/current_release_v3_1.json
```

The tests compare the extracted core with the byte-preserved v2.2 engine under the same numeric/string inputs, boundary placements, noise queries, and all eight salience switch combinations. They compare fields, processed payloads, patterns, scores, decoded outputs, and candidate order after translating artifact IDs. Schema differences are tested separately.

Install `.[test,legacy-test,visualization]` to include raster/bridge and plotting checks. `tests/test_hme_runtime.py` adds full tick-sequence parity for both restored controllers, all eight salience settings and three event modes. It checks actual event hashes/flags, automatic salience, replay, adapters, array-only imports, diffusion/drive ablations, the raster-signature bridge, plots and GIF export. Reference code is loaded only by tests from hash-checked archived files. `evidence/runtime_restoration_validation.json` records the local run; historical 3.0 evidence is retained unchanged.

Audit output records Python, NumPy, engine and harness hashes, configuration, seed, deterministic checks, linear-superposition reconstruction, noise sweeps, and field/ledger ablations. It supplies implementation evidence, not a nearest-neighbor comparison or calibrated confidence.

Historical evidence remains inside its complete archive. See [archive instructions](../archive/README.md) to rerun the original tests and bridge. Do not compare a v3 artifact ID with a v2.2 golden ID. Numeric-byte hashes may vary across numerical backends even when rankings and scores agree.

The [evidence index](EVIDENCE.md) maps each saved report to its tested version.
The current-release collector reruns both test suites separately, the unchanged
retrieval harness on five fixed seeds, and 20 short current-runtime traces. It
requires the three engine modules to match the named Git commit and source pins;
the collector's own hash is recorded separately. It aborts on failed or skipped
tests. Retrieve current CI outputs from the workflow's `hme-results-*` artifact;
those files belong to the workflow's commit and are not copied from saved reports.

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
