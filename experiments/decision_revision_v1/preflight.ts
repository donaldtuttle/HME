import { buildPackets } from "./memory.ts";
import { solve } from "./solver.ts";
import { supportAvailable } from "./diagnose.ts";
import { sameStringSet, toPublic } from "./text.ts";
import type { History, PublicMessage } from "./types.ts";

export type Check = {
  id: string;
  pass: boolean;
  detail: string;
};

function signature(message: PublicMessage): string {
  return JSON.stringify([
    message.index,
    message.id,
    message.authority,
    message.type,
    message.scope,
    message.effectiveAt,
    message.links,
    message.text,
  ]);
}

function sibling(history: History, corpus: History[]): History | undefined {
  return corpus.find(
    (other) =>
      other.familyId === history.familyId &&
      other.pairId === history.pairId &&
      other.side !== history.side,
  );
}

export function runPreflight(corpus: History[]): Check[] {
  const checks: Check[] = [];
  const push = (id: string, pass: boolean, detail: string) => checks.push({ id, pass, detail });

  push(
    "corpus-shape",
    corpus.length === 32 && new Set(corpus.map((history) => history.id)).size === 32,
    `${corpus.length} histories, ${new Set(corpus.map((history) => history.id)).size} unique ids. Fixture is 4 families × 8 histories, not the 480-history evaluation matrix.`,
  );

  const lengthsOk = corpus.every(
    (history) => history.messages.length === 80 && history.messages.every((message, index) => message.index === index + 1),
  );
  push("history-length", lengthsOk, "Each history has messages 1 through 80.");

  const late = corpus.filter((history) =>
    history.messages.some((message) => message.index > 50 && message.type !== "chatter"),
  );
  push(
    "evidence-window",
    late.length === 0,
    late.length
      ? `Decision-relevant records after message 50 in ${late.map((history) => history.id).join(", ")}.`
      : "Decision-relevant records sit before the last 30 messages.",
  );

  let solverFails: string[] = [];
  for (const history of corpus) {
    const solved = solve(history.model);
    for (const decision of history.model.decisions) {
      const expected = history.expected[decision.id];
      const got = solved.find((row) => row.decisionId === decision.id);
      if (
        !expected ||
        !got ||
        expected.action !== got.action ||
        expected.optionId !== got.optionId ||
        !sameStringSet(expected.decisive, got.decisivePremiseIds) ||
        !sameStringSet(expected.unresolved, got.unresolvedPremiseIds)
      ) {
        solverFails.push(
          `${history.id}/${decision.id} expected ${expected?.action ?? "?"} got ${got?.action ?? "?"}/${got?.matchedRuleId ?? "?"}`,
        );
      }
    }
  }
  push(
    "solver-agrees",
    solverFails.length === 0,
    solverFails.length ? solverFails.slice(0, 6).join("; ") : "Hand key and reference solver agree on every decision.",
  );

  const families = [...new Set(corpus.map((history) => history.familyId))];
  const tallyBad: string[] = [];
  for (const family of families) {
    const rows = corpus.filter((history) => history.familyId === family);
    const tally = { RETAIN: 0, REVISE: 0, DEFER: 0 };
    for (const history of rows) {
      const target = history.model.decisions[0];
      const action = target ? history.expected[target.id]?.action : undefined;
      if (action) tally[action] += 1;
      const control = history.model.decisions[1];
      if (control && history.expected[control.id]?.action !== "RETAIN") {
        tallyBad.push(`${history.id} control is not RETAIN`);
      }
    }
    if (tally.REVISE !== 3 || tally.RETAIN !== 4 || tally.DEFER !== 1) {
      tallyBad.push(`${family} target tally ${JSON.stringify(tally)}`);
    }
  }
  push(
    "outcome-mix",
    tallyBad.length === 0,
    tallyBad.length
      ? tallyBad.join("; ")
      : "Each family’s target decisions are 3 REVISE, 4 RETAIN, 1 DEFER. Every control decision is RETAIN.",
  );

  const diffBad: string[] = [];
  const seenPairs = new Set<string>();
  for (const history of corpus) {
    const key = `${history.familyId}:${history.pairId}`;
    if (seenPairs.has(key)) continue;
    seenPairs.add(key);
    const other = sibling(history, corpus);
    if (!other) {
      diffBad.push(`missing sibling ${key}`);
      continue;
    }
    let diffs = 0;
    for (let index = 0; index < history.messages.length; index++) {
      if (signature(history.messages[index]) !== signature(other.messages[index])) diffs += 1;
    }
    if (diffs !== 1) diffBad.push(`${key} differs in ${diffs} messages`);
  }
  push(
    "matched-pairs",
    diffBad.length === 0,
    diffBad.length ? diffBad.join("; ") : "Each matched pair differs in exactly one public message.",
  );

  const cue: Record<History["pairId"], string> = {
    changed_constraint: "no longer requires",
    withdrawn_evidence: "withdrawn",
    scoped_exception: "exception",
    validity_timing: "Effective time:",
  };
  const cueBad: string[] = [];
  for (const history of corpus) {
    const blob = history.messages.map((message) => message.text).join("\n");
    if (!blob.includes(cue[history.pairId])) cueBad.push(`${history.id} missing “${cue[history.pairId]}”`);
    for (const message of history.messages) {
      if (message.type === "status" && /\b(use|switch to|you should now)\b/i.test(message.text)) {
        cueBad.push(`${history.id} ${message.id} looks like a new-action instruction`);
      }
    }
    if (/\b(RETAIN|REVISE|DEFER)\b/.test(history.query)) cueBad.push(`${history.id} query names an action`);
  }
  push(
    "cues-and-instructions",
    cueBad.length === 0,
    cueBad.length
      ? cueBad.slice(0, 6).join("; ")
      : "Cue words appear on both sides. Status updates do not instruct the new action. Queries do not name the action.",
  );

  const supportBad: string[] = [];
  for (const history of corpus) {
    const ids = new Set(history.messages.map((message) => message.id).filter(Boolean));
    for (const [decisionId, sets] of Object.entries(history.model.supports)) {
      if (!sets.length) supportBad.push(`${history.id} ${decisionId} has no support set`);
      for (const set of sets) {
        for (const id of set) {
          if (!ids.has(id)) supportBad.push(`${history.id} cites missing ${id}`);
        }
      }
    }
  }
  push(
    "support-ids",
    supportBad.length === 0,
    supportBad.length ? supportBad.slice(0, 6).join("; ") : "Every accepted support id exists in that history.",
  );

  let leak = true;
  const sample = corpus[0];
  if (sample) {
    const before = JSON.stringify(buildPackets(toPublic(sample)));
    const clone = structuredClone(sample);
    clone.model.assertions = [];
    clone.model.withdrawals = [];
    clone.model.supports = {};
    clone.expected = {};
    leak = before === JSON.stringify(buildPackets(toPublic(clone)));
  }
  push(
    "key-not-in-packets",
    leak,
    leak
      ? "Wiping the hidden model leaves every packet byte-for-byte unchanged."
      : "Packet construction changed after the hidden model was wiped.",
  );

  const hybridBad: string[] = [];
  const ledgerMiss: string[] = [];
  const summaryMiss: string[] = [];
  const overBudget: string[] = [];
  for (const history of corpus) {
    const packets = buildPackets(toPublic(history));
    const hybrid = packets.find((packet) => packet.arm === "hme_hybrid");
    const projected = packets.find((packet) => packet.arm === "nn_projected");
    const ledger = packets.find((packet) => packet.arm === "decision_ledger");
    const summary = packets.find((packet) => packet.arm === "summary_recent");
    if (!hybrid || hybrid.fieldStatus !== "MECHANISM_NOT_TESTED") hybridBad.push(history.id);
    if (hybrid && projected && hybrid.text !== projected.text) hybridBad.push(`${history.id} hybrid diverged`);
    if (ledger && !supportAvailable(history, ledger.evidenceIds)) ledgerMiss.push(history.id);
    if (summary && !supportAvailable(history, summary.evidenceIds)) summaryMiss.push(history.id);
    for (const packet of packets) {
      if (packet.words > 512) overBudget.push(`${history.id} ${packet.arm} ${packet.words}`);
    }
  }
  push(
    "field-not-tested",
    hybridBad.length === 0,
    hybridBad.length
      ? hybridBad.join("; ")
      : "Hybrid packets equal projected NN and are marked MECHANISM_NOT_TESTED. The CM-1 field is not linked.",
  );
  push(
    "ledger-coverage",
    ledgerMiss.length === 0,
    ledgerMiss.length
      ? `Ledger missed a full support set on ${ledgerMiss.slice(0, 8).join(", ")}.`
      : "On this fixture the ledger packet contains a complete accepted support set for every history.",
  );
  push(
    "summary-coverage",
    summaryMiss.length === 0,
    summaryMiss.length
      ? `Summary missed a full support set on ${summaryMiss.slice(0, 8).join(", ")}.`
      : "On this fixture the extractive summary contains a complete accepted support set for every history.",
  );
  push(
    "word-budget",
    overBudget.length === 0,
    overBudget.length ? overBudget.join("; ") : "Every packet is within the 512-word reference allowance.",
  );

  return checks;
}
