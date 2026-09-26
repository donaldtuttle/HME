"""SAL-1 deterministic development fixtures, not a preregistered evaluation."""
import numpy as np
import pytest

from experiments.salience_v1.memory import (
    DirectMoment, FieldPredictor, ForgettingRLS, SurpriseMemory, fit_budget,
)

BASES = (FieldPredictor, DirectMoment, ForgettingRLS)


def stream():
    for i in range(1, 19):
        cue = np.array([np.cos(i), np.sin(i), .3])
        outcome = np.array([cue[0] + .2 * cue[1], cue[1] - .3 * cue[2]])
        yield cue, outcome, 1.0 + (i % 3)


@pytest.mark.parametrize('decay', [0., .01, .05])
def test_field_direct_weighted_prediction_parity(decay):
    field = FieldPredictor(3, 2, decay=decay)
    direct = DirectMoment(3, 2, decay=decay)
    for cue, y, gain in stream():
        field.update(cue, y, gain=gain); direct.update(cue, y, gain=gain)
        np.testing.assert_allclose(field.predict(cue), direct.predict(cue), atol=1e-12)
    assert field.state.consolidated
    assert field.state.storage_report()['records'] == 0


@pytest.mark.parametrize('decay', [0., .01, .05])
def test_rls_matches_explicit_forgetting_normal_equations(decay):
    model = ForgettingRLS(3, 2, decay=decay, ridge=.2)
    information = .2 * np.eye(3)
    cross = np.zeros((2, 3))
    for cue, y, gain in stream():
        z = np.concatenate((cue, y)); z /= np.linalg.norm(z)
        x, t = z[:3], z[3:]
        information = (1-decay)*information + gain*np.outer(x, x)
        cross = (1-decay)*cross + gain*np.outer(t, x)
        model.update(cue, y, gain=gain)
        np.testing.assert_allclose(model.predict(cue), cross@np.linalg.solve(information, cue), atol=1e-12)
        np.testing.assert_allclose(model._inverse, np.linalg.inv(information), atol=1e-11)
    before = model._coef.copy()
    model.update([1, 0, 0], [1, 1], gain=0)
    np.testing.assert_array_equal(before, model._coef)


@pytest.mark.parametrize('base', BASES)
def test_orthogonal_new_association_and_conflicting_revision_are_distinct(base):
    m = SurpriseMemory(base(2, 2), capacity=2, radius=.1)
    for _ in range(12):
        m.observe([1, 0], [1, 0], eligible=False)
    new = m.observe([0, 1], [0, 1])
    conflict = m.observe([1, 0], [-1, 0])
    assert new['admitted'] and conflict['admitted']
    np.testing.assert_array_equal(m.predict([0, 1]), [0, 1])
    np.testing.assert_array_equal(m.predict([1, 0]), [-1, 0])
    assert m.storage_report()['occupied'] == 2


@pytest.mark.parametrize('base', BASES)
def test_gain_one_scoped_override_does_not_change_off_scope_base_readout(base):
    m = SurpriseMemory(base(2, 2), capacity=2, radius=.05)
    for cue, y in [([1, 0], [1, 0]), ([0, 1], [0, 1])]*20:
        m.observe(cue, y, eligible=False)
    m.observe([1, 0], [-1, 0], gain=1)
    # This checks routing, not that the base itself is unperturbed by the write.
    np.testing.assert_array_equal(m.predict([0, 1]), m.base.predict([0, 1]))
    np.testing.assert_array_equal(m.predict([1, 0]), [-1, 0])
    assert not np.array_equal(m.base.predict([1, 0]), [-1, 0])


@pytest.mark.parametrize('base', BASES)
def test_same_cue_replaces_instead_of_duplicate_and_deletes_stale_if_base_agrees(base):
    m = SurpriseMemory(base(2, 1), capacity=3, radius=.1)
    m.observe([1, 0], [1]); m.observe([1, 0], [-1])
    assert m.storage_report()['occupied'] == 1
    np.testing.assert_array_equal(m.predict([1, 0]), [-1])
    target = m.base.predict([1, 0])
    event = m.observe([1, 0], target)
    assert event['removed']
    assert m.storage_report()['occupied'] == 0


@pytest.mark.parametrize('base', BASES)
def test_buffer_ownership_and_read_only_prediction(base):
    m = SurpriseMemory(base(2, 1), capacity=1)
    x = np.array([1., 0.]); y = np.array([3.])
    m.observe(x, y); x[:] = -7; y[:] = -7
    state = [v.tobytes() for v in (m._cues, m._targets, m._ages, m._valid, m._policy)]
    output = m.predict([1, 0]); output[:] = -100
    np.testing.assert_array_equal(m.predict([1, 0]), [3])
    assert state == [v.tobytes() for v in (m._cues, m._targets, m._ages, m._valid, m._policy)]


def test_eviction_uses_last_accepted_age_not_read_recency():
    m = SurpriseMemory(DirectMoment(2, 1), capacity=2, radius=0, always_admit=True)
    m.observe([1, 0], [1]); m.observe([0, 1], [2])
    m.predict([1, 0])
    m.observe([-1, 0], [3])
    assert m._match(np.array([1, 0])) is None
    np.testing.assert_array_equal(m.predict([0, 1]), [2])
    np.testing.assert_array_equal(m.predict([-1, 0]), [3])


def test_nearest_tie_selects_newest_and_antipodal_cues_differ():
    m = SurpriseMemory(DirectMoment(2, 1), capacity=2, radius=1., always_admit=True)
    m.observe([1, 1], [1]); m.observe([1, -1], [2])
    np.testing.assert_array_equal(m.predict([1, 0]), [2])
    assert m._match(np.array([-1, 0])) is None


def test_surprise_is_before_base_update_and_not_auto_truth():
    m = SurpriseMemory(DirectMoment(2, 1), capacity=2)
    before = m.storage_report()
    assert m.observe([1, 0], [99], trusted=False)['ignored']
    assert before == m.storage_report()
    event = m.observe([1, 0], [99], trusted=True)
    assert event['admitted'] and event['pre_update_base_nmse'] == 1.
    np.testing.assert_array_equal(m.predict([1, 0]), [99])
    # A deliberately wrong trusted target is still stored: no truth oracle.


def test_admit_all_control_and_zero_capacity_control():
    m = SurpriseMemory(DirectMoment(2, 1), capacity=2, always_admit=True)
    m.observe([1, 0], [1])
    assert m.observe([1, 0], m.base.predict([1, 0]))['admitted']
    no_buffer = SurpriseMemory(DirectMoment(2, 1), capacity=0)
    assert not no_buffer.observe([1, 0], [1])['admitted']
    np.testing.assert_array_equal(no_buffer.predict([1, 0]), no_buffer.base.predict([1, 0]))


@pytest.mark.parametrize('base', BASES)
def test_budget_includes_base_and_buffer_and_does_not_grow(base):
    m = fit_budget(lambda: base(8, 8), 8192)
    before = m.storage_report()
    assert before['instance_owned_bytes'] <= 8192
    assert before['capacity'] > 0
    with pytest.raises(ValueError):
        SurpriseMemory(base(8, 8), capacity=before['capacity']+1, byte_budget=8192)
    for i in range(64):
        x=np.zeros(8); x[i % 8]=1
        y=x if i % 3 else -x
        m.observe(x, y)
    after = m.storage_report()
    assert after['instance_owned_bytes'] == before['instance_owned_bytes']
    assert after['retained_array_bytes'] == before['retained_array_bytes']
    assert after['occupied'] <= after['capacity']
    with pytest.raises(ValueError):
        fit_budget(lambda: base(8, 8), 1)


@pytest.mark.parametrize('base', BASES)
@pytest.mark.parametrize('kwargs', [dict(gain=-1), dict(gain=np.nan), dict(gain=1e300),
                                   dict(trusted='yes'), dict(eligible=1)])
def test_invalid_inputs_do_not_mutate_state(base, kwargs):
    m = SurpriseMemory(base(2, 1), capacity=2)
    before = m.storage_report()
    with pytest.raises((ValueError, TypeError)):
        m.observe([1, 0], [1], **kwargs)
    assert before == m.storage_report()
    np.testing.assert_array_equal(m.base.predict([1, 0]), [0])


@pytest.mark.parametrize('cue,target', [([np.nan,0],[1]),([0,0],[1]),([1],[1]),
                                     ([1j,0],[1]),([1,0],[np.inf])])
def test_reject_invalid_vectors(cue, target):
    m = SurpriseMemory(DirectMoment(2, 1))
    with pytest.raises((ValueError, TypeError)):
        m.observe(cue, target)
    assert m.storage_report()['occupied'] == 0


def test_clock_overflow_fails_before_either_update():
    m = SurpriseMemory(DirectMoment(2, 1))
    m._policy['clock'][0] = np.iinfo(np.uint64).max
    with pytest.raises(OverflowError): m.observe([1,0],[1])
    assert m.storage_report()['occupied'] == 0
    np.testing.assert_array_equal(m.base.predict([1,0]), [0])


@pytest.mark.parametrize('kwargs', [dict(capacity=-1), dict(capacity=1.1),
                                   dict(radius=-1), dict(threshold=np.nan),
                                   dict(always_admit='yes')])
def test_invalid_policy(kwargs):
    with pytest.raises((ValueError, TypeError)):
        SurpriseMemory(DirectMoment(2, 1), **kwargs)


@pytest.mark.parametrize('base', BASES)
@pytest.mark.parametrize('kwargs',[dict(cue_dim=0),dict(outcome_dim=1.1),dict(decay=1),dict(ridge=0)])
def test_invalid_base_configuration(base, kwargs):
    with pytest.raises((ValueError, TypeError)):
        base(**kwargs)


@pytest.mark.parametrize('base', BASES)
def test_six_noisy_correction_repeats_use_one_slot_not_six(base):
    m = SurpriseMemory(base(8, 8), capacity=8, radius=.1)
    e = np.eye(8)
    for i in range(200):
        m.observe(e[i % 3], e[i % 3], eligible=False)
    first = m.observe(e[0], -e[0])
    assert first['admitted']
    state = [a.tobytes() for a in (m._cues, m._targets, m._ages, m._valid)]
    before = m.storage_report()
    for i in range(1, 6):
        event = m.observe(e[0] + i*1e-6*e[4], -e[0])
        assert event['pre_update_hybrid_nmse'] == 0
        assert event['pre_update_base_nmse'] > .1
        assert not event['admitted'] and not event['removed']
    after = m.storage_report()
    assert after['occupied'] == after['admissions'] == 1
    assert after['instance_owned_bytes'] == before['instance_owned_bytes']
    assert state == [a.tobytes() for a in (m._cues, m._targets, m._ages, m._valid)]


@pytest.mark.parametrize('base', BASES)
def test_noisy_repeats_do_not_evict_other_correction(base):
    m = SurpriseMemory(base(2, 1), capacity=2, radius=.1)
    m.observe([1, 0], [1], gain=0)
    m.observe([0, 1], [2], gain=0)
    for i in range(1, 7):
        m.observe([1, i*1e-6], [1], gain=0)
    assert m.storage_report()['occupied'] == 2
    assert m.storage_report()['admissions'] == 2
    np.testing.assert_array_equal(m.predict([0, 1]), [2])


@pytest.mark.parametrize('base', BASES)
def test_noisy_real_revision_reuses_slot_and_keeps_anchor(base):
    m = SurpriseMemory(base(2, 1), capacity=3, radius=.1)
    m.observe([1, 0], [1], gain=0)
    event = m.observe([1, .05], [-1], gain=0)
    assert event['admitted'] and event['revised']
    assert m.storage_report()['occupied'] == 1
    np.testing.assert_array_equal(m._cues[0], [1, 0])
    np.testing.assert_array_equal(m.predict([1, .05]), [-1])
    # .11 is near the revised observation, but outside the ORIGINAL anchor radius.
    m.observe([1, .11], [2], gain=0)
    assert m.storage_report()['occupied'] == 2


@pytest.mark.parametrize('base', BASES)
def test_radius_matched_stale_exception_removed_if_base_is_adequate(base):
    m = SurpriseMemory(base(2, 1), capacity=2, radius=.1)
    for _ in range(20):
        m.observe([1, 0], [1], eligible=False)
    m.observe([1, 0], [-1], gain=0)
    q = [1, 1e-6]
    y = m.base.predict(q)
    event = m.observe(q, y, gain=0)
    assert event['pre_update_base_nmse'] == 0
    assert event['removed'] and not event['admitted']
    assert m.storage_report()['occupied'] == 0


def test_revision_tie_uses_same_newest_match_as_recall():
    m = SurpriseMemory(DirectMoment(2, 1), capacity=2, radius=1, always_admit=True)
    m.observe([1, 1], [1], gain=0); m.observe([1, -1], [2], gain=0)
    m.observe([1, 0], [3], gain=0)
    np.testing.assert_array_equal(m._targets[:, 0], [1, 3])
    np.testing.assert_array_equal(m._cues, [[1, 1], [1, -1]])


def test_radius_boundary_is_inclusive_and_next_float_is_outside():
    m = SurpriseMemory(DirectMoment(2, 1), radius=.125, capacity=2)
    m.observe([1, 0], [1], gain=0)
    assert not m.observe([1, .125], [1], gain=0)['admitted']
    assert m.observe([1, np.nextafter(.125, np.inf)], [1], gain=0)['admitted']


def test_radius_zero_retains_exact_scope_not_fuzzy_matching():
    m = SurpriseMemory(DirectMoment(2, 1), radius=0, capacity=2)
    m.observe([1, 0], [1], gain=0)
    m.observe([1, 1e-6], [1], gain=0)
    assert m.storage_report()['occupied'] == 2


@pytest.mark.parametrize('trusted,eligible', [(False, True), (True, False)])
def test_ineligible_or_untrusted_noisy_feedback_does_not_revise_buffer(trusted, eligible):
    m = SurpriseMemory(DirectMoment(2, 1), capacity=2)
    m.observe([1, 0], [1], gain=0)
    before = [a.tobytes() for a in (m._cues, m._targets, m._ages, m._valid)]
    m.observe([1, 1e-6], [-1], gain=0, trusted=trusted, eligible=eligible)
    assert before == [a.tobytes() for a in (m._cues, m._targets, m._ages, m._valid)]


def test_admit_all_noisy_repeats_reuse_anchor_but_refresh_acceptance_age():
    m = SurpriseMemory(DirectMoment(2, 1), capacity=2, always_admit=True)
    m.observe([1, 0], [1], gain=0)
    m.observe([1, 1e-6], [1], gain=0)
    assert m.storage_report()['occupied'] == 1
    assert m.storage_report()['admissions'] == 2
    assert m._ages[0] == 2
    np.testing.assert_array_equal(m._cues[0], [1, 0])


def test_larger_automatic_buffer_is_not_universal_loss_dominance():
    # Both stored anchors are correct in their own scopes. A nearby *different*
    # scope should fall back to zero, but retaining the first entry misroutes it.
    small = SurpriseMemory(DirectMoment(2, 1), capacity=1, radius=.1)
    large = SurpriseMemory(DirectMoment(2, 1), capacity=2, radius=.1)
    for m in (small, large):
        m.observe([1, 0], [1], gain=0)
        m.observe([0, 1], [2], gain=0)
    np.testing.assert_array_equal(small.predict([1, .05]), [0])
    np.testing.assert_array_equal(large.predict([1, .05]), [1])


def test_admission_counter_overflow_fails_before_base_update():
    m = SurpriseMemory(DirectMoment(2, 1))
    m._policy['admissions'][0] = np.iinfo(np.uint64).max
    with pytest.raises(OverflowError):
        m.observe([1, 0], [1])
    np.testing.assert_array_equal(m.base._sum, np.zeros((3, 3)))
    assert m._policy['clock'][0] == 0


@pytest.mark.parametrize('backend,capacity', [('field', 20), ('direct_moment', 37), ('rls', 43)])
def test_fixed_capacities_are_constants_not_runtime_estimates(monkeypatch, backend, capacity):
    from experiments.salience_v1.configuration import build_fixed_memory
    import experiments.salience_v1.memory as module
    def forbidden(*a, **k):
        raise AssertionError('fit_budget must not choose evaluation capacity')
    monkeypatch.setattr(module, 'fit_budget', forbidden)
    m = build_fixed_memory(backend)
    assert m.storage_report()['capacity'] == capacity
    assert m.storage_report()['instance_owned_bytes'] <= 8192
    assert m._policy['radius'][0] == m._policy['threshold'][0] == .1


def test_fixed_capacity_budget_failure_aborts_without_resizing(monkeypatch):
    from experiments.salience_v1.configuration import build_fixed_memory
    monkeypatch.setattr('experiments.salience_v1.memory._owned_bytes', lambda _: 8193)
    with pytest.raises(ValueError, match='exceed'):
        build_fixed_memory('field')


@pytest.mark.parametrize('backend', ['field', 'direct_moment', 'rls'])
def test_nonbinding_profile_is_same_k_not_same_consumption(backend):
    from experiments.salience_v1.configuration import build_fixed_memory
    assert build_fixed_memory(backend, comparison='matched_nonbinding').storage_report()['capacity'] == 4


def test_fixed_profile_rejects_unknown_comparisons_and_backends():
    from experiments.salience_v1.configuration import build_fixed_memory
    with pytest.raises(ValueError): build_fixed_memory('other')
    with pytest.raises(ValueError): build_fixed_memory('field', comparison='resized')


@pytest.mark.parametrize('decay', [0., .01])
def test_field_direct_nonbinding_policy_actions_and_predictions_match(decay):
    models = [SurpriseMemory(cls(3, 2, decay=decay), capacity=4, radius=.1)
              for cls in (FieldPredictor, DirectMoment)]
    events = [([1, 0, 0], [1, 0]), ([0, 1, 0], [0, 1]),
              ([1, 1e-6, 0], [1, 0]), ([1, 2e-6, 0], [-1, 0])]
    for cue, target in events:
        a, b = [m.observe(cue, target) for m in models]
        for key in ('admitted', 'removed', 'revised'):
            assert a[key] == b[key]
        np.testing.assert_allclose(models[0].predict([.2, .4, .3]),
                                   models[1].predict([.2, .4, .3]), atol=1e-12)
        for attr in ('_cues', '_targets', '_ages', '_valid'):
            np.testing.assert_array_equal(getattr(models[0], attr), getattr(models[1], attr))
    assert models[0].storage_report()['occupied'] < 4


def test_raw_weight_semantics_of_joint_normalization():
    cue = np.array([1., .5]); target = np.array([2.]); gain = 3.
    raw = np.concatenate((cue, target))
    m = DirectMoment(2, 1); m.update(cue, target, gain=gain)
    np.testing.assert_allclose(m._sum, gain/(raw@raw)*np.outer(raw, raw))
    large = np.concatenate((cue, 3*target))
    raw_weight_ratio = (raw@raw)/(large@large)
    assert 0 < raw_weight_ratio < 1
    scaled = DirectMoment(2, 1); scaled.update(cue, 3*target, gain=gain)
    np.testing.assert_allclose(scaled._sum, gain/(large@large)*np.outer(large, large))
    assert m._cfg[4] == scaled._cfg[4] == gain
