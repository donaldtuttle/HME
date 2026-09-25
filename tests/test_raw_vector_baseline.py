"""Development fixtures only; HME-NN-3 evaluation seeds are never used here."""
import copy
import numpy as np
import pytest

from experiments.raw_vector_baseline_v1 import evaluate as ev


def test_raw_cosine_matches_scalar_and_is_not_windowed():
    rng = np.random.default_rng(19)
    vectors, query = rng.normal(size=(9, 8)), rng.normal(size=8)
    expected = [np.dot(v, query)/(np.linalg.norm(v)*np.linalg.norm(query)) for v in vectors]
    np.testing.assert_allclose(ev.cosine_scores(vectors, query), expected, atol=1e-14)
    np.testing.assert_allclose(ev.cosine_scores(vectors, query, True), np.abs(expected), atol=1e-14)
    assert not np.allclose(ev.cosine_scores(vectors*np.hanning(8), query), expected)


@pytest.mark.parametrize('seed', [2, 7, 31])
def test_cached_scores_match_every_public_api_hit(seed):
    rng = np.random.default_rng(seed)
    raw = rng.normal(size=(8, 8))
    engines = ev.build_engines(raw, seed, memory_size=16, position=(8, 8))
    snapshots = {name: ev.Snapshot(e, (8, 8)) for name, e in engines.items()}
    for query in list(raw) + list(rng.normal(size=(5, 8))) + [np.zeros(8)]:
        for name, e in engines.items():
            snapshots[name].verify_api(e, query, signed=name == 'signed')
        snapshots['default'].verify_api(engines['default'], query*np.hanning(8))
        scores = ev.score_arms(raw, query, snapshots)
        assert tuple(scores) == ev.ARMS
        np.testing.assert_array_equal(ev.order(scores['hme_no_window_field_erased']),
                                       ev.order(scores['raw_absolute_nn']))
    assert engines['default'].hme.config.use_hann_window is True
    assert not np.shares_memory(snapshots['no_window'].vectors,
                               next(iter(engines['no_window'].hme._payloads.values())))
    assert snapshots['no_window'].records == list(engines['no_window'].hme.records.values())


def test_antipodes_and_stable_ties():
    raw = np.array([[-1., 0, 0, 0], [1., 0, 0, 0]])
    q = np.array([1., 0, 0, 0])
    assert ev.order(ev.cosine_scores(raw, q)).tolist() == [1, 0]
    assert ev.order(ev.cosine_scores(raw, q, True)).tolist() == [0, 1]
    assert ev.order(ev.cosine_scores(raw, np.zeros(4))).tolist() == [0, 1]


def test_small_seed_is_repeatable_and_uses_registered_rng_order():
    kwargs = dict(n=5, dimension=8, memory_size=16, position=(8, 8))
    a = ev.seed_cells(43, **kwargs)
    b = ev.seed_cells(43, **kwargs)
    assert a == b
    rng = np.random.default_rng(43)
    raw = rng.standard_normal((5, 8))
    for cell, sigma in zip(a, ev.SIGMAS):
        query = raw + sigma*rng.standard_normal(raw.shape)
        assert cell['query_sha256'] == ev.array_hash(query)
        assert cell['item_sha256'] == ev.array_hash(raw)
        assert cell['ledger_erased_identity_hits'] == 0
        assert all(0 <= k <= 5 for k in cell['correct'].values())


def test_summary_is_paired_percentage_points_and_rejects_missing_cells():
    cells = []
    for seed in [11, 12]:
        for sigma in [0., 1.]:
            correct = {name: 128 for name in ev.ARMS}
            correct['hme_default'] = 64
            cells.append({'seed': seed, 'sigma': sigma, 'n': 128, 'correct': correct})
    result = ev.summarize(cells)
    contrast = result[1]['contrasts']['hme_default - raw_signed_nn']
    assert contrast['mean_pp'] == -50.
    assert contrast['ci95_pp'] == [-50., -50.]
    assert result[1]['descriptive_gap_reduction_fraction'] == 1.
    with pytest.raises(ValueError):
        ev.summarize(cells[:-1])


def test_registration_requires_full_separate_commit():
    for commit in ['main', 'abcdef', ev.PROTOCOL_COMMIT]:
        with pytest.raises(ValueError):
            ev.verify_registration(commit)
