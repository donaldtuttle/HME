/**
 * HME-CM-REV-1 illustrative fixture.
 * Status: DESIGN. Not a registered evaluation. The CM-1 field is not linked.
 *
 * generator   matched pairs, public messages, hidden model
 * solver      RETAIN / REVISE / DEFER from effective facts
 * memory      summary, lexical NN, projection, hybrid, ledger
 * score       both decisions, support set, packet membership
 * preflight   one-message pair diff, key leakage, 512-word cap
 */

export { actionTally, buildCorpus, PAIR_TITLE, THEMES } from "./generator.ts";
export type { Theme } from "./generator.ts";

export { solve } from "./solver.ts";
export type { PremiseTrace, SolvedDecision } from "./solver.ts";

export {
  ARM_LABEL,
  buildPackets,
  FULL_DIM,
  PACKET_WORD_CAP,
  PROJ_DIM,
  PROJECTION_SEED,
  RECENT_MESSAGE_COUNT,
  RETRIEVAL_K,
  SUMMARY_WORD_CAP,
} from "./memory.ts";

export { parseReaderJson, scoreHistory } from "./score.ts";
export type { DecisionScore, Score } from "./score.ts";

export { runPreflight } from "./preflight.ts";
export type { Check } from "./preflight.ts";

export { CORPUS, historyById } from "./corpus.ts";
export { diagnose, diagnoseHistory, oracleResponse, summarizeArms, supportAvailable } from "./diagnose.ts";
export type { ArmDiagnostic, ArmSummary } from "./diagnose.ts";
export { baselineResponse, BASELINE_LABEL, scoreBaseline } from "./baselines.ts";
export type { BaselineId } from "./baselines.ts";
export { ARM_SUMMARY, BASELINE_SUMMARY, PREFLIGHT } from "./report.ts";
export { GUIDE, guideMarkdown } from "./user-guide.ts";
export type {
  Action,
  ArmId,
  Assertion,
  Condition,
  DecisionSpec,
  ExpectedDecision,
  FieldStatus,
  HiddenModel,
  History,
  MessageType,
  Packet,
  PairId,
  PolicyModel,
  PolicyRule,
  PublicHistory,
  PublicMessage,
  ReaderDecision,
  ReaderResponse,
  Side,
  Withdrawal,
} from "./types.ts";
