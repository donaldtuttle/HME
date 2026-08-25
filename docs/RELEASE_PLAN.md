# HME GitHub Release Plan

This repository currently has two useful version surfaces that should not be
collapsed into one unlabeled tag.

## Recommended releases

### `v2.2.0-baseline`

**Target commit:** `0c7988eb79aa1e1e91242bd505cbf10db439f636`  
**Engine SHA-256:** `f81fb49e265d83f5206220584dfc6cabf28aeee5266aca33654182be1549c080`

Purpose:

- first GitHub-native standalone HME baseline;
- deterministic field-plus-ledger engine;
- portable HME skill and public manifest;
- independent audit evidence;
- no C(ψ) salience overlay.

Suggested release title:

```text
HME v2.2.0 Baseline - deterministic field-plus-ledger memory
```

### `v2.3.0-develop.1`

**Target:** current DEVELOP head after this documentation PR  
**Engine SHA-256 before this documentation-only change:**  
`1caff9577e8a4bdaa2b0510c79673035081a967a25f15067bfa8ce99ccca6d11`

Purpose:

- carries the optional C(ψ) write-gain, retrieval-reranking, and
  inscription-rejection channels;
- keeps all three switches disabled by default;
- includes the preregistered C0-C7 protocol and measurement harness;
- makes no efficacy or promotion claim.

Suggested prerelease title:

```text
HME v2.3.0-develop.1 - C(ψ) salience instrumentation, default off
```

Mark this release as **pre-release** until the C0-C7 evidence packet is complete
and reviewed.

## Release checklist

1. Confirm the target commit.
2. Run `python qosmos_hme_engine.py --self-test`.
3. Run `pytest -q`.
4. Run the independent audit.
5. Verify `MANIFEST.sha256`.
6. Record Python, NumPy, and platform versions.
7. Attach or link the machine-readable evidence packet.
8. State the claim boundary and known limitations.
9. Confirm that the release license text matches `skills/hme/LICENSE.txt`.
10. Create the tag and GitHub Release from the same commit.

## Version rule

Do not tag current DEVELOP head as the historical `v2.2.0-baseline`. A tag is a
coordinate, not a mood ring: it must resolve to the exact source whose hashes
and evidence it names.
