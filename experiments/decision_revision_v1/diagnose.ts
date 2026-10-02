import { buildPackets } from "./memory.ts";
import { solve } from "./solver.ts";
import type { SolvedDecision } from "./solver.ts";
import { scoreHistory, type Score } from "./score.ts";
import { toPublic } from "./text.ts";
import type { ArmId, History, Packet, ReaderResponse } from "./types.ts";

export function diagnose(history: History, packet: Packet): SolvedDecision[] {
  return solve(history.model, new Set(packet.evidenceIds));
}

export function oracleResponse(history: History, packet: Packet, solved: SolvedDecision[]): ReaderResponse {
  const visible = new Set(packet.evidenceIds);
  return {
    decisions: solved.map((decision) => {
      const accepted = history.model.supports[decision.decisionId] ?? [];
      const complete = accepted.find((set) => set.every((id) => visible.has(id)));
      const fallback = [
        ...new Set(
          decision.premiseTrace.flatMap((row) => row.sourceIds).filter((id) => visible.has(id)),
        ),
      ];
      if (visible.has(history.model.policyEvidenceId) && !fallback.includes("E01")) fallback.unshift("E01");
      return {
        decision_id: decision.decisionId,
        action: decision.action,
        selected_option_id: decision.optionId,
        decisive_premise_ids: decision.decisivePremiseIds,
        unresolved_premise_ids: decision.unresolvedPremiseIds,
        evidence_ids: complete ? [...complete] : fallback,
      };
    }),
  };
}

export type ArmDiagnostic = {
  arm: ArmId;
  packet: Packet;
  solved: SolvedDecision[];
  response: ReaderResponse;
  score: Score;
  supportAvailable: boolean;
};

export function supportAvailable(history: History, evidenceIds: string[]): boolean {
  const visible = new Set(evidenceIds);
  return history.model.decisions.every((decision) => {
    const sets = history.model.supports[decision.id] ?? [];
    return sets.some((set) => set.every((id) => visible.has(id)));
  });
}

export function diagnoseHistory(history: History): ArmDiagnostic[] {
  return buildPackets(toPublic(history)).map((packet) => {
    const solved = diagnose(history, packet);
    const response = oracleResponse(history, packet, solved);
    const score = scoreHistory(history, response, packet.evidenceIds);
    return {
      arm: packet.arm,
      packet,
      solved,
      response,
      score,
      supportAvailable: supportAvailable(history, packet.evidenceIds),
    };
  });
}

export type ArmSummary = {
  arm: ArmId;
  grounded: number;
  actionOnly: number;
  supportAvailable: number;
  histories: number;
  invalidHistories: number;
  falseRevision: number;
  missedRevision: number;
  inappropriateCommitment: number;
  fieldStatus: string;
};

export function summarizeArms(histories: History[]): ArmSummary[] {
  const totals = new Map<ArmId, ArmSummary>();
  for (const history of histories) {
    for (const row of diagnoseHistory(history)) {
      const current = totals.get(row.arm) ?? {
        arm: row.arm,
        grounded: 0,
        actionOnly: 0,
        supportAvailable: 0,
        histories: 0,
        invalidHistories: 0,
        falseRevision: 0,
        missedRevision: 0,
        inappropriateCommitment: 0,
        fieldStatus: row.packet.fieldStatus,
      };
      if (!row.score.scorable) {
        current.invalidHistories += 1;
        totals.set(row.arm, current);
        continue;
      }
      current.grounded += row.score.primary;
      current.actionOnly += row.score.actionOnly;
      current.supportAvailable += row.supportAvailable ? 1 : 0;
      current.histories += 1;
      current.falseRevision += row.score.falseRevision ? 1 : 0;
      current.missedRevision += row.score.missedRevision ? 1 : 0;
      current.inappropriateCommitment += row.score.inappropriateCommitment ? 1 : 0;
      current.fieldStatus = row.packet.fieldStatus;
      totals.set(row.arm, current);
    }
  }
  return [...totals.values()];
}
