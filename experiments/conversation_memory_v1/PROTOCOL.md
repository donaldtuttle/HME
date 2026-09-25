# HME-CM-1: project memory after interruptions

**Prepared protocol, not a completed model evaluation.** The protocol, code and
development tests are publishable now. A real execution additionally requires
an installed Ollama reader and embedding model, a generated runtime manifest,
and a public Git commit containing that manifest and the exact source bytes.
No held-out conversation outcomes have been generated in this environment.

The [machine-readable settings](protocol.json) define the experiment. This is a
new application-level test, not a rerun of Stage 2 and not the polarity-preserving
encoder redesign whose Stage 3 gate failed. Existing negative results stand.

## Task and scope

Thirty synthetic project histories use seeds 601001 through 601030. Each has 80
ordered messages: a project's decisions, a similar second project, explicit
corrections, a pending task and its cleared blocker, followed by interruptions.
Five questions test remembered reasons, corrected deadlines, absent information,
project separation, and resuming a pending task. The correct short answers and
necessary evidence IDs come from the generator and are never passed to retrieval,
summarization, or the reader. The last 30 messages contain no target evidence.

Development seeds 113, 127 and 131 are separate. Test seeds change names, values,
evidence placement and distractors; they use the same templates. This is held-out
instantiation, not held-out language or proof of natural-conversation performance.
Questions explicitly identify the project. Implicit topic inference, changing
user goals, prompt injection, external truth verification and open-ended prose
are outside scope. The facts are authoritative synthetic user statements.

## Four arms and attribution

1. **summary_recent:** the same reader builds a rolling summary, without seeing
   any evaluation questions. It processes the first 76 messages in batches of
   ten, retaining at most 256 whitespace-separated words. The last four original
   messages are appended at answer time.
2. **nn_full:** exact signed-cosine retrieval over the original semantic vectors.
3. **nn_projected:** exact signed-cosine retrieval after a fixed Gaussian random
   projection to 64 dimensions and L2 normalization.
4. **hme_hybrid:** the same 64-dimensional projected vectors, plus the existing
   Stage 2 candidate-specific field readout: 0.42 times signed cosine plus 0.20
   times magnitude pattern correlation.

The full-dimensional arm prevents an apparent gain caused by handicapping NN
with the projection HME needs for manageable two-dimensional patterns. Hybrid
minus projected NN isolates adding the field; hybrid minus full NN answers the
practical comparison. The projection is shared and seeded before outcomes, with
no training or tuning. HME's existing encoder is unchanged. Its Hann option is
off in this experiment because embedding dimensions have no temporal window;
both projected arms receive exactly the same normalized vectors. Field polarity
ambiguity remains. Nothing here reinstates the failed Stage 3 gate.

Eighty message patterns occupy an independently permuted 8-by-10 grid. Patterns
are 64-by-64, spacing is 32 (50% adjacent axis overlap), field size is 512-by-512,
all writes use the engine's default strength, and there is no decay or eviction.
Positions have no semantic meaning and no target address reaches a query.
Optional evolving-field runtime, salience and session-vector conditioning are off.

All retrieval arms retain the same original text, chronology, IDs and metadata.
No arm gets answer-derived relevance labels, project filters, correction links
or an oracle latest-value resolver. The common reader instruction gives explicit
corrections precedence and separates projects. Any learned summary-policy benefit
is distinct from a field benefit.

## Budget and inference contract

Each retrieval arm selects eight messages by stable descending score, packs
whole messages into at most 512 whitespace-separated words, then presents them
chronologically. Summary plus recent messages has the same maximum word budget.
This is **equal maximum reference-word allowance**, not equal consumed model
tokens or bytes. Actual prompt tokens are recorded per call. Shorter packets
are not padded. All arms use the same reader prompt, generation limit and 8192
context setting. Inputs are short; missing token accounting, incomplete outputs
or outputs exhausting generation length halt the run. Embedding requests set
truncate=false. Ollama does not provide an independent proof that a chat prompt
was not truncated; the small word cap and token/context margin are safeguards,
not such a proof. Differences in generated summaries remain part of that arm.

There is one response per question/arm, temperature zero, fixed reader seed, and
rotated arm order. Inference receives a fresh message list for every answer.
Seeding is not a promise of bit-identical GPU inference. The primary unit is the
independent history, not the 600 individual answers. A second model is a separate
registered run, not a reason to pool or selectively publish results.

## Scoring and decision

The reader returns exactly two JSON fields: a short source phrase (or null) and
evidence_ids. Answer comparison case-folds, normalizes whitespace and trims outer
quotes/periods. It does not use an LLM judge or accept arbitrary paraphrases.

The primary endpoint is **grounded short-answer accuracy**: the value must match
and the citation set must equal the required evidence set, with those IDs present
in the supplied memory. The resumption answer needs both the pending-task and
blocker-cleared records. Correct abstention is null with an empty citation list.
An extra/missing citation fails strict grounding even when the answer is correct;
answer-only accuracy is also reported so this distinction stays visible.

For a summary, available evidence IDs mean IDs mentioned in that summary or recent
messages, intersected with the actual history. This is not raw-message retrieval
coverage. Evidence recall is therefore reported only for retrieval arms.

Also report per-category answer accuracy, grounded accuracy, known stale values,
known other-project values, invalid JSON/format, and unverified answers. An
unverified answer is a non-null answer that fails strict grounding; it is **not a
general hallucination rate**. Malformed answers count as abstention failures on
absent-information questions. Wrong paraphrases or extra citations can contribute
to these failures without establishing fabricated content.

Average the five grounded outcomes within each history. Bootstrap paired
history-level differences 20,000 times using seed 2026092502 and report 95%
percentile intervals. A registered practical field benefit requires all three:

- Hybrid minus full-dimensional NN: lower interval endpoint above +5 percentage
  points on the primary endpoint.
- Hybrid minus projected NN: lower endpoint above zero, establishing an
  incremental field contribution in the matched representation.
- Hybrid minus full NN on absent-information failure: upper endpoint at most
  +5 percentage points, limiting the registered tradeoff in unsupported answers.

Other comparisons and category slices are descriptive, not independently
confirmed discoveries. A failure to pass is not equivalence, proof of universal
failure, or justification to tune on the test set. Thirty histories give limited
power, especially for one question per category; intervals must remain visible.

## Costs, raw data and failure handling

Record complete prompts/responses, model-reported tokens, reader wall times,
summary construction costs, embeddings, full candidate scores/ranks, chosen
message IDs, gold answers, and per-answer metrics. Embeddings are persisted in
compressed NumPy files with hashes. Model tags/digests, full show-response hashes,
Ollama version, software versions and a human-supplied hardware description are
pinned before held-out execution; identity is checked before and after each
history. Weight digests are registry identities, not independent re-hashing of
every local weight byte.

Numeric state sizes are reported separately from common stored text and Python
object overhead. They are **not total storage or peak RSS**. Shared-harness
embedding/build/ranking times are labelled as such, not arm-specific latency.
Real reader wall times and summary costs are available for the user-facing cost
comparison; no capacity or total-memory efficiency claim is preregistered.

No automatic retries, overwriting results, partial-sample confirmatory analysis,
or silent model substitutions. Invalid final JSON is scored as failure; transport,
identity, missing token counts or truncation failures stop execution and preserve
raw responses/status. Any full rerun requires a published amendment identifying
the failed run. Publish all registered histories, including negative outcomes.

## Relationship to existing benchmarks

[LongMemEval](https://github.com/xiaowu0162/LongMemEval) evaluates memory across
sessions, information updates, temporal reasoning and abstention. Its
[ICLR 2025 paper](https://arxiv.org/abs/2410.10813) motivates measuring retrieval
and answer generation separately. HME-CM-1 uses original scripted histories and
its own strict scoring; **it is not a LongMemEval score**. A published-dataset run
requires a separate adapter and registration after this harness is exercised.

Ollama adapter contracts:
[embed](https://docs.ollama.com/api/embed),
[chat](https://docs.ollama.com/api/chat),
[tags](https://docs.ollama.com/api/tags).

See [RUN_LOCAL.md](RUN_LOCAL.md) for preparation, smoke testing, publication and
the held-out run. Preparing or smoke-testing does not authorize an efficacy claim.
