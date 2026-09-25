# HME-CM-1 execution status

**Implemented and verified offline; real-model evaluation not run.**

The active suite has 128 passing tests: the previous 117 plus 11 conversation
harness checks. The new checks use development seeds 113, 127 and 131, small
numeric fixtures, and explicit HTTP/reader contract stubs. Stub outputs are not
semantic embeddings or language-model evidence and are not published as scores.

Verified behavior includes deterministic histories; separate gold labels;
corrected/stale/wrong-project/absent-answer grading; required source citations;
whole-message word budgets; a full-dimensional NN baseline; matched projected
vectors; zero-field ranking equality; embedding truncation disabled; exact model
names/digests; raw truncated responses retained before rejection; paired-history
analysis; refusal of incomplete samples; and no efficacy claim from smoke runs.

The local runtime inspection failed with connection refused at
http://localhost:11434. No Ollama binary or configured model API credentials were
available in this hosted workspace. No actual reader/encoder inference was
performed, no held-out seed was executed, and runtime.json has not been created.

The [protocol](PROTOCOL.md) and implementation are prepared. A complete execution
registration requires the local model digests, Ollama/software identity, hardware
description and source pins produced by the prepare command, publicly committed
before the first held-out run. The [local guide](RUN_LOCAL.md) gives those steps.

Pending evidence: the real-model development smoke run and all 30 held-out
histories (600 answers, plus 240 summary updates). Conversation efficacy, latency
and model-dependent outcomes remain unknown. The earlier Stage 2 negative result
and all historical evidence are unchanged.
