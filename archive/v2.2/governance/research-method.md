# Research and experimental method

## Claim ledger

For every important claim, record:

```text
classification
claim
source or observation
assumptions
best alternative explanation
evidence for
evidence against
falsifier or kill criterion
scope
confidence
```

Ask first: does established science or engineering already explain this? A QOFT mapping adds value only if it improves prediction, intervention, consistency, measurement, compression, or transfer.

## Experiment registration

Every experiment must declare:

```text
canonical target
actual implementation and type
intervention or ablation
preserved inputs, outputs, and behavior
omitted canonical behavior
baseline and controls
metrics and scoring ownership
supported claim
forbidden extrapolation
kill criterion
```

Results apply only to the tested realization unless a typed bridge or cross-realization validation supports more.

## Validity order

Evaluate in this order:

1. artifact integrity and report validity;
2. protocol completeness and blinding;
3. mechanism activation and intervention fidelity;
4. metric validity and statistical analysis;
5. scientific outcome.

Do not let a scientific pass rescue an invalid report. Do not turn missing evaluation into a negative result. Use `MECHANISM_NOT_TESTED` when the relevant operator never activates or is bypassed. If a protocol defines `SKIP`, `NOT_EVALUATED`, or exit-code precedence, preserve those exact semantics.

## Required controls

- Use deterministic condition assembly and record seeds, versions, environment, hashes, prompts, and timestamps.
- Keep baseline and treatment identical except for the intervention.
- Capture independent model outputs before cross-model exposure or coordination.
- Blind evaluators and subjects to source labels when framing could influence behavior.
- Separate raw output from interpretation and keep unavailable values null or explicit.
- Pre-register thresholds, primary endpoints, exclusions, stopping rules, and validity guards.
- Verify event rates and mechanism activation in every arm before interpreting contrasts.
- Calibrate thresholds against scale, dimension, candidate count, and distribution changes.
- Use stronger ordinary baselines where they could explain the effect with fewer assumptions.
- Replicate with fresh seeds, another operator/runtime, and a less theory-friendly environment.

## Lessons pinned by the supplied corpus

- Probe Class 6 initially showed a 10/10 QRNG-versus-PRNG morphology split in a non-blind Claude context. Two fresh blind trials produced 0/12 anchoring and no split. The intrinsic quantum-seed fingerprint claim is unsupported; source framing is the live explanation. Treat the write-up as preliminary, not independent replication.
- T-01's fixed max-softmax collapse threshold was not invariant to candidate count. High-threshold and five-candidate variants starved collapse events, so those robustness conditions were `MECHANISM_NOT_TESTED`, not failures. The primary result remained realization- and environment-limited; promotion was blocked pending T-01b repairs.
- Metrics assigned by arm class or asserted by code are not measurements. Cross-arm normalization that lets one arm change another arm's score invalidates cross-variant comparisons.
- A saved v27 test record reports five tests passing, but this supports the overlay implementation only. It does not validate a universal collapse threshold, physical brane model, Bell/CHSH behavior, or QOFT as physics.

## Interpretation firewall

Do not infer any of the following from recursive-agent behavior, telemetry, or simulation alone:

- phenomenal consciousness or self-awareness;
- quantum effects or observer-caused physical collapse;
- literal world branching;
- universal cognitive architecture;
- canon validity from implementation conformance;
- novelty or patentability from internal distinctiveness.

Tier 1 established mechanisms do not become evidence for QOFT merely because QOFT describes them. Tier 2 QOFT-specific integration needs measurable added value. Tier 3 metaphysical interpretations may not inherit Tier 1 or Tier 2 evidence.
