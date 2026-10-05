import type { Action, Assertion, Condition, HiddenModel } from "./types.ts";
import type { PremiseTrace, SolvedDecision } from "./solver-types.ts";

export type { PremiseTrace, SolvedDecision } from "./solver-types.ts";

type PremiseState = {
  known: boolean;
  value: string | number | boolean | null;
  supportCount: number;
  sourceIds: string[];
};

function consideredOrAll(model: HiddenModel, considered?: Set<string>): Set<string> {
  if (considered) return considered;
  const ids = new Set<string>([model.policyEvidenceId]);
  for (const assertion of model.assertions) ids.add(assertion.evidenceId);
  for (const withdrawal of model.withdrawals) ids.add(withdrawal.evidenceId);
  return ids;
}

function activeAssertions(
  model: HiddenModel,
  decisionProject: string,
  premiseId: string,
  allowed: Set<string>,
): Assertion[] {
  const withdrawn = new Set(
    model.withdrawals
      .filter(
        (withdrawal) =>
          allowed.has(withdrawal.evidenceId) && withdrawal.effectiveAt <= model.cutoff,
      )
      .map((withdrawal) => withdrawal.tokenId),
  );
  return model.assertions.filter(
    (assertion) =>
      assertion.projectId === decisionProject &&
      assertion.premiseId === premiseId &&
      assertion.effectiveAt <= model.cutoff &&
      allowed.has(assertion.evidenceId) &&
      !withdrawn.has(assertion.tokenId),
  );
}

function premiseState(
  model: HiddenModel,
  projectId: string,
  premiseId: string,
  allowed: Set<string>,
): PremiseState {
  const active = activeAssertions(model, projectId, premiseId, allowed);
  const supports = active.filter((assertion) => assertion.supportToken && assertion.value === true);
  const valued = active
    .filter((assertion) => !assertion.supportToken)
    .sort((a, b) => a.effectiveAt - b.effectiveAt || a.evidenceId.localeCompare(b.evidenceId));
  const latest = valued[valued.length - 1];
  const sourceIds = [
    ...new Set([
      ...(latest ? [latest.evidenceId] : []),
      ...supports.map((assertion) => assertion.evidenceId),
    ]),
  ];
  return {
    known: latest != null,
    value: latest ? latest.value : null,
    supportCount: supports.length,
    sourceIds,
  };
}

function compareNumber(left: number, op: "lt" | "lte" | "gt" | "gte", right: number): boolean {
  if (op === "lt") return left < right;
  if (op === "lte") return left <= right;
  if (op === "gt") return left > right;
  return left >= right;
}

function holds(condition: Condition, state: PremiseState): boolean {
  if (condition.op === "supports_gte") return state.supportCount >= condition.n;
  if (!state.known || state.value == null) return false;
  if (condition.op === "eq") return state.value === condition.value;
  if (typeof state.value !== "number") return false;
  return compareNumber(state.value, condition.op, condition.value);
}

function unique(values: string[]): string[] {
  return [...new Set(values)].sort();
}

/**
 * Reference solver. `considered` limits which public evidence ids are visible.
 * Omit it for the full immutable model. Memory construction must not call this.
 */
export function solve(model: HiddenModel, considered?: Set<string>): SolvedDecision[] {
  const allowed = consideredOrAll(model, considered);
  const policyVisible = allowed.has(model.policyEvidenceId);

  return model.decisions.map((decision) => {
    const trace: PremiseTrace[] = model.policy.premises.map((premise) => {
      const state = premiseState(model, decision.projectId, premise.id, allowed);
      return {
        premiseId: premise.id,
        known: state.known,
        value: state.value,
        supportCount: state.supportCount,
        sourceIds: state.sourceIds,
      };
    });

    if (!policyVisible) {
      return {
        decisionId: decision.id,
        projectId: decision.projectId,
        recordedOptionId: decision.recordedOptionId,
        action: "DEFER" as Action,
        optionId: null,
        matchedRuleId: "POLICY_NOT_IN_PACKET",
        decisivePremiseIds: [],
        unresolvedPremiseIds: ["POLICY_NOT_IN_PACKET"],
        premiseTrace: trace,
      };
    }

    const byPremise = new Map(trace.map((row) => [row.premiseId, row]));
    const matched = model.policy.rules.find((rule) =>
      rule.conditions.every((condition) => {
        const row = byPremise.get(condition.premiseId);
        const state: PremiseState = row
          ? {
              known: row.known,
              value: row.value,
              supportCount: row.supportCount,
              sourceIds: row.sourceIds,
            }
          : { known: false, value: null, supportCount: 0, sourceIds: [] };
        return holds(condition, state);
      }),
    );

    if (!matched) {
      return {
        decisionId: decision.id,
        projectId: decision.projectId,
        recordedOptionId: decision.recordedOptionId,
        action: "DEFER" as Action,
        optionId: null,
        matchedRuleId: "NO_MATCH",
        decisivePremiseIds: [],
        unresolvedPremiseIds: model.policy.premises.map((premise) => premise.id),
        premiseTrace: trace,
      };
    }

    const decisive = unique(matched.conditions.map((condition) => condition.premiseId));
    if (matched.optionId == null) {
      return {
        decisionId: decision.id,
        projectId: decision.projectId,
        recordedOptionId: decision.recordedOptionId,
        action: "DEFER",
        optionId: null,
        matchedRuleId: matched.id,
        decisivePremiseIds: decisive,
        unresolvedPremiseIds: [...matched.unresolvedPremiseIds],
        premiseTrace: trace,
      };
    }

    const action: Action = matched.optionId === decision.recordedOptionId ? "RETAIN" : "REVISE";
    return {
      decisionId: decision.id,
      projectId: decision.projectId,
      recordedOptionId: decision.recordedOptionId,
      action,
      optionId: matched.optionId,
      matchedRuleId: matched.id,
      decisivePremiseIds: decisive,
      unresolvedPremiseIds: [],
      premiseTrace: trace,
    };
  });
}
