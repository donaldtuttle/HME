"""HME-NN-2B frozen evaluator: run only after public preregistration."""
from __future__ import annotations
import os
THREAD_ENV={name:'1' for name in ('OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','MKL_NUM_THREADS','VECLIB_MAXIMUM_THREADS','NUMEXPR_NUM_THREADS')}
os.environ.update(THREAD_ENV)
import argparse
from contextlib import redirect_stdout
from datetime import datetime,timezone
import importlib.util
import io
import json
from pathlib import Path
import platform
import re
import subprocess
import sys
import time
import traceback
import numpy as np

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
sys.path.insert(0,str(ROOT))


def load(name,path):
    spec=importlib.util.spec_from_file_location(name,path)
    module=importlib.util.module_from_spec(spec)
    sys.modules[name]=module
    spec.loader.exec_module(module)
    return module


base=load('nn2b_base',ROOT/'experiments/nn_baseline_v1/evaluate.py')
model=load('nn2b_retrieval',HERE/'retrieval.py')
FROZEN_PATHS=('hme_engine.py','experiments/nn_baseline_v1/evaluate.py',
    'experiments/nn_baseline_v1/protocol.json','experiments/sign_ablation_v1/protocol.json',
    'experiments/field_retrieval_v1/PROTOCOL.md','experiments/field_retrieval_v1/protocol.json',
    'experiments/field_retrieval_v1/retrieval.py','experiments/field_retrieval_v1/evaluate.py',
    'tests/test_field_retrieval.py')


def build(vectors,seed,cfg,spacing,weights):
    positions=model.assigned_positions(seed,cfg,spacing)
    engine=base.HMEEngine(hme_config=base.HMEConfig(memory_size=cfg['memory_size'],encoding_resolution=cfg['dimension']),seed=seed)
    for i,(x,pos) in enumerate(zip(vectors,positions)):
        engine.encode_memory(x,tuple(pos),strength=cfg['write_strength'],tag=f'item-{i:04d}',t=i)
    offset=int(np.random.default_rng(np.random.SeedSequence([seed,4])).integers(1,len(vectors)))
    permutation=np.roll(np.arange(len(vectors)),offset)
    args={'a':weights['a'],'b':weights['b']}
    arms={'nn_signed':model.ExactNN(engine), 'nn_absolute':model.ExactNN(engine,absolute=True),
          'hybrid':model.FieldRetrieval(engine,hybrid=True,**args),
          'field_only':model.FieldRetrieval(engine,**args),
          'hybrid_permuted':model.FieldRetrieval(engine,hybrid=True,permutation=permutation,**args)}
    return engine,arms,permutation


def observe(scores):
    order=np.argsort(-scores,axis=1,kind='stable')
    truth=np.arange(scores.shape[0])
    ranks=np.argmax(order==truth[:,None],axis=1)+1
    return {**base.ranked_metrics(ranks),'target_ranks':ranks.tolist(),'top1_indices':order[:,0].tolist()}


def cell(arms,queries,mode,sigma,spacing,kind):
    values={name:arm.scores(queries,mode) for name,arm in arms.items()}
    result={name:observe(scores) for name,scores in values.items()}
    gates=[]
    if kind=='ordinary' and spacing==arms['hybrid'].dimension:
        for left,right in (('field_only','nn_absolute'),('hybrid','nn_signed')):
            if result[left]['target_ranks']!=result[right]['target_ranks']:
                raise RuntimeError(f'Isolated rank control failed: {left} vs {right}')
        gates.append('isolated_rank_controls')
    if spacing==0:
        for name in ('hybrid','hybrid_permuted'):
            if result[name]['target_ranks']!=result['nn_signed']['target_ranks'] or result[name]['top1_indices']!=result['nn_signed']['top1_indices']:
                raise RuntimeError('Shared-position hybrid differs from signed NN')
        if not np.all(values['field_only']==values['field_only'][:,:1]):
            raise RuntimeError('Shared-position field scores are not all tied')
        if result['field_only']['top1_accuracy']!=1/len(queries):
            raise RuntimeError('Shared-position field-only balanced accuracy differs from 1/N')
        gates.append('shared_position_controls')
    if kind=='antipodal':
        half=len(queries)//2
        if not np.array_equal(values['field_only'][:half],values['field_only'][half:]):
            raise RuntimeError('Opposite-sign queries produced different field-only scores')
        if result['field_only']['top1_accuracy']>.5:
            raise RuntimeError('Antipodal field-only accuracy exceeds its identification ceiling')
        gates.append('antipodal_ceiling')
    return {'kind':kind,'spacing':spacing,'query_mode':mode,'noise_sigma':sigma,'arms':result,'passed_controls':gates}


def reconstruction(engine):
    errors,correlations=[],[]
    for identifier,artifact in engine.hme.records.items():
        pattern=engine.hme._patterns[identifier]
        grid,local=engine.hme._patch_slices(artifact.position,pattern.shape)
        patch=engine.hme.field[grid]
        isolated=artifact.gain*pattern[local]
        errors.append(float(np.linalg.norm(patch-isolated)/np.linalg.norm(isolated)))
        correlations.append(float(abs(np.vdot(patch,isolated))/(np.linalg.norm(patch)*np.linalg.norm(isolated))))
    return {'relative_error_by_candidate':errors,'correlation_by_candidate':correlations,
            'mean_relative_error':float(np.mean(errors)),'mean_correlation':float(np.mean(correlations))}


def measure(engine,arms,queries,protocol):
    cfg=protocol['latency']
    cache={}
    for name in ('hybrid','field_only','hybrid_permuted'):
        arm=arms[name]
        arm.invalidate_cache()
        builds,discards=[],[]
        for _ in range(cfg['cache_cycles']):
            start=time.perf_counter_ns()
            arm.prepare_cache()
            builds.append(time.perf_counter_ns()-start)
            start=time.perf_counter_ns()
            arm.invalidate_cache()
            discards.append(time.perf_counter_ns()-start)
        arm.prepare_cache()
        cache[name]={'build_ns':builds,'invalidate_ns':discards,
                     'median_build_ns':float(np.median(builds)),
                     'median_invalidate_ns':float(np.median(discards))}
    weights=protocol['hybrid']
    uncached_h=model.FieldRetrieval(engine,hybrid=True,a=weights['a'],b=weights['b'])
    uncached_f=model.FieldRetrieval(engine,a=weights['a'],b=weights['b'])
    variants={'nn_signed':(arms['nn_signed'],{}),'nn_absolute':(arms['nn_absolute'],{}),
        'hybrid_cached':(arms['hybrid'],{'cached':True}),
        'hybrid_uncached':(uncached_h,{'cached':False}),
        'field_cached':(arms['field_only'],{'cached':True}),
        'field_uncached':(uncached_f,{'cached':False}),
        'hybrid_permuted_cached':(arms['hybrid_permuted'],{'cached':True})}
    storage={name:base.persistent_size(arm) for name,(arm,_) in variants.items()}
    if any(s['persistent_bytes']>protocol['budget']['persistent_bytes_cap_per_arm'] for s in storage.values()):
        raise RuntimeError('A retrieval snapshot exceeded the persistent storage cap')
    for arm,kwargs in variants.values():
        for q in queries[:cfg['warmup_queries_per_variant']]:
            arm.search(q,mode='native',top_k=cfg['top_k'],**kwargs)
    samples={name:[] for name in variants}
    names=list(variants)
    for repeat in range(cfg['repetitions']):
        for index,q in enumerate(queries[:cfg['queries_per_seed']]):
            shift=(index+repeat)%len(names)
            for name in names[shift:]+names[:shift]:
                arm,kwargs=variants[name]
                start=time.perf_counter_ns()
                arm.search(q,mode='native',top_k=cfg['top_k'],**kwargs)
                samples[name].append(time.perf_counter_ns()-start)
    latency={name:{'nanoseconds':values,'median_ns':float(np.median(values)),
                   'p95_ns':float(np.quantile(values,.95))} for name,values in samples.items()}
    return {'storage':storage,'latency':latency,'cache':cache,
            'source_writer_build_state':base.persistent_size(engine)}


def one_seed(seed,p):
    cfg=p['dataset']
    n,d=cfg['items_per_seed'],cfg['dimension']
    vectors=np.random.default_rng(seed).standard_normal((n,d))
    queries={sigma:vectors+sigma*np.random.default_rng(np.random.SeedSequence([seed,1,j])).standard_normal((n,d))
             for j,sigma in enumerate(cfg['noise_sigmas'])}
    unknown=np.random.default_rng(np.random.SeedSequence([seed,2])).standard_normal((cfg['unmatched_queries_per_seed'],d))
    half=np.random.default_rng(np.random.SeedSequence([seed,5])).standard_normal((n//2,d))
    antipodal=np.concatenate((half,-half))
    anti_queries={}
    for j,sigma in enumerate(p['antipodal_stress']['noise_sigmas']):
        positive=half+sigma*np.random.default_rng(np.random.SeedSequence([seed,6,j])).standard_normal(half.shape)
        anti_queries[sigma]=np.concatenate((positive,-positive))
    hashes={'source_vectors':base.array_hash(vectors),'unmatched_queries':base.array_hash(unknown),
            'antipodal_vectors':base.array_hash(antipodal)}
    hashes.update({f'queries_sigma_{sigma:g}':base.array_hash(q) for sigma,q in queries.items()})
    hashes.update({f'antipodal_queries_sigma_{sigma:g}':base.array_hash(q) for sigma,q in anti_queries.items()})
    cells,layouts=[],[]
    for spacing in cfg['spacings']:
        engine,arms,permutation=build(vectors,seed,cfg,spacing,p['hybrid'])
        primary_q=queries[p['primary']['condition']['noise_sigma']]
        for name in ('hybrid','field_only','hybrid_permuted'):
            arm=arms[name]
            cached=arm.scores(primary_q[:4],cached=True)
            uncached=arm.scores(primary_q[:4],cached=False)
            if not np.allclose(cached,uncached,atol=1e-13,rtol=0) or not np.array_equal(
                np.argsort(-cached,axis=1,kind='stable'),np.argsort(-uncached,axis=1,kind='stable')):
                raise RuntimeError('Cached and uncached readouts disagree')
        for sigma,q in queries.items():
            for mode in cfg['query_modes']:
                cells.append(cell(arms,q,mode,sigma,spacing,'ordinary'))
        if spacing==p['primary']['condition']['spacing']:
            zero=model.FieldRetrieval(engine,hybrid=True,a=p['hybrid']['a'],b=p['hybrid']['b'])
            zero.replace_field(np.zeros_like(engine.hme.field))
            if not np.array_equal(zero.scores(primary_q),arms['nn_signed'].scores(primary_q)):
                raise RuntimeError('Zero-field hybrid differs from signed NN')
        unmatched={}
        for mode in cfg['query_modes']:
            unmatched[mode]={name:{'accepted':len(unknown),'total':len(unknown),
                'top_scores':np.max(arm.scores(unknown,mode),axis=1).tolist()} for name,arm in arms.items()}
        costs=measure(engine,arms,primary_q,p)
        layouts.append({'spacing':spacing,'adjacent_overlap_fraction':max(0,1-spacing/d),
            'positions':arms['hybrid'].positions.tolist(),'artifact_ids':arms['hybrid'].ids,
            'permutation':permutation.tolist(), 'field_sha256':base.array_hash(engine.hme.field),
            'readout_sha256':base.array_hash(arms['hybrid']._cache),
            'processed_vectors_sha256':base.array_hash(arms['nn_signed'].vectors),
            'reconstruction':reconstruction(engine),'unmatched_queries':unmatched,**costs})
        del engine,arms
        anti_engine,anti_arms,_=build(antipodal,seed,cfg,spacing,p['hybrid'])
        for sigma,q in anti_queries.items():
            cells.append(cell(anti_arms,q,'symmetric',sigma,spacing,'antipodal'))
        for arm in anti_arms.values():
            if base.persistent_size(arm)['persistent_bytes']>p['budget']['persistent_bytes_cap_per_arm']:
                raise RuntimeError('Antipodal snapshot exceeded budget')
        del anti_engine,anti_arms
    return {'seed':seed,'data_hashes':hashes,'cells':cells,'layouts':layouts,
            'cache_agreement_passed':True,'zero_field_passed':True}


def analyze(runs,p):
    samples=np.random.default_rng(p['statistics']['bootstrap_seed']).integers(
        0,len(runs),size=(p['statistics']['bootstrap_resamples'],len(runs)))
    conditions=[]
    for template in runs[0]['cells']:
        key={k:template[k] for k in ('kind','spacing','query_mode','noise_sigma')}
        cells=[next(c for c in run['cells'] if all(c[k]==v for k,v in key.items())) for run in runs]
        arms={name:{metric:base.bootstrap_interval([c['arms'][name][metric] for c in cells],samples)
                     for metric in p['secondary']['metrics']} for name in p['arms']}
        contrasts={f'{left}_minus_{right}':{metric:base.bootstrap_interval(
            [c['arms'][left][metric]-c['arms'][right][metric] for c in cells],samples)
            for metric in p['secondary']['metrics']} for left,right in p['secondary']['contrasts']}
        conditions.append({**key,'arms':arms,'contrasts':contrasts})
    primary=next(c for c in conditions if c['kind']=='ordinary' and all(
        c[k]==v for k,v in p['primary']['condition'].items()))
    delta=primary['contrasts']['hybrid_minus_nn_signed']['top1_accuracy']
    gate=delta['ci95'][0]>p['primary']['minimum_mean_benefit']
    costs=[]
    for spacing in p['dataset']['spacings']:
        layouts=[next(x for x in run['layouts'] if x['spacing']==spacing) for run in runs]
        names=list(layouts[0]['storage'])
        storage={name:{'median_persistent_bytes':float(np.median([x['storage'][name]['persistent_bytes'] for x in layouts])),
            'max_persistent_bytes':max(x['storage'][name]['persistent_bytes'] for x in layouts),
            'numeric_array_bytes':[x['storage'][name]['numeric_array_bytes'] for x in layouts]} for name in names}
        latency={name:{'median_of_seed_medians_ns':float(np.median([x['latency'][name]['median_ns'] for x in layouts])),
            'median_of_seed_p95_ns':float(np.median([x['latency'][name]['p95_ns'] for x in layouts])),
            'median_paired_ratio_to_nn':float(np.median([x['latency'][name]['median_ns']/x['latency']['nn_signed']['median_ns'] for x in layouts]))} for name in names}
        cache={name:{metric:float(np.median([x['cache'][name][metric] for x in layouts]))
                    for metric in ('median_build_ns','median_invalidate_ns')} for name in layouts[0]['cache']}
        diagnostics={metric:base.bootstrap_interval([x['reconstruction'][metric] for x in layouts],samples)
                     for metric in ('mean_relative_error','mean_correlation')}
        costs.append({'spacing':spacing,'storage':storage,'latency':latency,'cache':cache,
            'reconstruction':diagnostics,'median_source_writer_bytes':float(np.median(
                [x['source_writer_build_state']['persistent_bytes'] for x in layouts]))})
    within=all(s['max_persistent_bytes']<=p['budget']['persistent_bytes_cap_per_arm']
               for c in costs for s in c['storage'].values())
    return {'primary':{'condition':p['primary']['condition'],'paired_delta':delta,
        'accuracy_advantage_supported':bool(gate and within),
        'lower_hybrid_accuracy':bool(delta['ci95'][1]<0),
        'minimum_mean_benefit':p['primary']['minimum_mean_benefit']},
        'conditions':conditions,'costs_by_layout':costs,'all_arms_within_budget':within,
        'all_correctness_gates_passed':True,
        'stage3_accuracy_gate_passed':bool(gate and within)}


def verify_registration(commit,p):
    if not re.fullmatch(r'[0-9a-f]{40}',commit):
        raise ValueError('Require the full 40-character public registration commit')
    hashes={}
    for path in FROZEN_PATHS:
        frozen=subprocess.check_output(['git','show',f'{commit}:{path}'],cwd=ROOT)
        current=(ROOT/path).read_bytes()
        if frozen!=current:
            raise RuntimeError(f'Frozen source changed: {path}')
        hashes[path]=base.sha(current)
    if hashes['hme_engine.py']!=p['engine_sha256']:
        raise RuntimeError('Engine pin mismatch')
    return hashes


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--registration-commit',required=True)
    parser.add_argument('--output',required=True)
    args=parser.parse_args()
    p=json.loads((HERE/'protocol.json').read_text())
    hashes=verify_registration(args.registration_commit,p)
    out=Path(args.output).resolve()
    out.mkdir(parents=True,exist_ok=False)
    started=datetime.now(timezone.utc).isoformat()
    config=io.StringIO()
    with redirect_stdout(config):
        np.show_config()
    runs=[]
    try:
        for seed in p['seeds']:
            run=one_seed(seed,p)
            runs.append(run)
            base.write_json(out/f'seed_{seed}.json',run)
            print(f'Completed seed {seed} ({len(runs)}/{len(p["seeds"])})',flush=True)
        analysis=analyze(runs,p)
        result={'protocol_id':p['protocol_id'],'registration_commit':args.registration_commit,
            'registration_url':f'https://github.com/donaldtuttle/HME/commit/{args.registration_commit}',
            'started_at_utc':started,'finished_at_utc':datetime.now(timezone.utc).isoformat(),
            'protocol':p,'source_hashes':hashes,'completed_seeds':[r['seed'] for r in runs],'deviations':[],
            'environment':{'python':platform.python_version(),'numpy':np.__version__,'platform':platform.platform(),
                'cpu_count':os.cpu_count(),'thread_environment':THREAD_ENV,'numpy_build_configuration':config.getvalue()},
            'raw_files':{f'seed_{r["seed"]}.json':base.sha((out/f'seed_{r["seed"]}.json').read_bytes()) for r in runs},
            'analysis':analysis}
        base.write_json(out/'results.json',result,pretty=True)
        print(json.dumps(analysis['primary'],indent=2),flush=True)
    except Exception:
        base.write_json(out/'FAILURE.json',{'registration_commit':args.registration_commit,
            'started_at_utc':started,'completed_seeds':[r['seed'] for r in runs],
            'error':traceback.format_exc()},pretty=True)
        raise
    return 0


if __name__=='__main__':
    raise SystemExit(main())
