# Changelog

## 2026-08-24 - Public front door and release preparation

- added a plain-language purpose statement, use-case map, architecture sketch,
  status panel, repository map, and credibility-scan badges;
- separated baseline behavior from the default-off DEVELOP C(ψ) salience
  overlay and stated that no efficacy claim follows from implementation;
- updated the active engine pin from the earlier public baseline to the
  current `1caff957…` source;
- found that the SFD bridge test still asserted the historical v2.2 receipt
  after the active engine changed;
- bound the bridge receipt to the active engine SHA-256 and made the script and
  pytest consume one shared expected-receipt object;
- reproduced the active receipt exactly across Python 3.10, 3.12, and 3.13 CI
  lanes, while retaining the older receipt as historical v2.2 evidence;
- moved the detailed QOFT/QOSMOS operator crosswalk into
  `docs/QOFT_QOSMOS_CONTEXT.md`;
- clarified `MANIFEST.sha256` scope and added a GitHub-native release/tag plan;
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
