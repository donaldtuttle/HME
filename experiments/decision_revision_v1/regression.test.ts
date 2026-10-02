import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { describe, it } from "node:test";
import { baselineResponse, scoreBaseline } from "./baselines.ts";
import { CORPUS } from "./corpus.ts";
import { diagnoseHistory, summarizeArms } from "./diagnose.ts";
import { buildPackets } from "./memory.ts";
import { parseReaderJson, scoreHistory } from "./score.ts";
import { toPublic } from "./text.ts";
import { guideMarkdown } from "./user-guide.ts";
import type { History, ReaderResponse } from "./types.ts";

function responseFor(history: History): ReaderResponse {
  return { decisions: history.queriedDecisionIds.map((id) => ({
    decision_id: id,
    action: history.expected[id].action,
    selected_option_id: history.expected[id].optionId,
    decisive_premise_ids: [...history.expected[id].decisive],
    unresolved_premise_ids: [...history.expected[id].unresolved],
    evidence_ids: [...history.model.supports[id][0]],
  })) };
}

function visibleIds(history: History): string[] {
  return history.messages.flatMap((message) => message.id ? [message.id] : []);
}

describe("decision revision regressions", () => {
  it("refuses scoring when any expected field disagrees with the solver or is missing", () => {
    const mutations: ((history: History) => void)[] = [
      (h) => { h.model.assertions = h.model.assertions.filter((a) => a.evidenceId !== "E05"); },
      (h) => { h.expected.D_ALDER.action = "RETAIN"; },
      (h) => { h.expected.D_ALDER.optionId = "RIG_A"; },
      (h) => { h.expected.D_ALDER.decisive = []; },
      (h) => { h.expected.D_ALDER.unresolved = ["P_SHADOW"]; },
      (h) => { delete h.expected.D_ALDER; },
      (h) => { h.model.decisions.pop(); },
    ];
    for (const mutate of mutations) {
      const history = structuredClone(CORPUS.find((h) => h.id === "alder-cc-1")!);
      const response = responseFor(history);
      mutate(history);
      const score = scoreHistory(history, response, visibleIds(history));
      assert.equal(score.scorable, false);
      assert.equal(score.primary, 0);
      assert.equal(score.actionOnly, 0);
      assert.equal(score.formatOk, true);
      assert.equal(score.formatError, null);
      assert.match(score.integrityError ?? "", /not scorable/);
      assert.deepEqual(score.decisions, []);
    }
  });

  it("excludes invalid histories from arm denominators", () => {
    const history = structuredClone(CORPUS[0]);
    history.expected = {};
    const totals = summarizeArms([history, CORPUS[1]]);
    assert.equal(totals.length, 5);
    for (const row of totals) {
      assert.equal(row.histories, 1);
      assert.equal(row.invalidHistories, 1);
    }
  });

  it("gives always-retain its recorded options and 16/32 action-and-option successes", () => {
    let successes = 0;
    for (const history of CORPUS) {
      const response = baselineResponse(history, "always_retain");
      for (const decision of response.decisions) {
        assert.equal(decision.selected_option_id, history.model.decisions.find((d) => d.id === decision.decision_id)?.recordedOptionId);
      }
      const scored = scoreBaseline(history, "always_retain");
      assert.equal(scored.primary, 0);
      successes += scored.actionOnly;
    }
    assert.equal(successes, 16);
  });

  it("constructs baseline choices from public records independently of the hidden answers", () => {
    for (const history of CORPUS) {
      const altered = structuredClone(history);
      altered.expected = {};
      altered.model.assertions = [];
      altered.model.withdrawals = [];
      altered.model.supports = {};
      altered.model.policy.options = [];
      for (const decision of altered.model.decisions) decision.recordedOptionId = "HIDDEN_SENTINEL";
      for (const baseline of ["always_retain", "always_revise", "always_defer", "latest_mentioned_option"] as const) {
        assert.deepEqual(baselineResponse(altered, baseline), baselineResponse(history, baseline));
      }
    }
  });

  it("names a different public option for always-revise only when one exists", () => {
    for (const history of CORPUS) {
      const response = baselineResponse(history, "always_revise");
      for (const given of response.decisions) {
        const current = history.model.decisions.find((d) => d.id === given.decision_id)!.recordedOptionId;
        const alternative = history.model.policy.options.find((o) => o.id !== current)?.id ?? null;
        assert.equal(given.action, "REVISE");
        assert.equal(given.selected_option_id, alternative);
      }
    }
  });

  it("expands only one link hop and still filters authority and effective time", () => {
    const history = toPublic(structuredClone(CORPUS[0]));
    history.messages.find((m) => m.id === "E03")!.links.push("LINK1", "DRAFT", "FUTURE");
    for (const [offset, id, links, authority, effectiveAt] of [
      [15, "LINK1", ["LINK2"], "project-lead", 1],
      [16, "LINK2", [], "project-lead", 1],
      [17, "DRAFT", [], "unverified-draft", 1],
      [18, "FUTURE", [], "project-lead", 120],
    ] as const) {
      history.messages[offset] = {
        index: offset + 1, id, links: [...links], authority, effectiveAt,
        type: "state", scope: ["Other"], text: "Linked record.",
      };
    }
    const packet = buildPackets(history).find((p) => p.arm === "decision_ledger")!;
    assert.ok(packet.evidenceIds.includes("LINK1"));
    for (const id of ["LINK2", "DRAFT", "FUTURE"]) assert.ok(!packet.evidenceIds.includes(id), id);
  });

  it("keeps full-history correctness distinct from reasoning over an incomplete packet", () => {
    const history = CORPUS.find((h) => h.id === "alder-cc-1")!;
    const row = diagnoseHistory(history).find((r) => r.arm === "nn_projected")!;
    assert.equal(row.solved[0].action, "RETAIN");
    assert.equal(history.expected.D_ALDER.action, "REVISE");
    assert.equal(row.score.primary, 0);
    assert.equal(row.score.scorable, true);
    assert.equal(row.supportAvailable, false);
  });

  it("accepts all 44 listed support combinations", () => {
    let count = 0;
    for (const history of CORPUS) {
      const [a, b] = history.queriedDecisionIds;
      for (const aSet of history.model.supports[a]) for (const bSet of history.model.supports[b]) {
        const response = responseFor(history);
        response.decisions[0].evidence_ids = [...aSet];
        response.decisions[1].evidence_ids = [...bSet];
        const score = scoreHistory(history, response, visibleIds(history));
        assert.equal(score.scorable, true);
        assert.equal(score.primary, 1, history.id);
        count++;
      }
    }
    assert.equal(count, 44);
  });

  it("rejects 544 incorrect, duplicate, incomplete or invisible-evidence cases", () => {
    let count = 0;
    for (const history of CORPUS) {
      const good = responseFor(history);
      const check = (response: ReaderResponse, visible = visibleIds(history)) => {
        const score = scoreHistory(history, response, visible);
        assert.equal(score.scorable, true);
        assert.equal(score.primary, 0, history.id);
        count++;
      };
      for (let i = 0; i < 2; i++) {
        for (const field of ["decisive_premise_ids", "unresolved_premise_ids", "evidence_ids"] as const) {
          const bad = structuredClone(good);
          const token = bad.decisions[i][field][0] ?? "P_FAKE";
          bad.decisions[i][field].push(token, token);
          check(bad);
        }
        check(good, visibleIds(history).filter((id) => id !== good.decisions[i].evidence_ids[0]));
        const option = structuredClone(good);
        option.decisions[i].selected_option_id = "NOT_AN_OPTION";
        check(option);
        const premise = structuredClone(good);
        premise.decisions[i].decisive_premise_ids = ["P_FAKE"];
        check(premise);
        const action = structuredClone(good);
        action.decisions[i].action = action.decisions[i].action === "RETAIN" ? "REVISE" : "RETAIN";
        check(action);
      }
      check({ decisions: [good.decisions[0], structuredClone(good.decisions[0])] });
      check({ decisions: [good.decisions[0]] });
      check({ decisions: [...good.decisions, { ...good.decisions[0], decision_id: "D_FAKE" }] });
    }
    assert.equal(count, 544);
    for (const raw of ["bad json", "null", "[]", "{}", '{"decisions":{}}', '{"decisions":[{}]}']) {
      assert.equal(parseReaderJson(raw).ok, false);
    }
  });

  it("keeps the downloadable guide identical to the UI guide and states the scoring boundary", () => {
    const guide = guideMarkdown();
    assert.equal(guide, readFileSync(new URL("./USER_GUIDE.md", import.meta.url), "utf8"));
    assert.match(guide, /Scoring always uses the full-history answer key/);
    assert.match(guide, /unscorable and excluded from outcome totals/);
  });
});
