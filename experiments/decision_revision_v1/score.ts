import type { Action, History, ReaderDecision, ReaderResponse } from "./types.ts";
import { sameStringSet } from "./text.ts";
import { solve } from "./solver.ts";

export type DecisionScore = {
  decisionId: string;
  actionOk: boolean;
  optionOk: boolean;
  premisesOk: boolean;
  unresolvedOk: boolean;
  supportOk: boolean;
  evidenceInPacket: boolean;
  grounded: boolean;
  falseRevision: boolean;
  inappropriateCommitment: boolean;
  incorrectDeferral: boolean;
  missedRevision: boolean;
  notes: string[];
};

export type Score = {
  scorable: boolean;
  integrityError: string | null;
  formatOk: boolean;
  formatError: string | null;
  primary: 0 | 1;
  targetGrounded: 0 | 1;
  controlGrounded: 0 | 1;
  actionOnly: 0 | 1;
  controlDamage: boolean;
  falseRevision: boolean;
  inappropriateCommitment: boolean;
  incorrectDeferral: boolean;
  missedRevision: boolean;
  decisions: DecisionScore[];
};

function emptyScore(error: string): Score {
  return {
    scorable: true,
    integrityError: null,
    formatOk: false,
    formatError: error,
    primary: 0,
    targetGrounded: 0,
    controlGrounded: 0,
    actionOnly: 0,
    controlDamage: false,
    falseRevision: false,
    inappropriateCommitment: false,
    incorrectDeferral: false,
    missedRevision: false,
    decisions: [],
  };
}

function isAction(value: unknown): value is Action {
  return value === "RETAIN" || value === "REVISE" || value === "DEFER";
}

export function parseReaderJson(raw: string): { ok: true; value: ReaderResponse } | { ok: false; error: string } {
  let parsed: unknown;
  try {
    parsed = JSON.parse(raw);
  } catch {
    return { ok: false, error: "Response is not JSON." };
  }
  if (!parsed || typeof parsed !== "object" || !("decisions" in parsed)) {
    return { ok: false, error: "JSON needs a decisions array." };
  }
  const decisions = (parsed as { decisions: unknown }).decisions;
  if (!Array.isArray(decisions)) return { ok: false, error: "decisions must be an array." };
  const clean: ReaderDecision[] = [];
  for (const entry of decisions) {
    if (!entry || typeof entry !== "object") return { ok: false, error: "Each decision must be an object." };
    const row = entry as Record<string, unknown>;
    if (typeof row.decision_id !== "string") return { ok: false, error: "decision_id must be a string." };
    if (!isAction(row.action)) return { ok: false, error: `Action for ${row.decision_id} must be RETAIN, REVISE, or DEFER.` };
    if (!(typeof row.selected_option_id === "string" || row.selected_option_id === null)) {
      return { ok: false, error: "selected_option_id must be a string or null." };
    }
    for (const field of ["decisive_premise_ids", "unresolved_premise_ids", "evidence_ids"] as const) {
      const value = row[field];
      if (!Array.isArray(value) || value.some((item) => typeof item !== "string")) {
        return { ok: false, error: `${field} must be an array of strings.` };
      }
    }
    clean.push({
      decision_id: row.decision_id,
      action: row.action,
      selected_option_id: row.selected_option_id,
      decisive_premise_ids: row.decisive_premise_ids as string[],
      unresolved_premise_ids: row.unresolved_premise_ids as string[],
      evidence_ids: row.evidence_ids as string[],
    });
  }
  return { ok: true, value: { decisions: clean } };
}

function supportMatch(cited: string[], accepted: string[][]): boolean {
  if (new Set(cited).size !== cited.length) return false;
  return accepted.some((candidate) => sameStringSet(cited, candidate));
}

/**
 * Primary outcome: both decisions grounded. Evidence must sit in the packet
 * actually shown. The solver's expected fields are the hand key, checked
 * against the reference solve by preflight before this is trusted.
 */
export function scoreHistory(
  history: History,
  response: ReaderResponse,
  packetEvidenceIds: string[],
): Score {
  const ids = history.queriedDecisionIds;
  const solved = solve(history.model);
  const inconsistent = ids.filter((id) => {
    const expected = history.expected[id];
    const truth = solved.find((row) => row.decisionId === id);
    return !expected || !truth ||
      expected.action !== truth.action ||
      expected.optionId !== truth.optionId ||
      !sameStringSet(expected.decisive, truth.decisivePremiseIds) ||
      !sameStringSet(expected.unresolved, truth.unresolvedPremiseIds);
  });
  if (inconsistent.length) {
    return {
      ...emptyScore(""),
      scorable: false,
      integrityError: `Hand key and reference solver disagree or are missing for ${inconsistent.join(", ")}. This history is not scorable.`,
      formatOk: true,
      formatError: null,
    };
  }
  const seen = response.decisions.map((decision) => decision.decision_id);
  if (new Set(seen).size !== seen.length) return emptyScore("Duplicate decision ids.");
  if (!sameStringSet(seen, ids)) {
    return emptyScore(`Decisions must be exactly ${ids.join(" and ")}.`);
  }

  const packet = new Set(packetEvidenceIds);
  const byId = new Map(response.decisions.map((decision) => [decision.decision_id, decision]));
  const targetId = history.model.decisions[0]?.id;

  const decisions: DecisionScore[] = ids.map((id) => {
    const given = byId.get(id);
    const expected = history.expected[id];
    const truth = solved.find((row) => row.decisionId === id);
    const notes: string[] = [];
    if (!given || !expected || !truth) {
      return {
        decisionId: id,
        actionOk: false,
        optionOk: false,
        premisesOk: false,
        unresolvedOk: false,
        supportOk: false,
        evidenceInPacket: false,
        grounded: false,
        falseRevision: false,
        inappropriateCommitment: false,
        incorrectDeferral: false,
        missedRevision: false,
        notes: ["Missing expected key or answer."],
      };
    }
    const actionOk = given.action === expected.action;
    const optionOk =
      expected.action === "DEFER"
        ? given.selected_option_id === null
        : given.selected_option_id === expected.optionId;
    const premisesOk = sameStringSet(given.decisive_premise_ids, expected.decisive);
    const unresolvedOk = sameStringSet(given.unresolved_premise_ids, expected.unresolved);
    const accepted = history.model.supports[id] ?? [];
    const supportOk = supportMatch(given.evidence_ids, accepted);
    const evidenceInPacket = given.evidence_ids.every((evidenceId) => packet.has(evidenceId));
    if (given.evidence_ids.length === 0) notes.push("No evidence cited.");
    if (supportOk && !evidenceInPacket) notes.push("Cited support was not in the supplied packet.");
    if (!supportOk && given.evidence_ids.length) notes.push("Citation is not an accepted support set.");
    const grounded = actionOk && optionOk && premisesOk && unresolvedOk && supportOk && evidenceInPacket;
    return {
      decisionId: id,
      actionOk,
      optionOk,
      premisesOk,
      unresolvedOk,
      supportOk,
      evidenceInPacket,
      grounded,
      falseRevision: expected.action === "RETAIN" && given.action === "REVISE",
      inappropriateCommitment: expected.action === "DEFER" && given.action !== "DEFER",
      incorrectDeferral: expected.action !== "DEFER" && given.action === "DEFER",
      missedRevision: expected.action === "REVISE" && given.action !== "REVISE",
      notes,
    };
  });

  const target = decisions.find((row) => row.decisionId === targetId) ?? decisions[0];
  const control = decisions.find((row) => row.decisionId !== targetId);
  const actionOnly =
    decisions.length === ids.length && decisions.every((row) => row.actionOk && row.optionOk) ? 1 : 0;

  return {
    scorable: true,
    integrityError: null,
    formatOk: true,
    formatError: null,
    primary: decisions.length === ids.length && decisions.every((row) => row.grounded) ? 1 : 0,
    targetGrounded: target?.grounded ? 1 : 0,
    controlGrounded: control?.grounded ? 1 : 0,
    actionOnly,
    controlDamage: Boolean(control && (!control.actionOk || !control.optionOk)),
    falseRevision: decisions.some((row) => row.falseRevision),
    inappropriateCommitment: decisions.some((row) => row.inappropriateCommitment),
    incorrectDeferral: decisions.some((row) => row.incorrectDeferral),
    missedRevision: decisions.some((row) => row.missedRevision),
    decisions,
  };
}
