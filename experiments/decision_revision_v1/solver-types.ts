import type { Action } from "./types.ts";

export type PremiseTrace = {
  premiseId: string;
  known: boolean;
  value: string | number | boolean | null;
  supportCount: number;
  sourceIds: string[];
};

export type SolvedDecision = {
  decisionId: string;
  projectId: string;
  recordedOptionId: string;
  action: Action;
  optionId: string | null;
  matchedRuleId: string;
  decisivePremiseIds: string[];
  unresolvedPremiseIds: string[];
  premiseTrace: PremiseTrace[];
};
