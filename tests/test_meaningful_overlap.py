"""HME-MO-1 correctness fixtures. Never generate reserved test corpora."""
import copy
import json
from pathlib import Path
import subprocess

import numpy as np
import pytest

from experiments.meaningful_overlap_v1 import dataset as data, placement as pl
from experiments.meaningful_overlap_v1 import retrieval as ret, statistics as st
from experiments.meaningful_overlap_v1 import evaluate as ev, integrity, costs

NS = "HME-MO-1/development/002"


def tiny():
    p = ev.config()
    p["dataset"].update(items=8, families=2, members_per_family=4, dimension=8,
        canvas=32, grid_shape=[2, 4], overlap_spacing=4, separated_spacing=8,
        search_restarts=2, swap_proposals=64)
    p["descriptive"].update(larger_canvas=64, larger_spacing=6)
    p["costs"].update(query_count=2, warmups=1, repetitions=1, cache_cycles=1)
    p["statistics"]["resamples"] = 200
    return p


def fixture(kind="SIMILARITY_PLACED"):
    cfg = tiny()["dataset"]
    corpus, truth = data.generate(NS, cfg)
    processed = ret.preprocess(corpus.vectors, "symmetric")
    pos, _ = pl.assign(processed, NS, cfg, kind)
    engine, arms, mapping = ret.build(corpus, pos, cfg)
    return corpus, truth, pos, engine, arms, mapping


def test_deterministic_generation_scale_and_stream_separation():
    cfg = tiny()["dataset"]
    a, truth = data.generate(NS, cfg)
    b, other_truth = data.generate(NS, cfg)
    np.testing.assert_array_equal(a.vectors, b.vectors)
    np.testing.assert_array_equal(truth.families, other_truth.families)
    assert a.ids == b.ids and len(set(a.ids)) == len(a.ids)
    assert all(len(i) == 32 and set(i) <= set("0123456789abcdef") for i in a.ids)
    assert not np.allclose(np.linalg.norm(a.vectors, axis=1), 1)
    q, target = data.queries(NS, a, 1.0)
    for _ in range(3):
        pl.assign(ret.preprocess(a.vectors, "symmetric"), NS, cfg, "SIMILARITY_PLACED")
    q2, target2 = data.queries(NS, a, 1.0)
    np.testing.assert_array_equal(q, q2)
    np.testing.assert_array_equal(target, target2)
    clean, clean_target = data.queries(NS, a, 0)
    np.testing.assert_array_equal(clean, a.vectors[clean_target])
    assert np.all(np.bincount(target) == 4)
    for split in ("development/003", "validation_tune/000", "validation_check/000"):
        c, _ = data.generate("HME-MO-1/"+split, cfg)
        assert not np.array_equal(c.vectors, a.vectors)
    other_r, _ = data.generate(NS, cfg, 0)
    assert a.ids == other_r.ids


@pytest.mark.parametrize("namespace", ["HME-MO-1/reserved_test/000", "HME-MO-1/reserved_test/049"])
def test_reserved_namespace_fails_before_rng(namespace, monkeypatch):
    monkeypatch.setattr(np.random, "default_rng", lambda *a, **k: pytest.fail("RNG invoked before guard"))
    with pytest.raises(PermissionError):
        data.generate(namespace, tiny()["dataset"])
    with pytest.raises(PermissionError):
        data.rng(namespace, "layout", permit=True)


@pytest.mark.parametrize("namespace", ["501001", "HME-MO-1/development/004", "HME-MO-1/validation_tune/012", "HME-MO-1/reserved_test/050"])
def test_unknown_or_out_of_plan_namespace_rejected(namespace):
    with pytest.raises(ValueError):
        data.check_namespace(namespace)


def test_historical_and_source_bytes_unchanged():
    integrity.verify_imports()
    assert ev.config()["status"] in ("DESIGN / DEVELOP", "REGISTERED")
    if ev.config()["status"] == "DESIGN / DEVELOP":
        assert not (integrity.ROOT/"experiments/meaningful_overlap_v1/REGISTRATION_APPROVAL.json").exists()
    for name, entry in json.loads((integrity.HERE/"SOURCE_PROVENANCE.json").read_text())["files"].items():
        if name != "MANIFEST.sha256":  # root payload inventory gains this new experiment
            assert integrity.digest(integrity.ROOT/name) == entry["sha256"]


def test_overlap_weights_geometry_matching_and_search_improvement():
    cfg = tiny()["dataset"]
    corpus, _ = data.generate(NS, cfg)
    processed = ret.preprocess(corpus.vectors, "symmetric")
    random, rmeta = pl.assign(processed, NS, cfg, "RANDOM_MATCHED")
    similar, smeta = pl.assign(processed, NS, cfg, "SIMILARITY_PLACED")
    separated, _ = pl.assign(processed, NS, cfg, "SEPARATED")
    assert sorted(map(tuple, random)) == sorted(map(tuple, similar))
    assert smeta["objective"] >= rmeta["objective"]
    assert not np.any(pl.overlap_matrix(separated, 8))
    w = pl.overlap_matrix(np.array([[4, 4], [4, 8], [8, 8], [12, 4]]), 8)
    assert w[0, 1] == .5 and w[0, 2] == .25 and w[0, 3] == 0
    assert np.all(np.diag(w) == 0)
    # Verify objective independently over unordered pairs.
    sim = (processed.conj() @ processed.T).real
    w = pl.overlap_matrix(similar, 8)
    i, j = np.where(np.triu(w, 1) > 0)
    assert np.isclose(smeta["objective"], np.sum(w[i, j]*sim[i, j])/np.sum(w[i, j]))
    zeros, zmeta = pl.assign(np.zeros_like(processed), NS, cfg, "SIMILARITY_PLACED")
    assert zmeta["objective"] == 0 and zmeta["accepted_swaps_all_restarts"] == 0


def test_label_target_and_query_order_firewall():
    corpus, truth, pos, engine, arms, _ = fixture()
    cfg = tiny()["dataset"]
    q, targets = data.queries(NS, corpus, 1)
    original = arms["HYBRID"].scores(q, "symmetric")
    permutation = np.arange(len(q))[::-1]
    np.testing.assert_allclose(arms["HYBRID"].scores(q[permutation], "symmetric"), original[permutation], atol=1e-14)
    changed_labels = np.arange(len(truth.families))
    st.observe(original, targets[::-1], changed_labels)
    truth.families[:] = -500
    again, _ = pl.assign(ret.preprocess(corpus.vectors, "symmetric"), NS, cfg, "SIMILARITY_PLACED")
    np.testing.assert_array_equal(pos, again)
    np.testing.assert_array_equal(original, arms["HYBRID"].scores(q, "symmetric"))
    for arm in arms.values():
        assert not any(key in vars(arm) for key in ("targets", "families", "prototypes", "corpus"))
    assert arms["FIELD_ONLY"].vectors is None
    assert not hasattr(arms["FIELD_ONLY"], "_patterns")
    assert all(not r.metadata for r in arms["FIELD_ONLY"].records)


def test_additive_reconstruction_no_decay_eviction_clipping_or_salience():
    corpus, _, pos, engine, _, _ = fixture()
    h = engine.hme
    expected = np.zeros_like(h.field)
    for record, vector in zip(h.records.values(), corpus.vectors):
        processed, pattern = h._generate_pattern(vector)
        x, y = np.asarray(record.position)-4
        expected[x:x+8, y:y+8] += .1*pattern
        assert record.gain == .1 and record.write_weight == 1
    np.testing.assert_array_equal(h.field, expected)
    assert h.config.field_decay == 0 and len(h.records) == len(corpus.ids)
    assert not engine.salience_config.influence_write_gain
    assert not engine.salience_config.influence_retrieval
    assert not engine.salience_config.enable_salience_rejection
    with pytest.raises(ValueError, match="Clipping"):
        ret.build(corpus, np.zeros_like(pos), tiny()["dataset"])
    with pytest.raises(ValueError, match="clip"):
        pl.slots(16, 8, [2, 4], 8)


def test_frozen_writer_decay_eviction_boundary_semantics():
    from hme_engine import HME, HMEConfig
    h = HME(config=HMEConfig(memory_size=16, encoding_resolution=8, field_decay=.5, max_records=1))
    vector = np.arange(8)
    first = h.encode(vector, (0, 0))
    before = h.field.copy()
    second = h.encode(vector, (12, 12))
    own = np.zeros_like(h.field)
    own[8:16, 8:16] = .1*h._patterns[second.artifact_id]
    np.testing.assert_array_equal(h.field, .5*before+own)
    assert first.artifact_id not in h.records and first.artifact_id not in h._payloads
    assert np.linalg.norm(h.field[:4, :4]) > 0


def test_external_mapping_and_shuffle_rebuild():
    corpus, _, pos, _, arms, mapping = fixture()
    _, _, _, other, shuffled, other_map = fixture("CONTENT_SHUFFLE")
    assert list(mapping) == list(other_map) == list(corpus.ids)
    assert mapping != other_map
    for arm in shuffled.values():
        assert arm.external_ids == list(corpus.ids)
        for i, item in enumerate(corpus.ids):
            assert other.hme.records[other_map[item]].position == tuple(arm.positions[i])
            np.testing.assert_allclose(other.hme._payloads[other_map[item]], ret.preprocess(corpus.vectors[i], "symmetric")[0])
    assert sorted(map(tuple, pos)) == sorted(map(tuple, shuffled["HYBRID"].positions))


@pytest.mark.parametrize("mode", ["symmetric", "native"])
def test_isolated_zero_cache_and_association_controls(mode):
    corpus, _, _, engine, arms, _ = fixture("SEPARATED")
    q, _ = data.queries(NS, corpus, 1)
    signed = arms["SIGNED_NN"].scores(q, mode)
    field = arms["FIELD_ONLY"].scores(q, mode)
    np.testing.assert_allclose(field, signed**2, atol=1e-14)
    np.testing.assert_array_equal(ret.ranks(arms["HYBRID"].scores(q, mode)), ret.ranks(signed))
    np.testing.assert_array_equal(ret.ranks(field), ret.ranks(np.abs(signed)))
    for arm in (arms["FIELD_ONLY"], arms["HYBRID"]):
        np.testing.assert_allclose(arm.scores(q, mode), arm.scores(q, mode, cached=False), atol=1e-14)
        old_cache = arm._cache
        engine.hme.field[:] = 0
        assert arm._cache is old_cache  # Detached snapshot, explicit replacement required.
        arm.replace_field(np.zeros_like(arm._field))
        assert arm._cache is None and not arm._field.flags.writeable
    np.testing.assert_array_equal(arms["HYBRID"].scores(q, mode), signed)
    _, _, _, engine, overlap, _ = fixture()
    permutation = np.roll(np.arange(8), 3)
    broken = ret.FieldRetrieval(engine, hybrid=True, permutation=permutation)
    expected = .42*overlap["SIGNED_NN"].scores(q, mode)+.20*overlap["FIELD_ONLY"].scores(q, mode)[:, permutation]
    np.testing.assert_allclose(broken.scores(q, mode), expected, atol=1e-14)


def test_shared_address_and_polarity():
    cfg = tiny()["dataset"]
    corpus, _ = data.generate(NS, cfg)
    engine, arms, _ = ret.build(corpus, np.full((8, 2), 16), cfg)
    q, _ = data.queries(NS, corpus, 1)
    scores = arms["FIELD_ONLY"].scores(q, "symmetric")
    assert np.all(scores == scores[:, :1])
    np.testing.assert_array_equal(scores, arms["FIELD_ONLY"].scores(-q, "symmetric"))
    np.testing.assert_array_equal(arms["HYBRID"].scores(q, "symmetric"), arms["SIGNED_NN"].scores(q, "symmetric"))


def test_actual_offset_pattern_agreement_independent_of_whole_similarity():
    patterns = np.ones((2, 4, 4), dtype=complex)
    patterns[1, :, :2] = -1
    pos = np.array([[2, 2], [2, 4]])
    g = pl.geometry(pos, np.ones((2, 4)), patterns, np.zeros((8, 8)), np.array([0, 0]))
    assert g["pair_count"] == 1 and g["weighted_signed_similarity"] == 1
    assert g["weighted_offset_pattern_agreement"] == pytest.approx(-1, abs=1e-12)
    assert g["occupancy_histogram"]["2"] == 8


def test_ties_target_removal_and_error_partition():
    scores = np.zeros((2, 8))
    families = np.array([0]*4+[1]*4)
    obs = st.observe(scores, np.array([0, 7]), families)
    assert obs["per_query"]["top6"] == [list(range(6)), list(range(6))]
    assert obs["per_query"]["sibling_precision_at_5"] == [.6, .2]
    m = obs["metrics"]
    assert m["exact_top1_accuracy"] == .5
    assert m["exact_top1_accuracy"]+m["wrong_member_within_family"]+m["wrong_family"] == 1
    assert m["queries_with_exact_score_ties"] == 2
    with pytest.raises(ValueError):
        ret.ranks(np.array([[np.nan]]))


def test_vector_aggregation_lambda_zero_weights_and_empty_neighborhood():
    corpus, _, _, _, _, _ = fixture()
    q, _ = data.queries(NS, corpus, 1)
    rule = {"representation": "raw", "k": 4, "lambda": 0}
    arm = ret.VectorAggregate(corpus, rule)
    np.testing.assert_array_equal(arm.scores(q), ret.RawNN(corpus).scores(q))
    assert not np.any(arm.neighbors == np.arange(8)[:, None])
    assert np.all(arm.weights >= 0)
    assert np.allclose(arm.weights.sum(axis=1)[~arm.empty], 1)
    empty = data.Corpus(np.eye(8), corpus.ids)
    rule["lambda"] = .5
    arm = ret.VectorAggregate(empty, rule)
    assert np.all(arm.empty)
    np.testing.assert_allclose(arm.scores(q), ret.RawNN(empty).scores(q))


def test_six_contrast_logic_zero_variance_and_threshold_boundaries():
    cfg = tiny()["statistics"]
    positive = np.tile([.03, .03, .03, .03, 0, 0], (10, 1))
    a = st.decision(positive, cfg)
    assert a["full_proposed_success"] and a["conclusion"] == "FULL_PROPOSED_SUCCESS"
    np.testing.assert_allclose(a["contrasts"][0]["ci95"], [.03, .03])
    zero = st.decision(np.zeros((10, 6)), cfg)
    assert not zero["placement_benefit"] and zero["identity_preservation"]
    threshold = st.decision(np.tile([.02]*4+[-.01]*2, (50, 1)), cfg)
    assert not any(x["clears_margin"] for x in threshold["contrasts"])
    positive[:, 5] = -.02
    assert st.decision(positive, cfg)["conclusion"] == "TRADEOFF"
    assert st.decision(positive, cfg, integrity=False)["conclusion"] == "MECHANISM_NOT_TESTED"
    assert st.decision(positive, cfg, placement_achieved=False)["conclusion"] == "MECHANISM_NOT_TESTED"
    varied = np.column_stack([np.linspace(.01, .06, 20)]*6)
    result = st.decision(varied, cfg)
    assert result == st.decision(varied, cfg)
    assert result["contrasts"][0]["decision_lower_bound"] <= result["contrasts"][0]["ci95"][0]


def test_registration_gate_does_not_touch_reserved_data_or_network(monkeypatch):
    monkeypatch.setattr(integrity, "git", lambda *a: pytest.fail("Network or git reached before proposed-status gate"))
    with pytest.raises(PermissionError, match="DESIGN"):
        integrity.verify_registration("a"*40, None)


def test_existing_output_refused(tmp_path):
    with pytest.raises(FileExistsError):
        ev.run("development", tmp_path)


def test_failure_records_preserve_successes_and_do_not_replace_seeds(tmp_path, monkeypatch):
    seen = []
    def fake(namespace, *args, **kwargs):
        seen.append(namespace)
        if namespace.endswith("000"):
            raise RuntimeError("injected correctness failure")
        return {"namespace": namespace}
    monkeypatch.setattr(ev, "one_corpus", fake)
    out = tmp_path/"attempt"
    with pytest.raises(RuntimeError, match="no seed replacement"):
        ev.run("development", out)
    assert seen == ["HME-MO-1/development/000", "HME-MO-1/development/001"]
    assert (out/"FAILURE.json").exists() and (out/"FAILURE_000.json").exists()
    assert (out/"corpus_001.json.gz").exists()
    assert not (out/"summary.json").exists()


def test_registered_status_does_not_bypass_hash_or_approval_gate(tmp_path, monkeypatch):
    monkeypatch.setattr(integrity, "HERE", tmp_path)
    monkeypatch.setattr(integrity, "git", lambda *a: pytest.fail("Remote reached before hash check"))
    (tmp_path/"protocol.json").write_text(json.dumps({"status": "REGISTERED"}))
    (tmp_path/"FROZEN_BASELINE.json").write_text(json.dumps({"status": "FROZEN_AFTER_VALIDATION_TUNING"}))
    approval = {"status": "APPROVED", "approved_by": "test fixture only", "approval_reference": "fixture",
        "approved_at_utc": "2026-01-01T00:00:00Z", "protocol_id": "HME-MO-1", "source_sha256": {},
        "reserved_namespace": "HME-MO-1/reserved_test/000..049", "prior_test_exposure": False,
        "contamination_decision": "fixture; no corpus generated"}
    path = tmp_path/"REGISTRATION_APPROVAL.json"
    path.write_text(json.dumps(approval))
    monkeypatch.setattr(integrity, "source_hashes", lambda: {"source.py": "abc"})
    with pytest.raises(RuntimeError, match="hash set mismatch"):
        integrity.verify_registration("a"*40, path)
    approval["prior_test_exposure"] = True
    path.write_text(json.dumps(approval))
    with pytest.raises(PermissionError, match="Exposed"):
        integrity.verify_registration("a"*40, path)


def test_registration_rejects_stale_remote_and_accepts_matching_mock_receipt(tmp_path, monkeypatch):
    # Exercises only proof validation. No reserved generator or live network call.
    import hashlib
    monkeypatch.setattr(integrity, "HERE", tmp_path)
    monkeypatch.setattr(integrity, "ROOT", tmp_path)
    (tmp_path/"protocol.json").write_text(json.dumps({"status": "REGISTERED"}))
    (tmp_path/"FROZEN_BASELINE.json").write_text(json.dumps({"status": "FROZEN_AFTER_VALIDATION_TUNING"}))
    (tmp_path/"source.py").write_text("fixture source")
    hashes = {"source.py": integrity.digest(tmp_path/"source.py")}
    approval = {"status": "APPROVED", "approved_by": "test fixture only", "approval_reference": "fixture",
        "approved_at_utc": "2026-01-01T00:00:00Z", "protocol_id": "HME-MO-1", "source_sha256": hashes,
        "reserved_namespace": "HME-MO-1/reserved_test/000..049", "prior_test_exposure": False,
        "contamination_decision": "fixture; no corpus generated"}
    path = tmp_path/"REGISTRATION_APPROVAL.json"
    path.write_text(json.dumps(approval))
    monkeypatch.setattr(integrity, "source_hashes", lambda: hashes)
    monkeypatch.setattr(integrity, "verify_imports", lambda: None)
    monkeypatch.setattr(subprocess, "check_output", lambda args, **kwargs: (tmp_path/args[-1].split(":", 1)[1]).read_bytes())
    tip = "b"*40
    def git_fixture(*args):
        if args[0] == "ls-remote":
            return "c"*40+"\trefs/heads/build/example"
        if args[0] == "for-each-ref":
            return tip+" refs/hme-mo-registration/build/example"
        return ""
    monkeypatch.setattr(integrity, "git", git_fixture)
    with pytest.raises(PermissionError, match="not visible"):
        integrity.verify_registration("a"*40, path)
    tip = "c"*40
    permit, receipt = integrity.verify_registration("a"*40, path)
    assert permit.registration_commit == "a"*40
    assert receipt["source_sha256"] == hashes


def test_complete_development_pipeline_canvas_and_costs():
    p = tiny()
    rule = {"representation": "raw", "k": 4, "lambda": 0}
    result = ev.one_corpus(NS, p, rule, development=True)
    assert result["integrity_passed"]
    assert all(v == 0 for v in result["larger_canvas"]["canvas_only_max_errors"].values())
    assert result["costs"]["within_cap"]
    assert result["primary"]["SEPARATED/HYBRID"] == result["primary"]["SIGNED_NN"]
    storage = result["costs"]["storage"]
    assert storage["SIMILARITY_PLACED/FIELD_ONLY"]["persistent_bytes"] > storage["SIMILARITY_PLACED/FIELD_ONLY/uncached"]["persistent_bytes"]
    assert storage["RAW_SIGNED_NN"]["serialized_total_bytes"] > 0
    json.dumps(result, allow_nan=False)


def test_uncached_cost_variant_really_retains_no_cache(monkeypatch):
    corpus, _, _, _, arms, _ = fixture()
    original = ret.FieldRetrieval.search
    counts = []
    def checked(self, query, **kwargs):
        if kwargs.get("cached") is False:
            assert self._cache is None
            counts.append(1)
        return original(self, query, **kwargs)
    monkeypatch.setattr(ret.FieldRetrieval, "search", checked)
    q, _ = data.queries(NS, corpus, 1)
    costs.measure({"RAW_SIGNED_NN": ret.RawNN(corpus), "HYBRID": arms["HYBRID"]}, q, tiny()["costs"])
    assert counts


def test_baseline_selection_predeclared_ties_and_feasibility():
    p = tiny()
    rows = [{"raw": {"exact_top1_accuracy": .5}, "namespace": NS,
             "candidates": [{"metrics": {"sibling_precision_at_5": .2, "exact_top1_accuracy": .5}}
                            for _ in ev.baseline_grid(p)]}]*2
    chosen = ev.select_baseline(rows, p)
    assert chosen["rule"] == {"representation": "raw", "k": 4, "lambda": 0}
    assert len(chosen["selection_table"]) == p["vector_selection"]["budget"]
