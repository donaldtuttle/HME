# Decision Revision Bench

User guide for the HME-CM-REV-1 illustrative fixture. Status: DESIGN. Not a registered evaluation.

## What this is

Decision Revision Bench lets you try the HME-CM-REV-1 task by hand. A history states a rule, a current choice, and a later fact. You decide whether to keep the choice, change it, or wait. The later fact never says “switch to” the new option. You have to apply the rule.

The status is DESIGN. This is an illustrative fixture: 4 invented families and 32 histories. It is not the proposed 480-history evaluation, it does not call a model, and it does not show that holographic memory works. The hybrid packet is marked MECHANISM_NOT_TESTED because the CM-1 field readout is not connected.

## A first session

- Open Read. The history alder-cc-1 and the Decision ledger packet are already selected.
- Read the question, then the records. Ignore unverified drafts if they appear in other packets.
- Replace the placeholder JSON. The placeholder keeps both decisions and names no option, so it scores 0. That is expected.
- Press Score this response. Read the primary outcome before you reveal anything.
- Press Reveal evaluator key only after you have scored. The matched history stays hidden until then.

Use Open the worked example on this page if you have already changed the history or the packet. It returns you to alder-cc-1 and the ledger without filling in the answer.

## The three actions

| Action | When to use it | Option field |
| --- | --- | --- |
| RETAIN | The rule still supports the option already chosen. | That same option id. |
| REVISE | The rule now supports exactly one different option. | The new option id. |
| DEFER | A required fact is missing or was withdrawn and nothing replaces it. | null. Name the unresolved premise. |

DEFER does not mean the old option was false. Withdrawing a test removes that support only. It does not prove the opposite. An unchanged action can still rest on a new reason, but this fixture’s score checks the action, the option, the premises, and the citations together.

## How to write the answer

Return one JSON object with a decisions array. Include both decision ids named in the question, and no others. Duplicate ids fail. Actions must be RETAIN, REVISE, or DEFER.

- decision_id comes from the question, such as D_ALDER.
- selected_option_id is a public option id from the policy record, such as RIG_A. Use null only for DEFER.
- decisive_premise_ids are the premises the matched rule actually uses. Order does not matter. Duplicates fail.
- unresolved_premise_ids is empty unless the action is DEFER. Then it must name the missing premise, such as P_COMPAT.
- evidence_ids must be an accepted support set for that decision, and every id must appear in the packet you were shown. An id list without those records in the packet does not count.

## Worked example: alder-cc-1

Project Alder uses Rig A while precise shadow placement is required. If that requirement is removed and the preview deadline is under ten minutes, Alder uses Rig B. Otherwise Alder keeps Rig A. Birch follows the same rule and still requires precise shadow placement.

The later record says Alder no longer requires precise shadow placement, and the eight-minute deadline remains. It does not mention Rig B. Birch is unchanged. On the ledger packet the grounded answer is:

```json
{
  "decisions": [
    {
      "decision_id": "D_ALDER",
      "action": "REVISE",
      "selected_option_id": "RIG_B",
      "decisive_premise_ids": ["P_SHADOW", "P_DEADLINE"],
      "unresolved_premise_ids": [],
      "evidence_ids": ["E01", "E02", "E03", "E05"]
    },
    {
      "decision_id": "D_BIRCH",
      "action": "RETAIN",
      "selected_option_id": "RIG_A",
      "decisive_premise_ids": ["P_SHADOW"],
      "unresolved_premise_ids": [],
      "evidence_ids": ["E01", "E04"]
    }
  ]
}
```

Citing E01, E03, and E05 for Alder is also accepted, because the update restates the eight-minute deadline. Citing a draft, or citing the Cedar update from the matched history, is not.

alder-cc-2 is the matched control. The same kind of sentence names Cedar instead of Alder, so Alder keeps Rig A. Read it only after you score alder-cc-1 if you want the trial to stay blind.

## The other three pairs

- Withdrawn evidence (we). Proceed only while a verified compatibility test remains. If the only test for that project is withdrawn, DEFER on P_COMPAT. If a second independent test is still active, RETAIN PROCEED.
- Scoped exception (se). The default option stays unless the named exception list includes that project. Another project’s exception does not transfer.
- Validity and timing (vt). The same update can be effective before the cutoff or scheduled after it. A note with an effective time after 80 does not change the decision, even if you can still read it.

Each family has eight histories. Across those eight, the queried project’s correct actions are three REVISE, four RETAIN, and one DEFER. The other project in the question always keeps its option. Harbor, Nimbus, and Kiln repeat the same rules with different names.

## How to read the score

| Line | Meaning |
| --- | --- |
| Primary outcome | 1 only when both decisions are fully grounded. Otherwise 0. |
| Target and Control | Which of the two decisions was grounded. A joint 0 does not hide which one failed. |
| Action only | 1 when both action and option are right, even if the citations are not. |
| Format failure | The JSON could not be scored. Primary outcome is 0. This is a scored failure, not a crash. |

Under each decision, the bench names what failed: action, option, premises, unresolved list, support set, or not in packet. A right action with an empty citation list is an action-only success and a grounded failure. That split is intentional.

## The five packets

Every arm sees the same public history. None of them sees the answer key. Each packet is capped at 512 words. Changing the hidden key does not change the packet.

| Packet | What you are looking at |
| --- | --- |
| Summary + recent | Extractive copy of the policy, decision, state, and status records, then the last four messages. It does not paraphrase. |
| Lexical NN (full) | A signed-hash stand-in for semantic search. It is not CM-1’s embedding model. |
| Lexical NN (projected) | The same stand-in, reduced with a fixed 64-dimensional map. |
| HME hybrid | Same text as the projected arm. The field is not running. Treat the MECHANISM_NOT_TESTED label as the result. |
| Decision ledger | Policy and project-lead records whose scope and effective time match the question. Drafts are left out. Overflow would drop the latest records first. |

Scoring always uses the full-history answer key. If a decisive update is missing from the packet, an answer that is reasonable from the remaining records can still score 0. Guessing the full-history answer without accepted citations also scores 0. Missing support is a retrieval limitation, not evidence that the reader misapplied the visible policy. A higher oracle count on Checks only means a perfect reader found a complete support set in that packet. It is not a model score and not a reason to prefer one memory design.

## Bench, Checks, and Export

- Bench is the author view. The solver’s answer is visible, the single line that differs from the matched history is marked, and the oracle line says whether that packet contained a full support set. Do not use Bench as a blind trial.
- Checks lists fixture preflight. PASS means the generator agrees with the solver, pairs differ by one message, and packets stay inside the word cap. If the key and solver disagree, the history is unscorable and excluded from outcome totals; it is not a reader failure. The oracle table and the baselines are descriptive. Always retain names the recorded option from public records. Always revise names the first different public option, or no option when none exists. These baselines earn no grounded success because they omit required premises and support sets, not because their scores are forcibly capped.
- Export downloads the 32 histories, including the hidden key, and a short layout note for experiments/decision_revision_v1/. Label anything you share from that file as an illustrative fixture.

## What not to claim

- Do not report these screens as a registered evaluation or as evidence that HME beats retrieval or a ledger.
- Do not describe the hybrid arm as a field result while it says MECHANISM_NOT_TESTED.
- Do not treat a citation as proof of the model’s internal reason. This bench never sees a model’s hidden state.
- Do not generalize to professional judgment, real software, or real hardware. The policies and the rigs are invented.

Protocol states the research question and the proposed gates. Those gates are review margins, not findings. Open the Protocol page for that contract, and use this guide for the bench itself.
