# Decision Revision Bench source and port boundary

Owner-authorized repository import from `grok-workspace_v3(1).zip`, supplied
2026-10-02. The filename's `v3` is not a software version claim.
[`source-provenance.json`](source-provenance.json) records the archive SHA-256
and individual hashes of the imported core, guide, interface, stylesheet and
favicon. The archive itself is not committed.

All 17 files originally under `experiments/decision_revision_v1/` are imported
byte-for-byte. The README, dependency-free package commands and diagnostic CLI
are new repository integration files. No fixture policy, source text, packet
construction or scorer behavior was changed during this import.

The interface is ported into a small React/Vite static shell, following the
existing HME Plate demo layout. Its core imports resolve to the shared experiment
directory. The Guide import becomes local, and archive links become relative
so a repository subpath works. Existing colors, controls and screen copy are
retained. Fonts reuse the existing HME Plate assets and SIL Open Font Licenses.

The Grok-specific TanStack/server/auth/database/PWA scaffold, generated builds,
editor instructions, logs, prior screenshots and pasted patch attachment are
not part of the portable application. This is a separate repository port; the
uploaded workspace and hosted Grok deployment are unchanged.

The two imported core test files contain 15 tests. Their old update notes are
historical reports, not new verification. Current results belong in
[verification.md](verification.md).

The hybrid arm remains identical to projected lexical NN and is explicitly
`MECHANISM_NOT_TESTED`. There is no reader-model integration, semantic embedding
adapter, CM-1 field bridge, preregistration or held-out result in this import.
