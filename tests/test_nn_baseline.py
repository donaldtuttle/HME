"""Correctness fixtures only; never execute HME-NN-1's registered evaluation seeds."""
import copy
import importlib.util
import json
from pathlib import Path
import sys

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location('nn_evaluation', ROOT/'experiments/nn_baseline_v1/evaluate.py')
evaluation = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(evaluation)
from hme_engine import HMEConfig, HMEEngine


@pytest.mark.parametrize('absolute', [False, True])
def test_exact_nn_matches_independent_scalar_cosine(absolute):
    engine = HMEEngine(hme_config=HMEConfig(memory_size=16, encoding_resolution=8))
    rng = np.random.default_rng(41)
    for vector in rng.normal(size=(7, 8)):
        engine.encode_memory(vector, (8, 8))
    nn = evaluation.ExactNN(engine, absolute)
    query = rng.normal(size=8)
    for mode in ('native', 'symmetric'):
        q = query * np.hanning(8) if mode == 'symmetric' else query
        expected = [float(np.dot(v.real, q)/(np.linalg.norm(v)*np.linalg.norm(q))) for v in engine.hme._payloads.values()]
        if absolute:
            expected = [abs(x) for x in expected]
        order, scores = nn.search(query, mode, 7)
        wanted = sorted(range(7), key=lambda i: -expected[i])
        assert list(order) == wanted
        np.testing.assert_allclose(scores, np.asarray(expected)[wanted], atol=1e-14)
    np.testing.assert_array_equal(nn.vectors, np.stack(list(engine.hme._payloads.values())))
    assert not np.shares_memory(nn.vectors, next(iter(engine.hme._payloads.values())))
    assert nn.records == list(engine.hme.records.values())
    assert nn.lineage.to_dict() == engine.lineage.to_dict()


def test_signed_absolute_and_zero_query_ties():
    engine = HMEEngine(hme_config=HMEConfig(memory_size=8, encoding_resolution=4, use_hann_window=False))
    engine.encode_memory([-1, 0, 0, 0], (4, 4))
    engine.encode_memory([1, 0, 0, 0], (4, 4))
    signed, absolute = evaluation.ExactNN(engine, False), evaluation.ExactNN(engine, True)
    assert signed.search(np.array([1, 0, 0, 0]), 'native', 1)[0].tolist() == [1]
    assert absolute.search(np.array([1, 0, 0, 0]), 'native', 2)[0].tolist() == [0, 1]
    order, scores = signed.search(np.zeros(4), 'native', 2)
    assert order.tolist() == [0, 1]
    assert scores.tolist() == [0., 0.]


@pytest.mark.parametrize('mode', ['native', 'symmetric'])
def test_erased_field_control_equals_absolute_nn_and_full_hme_api(mode):
    cfg = {'position': [8, 8], 'memory_size': 16, 'dimension': 8, 'write_strength': .1}
    vectors = np.random.default_rng(17).normal(size=(9, 8))
    arms, ids = evaluation.build_arms(vectors, 17, cfg)
    lookup = {identifier: i for i, identifier in enumerate(ids)}
    query = vectors[4] + np.random.default_rng(18).normal(size=8)
    prior = arms['hme'].hme.field.copy()
    for name in ('hme', 'hme_field_erased'):
        order, scores = evaluation.search(name, arms[name], query, mode, 9, (8, 8), lookup)
        direct = arms[name].retrieve_memory((8, 8), query=evaluation.query_input(query, mode), top_k=9)
        assert order.tolist() == [lookup[h.artifact_id] for h in direct.hits]
        np.testing.assert_array_equal(scores, [h.final_score for h in direct.hits])
    a = evaluation.search('hme_field_erased', arms['hme_field_erased'], query, mode, 9, (8, 8), lookup)
    b = arms['nn_absolute'].search(query, mode, 9)
    assert a[0].tolist() == b[0].tolist()
    np.testing.assert_allclose(a[1], .38 + .42*b[1], atol=1e-14)
    np.testing.assert_array_equal(arms['hme'].hme.field, prior)
    assert not np.any(arms['hme_field_erased'].hme.field)


def test_memory_accounting_counts_buffers_aliases_and_patterns():
    a = np.ones(100)
    assert evaluation.persistent_size([a, a])['numeric_array_bytes'] == a.nbytes
    assert evaluation.persistent_size([a, a[:10]])['numeric_array_bytes'] == a.nbytes
    one = evaluation.persistent_size([a])['persistent_bytes']
    two = evaluation.persistent_size([a, a.copy()])['persistent_bytes']
    assert two >= one + a.nbytes
    cfg = {'position': [8, 8], 'memory_size': 16, 'dimension': 8, 'write_strength': .1}
    arms, _ = evaluation.build_arms(np.ones((2, 8)), 2, cfg)
    hme = evaluation.persistent_size(arms['hme'])
    nn = evaluation.persistent_size(arms['nn_cosine'])
    assert hme['numeric_array_bytes'] == (16*16 + 2*8 + 2*8*8)*16
    assert nn['numeric_array_bytes'] == 2*8*16 + 2*8
    assert hme['persistent_bytes'] > nn['persistent_bytes']


def test_metrics_paired_bootstrap_and_preregistered_decision():
    metrics = evaluation.ranked_metrics([1, 2, 6, 0])
    assert metrics['top1_accuracy'] == .25
    assert metrics['top5_accuracy'] == .5
    assert metrics['mean_reciprocal_rank'] == pytest.approx((1+.5+1/6)/4)
    samples = np.random.default_rng(3).integers(0, 10, size=(100, 10))
    paired = evaluation.bootstrap_interval(np.full(10, .03), samples)
    np.testing.assert_allclose(paired['ci95'], [.03, .03])
    assert evaluation.decision(paired, .02) == 'registered_practical_advantage_supported'
    assert evaluation.decision({'ci95': [-.03, -.01]}, .02) == 'hme_lower_accuracy_in_primary_condition'
    assert evaluation.decision({'ci95': [-.01, .03]}, .02) == 'registered_practical_advantage_not_established'


def test_frozen_sources_are_checked_before_execution():
    protocol = json.loads((ROOT/'experiments/nn_baseline_v1/protocol.json').read_text())
    assert {2, 3, 17, 18, 41}.isdisjoint(protocol['seeds'])
    with pytest.raises(ValueError, match='40-character'):
        evaluation.verify_registration('not-a-commit', protocol)
    assert set(evaluation.THREAD_ENV.values()) == {'1'}


def test_complete_reporting_path_uses_only_small_non_evaluation_fixtures():
    protocol = json.loads((ROOT/'experiments/nn_baseline_v1/protocol.json').read_text())
    fixture_seeds = [43, 47]
    assert set(fixture_seeds).isdisjoint(protocol['seeds'])
    protocol['seeds'] = fixture_seeds
    protocol['dataset'].update(items_per_seed=8, dimension=8, memory_size=16,
                               position=[8, 8], unmatched_queries_per_seed=2)
    protocol['latency'].update(queries_per_seed=2, warmup_queries_per_arm=1, repetitions=1)
    protocol['statistics']['bootstrap_resamples'] = 100
    runs = [evaluation.one_seed(seed, protocol) for seed in fixture_seeds]
    report = evaluation.analyze(runs, protocol)
    assert len(report['conditions']) == 8
    assert report['all_arms_within_budget']
    for run in runs:
        assert run['field_only_check']['hit_count'] == 0
        assert run['field_only_check']['decoded_surface_norm'] > 0
        for cell in run['cells']:
            for arm in cell['arms'].values():
                assert len(arm['target_ranks']) == 8
        assert all(len(arm['nanoseconds']) == 2 for arm in run['latency'].values())
    # Every raw observation and summary must be serializable without NaN/Infinity.
    json.dumps({'runs': runs, 'analysis': report}, allow_nan=False)
