"""Development fixtures only. Never execute HME-REC-2's registered seeds here."""
import numpy as np

from hme_engine import HMEConfig, HMEEngine
from experiments.rec2_v1 import evaluate as ev


def test_registered_seeds_exclude_development_seed():
    assert ev.P["development_seed"] == 7
    assert 7 not in ev.P["seeds"]
    assert len(ev.P["seeds"]) == 30
    assert len(set(ev.P["seeds"])) == 30


def test_blocks_are_disjoint_and_inside_the_grid():
    memory, centers = ev.geometry()
    d = ev.P["dimension"]
    half = d // 2
    boxes = []
    for center in centers:
        assert 0 <= center[0] < memory and 0 <= center[1] < memory
        r0, c0 = center[0] - half, center[1] - half
        boxes.append((r0, r0 + d, c0, c0 + d))
        assert r0 >= 0 and c0 >= 0 and r0 + d <= memory and c0 + d <= memory
    for i, a in enumerate(boxes):
        for b in boxes[i + 1:]:
            row_overlap = not (a[1] <= b[0] or b[1] <= a[0])
            col_overlap = not (a[3] <= b[2] or b[3] <= a[2])
            assert not (row_overlap and col_overlap)


def test_integer_shift_pool_matches_the_published_example_and_the_lag_sum():
    x = np.array([[1.0, 0.0, 1.0]])
    got = ev.shift_sum(x)
    expected = np.array([[2.0, 0.0, 1.0], [0.0, 2.0, 0.0], [1.0, 0.0, 2.0]])
    np.testing.assert_allclose(got, expected, atol=0.0)
    np.testing.assert_allclose(ev.lag_sum(x), expected, atol=0.0)
    assert np.min(np.linalg.eigvalsh(got)) >= -1e-8


def test_shift_pool_is_not_the_shipped_engine_pattern():
    x = np.array([1.0, 0.0, 1.0])
    engine = HMEEngine(hme_config=HMEConfig(
        memory_size=8, encoding_resolution=3, use_hann_window=False,
    ))
    _vector, pattern = engine.hme._generate_pattern(x)
    pooled = ev.shift_sum(x[None, :])
    assert pattern.shape == pooled.shape
    assert not np.allclose(pattern.real, pooled)


def test_development_seed_banks_match_direct_moments():
    trains, tests, engine, centers = ev.build_banks(ev.P["development_seed"])
    assert len(tests) == ev.P["sites"]
    gap = 0.0
    for train, center in zip(trains, centers):
        got = ev.block_moment(engine.hme.field, center, len(train))
        gap = max(gap, float(np.max(np.abs(got - ev.direct_moment(train)))))
    assert gap <= 1e-10
    y, mask = ev.observations(tests[0], ev.P["development_seed"], 0, 0.1)
    field_hat = ev.reconstruct(
        ev.block_moment(engine.hme.field, centers[0], len(trains[0])), y[0], mask[0])
    direct_hat = ev.reconstruct(ev.direct_moment(trains[0]), y[0], mask[0])
    assert float(np.max(np.abs(field_hat - direct_hat))) <= 1e-8


def test_ppca_fit_uses_training_rows_only():
    rng = np.random.default_rng(7)
    train = ev.normalize_rows(rng.standard_normal((20, 8)))
    other = train.copy()
    other[0] = ev.normalize_rows(rng.standard_normal((1, 8)))[0]
    mu, moment = ev.fit_oracle_ppca(train)
    mu2, moment2 = ev.fit_oracle_ppca(train)
    np.testing.assert_array_equal(mu, mu2)
    np.testing.assert_array_equal(moment, moment2)
    assert not np.allclose(moment, ev.fit_oracle_ppca(other)[1])
    y = np.zeros(8)
    mask = np.array([True, True, True, True, False, False, False, False])
    y[mask] = train[1, mask]
    hat, singular = ev.reconstruct_ppca(mu, moment, y, mask)
    assert hat.shape == (8,)
    assert np.all(np.isfinite(hat))
    assert singular in (True, False)


def test_development_shift_control_agrees():
    report = ev.check_shifts(ev.P["development_seed"])
    assert report["biased_gap"] <= 1e-10
    assert report["toeplitz_gap"] <= 1e-10
    assert report["min_eigenvalue"] >= -1e-8


def test_tiny_identity_guardrail_does_not_mutate_the_field():
    report = ev.identity_guardrail(ev.P["development_seed"], n=6, d=8)
    assert report["unchanged"] is True
    assert report["n"] == 6
