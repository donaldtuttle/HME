# Changelog

## 2026-08-24 - Public front door and release preparation

- added a plain-language purpose statement, use-case map, architecture sketch,
  status panel, repository map, and credibility-scan badges;
- separated baseline behavior from the default-off DEVELOP C(ψ) salience
  overlay and stated that no efficacy claim follows from implementation;
- updated the active engine pin from the earlier public baseline to the
  current `1caff957…` source;
- found that the SFD bridge test still asserted one earlier exact receipt after
  the active engine changed;
- initially rebound the bridge to one active-engine receipt, then discovered a
  second complete numeric-byte receipt on a heterogeneous Python 3.12 runner;
- preserved the stable source, signature, trajectory, glyph, top-hit, and score
  invariants while classifying the two observed `(artifact, payload, pattern)`
  tuples atomically;
- made unknown or mixed byte tuples fail validation instead of pretending that
  floating-point and FFT byte identity is portable across every runner;
- recorded the numerical portability boundary, diagnostic CI runs, and future
  canonicalized-hashing option without changing engine behavior;
- moved the detailed QOFT/QOSMOS operator crosswalk into
  `docs/QOFT_QOSMOS_CONTEXT.md`;
- clarified `MANIFEST.sha256` scope, enforced it in CI, and added a
  GitHub-native release/tag plan;
- enforced byte parity between the root and portable HME licenses in CI;
- added a narrow license grant for local execution of unmodified copies for
  non-commercial evaluation, testing, and result reproduction;
- kept modification, redistribution, derivatives, hosted use, production use,
  commercial use, and external contributions closed.

## 2026-08-23 - Standalone HME positioning

- made HME the primary repository and package identity;
- reframed the public description around deterministic memory, reconstruction, provenance, retrieval, and lineage;
- retained QOFT/QOSMOS only as origin and compatibility context;
- left the engine implementation, API, evidence, and historical provenance unchanged.

## 2026-08-23 - Public visibility with proprietary rights

- published the repository for public inspection and research discussion;
- retained copyright and all rights under a proprietary rights notice;
- made explicit that public visibility does not make the project open source;
- declared the repository owner-maintained and closed to external contributions;
- preserved the HME implementation, evidence, operator contracts, and DEVELOP/noncanonical classification unchanged.

## 2026-08-23 - Initial private repository assembly

- selected the later HME operator-conformance source as active;
- preserved the pre-conformance engine under `legacy/`;
- isolated HME-specific code, governance references, audit evidence, and SFD bridge;
- corrected two audit write glyphs from `Θλ` to `Σ◯`;
- added packaging, deterministic tests, CI, and claim-boundary documentation.
