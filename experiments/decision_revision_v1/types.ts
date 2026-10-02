/** Public types for the HME-CM-REV-1 illustrative fixture. Not a registration. */

export type Action = "RETAIN" | "REVISE" | "DEFER";

export type PairId =
  | "changed_constraint"
  | "withdrawn_evidence"
  | "scoped_exception"
  | "validity_timing";

export type Side = "target" | "control";

export type Condition =
  | { op: "eq"; premiseId: string; value: string | number | boolean }
  | { op: "lt" | "lte" | "gt" | "gte"; premiseId: string; value: number }
  | { op: "supports_gte"; premiseId: string; n: number };

export type PolicyRule = {
  id: string;
  optionId: string | null;
  unresolvedPremiseIds: string[];
  conditions: Condition[];
};

export type PolicyModel = {
  id: string;
  premises: { id: string; label: string }[];
  options: { id: string; label: string }[];
  rules: PolicyRule[];
};

export type Assertion = {
  evidenceId: string;
  tokenId: string;
  premiseId: string;
  projectId: string;
  value: string | number | boolean;
  supportToken: boolean;
  effectiveAt: number;
};

export type Withdrawal = {
  evidenceId: string;
  tokenId: string;
  effectiveAt: number;
};

export type DecisionSpec = {
  id: string;
  projectId: string;
  recordedOptionId: string;
  recordId: string;
};

/** Immutable policy/event model. Memory builders must not read this. */
export type HiddenModel = {
  policyEvidenceId: string;
  policy: PolicyModel;
  assertions: Assertion[];
  withdrawals: Withdrawal[];
  decisions: DecisionSpec[];
  cutoff: number;
  supports: Record<string, string[][]>;
};

export type ExpectedDecision = {
  action: Action;
  optionId: string | null;
  decisive: string[];
  unresolved: string[];
};

export type MessageType = "policy" | "state" | "decision" | "status" | "draft" | "chatter";

export type PublicMessage = {
  index: number;
  id: string | null;
  authority: string;
  type: MessageType;
  scope: string[];
  effectiveAt: number;
  links: string[];
  text: string;
};

export type PublicHistory = {
  id: string;
  messages: PublicMessage[];
  query: string;
  cutoff: number;
  queriedProjects: string[];
  queriedDecisionIds: string[];
};

export type History = {
  id: string;
  blindLabel: string;
  familyId: string;
  familyTitle: string;
  pairId: PairId;
  pairTitle: string;
  side: Side;
  messages: PublicMessage[];
  query: string;
  queriedDecisionIds: string[];
  model: HiddenModel;
  expected: Record<string, ExpectedDecision>;
};

export type ArmId =
  | "summary_recent"
  | "nn_full"
  | "nn_projected"
  | "hme_hybrid"
  | "decision_ledger";

export type FieldStatus = "NOT_APPLICABLE" | "MECHANISM_NOT_TESTED";

export type Packet = {
  arm: ArmId;
  messages: PublicMessage[];
  text: string;
  words: number;
  evidenceIds: string[];
  notes: string[];
  fieldStatus: FieldStatus;
};

export type ReaderDecision = {
  decision_id: string;
  action: Action;
  selected_option_id: string | null;
  decisive_premise_ids: string[];
  unresolved_premise_ids: string[];
  evidence_ids: string[];
};

export type ReaderResponse = {
  decisions: ReaderDecision[];
};
