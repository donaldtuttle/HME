"""Radius-selection and eviction development fixtures; no SAL-1 evaluation."""
import math

import numpy as np
import pytest

from experiments.salience_v1.configuration import build_fixed_memory, policy_constants
from experiments.salience_v1.memory import DirectMoment, FieldPredictor, ForgettingRLS, SurpriseMemory
from experiments.salience_v1.radius_selection import select_validation_radius as _select_validation_radius


from experiments.salience_v1.routine_gate import base_contamination_precheck


def select_validation_radius(rows, **kwargs):
    """Existing synthetic radius fixtures now supply the mandatory base screen."""
    check = base_contamination_precheck(
        [{"stream_id": s, "base_routine_error": .2, "routine_reference_error": .2}
         for s in ("fixture-A", "fixture-B")],
        backend=kwargs.get("backend"), noise_std=kwargs.get("noise_std"),
        comparison=kwargs.get("comparison", "budget"),
        configuration={"gain": 1., "decay": 0., "ridge": .01,
                       "observation_noise_std": .1, "routine_writes": 1000,
                       "correction_writes": 1, "conflicting_corrections": 1,
                       "corpus_id": "fabricated-existing-radius-fixture"},
        expected_stream_ids=["fixture-A", "fixture-B"])
    return _select_validation_radius(rows, base_precheck=check, **kwargs)

BASES = (FieldPredictor, DirectMoment, ForgettingRLS)


def validation_rows():
    # Fabricated aggregate losses to exercise selection, NOT measured performance.
    return [dict(stream_id=s, radius=r, correction_error=.4 if r < .2 else .1,
                 routine_error=.2 if r <= .3 else .5, routine_reference_error=.2)
            for r in policy_constants()['radius_selection']['candidate_radii']
            for s in ('fixture-A', 'fixture-B')]


@pytest.mark.parametrize('base', BASES)
def test_confirmed_correction_survives_pressure_only_in_refresh_arm(base):
    pair = [SurpriseMemory(base(2, 1), capacity=2, radius=.1, refresh_on_confirmation=flag)
            for flag in (False, True)]
    for m in pair:
        m.observe([1, 0], [1], gain=0)
        m.observe([0, 1], [2], gain=0)
    before = [m.storage_report() for m in pair]
    for i in range(1, 101):
        events = [m.observe([1, i*1e-6], [1], gain=0) for m in pair]
        assert not events[0]['refreshed'] and events[1]['refreshed']
        assert all(not ev['admitted'] and not ev['removed'] for ev in events)
    assert before == [m.storage_report() for m in pair]
    for m in pair:
        m.observe([-1, 0], [3], gain=0)
    assert pair[0]._match(np.array([1, 0])) is None
    assert pair[1]._match(np.array([0, 1])) is None
    np.testing.assert_array_equal(pair[1].predict([1, 0]), [1])


@pytest.mark.parametrize('eviction', ['fifo', 'confirmation_refresh'])
@pytest.mark.parametrize('backend,capacity', [('field',20),('direct_moment',37),('rls',43)])
def test_modes_use_identical_bytes_and_fixed_capacities(backend,capacity,eviction):
    m = build_fixed_memory(backend, eviction=eviction)
    control = build_fixed_memory(backend)
    assert m.storage_report() == control.storage_report()
    assert m.storage_report()['capacity'] == capacity
    assert m.storage_report()['instance_owned_bytes'] <= 8192
    assert m._policy.dtype.itemsize == 33


@pytest.mark.parametrize('trusted,eligible', [(False,True),(True,False)])
def test_confirmation_requires_trusted_eligible_feedback(trusted,eligible):
    m = SurpriseMemory(DirectMoment(2,1), refresh_on_confirmation=True)
    m.observe([1,0],[1],gain=0)
    old = [a.tobytes() for a in (m._cues,m._targets,m._ages,m._valid)]
    m.observe([1,1e-6],[1],gain=0,trusted=trusted,eligible=eligible)
    assert old == [a.tobytes() for a in (m._cues,m._targets,m._ages,m._valid)]


def test_unlabelled_recall_does_not_confirm_itself():
    m = SurpriseMemory(DirectMoment(2,1), refresh_on_confirmation=True)
    m.observe([1,0],[1],gain=0)
    old = [a.tobytes() for a in (m._cues,m._targets,m._ages,m._valid,m._policy)]
    for _ in range(100):
        np.testing.assert_array_equal(m.predict([1,0]),[1])
    assert old == [a.tobytes() for a in (m._cues,m._targets,m._ages,m._valid,m._policy)]


def test_confirmation_does_not_change_equal_distance_recall_tie():
    m = SurpriseMemory(DirectMoment(2,1), capacity=2, radius=1,
                       refresh_on_confirmation=True)
    m.observe([1,1],[1],gain=0);m.observe([1,-1],[2],gain=0)
    assert m.observe([1,1],[1],gain=0)['refreshed']
    # First entry was confirmed later, but the second was ACCEPTED later.
    np.testing.assert_array_equal(m.predict([1,0]),[2])
    m.observe([1,1],[3],gain=0)
    # A genuine revision changes acceptance ordering, just as in the old policy.
    np.testing.assert_array_equal(m.predict([1,0]),[3])


def test_retirement_precedes_confirmation_and_anchor_stays_fixed():
    m = SurpriseMemory(DirectMoment(2,1), refresh_on_confirmation=True)
    for _ in range(30):m.observe([1,0],[1],eligible=False)
    m.observe([1,0],[-1],gain=0)
    m.observe([1,.05],[-1],gain=0)
    np.testing.assert_array_equal(m._cues[0],[1,0])
    event=m.observe([1,0],m.base.predict([1,0]),gain=0)
    assert event['removed'] and not event['refreshed']
    assert m.storage_report()['occupied']==0


def test_rejected_base_update_does_not_refresh(monkeypatch):
    m = SurpriseMemory(DirectMoment(2,1), refresh_on_confirmation=True)
    m.observe([1,0],[1],gain=0)
    before=[a.tobytes() for a in (m._ages,m._policy)]
    def fail(*a,**kw):raise FloatingPointError('fixture rejection')
    monkeypatch.setattr(DirectMoment,'update',fail)
    with pytest.raises(FloatingPointError):m.observe([1,0],[1])
    assert before==[a.tobytes() for a in (m._ages,m._policy)]


@pytest.mark.parametrize('value', ['yes', 1, None])
def test_refresh_boolean_validated(value):
    with pytest.raises(TypeError):
        SurpriseMemory(DirectMoment(2,1),refresh_on_confirmation=value)


def test_confirmation_counter_limit_before_mutation():
    m=SurpriseMemory(DirectMoment(2,1),refresh_on_confirmation=True)
    m.observe([1,0],[1],gain=0)
    age=m._ages.copy();m._policy['clock'][0]=np.iinfo(np.uint64).max
    with pytest.raises(OverflowError):m.observe([1,0],[1],gain=0)
    np.testing.assert_array_equal(m._ages,age)


def test_known_pairwise_gaussian_coverage_formula():
    # For df=8 the chi-square CDF has this elementary finite-sum form.
    def pair_p(sigma):
        a=.1**2/(4*sigma*sigma)
        return 1-math.exp(-a)*sum(a**k/math.factorial(k) for k in range(4))
    assert pair_p(.05)==pytest.approx(.0189881568761538)
    assert pair_p(.01)==pytest.approx(.9999999591324105)


def test_fixed_stress_reproduces_geometric_fragmentation_not_an_admission_bug():
    # Six deterministically chosen perturbations, not draws from evaluation seeds.
    m=build_fixed_memory('direct_moment',radius_profile='fixed_stress',noise_std=.05)
    x=np.eye(8)[0];y=-x
    for i in range(6):
        delta=.05*np.ones(8);delta[i]=-.05;delta[(i+1)%8]=-.05
        m.observe(x+delta,y,gain=0)
    assert m.storage_report()['occupied']>1


def test_wider_radius_can_wrongly_override_nearby_context():
    narrow=SurpriseMemory(DirectMoment(2,1),radius=.1)
    wide=SurpriseMemory(DirectMoment(2,1),radius=.3)
    for m in (narrow,wide):m.observe([1,0],[1],gain=0)
    np.testing.assert_array_equal(narrow.predict([1,.2]),[0])
    np.testing.assert_array_equal(wide.predict([1,.2]),[1])


def test_validation_balances_routine_error_and_breaks_ties_by_small_radius():
    choice=select_validation_radius(validation_rows(),backend='direct_moment',noise_std=.05)
    assert choice['radius']==.2  # .25 and .3 tie; .4 violates the routine gate.
    assert choice['status']=='selected'
    a=build_fixed_memory('direct_moment',radius_profile='validation_selected',noise_std=.05,selection=choice)
    b=build_fixed_memory('direct_moment',eviction='confirmation_refresh',radius_profile='validation_selected',noise_std=.05,selection=choice)
    assert a._policy['radius'][0]==b._policy['radius'][0]==.2
    assert a.storage_report()==b.storage_report()


@pytest.mark.parametrize('split', ['test','evaluation','development'])
def test_selection_rejects_nonvalidation_label(split):
    with pytest.raises(ValueError):select_validation_radius(validation_rows(),backend='field',noise_std=.01,split=split)


def test_isolated_eviction_comparison_cannot_select_separate_refresh_radius():
    with pytest.raises(ValueError):
        select_validation_radius(validation_rows(),backend='field',noise_std=.01,eviction='confirmation_refresh')


@pytest.mark.parametrize('change',['missing','duplicate','nonfinite','negative','unequal_reference'])
def test_incomplete_or_invalid_validation_tables_rejected(change):
    rows=validation_rows()
    if change=='missing':rows.pop()
    if change=='duplicate':rows.append(rows[0])
    if change=='nonfinite':rows[0]['routine_error']=np.nan
    if change=='negative':rows[0]['routine_error']=-1
    if change=='unequal_reference':rows[0]['routine_reference_error']=2
    with pytest.raises(ValueError):select_validation_radius(rows,backend='field',noise_std=.01)


def test_no_feasible_radius_is_recorded_not_silently_repaired():
    rows=validation_rows()
    for row in rows:row['routine_error']=10
    choice=select_validation_radius(rows,backend='field',noise_std=.01)
    assert choice['status']=='infeasible' and choice['radius'] is None
    assert len(choice['scores'])==7
    with pytest.raises(ValueError,match='no feasible'):
        build_fixed_memory('field',radius_profile='validation_selected',noise_std=.01,selection=choice)


@pytest.mark.parametrize('change',['radius','noise','backend','policy'])
def test_selection_is_bound_to_policy_noise_backend_and_scores(change):
    choice=select_validation_radius(validation_rows(),backend='field',noise_std=.01)
    if change=='radius':choice['radius']=.4
    if change=='noise':choice['noise_std']=.05
    if change=='backend':choice['backend']='rls'
    if change=='policy':choice['policy_sha256']='0'*64
    with pytest.raises(ValueError):
        build_fixed_memory('field',radius_profile='validation_selected',noise_std=.01,selection=choice)


def test_matched_field_direct_share_selection_and_no_automatic_defaults():
    choice=select_validation_radius(validation_rows(),backend='direct_moment',noise_std=.01,comparison='matched_nonbinding')
    pair=[build_fixed_memory(b,comparison='matched_nonbinding',noise_std=.01,
                             radius_profile='validation_selected',selection=choice)
          for b in ('field','direct_moment')]
    assert all(m._policy['radius'][0]==.2 for m in pair)
    with pytest.raises(ValueError):build_fixed_memory('field',radius_profile='validation_selected',noise_std=.01)
    with pytest.raises(ValueError):build_fixed_memory('field',radius_profile='fixed_stress',noise_std=.01)
    with pytest.raises(ValueError):build_fixed_memory('field',radius_profile='other')
    with pytest.raises(ValueError):build_fixed_memory('field',eviction='other')
