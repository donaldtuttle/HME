import assert from "node:assert/strict";
import { describe, it } from "node:test";
import { scoreBaseline } from "./baselines.ts";
import { CORPUS } from "./corpus.ts";
import { diagnoseHistory } from "./diagnose.ts";
import { runPreflight } from "./preflight.ts";
import { parseReaderJson, scoreHistory } from "./score.ts";
import { solve } from "./solver.ts";

describe("decision revision fixture", () => {
  it("passes preflight", () => {
    const checks = runPreflight(CORPUS);
    const failed = checks.filter((check) => !check.pass);
    assert.deepEqual(
      failed.map((check) => `${check.id}: ${check.detail}`),
      [],
    );
  });

  it("keeps the Alder changed-constraint wording from the proposal", () => {
    const history = CORPUS.find((item) => item.id === "alder-cc-1");
    assert.ok(history);
    assert.equal(history.side, "target");
    const text = (id: string) => history.messages.find((message) => message.id === id)?.text ?? "";
    assert.match(
      text("E01"),
      /^For Project Alder, use Rig A while precise shadow placement is required\. If that requirement is removed and the preview deadline is under ten minutes, use Rig B\. Rig B satisfies all remaining requirements\. Otherwise keep Rig A\./,
    );
    assert.equal(
      text("E02"),
      "Project Alder currently requires precise shadow placement and has an eight-minute preview deadline.",
    );
    assert.equal(
      text("E03"),
      "We selected Rig A for Project Alder because precise shadow placement is required.",
    );
    assert.equal(
      text("E04"),
      "Project Birch independently requires precise shadow placement, uses Rig A, and follows the same rule.",
    );
    assert.equal(
      text("E05"),
      "Project Alder no longer requires precise shadow placement. Its eight-minute preview deadline remains.",
    );
    const solved = solve(history.model);
    assert.equal(solved[0]?.action, "REVISE");
    assert.equal(solved[0]?.optionId, "RIG_B");
    assert.equal(solved[1]?.action, "RETAIN");
    assert.equal(solved[1]?.optionId, "RIG_A");
  });

  it("scores a grounded answer as 1 and an uncited answer as an action-only success", () => {
    const history = CORPUS.find((item) => item.id === "alder-cc-1");
    assert.ok(history);
    const good = parseReaderJson(
      JSON.stringify({
        decisions: [
          {
            decision_id: "D_ALDER",
            action: "REVISE",
            selected_option_id: "RIG_B",
            decisive_premise_ids: ["P_DEADLINE", "P_SHADOW"],
            unresolved_premise_ids: [],
            evidence_ids: ["E01", "E02", "E03", "E05"],
          },
          {
            decision_id: "D_BIRCH",
            action: "RETAIN",
            selected_option_id: "RIG_A",
            decisive_premise_ids: ["P_SHADOW"],
            unresolved_premise_ids: [],
            evidence_ids: ["E01", "E04"],
          },
        ],
      }),
    );
    assert.equal(good.ok, true);
    if (!good.ok) return;
    const packet = history.messages.map((message) => message.id).filter((id): id is string => Boolean(id));
    const scored = scoreHistory(history, good.value, packet);
    assert.equal(scored.primary, 1);
    assert.equal(scored.targetGrounded, 1);
    assert.equal(scored.controlGrounded, 1);

    const uncited = structuredClone(good.value);
    uncited.decisions[0].evidence_ids = [];
    uncited.decisions[1].evidence_ids = [];
    const partial = scoreHistory(history, uncited, packet);
    assert.equal(partial.primary, 0);
    assert.equal(partial.actionOnly, 1);
  });

  it("does not let baselines earn a grounded success", () => {
    for (const history of CORPUS) {
      for (const baseline of ["always_retain", "always_revise", "always_defer", "latest_mentioned_option"] as const) {
        assert.equal(scoreBaseline(history, baseline).primary, 0, `${history.id} ${baseline}`);
      }
    }
  });

  it("shows the ledger and the lexical proxy disagree on at least one revise history", () => {
    const revise = CORPUS.filter((history) => {
      const target = history.model.decisions[0];
      return target && history.expected[target.id]?.action === "REVISE";
    });
    const differs = revise.some((history) => {
      const rows = diagnoseHistory(history);
      const ledger = rows.find((row) => row.arm === "decision_ledger");
      const lexical = rows.find((row) => row.arm === "nn_full");
      return ledger && lexical && ledger.packet.text !== lexical.packet.text;
    });
    assert.equal(differs, true);
  });
});
