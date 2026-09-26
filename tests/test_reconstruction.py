"""Development fixtures only. Never execute HME-REC-1's registered seeds here."""
import copy
import subprocess

import numpy as np
import pytest

from hme_engine import HMEConfig, HMEEngine
from experiments.reconstruction_v1 import evaluate as ev


@pytest.mark.parametrize("d", [7, 8, 16])
@pytest.mark.parametrize("complex_input", [False, True])
def test_fft_pattern_is_reversed_outer_product(d, complex_input):
    rng=np.random.default_rng(113)
    v=rng.normal(size=d)
    if complex_input:
        v=v+1j*rng.normal(size=d)
    e=HMEEngine(hme_config=HMEConfig(encoding_resolution=d,use_hann_window=False))
    vector,pattern=e.hme._generate_pattern(v)
    expected=vector[:,None]*vector[(-np.arange(d))%d].conj()[None,:]
    np.testing.assert_allclose(pattern,expected,atol=1e-14)


def fixture():
    x,t=ev.dataset(173,3,12,8,8)
    engine,models,costs=ev.prepare(x)
    y,m=ev.observations(t,173,3,.5,.1,"random")
    return x,t,engine,models,costs,y,m


def test_field_matches_direct_moment_and_ledger_erasure():
    x,t,e,models,costs,y,m=fixture()
    np.testing.assert_allclose(ev.field_moment(*models['field_ridge']),x.T@x/len(x),atol=1e-14)
    before=ev.reconstruct('field_ridge',models['field_ridge'],y[0],m[0])
    for attr in ('records','_payloads','_patterns'):
        getattr(e.hme,attr).clear()
    np.testing.assert_array_equal(before,ev.reconstruct('field_ridge',models['field_ridge'],y[0],m[0]))
    np.testing.assert_allclose(before,ev.reconstruct('direct_moment',models['direct_moment'],y[0],m[0]),atol=1e-13)


@pytest.mark.parametrize('arm',ev.ARMS)
def test_predictions_ignore_hidden_coordinates_and_keep_observations(arm):
    x,t,e,models,costs,y,m=fixture()
    before=ev.array_hash(e.hme.field)
    altered=y[0].copy(); altered[~m[0]]=1e90
    a=ev.reconstruct(arm,models[arm],y[0],m[0])
    b=ev.reconstruct(arm,models[arm],altered,m[0])
    np.testing.assert_array_equal(a,b)
    np.testing.assert_array_equal(a[m[0]],y[0][m[0]])
    assert before==ev.array_hash(e.hme.field)
    assert np.all(np.isfinite(a))


def test_zero_field_and_diagonal_controls_equal_zero_fill():
    x,t,e,models,costs,y,m=fixture()
    zero=ev.reconstruct('zero_fill',None,y[0],m[0])
    np.testing.assert_array_equal(zero,ev.reconstruct('diagonal_field',models['diagonal_field'],y[0],m[0]))
    e.hme.field.fill(0)
    np.testing.assert_array_equal(zero,ev.reconstruct('field_ridge',models['field_ridge'],y[0],m[0]))


def test_readout_linear_and_deterministic():
    x,t,e,models,costs,y,m=fixture()
    a=ev.reconstruct('field_ridge',models['field_ridge'],y[0],m[0])
    b=ev.reconstruct('field_ridge',models['field_ridge'],2*y[0],m[0])
    np.testing.assert_allclose(2*a,b,atol=1e-14)
    x2,t2=ev.dataset(173,3,12,8,8)
    np.testing.assert_array_equal(x,x2); np.testing.assert_array_equal(t,t2)
    assert not np.shares_memory(x,t)
    assert all(not np.array_equal(v,w) for v in x for w in t)


def test_scalar_baselines_and_ties():
    x=np.array([[1.,0.,.1,0.],[1.,0.,.3,0.],[-1.,0.,.8,0.]])
    mask=np.array([True,True,False,False]); y=np.array([1.,0.,np.nan,np.nan])
    assert ev.reconstruct('nn_copy',x,y,mask)[2]==.1
    scores=np.array([1.,1.,-1.]); weights=np.exp((scores-1)/ev.P['blend_temperature']); weights/=weights.sum()
    np.testing.assert_allclose(ev.reconstruct('weighted_blend',x,y,mask)[2:], weights@x[:,2:])


@pytest.mark.parametrize('mask', [np.ones(8,dtype=bool),np.zeros(8,dtype=bool),np.ones(8),np.ones(7,dtype=bool)])
def test_invalid_masks_rejected(mask):
    with pytest.raises(ValueError):ev.reconstruct('zero_fill',None,np.ones(8),mask)


def test_nonfinite_observations_rejected():
    mask=np.arange(8)%2==0; y=np.ones(8); y[0]=np.nan
    with pytest.raises(ValueError):ev.reconstruct('zero_fill',None,y,mask)


def test_small_cell_controls_and_storage_accounting():
    x,t,e,models,costs,y,m=fixture()
    result=ev.cell(173,3,.5,.1,'random',t,models,None)
    assert set(result['nmse'])==set(ev.ARMS)
    assert result['field_direct_max_error']<1e-12
    assert costs['bundle_bytes']['field_ridge']>costs['compact_state_bytes']['field_ridge']
    assert costs['bundle_bytes']['direct_moment']>costs['compact_state_bytes']['direct_moment']
    a=np.ones(100); assert ev.persistent_bytes((a,a))<ev.persistent_bytes((a,a.copy()))


def test_identity_path_unchanged_on_small_development_fixture():
    g=ev.identity_guardrail(187,n=8,d=8)
    assert g['unchanged']
    assert len(g['hme_predictions'])==8


def registration_runner(remote=True, origin=ev.ORIGINS[0], changed=False):
    calls=[]
    def fake(*args):
        calls.append(args)
        if args[0]=='show':return (ev.ROOT/args[1].split(':',1)[1]).read_text().strip()
        if args[0] in ('rev-parse','hash-object'):
            return 'b'*40 if changed and args[0]=='hash-object' else 'a'*40
        if args[:2]==('remote','get-url'):return origin
        if args[0]=='for-each-ref':
            return 'refs/remotes/origin/study '+'a'*40 if remote else ''
        return ''
    return fake,calls


def test_registration_fetches_canonical_origin_before_containment_check():
    fake,calls=registration_runner()
    record=ev.verify_registration('1'*40,runner=fake)
    assert record['containing_remote_refs']
    names=[c[0] for c in calls]
    assert names.index('fetch')<names.index('for-each-ref')
    assert '+refs/heads/*:refs/remotes/origin/*' in calls[names.index('fetch')]


@pytest.mark.parametrize('settings',[{'remote':False},{'origin':'/tmp/local.git'},{'changed':True}])
def test_registration_rejects_local_only_other_origin_and_changed_bytes(settings):
    fake,_=registration_runner(**settings)
    with pytest.raises(RuntimeError):ev.verify_registration('1'*40,runner=fake)


def test_registration_rejects_symbolic_refs_and_non_ancestor():
    with pytest.raises(ValueError):ev.verify_registration('main')
    def failed(*args):raise subprocess.CalledProcessError(1,args)
    with pytest.raises(subprocess.CalledProcessError):ev.verify_registration('1'*40,runner=failed)


def test_no_development_seed_is_registered_and_summary_rejects_missing_cells():
    assert not {113,173,187}&set(ev.P['seeds'])
    with pytest.raises(ValueError):ev.summarize([],[],[])
