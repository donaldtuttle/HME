"""Tiny correctness fixtures for HME-NN-2B; never run registered evaluation seeds."""
import importlib.util
import json
from pathlib import Path
import numpy as np
import pytest

ROOT=Path(__file__).resolve().parents[1]
SPEC=importlib.util.spec_from_file_location('field_eval_tests',ROOT/'experiments/field_retrieval_v1/evaluate.py')
e=importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(e)


def config():
    return {'items_per_seed':8,'dimension':8,'memory_size':32,'grid_shape':[2,4],
            'write_strength':.1,'spacings':[8,6,4,2,0],'noise_sigmas':[0.,.25,.5,1.],
            'query_modes':['native','symmetric'],'unmatched_queries_per_seed':2}


def fixture(spacing=4):
    rng=np.random.default_rng(83)
    vectors=rng.normal(size=(8,8))
    engine,arms,permutation=e.build(vectors,83,config(),spacing,{'a':.42,'b':.20})
    return vectors,engine,arms,permutation


def test_pattern_encoder_matches_core_and_preserves_sign_ambiguity():
    rng=np.random.default_rng(89)
    vectors=rng.normal(size=(5,8))
    core=e.base.HMEEngine(hme_config=e.base.HMEConfig(memory_size=16,encoding_resolution=8,use_hann_window=False))
    processed=e.model.preprocess(vectors,'symmetric')
    generated=e.model.patterns(processed)
    expected=np.stack([core.hme._generate_pattern(v)[1].reshape(-1) for v in processed])
    np.testing.assert_allclose(generated,expected,atol=1e-14)
    np.testing.assert_array_equal(generated,e.model.patterns(-processed))
    np.testing.assert_array_equal(e.model.patterns(np.zeros((1,8))),np.zeros((1,64)))
    np.testing.assert_allclose(np.abs(generated@generated.conj().T),np.abs(processed@processed.conj().T)**2,atol=1e-14)


def test_layout_no_clipping_content_independent_and_same_candidate_provenance():
    cfg=config()
    for spacing in cfg['spacings']:
        positions=e.model.assigned_positions(83,cfg,spacing)
        assert np.all(positions-cfg['dimension']//2>=0)
        assert np.all(positions+cfg['dimension']//2<=cfg['memory_size'])
        assert len(np.unique(positions,axis=0))==(1 if spacing==0 else 8)
    vectors,engine,arms,permutation=fixture()
    assert sorted(permutation)==list(range(8))
    assert not np.any(permutation==np.arange(8))
    expected=[r.to_dict() for r in engine.hme.records.values()]
    for arm in arms.values():
        assert [r.to_dict() for r in arm.records]==expected
        assert arm.lineage.to_dict()==engine.lineage.to_dict()
        assert arm.ids==list(engine.hme.records)
    assert arms['field_only'].vectors is None
    assert not hasattr(arms['field_only'],'_patterns')


@pytest.mark.parametrize('mode',['native','symmetric'])
def test_isolated_readouts_equal_absolute_squared_and_hybrid_monotone(mode):
    vectors,_,arms,_=fixture(spacing=8)
    queries=vectors+np.random.default_rng(97).normal(size=vectors.shape)
    signed=arms['nn_signed'].scores(queries,mode)
    field=arms['field_only'].scores(queries,mode)
    hybrid=arms['hybrid'].scores(queries,mode)
    np.testing.assert_allclose(field,signed**2,atol=1e-14)
    np.testing.assert_allclose(hybrid,.42*signed+.20*field,atol=1e-14)
    np.testing.assert_array_equal(np.argsort(-hybrid,axis=1),np.argsort(-signed,axis=1))
    np.testing.assert_array_equal(np.argsort(-field,axis=1),np.argsort(-np.abs(signed),axis=1))


def test_overlapping_score_matches_scalar_patch_correlation_and_permutation():
    vectors,engine,arms,permutation=fixture(spacing=4)
    query=vectors[3]+np.random.default_rng(101).normal(size=8)
    q=e.model.preprocess(query,'native')[0]
    p=e.model.patterns(q)[0].reshape(8,8)
    expected=[]
    for record in engine.hme.records.values():
        grid,local=engine.hme._patch_slices(record.position,(8,8))
        patch=engine.hme.field[grid]
        expected.append(abs(np.vdot(p[local],patch))/(np.linalg.norm(p[local])*np.linalg.norm(patch)))
    signed=np.array([np.vdot(v,q).real/np.linalg.norm(v) for v in engine.hme._payloads.values()])
    np.testing.assert_allclose(arms['field_only'].scores(query)[0],expected,atol=1e-14)
    np.testing.assert_allclose(arms['hybrid'].scores(query)[0],.42*signed+.20*np.array(expected),atol=1e-14)
    np.testing.assert_allclose(arms['hybrid_permuted'].scores(query)[0],.42*signed+.20*np.array(expected)[permutation],atol=1e-14)


def test_shared_zero_field_cache_invalidation_and_single_query_api():
    vectors,engine,arms,_=fixture(spacing=0)
    for name in ('hybrid','hybrid_permuted'):
        np.testing.assert_array_equal(arms[name].scores(vectors),arms['nn_signed'].scores(vectors))
    field=arms['field_only'].scores(vectors)
    assert np.all(field==field[:,:1])
    vectors,engine,arms,_=fixture(spacing=4)
    for name in ('hybrid','field_only','hybrid_permuted'):
        arm=arms[name]
        batch=arm.scores(vectors)
        np.testing.assert_allclose(batch,arm.scores(vectors,cached=False),atol=1e-14)
        for i,q in enumerate(vectors):
            order,scores=arm.search(q,top_k=8)
            np.testing.assert_array_equal(order,np.argsort(-batch[i],kind='stable'))
            np.testing.assert_allclose(scores,batch[i,order],atol=1e-14)
        cached=e.base.persistent_size(arm)['numeric_array_bytes']
        arm.invalidate_cache()
        uncached=e.base.persistent_size(arm)['numeric_array_bytes']
        assert cached-uncached==8*8*8*16
        arm.prepare_cache()
        arm.replace_field(np.zeros_like(engine.hme.field))
        assert arm._cache is None
    np.testing.assert_array_equal(arms['hybrid'].scores(vectors),arms['nn_signed'].scores(vectors))
    np.testing.assert_array_equal(arms['field_only'].scores(vectors),np.zeros((8,8)))


def test_antipodal_identification_ceiling():
    half=np.random.default_rng(103).normal(size=(4,8))
    vectors=np.concatenate((half,-half))
    for spacing in (8,4,0):
        _,arms,_=e.build(vectors,103,config(),spacing,{'a':.42,'b':.20})
        result=e.cell(arms,vectors,'symmetric',0.,spacing,'antipodal')
        assert result['arms']['field_only']['top1_accuracy']<=.5
        assert 'antipodal_ceiling' in result['passed_controls']


def test_complete_small_fixture_pipeline_without_registered_seeds():
    p=json.loads((e.HERE/'protocol.json').read_text())
    fixtures={83,89,97,101,103,107,109}
    assert fixtures.isdisjoint(p['seeds'])
    for name in ('nn_baseline_v1','sign_ablation_v1'):
        old=json.loads((ROOT/'experiments'/name/'protocol.json').read_text())
        assert set(old['seeds']).isdisjoint(p['seeds'])
    p['dataset']=config()
    p['primary']['condition']['spacing']=4
    p['latency'].update(queries_per_seed=2,warmup_queries_per_variant=1,repetitions=1,cache_cycles=1)
    p['statistics']['bootstrap_resamples']=100
    runs=[e.one_seed(seed,p) for seed in (107,109)]
    result=e.analyze(runs,p)
    assert len(result['conditions'])==50
    assert len(result['costs_by_layout'])==5
    assert result['all_arms_within_budget']
    assert result['all_correctness_gates_passed']
    json.dumps({'runs':runs,'result':result},allow_nan=False)
    with pytest.raises(ValueError,match='40-character'):
        e.verify_registration('invalid',p)
