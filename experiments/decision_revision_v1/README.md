# HME-CM-REV-1: decision revision fixture

**DESIGN — illustrative fixture, not a registered evaluation.**

A history states a policy, a current choice and a later fact. Apply the policy
to decide whether to **RETAIN**, **REVISE** or **DEFER**, cite the supporting
records, and preserve a second project's unaffected decision. The update never
directly instructs the replacement action.

The [user guide](USER_GUIDE.md) includes the worked Alder/Birch example,
JSON fields, scoring rules, memory packets and limits. The
[browser demo](../../demos/decision-revision/README.md) provides the interface.

## Run the fixture

From this directory, with Node 22.18 or newer:

```bash
npm test
npm run check
```

No npm dependencies, API keys, model runtime or Python engine are needed for
these core commands. `check` prints preflight checks, packet diagnostics and
simple baselines. Those are fixture diagnostics, not model performance.

## Current implementation

- Four invented families, eight histories per family, 80 messages per history.
- Four matched-pair categories: changed constraint, withdrawn evidence, scoped
  exception, and effective-time boundary. A pair differs by one message.
- Public history and packet builders are separated from the hidden policy/event
  model, expected decisions and accepted citation sets.
- Packets use an extractive summary, two lexical signed-hash NN stand-ins, a
  hybrid placeholder, or a structured decision ledger. Each has a 512-word cap.
- The hybrid copies projected NN and reports `MECHANISM_NOT_TESTED`.
- Scoring uses the full-history key and requires the cited records in the packet.
  A key/solver disagreement is an integrity failure excluded from outcome totals.

The retained tests exercise all 44 accepted support combinations and 544 invalid
answer or missing-evidence cases. The guide is generated from `user-guide.ts`;
a regression requires the checked-in Markdown to match it exactly.

## Relationship to other studies

[CM-1](../conversation_memory_v1/PROTOCOL.md) tests recall of explicit decisions,
reasons, corrections and task resumption. This fixture illustrates applying a
remembered policy after a premise changes. It does not amend CM-1 or supply an
HME field result, SAL-1 result or consolidation result.

The proposed larger study remains a design: the contemplated 480 histories and
five real memory methods are not implemented by this 32-history fixture. Before
a registered run, complete and freeze the corpus/template split, independent
evaluator, semantic embeddings and field adapter, ledger policy, summary clause
matching, model/runtime/source pins, sample-size rationale, margins, budgets,
failure handling and analysis. Publish all registered cases, including losses.

No model calls, held-out evaluation or efficacy claim accompany this import.
See [source provenance](../../demos/decision-revision/SOURCE.md) and
[verification](../../demos/decision-revision/verification.md).
