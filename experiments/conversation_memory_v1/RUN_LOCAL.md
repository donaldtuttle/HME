# Run HME-CM-1 on a local Ollama installation

The implementation is ready for a real model run. The current hosted workspace
has no reachable Ollama service and no configured model credentials. Its offline
fixtures validate plumbing only; no conversation-quality percentages are reported.

Use a clean checkout of HME on the machine that runs Ollama. These commands run
from the repository root. Windows PowerShell and a Python virtual environment work;
replace python with the interpreter used to install HME if necessary.

## 1. Install the harness and inspect installed models

```bash
python -m pip install -e ".[test]"
python experiments/conversation_memory_v1/evaluate.py inspect
```

Ollama must already be running. The command only lists its version and models;
it does not download or invoke a model. Choose one exact installed chat-model
name and one exact installed embedding-model name, including their tags. The
example below uses llama3.2:3b and nomic-embed-text:latest; substitute the names
actually reported by inspect. The harness never downloads models automatically.
If an embedding model is missing, install one through Ollama before continuing.

## 2. Pin the runtime using development-only probes

```bash
git switch -c conversation-runtime-v1
python experiments/conversation_memory_v1/evaluate.py prepare --reader llama3.2:3b --embedder nomic-embed-text:latest --hardware "Describe CPU/GPU, RAM and OS here"
```

This creates experiments/conversation_memory_v1/runtime.json, including model
digests, Ollama version, embedding dimension, source hashes and a small development
probe. It runs no held-out history. Runtime tags must resolve exactly; no fallback
model is allowed. An existing manifest is never overwritten.

## 3. Exercise one development history

```bash
python experiments/conversation_memory_v1/evaluate.py smoke --output outputs/conversation_smoke_v1
```

This uses development seed 113: 20 answer calls and eight incremental-summary
calls. Results are explicitly marked development, with efficacy claims disabled.
Inspect status.json and requests.jsonl. Do not choose settings from held-out
performance. Fix contract defects before registration; if source changes, produce
a fresh runtime manifest because its source hashes will no longer match.

## 4. Publish the exact runtime before evaluating

```bash
python scripts/update_manifest.py
git add experiments/conversation_memory_v1/runtime.json MANIFEST.sha256
git commit -m "Preregister HME-CM-1 local runtime before evaluation"
git push -u origin conversation-runtime-v1
git fetch origin
git rev-parse HEAD
```

Keep the full 40-character commit returned by the last command. This is the
execution registration, including actual model/runtime pins. The earlier harness
commit alone is insufficient. The source and protocol must remain byte-identical.
The runner verifies the commit and requires a fetched origin ref containing it;
the public repository history supplies the independently inspectable chronology.

## 5. Run all registered histories once

Replace REGISTRATION_SHA with that full commit:

```bash
python experiments/conversation_memory_v1/evaluate.py run --registration-commit REGISTRATION_SHA --output outputs/conversation_memory_v1
```

The output directory must not exist. This executes 30 histories, 600 answer calls,
240 summary calls, and embedding batches. Generation time depends on the machine
and model; no duration is promised. Progress is printed per history and raw calls
are written as they finish. The reader and embedder must stay installed unchanged.

On success, analysis.json contains paired intervals and the registered decision.
Keep the whole output directory: raw requests/responses, status, runtime, history
files, seed files and embedding arrays are necessary evidence. Do not publish
only the aggregate or discard failed cases. A technical failure preserves status
and a traceback; it does not produce a confirmatory result. Publish a deviation
and a new registration before rerunning the full held-out set.

## What this run can establish

It can compare remembered decisions, corrections, missing-information responses,
project separation and one-step task resumption on scripted histories. It cannot
establish general conversational intelligence, an open-ended hallucination rate,
or a LongMemEval result. See the [protocol](PROTOCOL.md) for exact scoring and gates.
