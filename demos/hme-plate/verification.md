# HME Plate verification

Checked 2026-09-26 against HME main commit
`3e93c66f0a2eadf7ad840d963276cdfead4836c7`.

| Check | Result |
| --- | --- |
| Clean `npm ci` and production build | Pass |
| Model tests and source self-checks | 16 passed |
| React/jsdom interaction regressions | 6 passed |
| Numeric comparison to pinned Python engine | 26/26 cases passed at absolute tolerance 1e-10 |
| Relative static asset build check | 1 passed |
| Optional Sites worker/packaging checks | 4 passed |
| Python engine built-in self-test | PASS |
| Existing Python test suite | 233 passed |
| Archived v2.2 Python test suite | 11 passed |
| Local desktop/mobile browser rendering | Blocked by unavailable preview service; see design-qa.md |

Numeric cases cover Hann on/off, clipped/interior writes, field erasure,
positive/antipodal/spatial queries, and zero input at threshold endpoints.
Field values, every score component, rankings, outcome, decoded vector and
surface magnitudes are checked. Maximum absolute error was
`1.2212453270876722e-15` (scores). Field error was
`1.702806641430691e-16`, decoded-vector error `1.6653345369377348e-16`,
and surface-magnitude error `2.688821387764051e-17`.

Regression coverage includes Hann-off followed by reset, probe threshold and
stale-result labeling, all-zero vectors, numeric validation, symbol writes,
query modes, field controls, keyboard placement and ledger/field ablations.
jsdom does not render the canvas or establish visual/accessibility parity.

Local versions: Node 24.19.0, Python 3.12.14, NumPy 2.3.5. CI uses Node 22 and
Python 3.12 for the demo and preserves the existing Python regression matrix.
CI retains the static build and machine-readable numeric report as artifacts.

The Python engine, source pins, runtime and experimental implementations are
unchanged. Symbol generation and hashing intentionally remain viewer-specific;
see SOURCE.md. These tests establish the stated real-numeric compatibility,
not performance, full API equivalence, or scientific validation of the model.
