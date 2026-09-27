# HME Plate browser demo

Explore the released HME field-plus-ledger model: place numeric or symbol
writes, query the plate, inspect ranking components, and erase the field or
ledger independently. This is a client-side educational instrument; no Python
server, model provider, login, API key or Grok runtime is required.

This port preserves the updated [HME Plate](https://hme-plate.grok.me/) interface.
It includes the corrected Hann reset ordering, threshold-aware noise probe,
previous-probe settings notice, and explicit zero-vector display.

## Run locally

From the repository root, with Node 22 or newer and npm installed:

```bash
cd demos/hme-plate
npm ci
npm run dev
```

Open the local address printed by Vite. To build a static distribution:

```bash
npm run build
npm run preview
```

`dist/client/` contains the complete static app, including fonts and the favicon.
Relative asset paths support a repository subpath such as `/HME/`. Copy the
**contents** of that directory into the chosen static hosting root. This PR
does not enable GitHub Pages or publish a live deployment. The starter also
retains its optional Sites packaging under `dist/server/` and `dist/.openai/`;
those directories are not needed for ordinary static hosting.

## What to try

1. Select a ledger item and vary query noise; inspect the three score components.
2. Switch to **Place query** and click the field, or use arrow keys (Shift moves
   four cells). Select **Phase** to change the field view.
3. Enter a numeric item or an exact symbol, select its write location, and encode.
4. **Erase field, keep ledger** removes the pattern-score contribution.
5. **Drop ledger, keep field** keeps the pattern but removes identity hits and
   displays **All zeros** for the decoded vector. Reset to restore the examples.
6. Set the retrieval threshold and run the eight-seed probe. Its report records
   the threshold used; changing that setting labels the prior result as stale.

## Contract and limitations

The numeric model follows the pinned `hme_engine.py` score and preprocessing
contract. It uses a direct DFT implementation of the Fourier transforms, a
64×64 complex-valued plate and 16-point patterns by default. The displayed
“energy” is the field's Euclidean norm, following the source viewer's label.

- Scores are uncalibrated ranking values. `MATCH` means threshold eligibility.
- The decoded vector blends retained processed payloads. The displayed inverse
  transform is a separate field-window output.
- The browser accepts real numeric inputs. Symbol RNG, rounded hashes and viewer
  IDs intentionally differ from NumPy/canonical artifact IDs.
- This represents the released model, not the optional consolidation adapter,
  SAL-1, semantic-memory performance, or a reproduction of published NN studies.
- State is in-memory and resets on reload. The demo is not a persistence format.

See [SOURCE.md](SOURCE.md) for captured asset hashes and exact port boundaries,
[verification.md](verification.md) for checks, and [design-qa.md](design-qa.md)
for the explicitly pending rendered-browser verification.

## Checks

```bash
npm test
npm run test:parity
npm run build
npm run test:build
npm run test:sites
```

`test:parity` also needs Python 3.10+ and NumPy (CI pins NumPy 2.3.5). It checks
26 input fixtures against the repository's actual engine, first validating its
source hash. It compares full field arrays, score components, rankings, outcomes,
decoded vectors and decoded-surface magnitudes with `atol=1e-10, rtol=0`.
Symbol identity and hashes are outside that comparison. The JSON result is written
to ignored `outputs/parity.json`.

`npm test` runs model checks and React DOM interactions under jsdom. These are
not raster/layout, mobile, canvas, or screen-reader checks. Build checks confirm
relative, local asset references and optional starter packaging.

## Source layout

- `src/model.js`: recovered numerical model, query/probe helpers and source checks.
- `src/App.jsx`: recovered React controls and field/result rendering.
- `src/styles.css`, `src/fonts.css`, `src/assets/fonts/`: original visual styles
  and locally bundled IBM Plex fonts.
- `tests/fixtures/numeric-cases.json`: deterministic input cases.
- `scripts/check_parity.py`: independent Python/JavaScript comparison.

HME material remains under the repository license. Bundled IBM Plex fonts retain
their SIL Open Font License files. See [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md).
