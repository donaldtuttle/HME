# Decision Revision Bench verification

Checked 2026-10-02 against HME base commit
`11b8d916b7708d3b219984d94d9919fd91519c43`, using the uploaded source recorded in
[source-provenance.json](source-provenance.json).

| Check | Result |
| --- | --- |
| Imported core and guide source hashes | All 17 files match the upload byte-for-byte |
| Core fixture tests | 15 passed across two suites |
| Accepted citation combinations | 44 checked by the core regressions |
| Invalid answers or absent-evidence cases | 544 rejected by the core regressions |
| Corpus preflight | All 13 checks passed on 32 histories |
| React/jsdom interface regressions | 4 passed |
| TypeScript type checking | Passed |
| Vite production build | Passed |
| Local relative assets and font packaging | Passed |
| Built source download | All 20 files match current core bytes and paths |

The interface checks cover placeholder score 0, worked-answer score 1, reveal
gating, stale-score/key clearing after an edit, independent history/packet drafts,
malformed input, incomplete-packet failure, subpath source links, and the
16/32 action-and-option retain baseline. Its grounded result remains 0/32.

Local versions: Node 24.19.0 and npm 11.9.0. The new CI workflow uses Node 22
and Python 3.12, installs the committed npm lockfile, and retains the static build
and diagnostic JSON. A CI run is separate from the local checks above.

These are functional fixture and DOM checks. jsdom does not verify rendered
desktop/mobile layout or screen-reader behavior. The hosted Grok source was
visually inspected separately; that is not rendered-browser verification of
this static port. Port-specific visual and accessibility checks remain pending.
The existing Python engine suite was not rerun locally for this import; repository
CI retains its normal Python and source-integrity checks.

All packet coverage, oracle outcomes and baseline counts concern the illustrative
fixture. No model was called, no HME field adapter was connected, and no
registered decision-revision evaluation or efficacy result was produced.
