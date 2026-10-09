# HME-MO-1 recovery and validation replay

Status: **DESIGN / DEVELOP. Not registered. No confirmatory evaluation.**

## Recovered implementation

The experiment was absent from main, but the original implementation remained
available as GitHub commit
[`a0d123bca583deb790cfbb33346f3cd3e3b4b21c`](https://github.com/donaldtuttle/HME/commit/a0d123bca583deb790cfbb33346f3cd3e3b4b21c).
Its parent, `a4d871618e31b8184c2cf5c2e13c9256accd254d`, is also the main branch
base inspected for this recovery. Recovering the experiment required no changes
to the production engine or historical experiments.

The recovered modules implement 128 items in 16 families, dimension 16,
four shared-variance settings, matched random and similarity placements,
separated patches, four noise levels, six retrieval arms, corpus-level paired
bootstrap statistics, six predeclared contrasts, storage and latency accounting,
and source/registration guards. The proposed confirmatory study retains 50
independent corpora and 20,000 bootstrap resamples.

The original protocol, implementation map, development report, summary,
receipt, frozen baseline, plots, source provenance, and local source-history
bundle were recovered. The bundle verifies against its recorded base commit.
The separate `HME-MO-1-development-records.zip` was not recovered. Its historical
inventory and checksum remain in the original receipt; this recovery does not
claim to verify the contents of that ZIP.

The original numerical modules, configuration, baseline selection, and 28-test
suite are unchanged. This recovery adds two complete-runner guard tests,
this report, a recovery receipt, a README link, and fresh raw validation records.
The root manifest inventories the added files.

## Fresh checks on October 9, 2026

| Check | Result |
|---|---|
| Current repository tests, including recovered experiment | 458 passed |
| Archived v2.2 tests | 11 passed |
| Built-in engine self-test | PASS; deterministic field/artifact and correct top hit |
| Imported historical source hashes | All matched recovered pins |
| Production/source/archive integrity manifests | Passed |
| Development primary-cell smoke | Both planned exposed corpora completed |
| Tuning replay | All 12 exposed tuning corpora completed; frozen selection JSON identical |
| Validation replay | All 12 exposed validation corpora completed; no failures |
| Summary comparison with October 6 | Every common field identical, including all primary means and six-contrast analysis |
| Complete-runner proposed-status guard | Both tests blocked before data generation |

The validation replay covers every declared shared-variance/noise/preprocessing
cell, all principal layouts, content shuffle, association permutation,
cached/uncached readout controls, and canvas translation checks.
The selected vector rule remains raw representation, eight neighbors,
lambda 0.25. No tuning choice was changed after replaying validation.

| Primary validation method | Sibling precision at 5 | Exact top-1 |
|---|---:|---:|
| Similarity placed hybrid | 25.055% | 36.995% |
| Random matched hybrid | 25.104% | 37.207% |
| Raw signed nearest neighbor | 38.815% | 70.492% |
| Frozen vector aggregate | 42.852% | 69.743% |

The proposed diagnostic conclusion remains `ADVANTAGE_NOT_ESTABLISHED`.
This replay is reproducibility evidence on already exposed validation data;
it supplies no new independent confirmatory evidence.

## Reproducibility records

`recovery_validation/development`, `recovery_validation/tune`, and
`recovery_validation/validation` contain complete fresh corpus records,
run manifests, completion receipts, and summaries or baseline selection.
`RECOVERY_RECEIPT.json` inventories their SHA256 hashes and records exact summary
and baseline comparisons. Each gzip file contains a JSON corpus record and can
be read with Python's `gzip.open` and `json.load`.

From the repository root, use new output paths:

```bash
python -m pytest -q
python -m experiments.meaningful_overlap_v1.evaluate development --output outputs/new-mo-development
python -m experiments.meaningful_overlap_v1.evaluate tune --output outputs/new-mo-tune
python -m experiments.meaningful_overlap_v1.evaluate validation --output outputs/new-mo-validation
sha256sum --check MANIFEST.sha256
sha256sum --check SOURCE_PINS.sha256
sha256sum --check archive/v2.2.sha256
```

Fresh run manifests retain the actual pre-publication worktree status and source
hashes. They are execution records, not a registration or a claim that the
delivered tree was committed before these development runs. Timings and resource
measurements belong to this host; the old report's costs remain historical.
The current and archived test processes completed before the full validation
replay began. The primary-cell smoke overlapped the initial regression checks,
so its timings should not be used as benchmark measurements.

## Remaining review and evidence gaps

Protocol approval, immutable registration, and separate execution authorization
are still required. No `REGISTRATION_APPROVAL.json` is supplied, and protocol
status remains `DESIGN / DEVELOP`. No reserved test corpus was generated or
inspected. The live approved registration path remains unverified; its remote
proof checks have mocked tests only. Cross-version CI results must be checked
on this pull request. Shared-feature binding, an encoder redesign, production
adoption, a release, and merging are outside this recovery.
