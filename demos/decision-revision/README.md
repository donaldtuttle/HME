# Decision Revision Bench

Try a decision task by hand: read an earlier rule and a later update, decide
whether to keep the current choice, change it or wait, then check both the
answer and its supporting evidence.

**DESIGN / illustrative fixture.** This is a browser interface for
[HME-CM-REV-1](../../experiments/decision_revision_v1/README.md), with 32 invented
histories. It makes no model calls. The HME field is not connected.

## User guide

Start with the [complete user guide](../../experiments/decision_revision_v1/USER_GUIDE.md).
The same guide is available in the application's **Guide** tab and as a Markdown
download. Select **Open the worked example** to begin with Alder and Birch.

1. Read the question and the selected packet.
2. Replace the placeholder JSON with both decisions and their evidence IDs.
3. Select **Score this response**, then inspect primary, target, control and
   action-only outcomes.
4. Select **Reveal evaluator key** after scoring to inspect the answer and pair.
5. Use **Checks** for fixture diagnostics or **Export** for the complete histories.

The placeholder intentionally scores zero. Editing it clears the previous score
and reveal. Drafts are separate for each history/packet while the Read view is
mounted; reloading or leaving that view resets its in-memory state.

## Run locally

From the repository root, with Node 22.18 or newer, npm, and Python 3:

```bash
cd demos/decision-revision
npm ci
npm run dev
```

Open the address printed by Vite. Build a static copy with:

```bash
npm run build
npm run preview
```

The complete static application is in `dist/client/`. Relative URLs support a
repository subpath. Copy that directory's contents to the desired static host.
CI retains it as an artifact; this addition does not change HME Plate's Pages
deployment. The [original hosted bench](https://decision-revision.grok.me/) is
a separate deployment and is not a commit-pinned copy of this port.

## Checks

```bash
npm test
npm run typecheck
npm run build
npm run test:build
```

Core regressions check scorer integrity, baselines, one-hop ledger traversal,
support combinations and guide consistency. React DOM tests check scoring,
reveal gating, stale results, packet/history drafts and source-download paths.
Build checks validate local relative assets and byte-identical core downloads.
See [verification.md](verification.md) for the actual checks run and their limits.

## Source layout and boundaries

- `src/Workbench.tsx` and `src/Guide.tsx`: imported interface with portable imports
  and relative archive links.
- `../../experiments/decision_revision_v1/`: generator, policy solver, packet
  builders, scorer, diagnostics, user guide and core tests.
- `scripts/package_source.py`: deterministic core archive built from the current
  source before development or production build; generated ZIPs are not committed.
- IBM Plex fonts reuse HME Plate's locally bundled fonts and their existing OFL
  notices; this demo does not need a font CDN or a Grok runtime.

The answer key ships to the browser for teaching and inspection. Reveal gating
is a UI aid, not secure blinding. A registered evaluation needs a separate
runner that withholds hidden labels from packet construction and the reader.
Packet coverage and oracle counts do not establish HME efficacy.

HME material remains under the repository license. React, Vite, Tailwind CSS,
Lucide and test dependencies retain their package licenses. See
[SOURCE.md](SOURCE.md) for provenance and the import boundary.
