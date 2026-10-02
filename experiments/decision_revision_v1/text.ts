import type { PublicHistory, PublicMessage, History } from "./types.ts";

export function wordCount(text: string): number {
  const trimmed = text.trim();
  if (!trimmed) return 0;
  return trimmed.split(/\s+/).length;
}

export function renderMessage(message: PublicMessage): string {
  if (!message.id) return message.text;
  const scope = message.scope.length ? message.scope.join("+") : "none";
  const links = message.links.length ? message.links.join("+") : "none";
  const head = `${message.id} · type=${message.type} · authority=${message.authority} · effective=${message.effectiveAt} · scope=${scope} · links=${links}`;
  return `${head}\n${message.text}`;
}

export function renderPacket(messages: PublicMessage[]): string {
  return [...messages]
    .sort((a, b) => a.index - b.index)
    .map(renderMessage)
    .join("\n\n");
}

export function tokenize(text: string): string[] {
  return text
    .toLowerCase()
    .replace(/[^a-z0-9_]+/g, " ")
    .split(/\s+/)
    .filter((token) => token.length > 1);
}

export function hashToken(token: string): number {
  let hash = 2166136261;
  for (let i = 0; i < token.length; i++) {
    hash ^= token.charCodeAt(i);
    hash = Math.imul(hash, 16777619);
  }
  return hash >>> 0;
}

export function toPublic(history: History): PublicHistory {
  return {
    id: history.id,
    messages: history.messages,
    query: history.query,
    cutoff: history.model.cutoff,
    queriedProjects: history.model.decisions.map((decision) => decision.projectId),
    queriedDecisionIds: history.queriedDecisionIds,
  };
}

export function sameStringSet(left: string[], right: string[]): boolean {
  if (left.length !== right.length) return false;
  if (new Set(left).size !== left.length) return false;
  if (new Set(right).size !== right.length) return false;
  const a = [...left].sort();
  const b = [...right].sort();
  return a.every((value, index) => value === b[index]);
}
