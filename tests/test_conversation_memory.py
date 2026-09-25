"""Development fixtures only; no real-model or held-out efficacy results."""
import hashlib
import json
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest

from experiments.conversation_memory_v1 import evaluate as e
from experiments.conversation_memory_v1.corpus import scenario, score
from experiments.conversation_memory_v1.memory import ARMS, RetrievalMemory, pack, word_count
from experiments.conversation_memory_v1.ollama import Ollama, validate_chat


def small_config():
    cfg = e.protocol()
    cfg["field"].update(projection_dimension=8, field_size=48, spacing=4)
    cfg["statistics"]["bootstrap_resamples"] = 100
    return cfg


def test_history_determinism_corrections_absence_and_source_identity():
    cfg = e.protocol()
    assert set(cfg["development_seeds"]).isdisjoint(range(cfg["seed_start"], cfg["seed_start"] + cfg["seed_count"]))
    for seed in cfg["development_seeds"]:
        history = scenario(seed)
        assert history == scenario(seed)
        assert len(history.messages) == 80 and len(history.questions) == 5
        records = {m.id: m for m in history.messages}
        for q in history.questions:
            assert set(q.evidence_ids) <= set(records)
            if q.answer is None:
                assert not q.evidence_ids
                assert all("purchase-order" not in m.text for m in history.messages)
            else:
                assert any(q.answer in records[i].text for i in q.evidence_ids)
                assert max(records[i].sequence for i in q.evidence_ids) < 50
        # The only evidence supplied to a reader is rendered message text.
        assert all(set(m) == {"id", "sequence", "text"} for m in history.public_history())
    assert scenario(113).digest() != scenario(127).digest()


def test_grading_correctness_grounding_staleness_and_abstention():
    h = scenario(113)
    update, absent, focus, resume = h.questions[1:]
    right = {"answer": update.answer, "evidence_ids": list(update.evidence_ids)}
    assert score(update, right, set(update.evidence_ids))["grounded_correct"]
    assert score(update, right, set())["answer_correct"]
    assert not score(update, right, set())["grounded_correct"]
    assert score(update, {"answer": update.stale_answers[0], "evidence_ids": []}, set())["stale_answer"]
    assert score(focus, {"answer": focus.other_project_answers[0], "evidence_ids": []}, set())["wrong_project_answer"]
    assert score(absent, {"answer": None, "evidence_ids": []}, set())["grounded_correct"]
    assert score(absent, {"answer": "PO-123", "evidence_ids": []}, set())["false_answer_on_absent"]
    assert not score(resume, {"answer": resume.answer, "evidence_ids": list(resume.evidence_ids[:1])}, set(resume.evidence_ids))["grounded_correct"]
    assert not score(update, {**right, "extra": "claim"}, set(update.evidence_ids))["valid_format"]
    assert not score(update, [right], set())["valid_format"]


def test_pack_caps_complete_records_and_preserves_chronology():
    h = scenario(113)
    selected = pack(h.messages, list(range(79, -1, -1)), 100)
    assert word_count("\n".join(m.render() for m in selected)) <= 100
    assert selected == sorted(selected, key=lambda m: m.sequence)
    assert not pack(h.messages, range(80), 1)


def test_embedding_fairness_raw_baseline_and_zero_field_control():
    cfg = small_config()
    h = scenario(113)
    vectors = np.random.default_rng(113).normal(size=(80, 12))
    memory = RetrievalMemory(h.messages, vectors, cfg["field"], 113)
    query = vectors[5]
    original = memory.rank(query)
    assert original["nn_full"]["order"][0] == 5
    assert original["nn_projected"]["order"][0] == 5
    np.testing.assert_allclose(memory.hybrid.vectors.real, memory.projected, atol=1e-14)
    memory.hybrid.replace_field(np.zeros_like(memory.hybrid._field))
    without_field = memory.rank(query)
    assert without_field["hme_hybrid"]["order"] == without_field["nn_projected"]["order"]
    assert memory.numeric_bytes()["hme_hybrid"] > memory.numeric_bytes()["nn_projected"]
    packets = e.contexts(h, "development summary", original, cfg)
    assert set(packets) == set(ARMS)
    assert all(word_count(p["text"]) <= cfg["memory_word_budget"] for p in packets.values())


def test_projection_rejects_invalid_or_zero_inputs():
    h = scenario(113)
    cfg = small_config()["field"]
    with pytest.raises(ValueError, match="Zero"):
        RetrievalMemory(h.messages, np.zeros((80, 12)), cfg, 113)
    with pytest.raises(ValueError, match="match"):
        RetrievalMemory(h.messages, np.ones((79, 12)), cfg, 113)


class FixtureClient:
    """Contract stub, deliberately not a language model or semantic encoder."""
    calls = 0

    def __init__(self, *args):
        pass

    def identity(self, *args):
        return {"models": {"reader": {"name": "fixture-reader"}, "embedder": {"name": "fixture-embedder"}}}

    def embed(self, name, texts):
        vectors = np.array([list(hashlib.sha256(t.encode()).digest()[:12]) for t in texts], dtype=float) - 127
        return vectors, {"model": name, "prompt_eval_count": 10}

    def chat(self, name, messages, options, *, json_output=False):
        self.calls += 1
        content = json.dumps({"answer": None, "evidence_ids": []}) if json_output else "No retained facts in this contract stub."
        return {"model": name, "done": True, "done_reason": "stop", "prompt_eval_count": 20, "eval_count": 10,
                "message": {"content": content}}


def test_end_to_end_development_fixture_and_logs(tmp_path):
    client = FixtureClient()
    cfg = small_config()
    runtime = {"identity": client.identity(), "embedding_dimension": 12}
    journal = e.Journal(tmp_path / "requests.jsonl")
    result = e.one_history(113, cfg, runtime, client, tmp_path, journal)
    assert len(result["observations"]) == 20
    assert result["summary_cost"]["calls"] == 8
    assert len({(r["question_id"], r["arm"]) for r in result["observations"]}) == 20
    assert sum(r["metrics"]["grounded_correct"] for r in result["observations"]) == 4
    assert all(r["memory_words"] <= 512 for r in result["observations"])
    entries = [json.loads(line) for line in journal.path.read_text().splitlines()]
    assert len([x for x in entries if x["event"] == "response"]) == 28
    assert (tmp_path / "embeddings_113.npz").is_file()
    # Smoke outcomes cannot be analyzed as the preregistered held-out sample.
    with pytest.raises(ValueError, match="seed set"):
        e.analyze([result], cfg)


def test_adapter_disables_embedding_truncation_and_pins_exact_tags(monkeypatch):
    client = Ollama()
    calls = []

    def request(endpoint, payload=None):
        calls.append((endpoint, payload))
        if endpoint == "/api/embed":
            return {"model": "embedder:one", "embeddings": [[1.0, 2.0]]}
        if endpoint == "/api/version":
            return {"version": "fixture"}
        if endpoint == "/api/tags":
            return {"models": [{"name": "reader:one", "digest": "abc"},
                                {"name": "embedder:one", "digest": "def"}]}
        return {"template": "fixed"}

    monkeypatch.setattr(client, "request", request)
    client.embed("embedder:one", ["sample"])
    assert calls[0][1]["truncate"] is False
    identity = client.identity("reader:one", "embedder:one")
    assert identity["models"]["embedder"]["digest"] == "def"
    with pytest.raises(ValueError, match="exact installed"):
        client.identity("reader", "embedder:one")


def test_truncated_generations_retained_before_rejection(tmp_path):
    class Truncated(FixtureClient):
        def chat(self, *args, **kwargs):
            return {"done": True, "done_reason": "length", "message": {"content": "partial"}}
    path = tmp_path / "requests.jsonl"
    with pytest.raises(RuntimeError, match="truncated"):
        e.generation(Truncated(), "fixture", [], e.protocol()["reader_options"], e.Journal(path), "fixture")
    entries = [json.loads(x) for x in path.read_text().splitlines()]
    assert entries[-1]["response"]["message"]["content"] == "partial"
    with pytest.raises(RuntimeError, match="token"):
        validate_chat({"done": True, "done_reason": "stop", "message": {"content": "x"}}, e.protocol()["reader_options"])
    with pytest.raises(RuntimeError, match="pinned"):
        validate_chat({"done": True, "done_reason": "stop", "model": "other"},
                      e.protocol()["reader_options"], "expected")


def test_seed_bootstrap_pairs_histories_and_refuses_missing_outcomes(tmp_path):
    cfg = small_config()
    cfg.update(seed_start=113, seed_count=1)
    client = FixtureClient()
    run = e.one_history(113, cfg, {"identity": client.identity(), "embedding_dimension": 12}, client,
                        tmp_path, e.Journal(tmp_path / "requests.jsonl"))
    analysis = e.analyze([run], cfg)
    assert all(v == .2 for v in analysis["grounded_accuracy"].values())
    assert analysis["hybrid_minus"]["nn_full"]["ci95_pp"] == [0.0, 0.0]
    assert not analysis["registered_gain_passed"]
    run["observations"].pop()
    with pytest.raises(ValueError, match="Missing or duplicate"):
        e.analyze([run], cfg)


def test_smoke_never_claims_efficacy_and_failure_is_durable(tmp_path, monkeypatch):
    cfg = small_config()
    runtime = {"identity": FixtureClient().identity(), "embedding_dimension": 12,
               "source_hashes": e.source_hashes(), "software": e.software(), "base_url": "fixture"}
    manifest = tmp_path / "runtime.json"
    e.write_json(manifest, runtime)
    monkeypatch.setattr(e, "protocol", lambda: cfg)
    monkeypatch.setattr(e, "Ollama", FixtureClient)
    args = SimpleNamespace(runtime=manifest, url=None, output=tmp_path / "smoke")
    e.execute(args, smoke=True)
    status = json.loads((args.output / "status.json").read_text())
    assert status["status"] == "complete" and not status["efficacy_claim_permitted"]
    assert not (args.output / "analysis.json").exists()
    with pytest.raises(FileExistsError):
        e.execute(args, smoke=True)

    class Broken(FixtureClient):
        def chat(self, *args, **kwargs):
            raise RuntimeError("fixture outage")
    monkeypatch.setattr(e, "Ollama", Broken)
    args.output = tmp_path / "failed"
    with pytest.raises(RuntimeError, match="fixture outage"):
        e.execute(args, smoke=True)
    status = json.loads((args.output / "status.json").read_text())
    assert status["status"] == "failed" and not status["efficacy_claim_permitted"]
    assert "fixture outage" in (args.output / "failure.txt").read_text()


def test_registration_rejects_unpublished_or_changed_bytes(tmp_path, monkeypatch):
    with pytest.raises(ValueError, match="40-character"):
        e.verify_registration("not-a-commit", tmp_path / "runtime.json", {})
    with pytest.raises(ValueError, match="source changed"):
        e.verify_registration("a" * 40, tmp_path / "runtime.json", {"source_hashes": {}})
