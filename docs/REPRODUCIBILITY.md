# Reproducibility

The active module is `hme_engine.py`; its source pin and the prior source pin are recorded in `SOURCE_PINS.sha256` and `SOURCE_PROVENANCE.json`.

```bash
sha256sum --check MANIFEST.sha256
sha256sum --check SOURCE_PINS.sha256
python hme_engine.py --self-test
python -m pytest -q
python tests/hme_independent_audit.py --engine ./hme_engine.py --output outputs/hme_audit.json
```

The tests compare the extracted core with the byte-preserved v2.2 engine under the same numeric/string inputs, boundary placements, noise queries, and all eight salience switch combinations. They compare fields, processed payloads, patterns, scores, decoded outputs, and candidate order after translating artifact IDs. Schema differences are tested separately.

Audit output records Python, NumPy, engine and harness hashes, configuration, seed, deterministic checks, linear-superposition reconstruction, noise sweeps, and field/ledger ablations. It supplies implementation evidence, not a nearest-neighbor comparison or calibrated confidence.

Historical evidence remains inside its complete archive. See [archive instructions](../archive/README.md) to rerun the original tests and bridge. Do not compare a v3 artifact ID with a v2.2 golden ID. Numeric-byte hashes may vary across numerical backends even when rankings and scores agree.
