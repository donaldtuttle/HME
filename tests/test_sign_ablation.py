"""HME-NN-2A correctness fixtures; no registered evaluation seed is executed."""
import importlib.util
import json
from pathlib import Path
import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location('sign_evaluation',ROOT/'experiments/sign_ablation_v1/evaluate.py')
e = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(e)


def test_variant_has_exactly_one_registered_expression_change():
    original = (ROOT/'hme_engine.py').read_text()
    changed = e.variant.transformed_source()
    assert original.count(e.variant.ORIGINAL) == 1
    assert changed == original.replace(e.variant.ORIGINAL,e.variant.REPLACEMENT)
    assert changed.replace(e.variant.REPLACEMENT,e.variant.ORIGINAL) == original
    assert e.variant.signed_module() is e.variant.signed_module()


@pytest.mark.parametrize('mode',['native','symmetric'])
def test_writes_identical_and_ranker_matches_independent_scalar_calculation(mode):
    cfg = dict(memory_size=16,dimension=8,position=[8,8],write_strength=.1)
    rng = np.random.default_rng(67)
    vectors = rng.normal(size=(9,8))
    arms,ids = e.build_arms(vectors,67,cfg)
    absolute,signed = arms['hme_abs'],arms['hme_signed']
    np.testing.assert_array_equal(absolute.hme.field,signed.hme.field)
    assert absolute.lineage.to_dict() == signed.lineage.to_dict()
    for identifier in ids:
        assert absolute.hme.records[identifier].to_dict() == signed.hme.records[identifier].to_dict()
        np.testing.assert_array_equal(absolute.hme._payloads[identifier],signed.hme._payloads[identifier])
        np.testing.assert_array_equal(absolute.hme._patterns[identifier],signed.hme._patterns[identifier])
    query = e.base.query_input(rng.normal(size=8),mode)
    q = query/np.linalg.norm(query)
    for name in ('hme_abs','hme_signed'):
        scores = {}
        for identifier in ids:
            vector = arms[name].hme._payloads[identifier]
            cosine = float(np.vdot(vector,q).real/(np.linalg.norm(vector)*np.linalg.norm(q)))
            if name == 'hme_abs':
                cosine = abs(cosine)
            pattern = arms[name].hme._patterns[identifier]
            grid,local = arms[name].hme._patch_slices((8,8),pattern.shape)
            patch = arms[name].hme.field[grid]
            pattern_score = abs(np.vdot(patch,pattern[local]))/(np.linalg.norm(patch)*np.linalg.norm(pattern[local]))
            scores[identifier] = float(np.clip(.38+.42*cosine+.20*pattern_score,0,1))
        result = arms[name].retrieve_memory((8,8),query=query,top_k=9)
        expected = sorted(ids,key=lambda identifier:-scores[identifier])
        assert [h.artifact_id for h in result.hits] == expected
        np.testing.assert_allclose([h.final_score for h in result.hits],[scores[i] for i in expected],atol=1e-14)
        assert result.decoded_surface.shape == (9,9)
        assert result.decoded_vector.shape == (8,)


def test_opposite_vector_loses_only_in_signed_variant_with_same_field_bias():
    engines = []
    for module in (e.sys.modules['hme_engine'],e.variant.signed_module()):
        engine = module.HMEEngine(hme_config=module.HMEConfig(memory_size=8,encoding_resolution=4,use_hann_window=False))
        neg = engine.encode_memory([-1,0,0,0],(4,4),tag='negative')
        pos = engine.encode_memory([1,0,0,0],(4,4),tag='positive')
        result = engine.retrieve_memory((4,4),query=[1,0,0,0],top_k=2)
        engines.append((engine,neg,pos,result))
    assert engines[0][3].hits[0].artifact_id == engines[0][1].artifact_id
    assert engines[1][3].hits[0].artifact_id == engines[1][2].artifact_id
    assert {h.query_score for h in engines[0][3].hits} == {1.}
    assert {h.query_score for h in engines[1][3].hits} == {-1.,1.}
    assert {h.pattern_score for h in engines[0][3].hits} == {h.pattern_score for h in engines[1][3].hits}


def test_equivalence_is_not_zero_overlap_or_noninferiority():
    assert e.decisions({'ci90':[-.009,.009],'ci95':[-.011,.011]},.01)['equivalence_within_margin']
    wide = e.decisions({'ci90':[-.02,.02],'ci95':[-.03,.03]},.01)
    assert not wide['equivalence_within_margin']
    assert not wide['noninferiority_within_margin']
    beneficial = e.decisions({'ci90':[.005,.02],'ci95':[.003,.025]},.01)
    assert beneficial['noninferiority_within_margin']
    assert not beneficial['equivalence_within_margin']
    assert beneficial['higher_mean_accuracy_ci95']
    deficit = e.decisions({'ci90':[-.025,-.015],'ci95':[-.027,-.013]},.01)
    assert deficit['deficit_exceeds_margin']
    assert deficit['lower_mean_accuracy_ci95']
    assert not e.decisions({'ci90':[-.01,.009],'ci95':[-.012,.012]},.01)['equivalence_within_margin']


def test_complete_pipeline_with_two_tiny_non_evaluation_seeds():
    p = json.loads((e.HERE/'protocol.json').read_text())
    old = json.loads((ROOT/'experiments/nn_baseline_v1/protocol.json').read_text())
    fixtures = {67,71,73}
    assert fixtures.isdisjoint(p['seeds']) and fixtures.isdisjoint(old['seeds'])
    assert set(p['seeds']).isdisjoint(old['seeds'])
    p['dataset'].update(items_per_seed=8,dimension=8,memory_size=16,position=[8,8],unmatched_queries_per_seed=2)
    p['latency'].update(queries_per_seed=2,warmup_queries_per_arm=1,repetitions=1)
    p['statistics']['bootstrap_resamples'] = 100
    runs = [e.one_seed(seed,p) for seed in (71,73)]
    report = e.analyze(runs,p)
    assert len(report['conditions']) == 8
    assert report['all_arms_within_budget']
    for run in runs:
        for cell in run['cells']:
            assert set(cell['arms']) == {'hme_abs','hme_signed','nn_cosine'}
            for arm in cell['arms'].values():
                assert len(arm['target_ranks']) == 8
        assert all(len(arm['nanoseconds']) == 2 for arm in run['latency'].values())
    json.dumps({'runs':runs,'analysis':report},allow_nan=False)
    with pytest.raises(ValueError,match='40-character'):
        e.verify_registration('invalid',p)
