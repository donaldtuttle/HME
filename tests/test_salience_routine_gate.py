"""Fabricated-score and algebra fixtures only, not SAL-1 performance evidence."""
import copy

import numpy as np
import pytest

from experiments.salience_v1.configuration import build_fixed_memory, policy_constants
from experiments.salience_v1.memory import DirectMoment, SurpriseMemory
from experiments.salience_v1.radius_selection import select_validation_radius, checked_radius
from experiments.salience_v1.routine_gate import (
    routine_gate, base_contamination_precheck, checked_base_precheck,
)

IDS = ['gate-fixture-A', 'gate-fixture-B']


def config(**overrides):
    out = dict(gain=1., decay=0., ridge=.01, observation_noise_std=.1,
               routine_writes=1000, correction_writes=1, conflicting_corrections=1,
               corpus_id='fabricated-gate-fixture')
    out.update(overrides)
    return out


def base_check(error=.0003, reference=.0002, **overrides):
    return base_contamination_precheck(
        [dict(stream_id=s, base_routine_error=error, routine_reference_error=reference)
         for s in IDS], backend='direct_moment', noise_std=.01,
        configuration=config(**overrides), expected_stream_ids=IDS)


def radius_rows(error=.0003, reference=.0002):
    return [dict(stream_id=s, radius=r, routine_error=error,
                 routine_reference_error=reference, correction_error=1 if r<.2 else .05)
            for r in policy_constants()['radius_selection']['candidate_radii'] for s in IDS]


@pytest.mark.parametrize('reference', [0.,1e-12,.0002,.0337,.2044])
def test_small_absolute_increase_is_not_rejected_by_small_reference(reference):
    result = routine_gate(reference+.0001, reference)
    assert result['feasible']
    assert result['allowed_increase'] == pytest.approx(.001+.01*reference)


def test_clean_example_old_rule_fails_but_practical_rule_passes():
    assert .0003 > 1.01*.0002
    result = routine_gate(.0003, .0002)
    assert result['limit'] == pytest.approx(.001202)
    assert result['feasible']
    assert result['absolute_change'] == pytest.approx(.0001)


def test_boundary_is_inclusive_without_extra_isclose_tolerance():
    limit = routine_gate(0, .0002)['limit']
    assert routine_gate(limit,.0002)['feasible']
    assert not routine_gate(np.nextafter(limit,np.inf),.0002)['feasible']


@pytest.mark.parametrize('reference', [0.,.0002,.2])
def test_absolute_floor_does_not_excuse_large_damage(reference):
    assert not routine_gate(reference+.02,reference)['feasible']


@pytest.mark.parametrize('value', [-1.,float('nan'),float('inf'),True,'0.01',None])
@pytest.mark.parametrize('which', ['error','reference'])
def test_invalid_gate_values_rejected(value,which):
    values=dict(error=.1,reference=.1);values[which]=value
    with pytest.raises(ValueError):routine_gate(**values)


def test_gate_rejects_overflow_instead_of_accepting_infinite_limit():
    with pytest.raises(ValueError):routine_gate(0,np.finfo(float).max)


def test_nearzero_base_and_radius_use_same_gate():
    pre=base_check()
    assert pre['status']=='eligible'
    choice=select_validation_radius(radius_rows(),backend='direct_moment',noise_std=.01,
                                    base_precheck=pre)
    assert choice['status']=='selected' and choice['radius']==.2
    assert all(row['routine_gate']==pre['gate'] for row in choice['scores'])


def test_base_failure_never_consumes_radius_search():
    class SearchMustNotRun:
        def __iter__(self):raise AssertionError('radius generation was incorrectly started')
    choice=select_validation_radius(SearchMustNotRun(),backend='direct_moment',noise_std=.01,
                                    base_precheck=base_check(.02))
    assert choice['status']=='base_contamination'
    assert choice['radius'] is None and choice['scores']==[] and choice['rows']==[]
    with pytest.raises(ValueError,match='base contamination'):
        checked_radius(choice,backend='direct_moment',noise_std=.01,comparison='budget')


def test_radius_failure_is_distinct_from_base_failure():
    choice=select_validation_radius(radius_rows(.1),backend='direct_moment',noise_std=.01,
                                    base_precheck=base_check())
    assert choice['status']=='infeasible' and choice['base_precheck']['status']=='eligible'
    assert len(choice['scores'])==7


def test_missing_precheck_cannot_bypass_base_screen():
    with pytest.raises(ValueError,match='precheck'):
        select_validation_radius(radius_rows(),backend='direct_moment',noise_std=.01)


@pytest.mark.parametrize('tamper',['status','configuration','noise','backend','gate','policy'])
def test_precheck_tampering_or_wrong_group_rejected(tamper):
    pre=base_check()
    if tamper=='status':pre['status']='base_contamination'
    if tamper=='configuration':pre['configuration']['decay']=.1
    if tamper=='noise':pre['noise_std']=.05
    if tamper=='backend':pre['backend']='rls'
    if tamper=='gate':pre['gate']['feasible']=False
    if tamper=='policy':pre['policy_sha256']='0'*64
    # A different valid configuration cannot be inferred from aggregate losses,
    # so changing its label and recomputing all bindings could forge provenance.
    # Here raw replacement alone is detected by outer selection record binding.
    if tamper=='configuration':
        choice=select_validation_radius(radius_rows(),backend='direct_moment',noise_std=.01,
                                        base_precheck=base_check())
        choice['base_precheck']=pre
        with pytest.raises(ValueError):checked_radius(choice,backend='direct_moment',noise_std=.01,comparison='budget')
    else:
        with pytest.raises(ValueError):select_validation_radius(radius_rows(),backend='direct_moment',noise_std=.01,base_precheck=pre)


@pytest.mark.parametrize('change',['missing','duplicate','unexpected','negative','bool','nonfinite'])
def test_base_table_rejects_incomplete_or_invalid_streams(change):
    rows=copy.deepcopy(base_check()['rows'])
    if change=='missing':rows.pop()
    if change=='duplicate':rows.append(rows[0])
    if change=='unexpected':rows[0]['stream_id']='different'
    if change=='negative':rows[0]['base_routine_error']=-1
    if change=='bool':rows[0]['base_routine_error']=True
    if change=='nonfinite':rows[0]['base_routine_error']=np.nan
    with pytest.raises(ValueError):
        base_contamination_precheck(rows,backend='direct_moment',noise_std=.01,
                                    configuration=config(),expected_stream_ids=IDS)


@pytest.mark.parametrize('which',['stream','reference'])
def test_radius_inputs_bound_to_base_screen(which):
    rows=radius_rows()
    for row in rows:
        if which=='stream':row['stream_id']+='different'
        else:row['routine_reference_error']=.9
    with pytest.raises(ValueError):select_validation_radius(rows,backend='direct_moment',noise_std=.01,base_precheck=base_check())


@pytest.mark.parametrize('overrides',[{'decay':1.},{'ridge':0.},{'gain':-1.},
                                     {'observation_noise_std':-1.},{'routine_writes':0},
                                     {'correction_writes':True},{'conflicting_corrections':2},
                                     {'corpus_id':''}])
def test_configuration_contract_rejects_invalid_counts_or_settings(overrides):
    with pytest.raises(ValueError):base_check(**overrides)


def test_density_counts_feedback_events_and_zero_noise_is_allowed():
    pre=base_check(correction_writes=6,conflicting_corrections=6,observation_noise_std=0)
    assert pre['conflicting_fraction']==pytest.approx(6/1006)
    assert pre['configuration']['observation_noise_std']==0


def test_selected_backend_uses_screened_decay_and_ridge():
    choice=select_validation_radius(radius_rows(),backend='direct_moment',noise_std=.01,
                                    base_precheck=base_check(decay=.02,ridge=.03))
    m=build_fixed_memory('direct_moment',radius_profile='validation_selected',noise_std=.01,selection=choice)
    assert m.base._cfg[2]==.02 and m.base._cfg[3]==.03
    refreshed=build_fixed_memory('direct_moment',eviction='confirmation_refresh',radius_profile='validation_selected',noise_std=.01,selection=choice)
    assert m.storage_report()==refreshed.storage_report()


def test_record_roundtrip_order_and_no_input_mutation():
    import json
    pre=base_check();rows=radius_rows();before=copy.deepcopy((pre,rows))
    a=select_validation_radius(rows,backend='direct_moment',noise_std=.01,base_precheck=pre)
    b=select_validation_radius(list(reversed(rows)),backend='direct_moment',noise_std=.01,base_precheck=pre)
    assert a==b and before==(pre,rows)
    assert checked_radius(json.loads(json.dumps(a)),backend='direct_moment',noise_std=.01,comparison='budget')==.2


def test_base_rejection_is_not_a_theorem_about_hybrid_error():
    # Deterministic counterexample: supplied feedback buffer repairs a bad base
    # on this same cue. The conservative screen still rejects that base setting.
    m=SurpriseMemory(DirectMoment(2,1),radius=.1)
    for _ in range(30):m.observe([1,0],[1],eligible=False)
    m.observe([1,0],[-1],gain=100)
    target=np.array([1.])
    assert np.sum((m.base.predict([1,0])-target)**2)>.01
    m.observe([1,0],target,gain=0)
    np.testing.assert_array_equal(m.predict([1,0]),target)


def test_radius_changes_do_not_change_base_state_for_fixed_feedback_stream():
    pair=[SurpriseMemory(DirectMoment(2,1),radius=r) for r in (.05,.4)]
    for j in range(20):
        for m in pair:m.observe([1.,j*.001],[1. if j!=10 else -1.],gain=1)
    np.testing.assert_array_equal(pair[0].base._sum,pair[1].base._sum)
    np.testing.assert_array_equal(pair[0].base._cfg,pair[1].base._cfg)
