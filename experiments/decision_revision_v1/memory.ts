import type { ArmId, Packet, PublicHistory, PublicMessage } from "./types.ts";
import { hashToken, renderMessage, renderPacket, tokenize, wordCount } from "./text.ts";

/** Reviewable defaults from the proposal. Not frozen registration settings. */
export const SUMMARY_WORD_CAP = 256;
export const PACKET_WORD_CAP = 512;
export const RECENT_MESSAGE_COUNT = 4;
export const RETRIEVAL_K = 8;
export const FULL_DIM = 256;
export const PROJ_DIM = 64;
export const PROJECTION_SEED = 20261002;

const LEDGER_AUTHORITIES = new Set(["policy", "project-lead"]);
const LEDGER_TYPES = new Set(["policy", "state", "decision", "status"]);

const ARM_NOTES: Record<ArmId, string[]> = {
  summary_recent: [
    "Extractive summary: public policy, decision, state, and status records, capped at 256 words, then the last four messages.",
    "No paraphrase. An identifier counts only because its assertion text is copied with it.",
  ],
  nn_full: [
    "Development stand-in: signed hash embedding, 256 dimensions, cosine against the query.",
    "Not CM-1's pinned embedding model. Not an efficacy result.",
  ],
  nn_projected: [
    "Same signed hash embedding, then a fixed 64-d signed block projection (seed 20261002).",
    "Not CM-1's pinned projection. Not an efficacy result.",
  ],
  hme_hybrid: [
    "The CM-1 field readout is not linked in this fixture.",
    "Field status: MECHANISM_NOT_TESTED. The packet is identical to nn_projected.",
    "A numeric contribution that changes no rank must not be described as a field benefit.",
  ],
  decision_ledger: [
    "Admits policy, project-lead records of type policy, state, decision, or status whose effective time is at or before the cutoff and whose scope hits a queried project (policies always).",
    "One hop along public links, still subject to authority, type, and effective time.",
    "Overflow drops the latest effective records first. No answer key and no resolved truth labels.",
  ],
};

function fitWords(ranked: PublicMessage[], cap: number): PublicMessage[] {
  const kept = [...ranked];
  const weight = (message: PublicMessage) => wordCount(renderMessage(message));
  while (kept.reduce((sum, message) => sum + weight(message), 0) > cap && kept.length > 0) {
    kept.pop();
  }
  return kept.sort((a, b) => a.index - b.index);
}

function summaryPacket(history: PublicHistory): Packet {
  const priority: Record<string, number> = { policy: 0, decision: 1, state: 2, status: 3 };
  const ranked = history.messages
    .filter((message) => message.type in priority)
    .sort(
      (a, b) =>
        priority[a.type] - priority[b.type] || a.index - b.index,
    );
  const summary: PublicMessage[] = [];
  let words = 0;
  for (const message of ranked) {
    const next = wordCount(renderMessage(message));
    if (words + next > SUMMARY_WORD_CAP) continue;
    summary.push(message);
    words += next;
  }
  const recent = history.messages.slice(-RECENT_MESSAGE_COUNT);
  const seen = new Set(summary.map((message) => message.index));
  const body = [...summary];
  for (const message of recent) {
    if (!seen.has(message.index)) body.push(message);
  }
  const summaryIndex = new Set(summary.map((message) => message.index));
  let packed = [...body].sort((a, b) => a.index - b.index);
  while (wordCount(renderPacket(packed)) > PACKET_WORD_CAP) {
    const droppable = packed.filter((message) => summaryIndex.has(message.index));
    if (!droppable.length) break;
    const loser = droppable[droppable.length - 1];
    packed = packed.filter((message) => message.index !== loser.index);
    summaryIndex.delete(loser.index);
  }
  return finish("summary_recent", packed, "NOT_APPLICABLE");
}

function mulberry32(seed: number): () => number {
  let state = seed >>> 0;
  return () => {
    state = (state + 0x6d2b79f5) | 0;
    let t = Math.imul(state ^ (state >>> 15), 1 | state);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

let projectionSigns: Int8Array | null = null;

function signsForProjection(): Int8Array {
  if (projectionSigns) return projectionSigns;
  const random = mulberry32(PROJECTION_SEED);
  const signs = new Int8Array(FULL_DIM);
  for (let index = 0; index < FULL_DIM; index++) signs[index] = random() < 0.5 ? -1 : 1;
  projectionSigns = signs;
  return signs;
}

function embedFull(text: string): Float64Array {
  const vector = new Float64Array(FULL_DIM);
  for (const token of tokenize(text)) {
    const hash = hashToken(token);
    const bucket = hash % FULL_DIM;
    vector[bucket] += (hash & 1) === 0 ? 1 : -1;
  }
  return vector;
}

function project(full: Float64Array): Float64Array {
  const signs = signsForProjection();
  const out = new Float64Array(PROJ_DIM);
  const span = FULL_DIM / PROJ_DIM;
  for (let row = 0; row < PROJ_DIM; row++) {
    let sum = 0;
    for (let offset = 0; offset < span; offset++) {
      const column = row * span + offset;
      sum += signs[column] * full[column];
    }
    out[row] = sum;
  }
  return out;
}

function cosine(left: Float64Array, right: Float64Array): number {
  let dot = 0;
  let leftNorm = 0;
  let rightNorm = 0;
  for (let index = 0; index < left.length; index++) {
    dot += left[index] * right[index];
    leftNorm += left[index] * left[index];
    rightNorm += right[index] * right[index];
  }
  if (leftNorm === 0 || rightNorm === 0) return 0;
  return dot / Math.sqrt(leftNorm * rightNorm);
}

function retrievalPacket(history: PublicHistory, arm: "nn_full" | "nn_projected"): Packet {
  const queryVector =
    arm === "nn_full" ? embedFull(history.query) : project(embedFull(history.query));
  const ranked = history.messages
    .map((message) => {
      const full = embedFull(renderMessage(message));
      const vector = arm === "nn_full" ? full : project(full);
      return { message, score: cosine(queryVector, vector) };
    })
    .sort((a, b) => b.score - a.score || a.message.index - b.message.index)
    .slice(0, RETRIEVAL_K)
    .map((row) => row.message);
  return finish(arm, fitWords(ranked, PACKET_WORD_CAP), "NOT_APPLICABLE");
}

function ledgerAdmit(message: PublicMessage, history: PublicHistory): boolean {
  if (!message.id) return false;
  if (!LEDGER_AUTHORITIES.has(message.authority)) return false;
  if (!LEDGER_TYPES.has(message.type)) return false;
  if (message.effectiveAt > history.cutoff) return false;
  if (message.type === "policy") return true;
  return message.scope.some((project) => history.queriedProjects.includes(project));
}

function ledgerPacket(history: PublicHistory): Packet {
  const initial = history.messages.filter((message) => ledgerAdmit(message, history));
  const kept = new Map<string, PublicMessage>();
  for (const message of initial) {
    if (message.id) kept.set(message.id, message);
  }
  // Expand only the initial records; newly linked records cannot start another hop.
  for (const current of initial) {
    for (const link of current.links) {
      if (kept.has(link)) continue;
      const linked = history.messages.find((message) => message.id === link);
      if (!linked?.id) continue;
      if (!LEDGER_AUTHORITIES.has(linked.authority) || !LEDGER_TYPES.has(linked.type)) continue;
      if (linked.effectiveAt > history.cutoff) continue;
      kept.set(link, linked);
    }
  }
  const chronological = [...kept.values()].sort(
    (a, b) => a.effectiveAt - b.effectiveAt || a.index - b.index,
  );
  // fitWords drops from the end, so latest effective records go first when over budget.
  const fitted = fitWords(chronological, PACKET_WORD_CAP);
  return finish("decision_ledger", fitted, "NOT_APPLICABLE");
}

function finish(
  arm: ArmId,
  messages: PublicMessage[],
  fieldStatus: Packet["fieldStatus"],
): Packet {
  const ordered = [...messages].sort((a, b) => a.index - b.index);
  const text = renderPacket(ordered);
  return {
    arm,
    messages: ordered,
    text,
    words: wordCount(text),
    evidenceIds: ordered.map((message) => message.id).filter((id): id is string => Boolean(id)),
    notes: ARM_NOTES[arm],
    fieldStatus,
  };
}

/** Packet builders accept only the public history. They do not take the answer key. */
export function buildPackets(history: PublicHistory): Packet[] {
  const projected = retrievalPacket(history, "nn_projected");
  const hybrid: Packet = {
    ...projected,
    arm: "hme_hybrid",
    notes: ARM_NOTES.hme_hybrid,
    fieldStatus: "MECHANISM_NOT_TESTED",
    messages: projected.messages.map((message) => ({ ...message })),
  };
  return [
    summaryPacket(history),
    retrievalPacket(history, "nn_full"),
    projected,
    hybrid,
    ledgerPacket(history),
  ];
}

export const ARM_LABEL: Record<ArmId, string> = {
  summary_recent: "Summary + recent",
  nn_full: "Lexical NN (full)",
  nn_projected: "Lexical NN (projected)",
  hme_hybrid: "HME hybrid",
  decision_ledger: "Decision ledger",
};
