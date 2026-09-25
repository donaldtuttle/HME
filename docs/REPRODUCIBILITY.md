# Reproducibility

The storage module is `hme_engine.py`; optional controllers and dynamics live in `hme_runtime.py` and `hme_dynamics.py`. Their source pins and the prior source pins are recorded in `SOURCE_PINS.sha256` and `SOURCE_PROVENANCE.json`. The storage source stays byte-identical to 3.0 (including its component engine ID); the package/runtime version is 3.1.0.

```bash
sha256sum --check MANIFEST.sha256
sha256sum --check SOURCE_PINS.sha256
python hme_engine.py --self-test
python -m pytest -q
python tests/hme_independent_audit.py --engine ./hme_engine.py --output outputs/hme_audit.json
python examples/runtime_demo.py
```

The tests compare the extracted core with the byte-preserved v2.2 engine under the same numeric/string inputs, boundary placements, noise queries, and all eight salience switch combinations. They compare fields, processed payloads, patterns, scores, decoded outputs, and candidate order after translating artifact IDs. Schema differences are tested separately.

Install `.[test,legacy-test,visualization]` to include raster/bridge and plotting checks. `tests/test_hme_runtime.py` adds full tick-sequence parity for both restored controllers, all eight salience settings and three event modes. It checks actual event hashes/flags, automatic salience, replay, adapters, array-only imports, diffusion/drive ablations, the raster-signature bridge, plots and GIF export. Reference code is loaded only by tests from hash-checked archived files. `evidence/runtime_restoration_validation.json` records the local run; historical 3.0 evidence is retained unchanged.

Audit output records Python, NumPy, engine and harness hashes, configuration, seed, deterministic checks, linear-superposition reconstruction, noise sweeps, and field/ledger ablations. It supplies implementation evidence, not a nearest-neighbor comparison or calibrated confidence.

Historical evidence remains inside its complete archive. See [archive instructions](../archive/README.md) to rerun the original tests and bridge. Do not compare a v3 artifact ID with a v2.2 golden ID. Numeric-byte hashes may vary across numerical backends even when rankings and scores agree.
