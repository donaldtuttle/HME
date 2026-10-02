import { buildCorpus } from "./generator.ts";

/** Illustrative development fixture. Not the held-out evaluation corpus. */
export const CORPUS = buildCorpus();

export function historyById(id: string) {
  return CORPUS.find((history) => history.id === id);
}
