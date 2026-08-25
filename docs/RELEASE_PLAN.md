# HME GitHub Release Plan

This repository currently has two useful version surfaces that should not be
collapsed into one unlabeled tag.

## Recommended releases

### `v2.2.0-baseline`

**Target commit:** `0c7988eb79aa1e1e91242bd505cbf10db439f636`  
**Engine SHA-256:** `f81fb49e265d83f5206220584dfc6cabf28aeee5266aca33654182be1549c080`  
**Recorded bridge artifact:** `d902825c52772941b345`

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

**Target:** current DEVELOP head after this PR  
**Active engine SHA-256:**  
`1caff9577e8a4bdaa2b0510c79673035081a967a25f15067bfa8ce99ccca6d11`

Purpose:

- carries the optional C(ψ) write-gain, retrieval-reranking, and
  inscription-rejection channels;
- keeps all three switches disabled by default;
- includes the preregistered C0-C7 protocol and measurement harness;
- binds bridge validation to the active source hash and stable semantic
  invariants;
- recognizes two complete numeric-byte receipt tuples observed across
  heterogeneous CI runners, while rejecting mixed or unknown tuples;
- makes no efficacy or promotion claim.

Suggested prerelease title:

```text
HME v2.3.0-develop.1 - C(ψ) salience instrumentation, default off
```

Mark this release as **pre-release** until the C0-C7 evidence packet is complete
and reviewed.

## Current bridge release gate

Stable invariants:

```text
signature_hash   7fef693477ffaf55104f12f25be9b91b72a8ab8e4aed8d13c4c3604fa5719ce9
trajectory_hash  e90921fbd2fd990efab3b684249de68a28e7186e8fc226d2f3ca3a4038e8f5db
write_glyph      Σ◯
retrieval_score  0.9307851800354883 ± 1e-12
top_is_artifact  true
```

Recognized complete byte receipts:

```text
numeric_bytes_7264  artifact 7264c7cc7b27aceb15f1
numeric_bytes_d902  artifact d902825c52772941b345
```

See [`REPRODUCIBILITY.md`](REPRODUCIBILITY.md) for the full payload and pattern
hash tuples and the numerical-portability finding.

## Release checklist

1. Confirm the target commit.
2. Run `python qosmos_hme_engine.py --self-test`.
3. Run `pytest -q`.
4. Run the independent audit.
5. Run the SFD to HME bridge and verify the active source hash, stable
   invariants, and one complete recognized byte tuple.
6. Verify `MANIFEST.sha256`.
7. Confirm root and portable licenses are byte-identical.
8. Record Python, NumPy, architecture, and runner platform.
9. Attach or link the machine-readable evidence packet.
10. State the claim boundary and known limitations.
11. Create the tag and GitHub Release from the same commit.

## Version rule

Do not tag current DEVELOP head as the historical `v2.2.0-baseline`. A tag is a
coordinate, not a mood ring: it must resolve to the exact source whose hashes
and evidence it names.
