import { BASELINE_LABEL, type BaselineId, scoreBaseline } from "./baselines.ts";
import { CORPUS } from "./corpus.ts";
import { summarizeArms } from "./diagnose.ts";
import { runPreflight } from "./preflight.ts";

export const PREFLIGHT = runPreflight(CORPUS);
export const ARM_SUMMARY = summarizeArms(CORPUS);

const BASELINES: BaselineId[] = [
  "always_retain",
  "always_revise",
  "always_defer",
  "latest_mentioned_option",
];

export const BASELINE_SUMMARY = BASELINES.map((baseline) => {
  let actionOnly = 0;
  let grounded = 0;
  let invalidHistories = 0;
  for (const history of CORPUS) {
    const score = scoreBaseline(history, baseline);
    if (!score.scorable) {
      invalidHistories += 1;
      continue;
    }
    grounded += score.primary;
    actionOnly += score.actionOnly;
  }
  return {
    baseline,
    label: BASELINE_LABEL[baseline],
    grounded,
    actionOnly,
    histories: CORPUS.length - invalidHistories,
    invalidHistories,
  };
});
