import type { History, ReaderResponse } from "./types.ts";
import { scoreHistory, type Score } from "./score.ts";

export type BaselineId = "always_retain" | "always_revise" | "always_defer" | "latest_mentioned_option";

export const BASELINE_LABEL: Record<BaselineId, string> = {
  always_retain: "Always retain",
  always_revise: "Always revise (first alternative)",
  always_defer: "Always defer",
  latest_mentioned_option: "Latest mentioned option",
};

function blank(id: string, action: ReaderResponse["decisions"][number]["action"], option: string | null, evidence: string[]): ReaderResponse["decisions"][number] {
  return {
    decision_id: id,
    action,
    selected_option_id: option,
    decisive_premise_ids: [],
    unresolved_premise_ids: action === "DEFER" ? ["UNSPECIFIED"] : [],
    evidence_ids: evidence,
  };
}

function optionIds(policyText: string): string[] {
  const declaration = policyText.match(/Public identifiers: options? ([^;]+);/);
  return [...new Set(declaration?.[1].match(/\b[A-Z][A-Z0-9_]{2,}\b/g) ?? [])];
}

/** Fixture wording only: recover the recorded choice from public records, never the key. */
function recordedOption(history: History, decisionId: string, options: string[]): string | null {
  const records = history.messages.filter((message) =>
    (message.type === "decision" || message.type === "state") &&
    message.authority === "project-lead" && message.effectiveAt <= history.model.cutoff &&
    message.scope.some((project) => `D_${project.toUpperCase()}` === decisionId),
  ).sort((a, b) => b.effectiveAt - a.effectiveAt || b.index - a.index);
  for (const record of records) {
    for (const option of options) {
      const label = option.replaceAll("_", " ");
      if (new RegExp(`\\b(?:selected|uses)\\s+(?:option\\s+)?${label}\\b`, "i").test(record.text)) return option;
    }
  }
  return null;
}

function latestMention(history: History): { optionId: string | null; evidenceId: string | null; firstOptionId: string | null } {
  const policy = history.messages.find((message) => message.id === "E01");
  const ids = policy ? optionIds(policy.text) : [];
  const first = ids[0] ?? null;
  let best: { optionId: string; evidenceId: string | null; at: number; pos: number } | null = null;
  for (const message of history.messages) {
    for (const optionId of ids) {
      const pos = message.text.lastIndexOf(optionId);
      if (pos < 0) continue;
      const at = message.index * 10000 + pos;
      if (!best || at >= best.at) {
        best = { optionId, evidenceId: message.id, at, pos };
      }
    }
  }
  return { optionId: best?.optionId ?? null, evidenceId: best?.evidenceId ?? null, firstOptionId: first };
}

export function baselineResponse(history: History, baseline: BaselineId): ReaderResponse {
  const options = optionIds(history.messages.find((message) => message.id === "E01")?.text ?? "");
  if (baseline === "latest_mentioned_option") {
    const latest = latestMention(history);
    const evidence = latest.evidenceId ? [latest.evidenceId] : [];
    return {
      decisions: history.queriedDecisionIds.map((id) => {
        const current = recordedOption(history, id, options);
        const action = latest.optionId && current && latest.optionId !== current ? "REVISE" : "RETAIN";
        return blank(id, action, latest.optionId, evidence);
      }),
    };
  }
  const action = baseline === "always_revise" ? "REVISE" : baseline === "always_defer" ? "DEFER" : "RETAIN";
  return {
    decisions: history.queriedDecisionIds.map((id) => {
      const current = recordedOption(history, id, options);
      const option = action === "RETAIN" ? current : action === "REVISE"
        ? (current ? options.find((option) => option !== current) ?? null : null) : null;
      return blank(id, action, option, []);
    }),
  };
}

export function scoreBaseline(history: History, baseline: BaselineId): Score {
  const response = baselineResponse(history, baseline);
  const everyId = history.messages.map((message) => message.id).filter((id): id is string => Boolean(id));
  return scoreHistory(history, response, everyId);
}
