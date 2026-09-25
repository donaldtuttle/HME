"""Frozen HME-NN-2A evaluator; publish its registration before evaluation."""
from __future__ import annotations
import os
THREAD_ENV = {name: '1' for name in ('OPENBLAS_NUM_THREADS','OMP_NUM_THREADS',
    'MKL_NUM_THREADS','VECLIB_MAXIMUM_THREADS','NUMEXPR_NUM_THREADS')}
os.environ.update(THREAD_ENV)
import argparse
from contextlib import redirect_stdout
from datetime import datetime, timezone
import hashlib
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

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT))


def load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


base = load_module('hme_nn1_helpers_for_nn2', ROOT/'experiments/nn_baseline_v1/evaluate.py')
variant = load_module('hme_nn2_variant', HERE/'signed_variant.py')
FROZEN_PATHS = ('hme_engine.py', 'experiments/nn_baseline_v1/evaluate.py',
    'experiments/nn_baseline_v1/protocol.json',
    'experiments/sign_ablation_v1/protocol.json', 'experiments/sign_ablation_v1/PROTOCOL.md',
    'experiments/sign_ablation_v1/signed_variant.py', 'experiments/sign_ablation_v1/evaluate.py',
    'tests/test_sign_ablation.py')


def build_arms(vectors, seed, cfg):
    modules = {'hme_abs': sys.modules['hme_engine'], 'hme_signed': variant.signed_module()}
    arms, all_ids = {}, []
    for name, module in modules.items():
        arm = module.HMEEngine(hme_config=module.HMEConfig(memory_size=cfg['memory_size'],
            encoding_resolution=cfg['dimension']), seed=seed)
        ids = [arm.encode_memory(x, tuple(cfg['position']), strength=cfg['write_strength'],
                                 tag=f'item-{i:04d}', t=i).artifact_id for i, x in enumerate(vectors)]
        arms[name] = arm
        all_ids.append(ids)
    if all_ids[0] != all_ids[1] or not np.array_equal(arms['hme_abs'].hme.field, arms['hme_signed'].hme.field):
        raise RuntimeError('The sign variant changed write state or artifact identity')
    arms['nn_cosine'] = base.ExactNN(arms['hme_abs'], False)
    return arms, all_ids[0]


def search(name, arm, q, mode, k, position, lookup):
    if name == 'nn_cosine':
        return arm.search(q, mode, k)
    return base.hme_search(arm, q, mode, k, position, lookup)


def one_seed(seed, protocol):
    cfg = protocol['dataset']
    n, d = cfg['items_per_seed'], cfg['dimension']
    position = tuple(cfg['position'])
    vectors = np.random.default_rng(seed).standard_normal((n,d))
    arms, ids = build_arms(vectors, seed, cfg)
    lookup = {identifier:i for i, identifier in enumerate(ids)}
    storage = {name:base.persistent_size(arm) for name,arm in arms.items()}
    if any(s['persistent_bytes'] > protocol['budget']['persistent_bytes_cap_per_arm'] for s in storage.values()):
        raise RuntimeError(f'Persistent storage cap exceeded at seed {seed}')
    hashes = {'source_vectors':base.array_hash(vectors),
              'processed_vectors':base.array_hash(arms['nn_cosine'].vectors)}
    cells, primary_queries = [], None
    for noise_index,sigma in enumerate(cfg['noise_sigmas']):
        rng = np.random.default_rng(np.random.SeedSequence([seed,1,noise_index]))
        queries = vectors + sigma*rng.standard_normal(vectors.shape)
        hashes[f'queries_sigma_{sigma:g}'] = base.array_hash(queries)
        if sigma == protocol['primary']['condition']['noise_sigma']:
            primary_queries = queries
        for mode in cfg['query_modes']:
            observations = {}
            for name,arm in arms.items():
                ranks, predictions = [], []
                for truth,q in enumerate(queries):
                    order,_ = search(name,arm,q,mode,n,position,lookup)
                    where = np.flatnonzero(order == truth)
                    ranks.append(int(where[0])+1 if where.size else 0)
                    predictions.append(int(order[0]) if order.size else -1)
                observations[name] = {**base.ranked_metrics(ranks), 'target_ranks':ranks,
                                      'top1_indices':predictions}
            cells.append({'query_mode':mode, 'noise_sigma':sigma, 'arms':observations})
    unknown = np.random.default_rng(np.random.SeedSequence([seed,2])).standard_normal(
        (cfg['unmatched_queries_per_seed'],d))
    hashes['unmatched_queries'] = base.array_hash(unknown)
    unmatched = {}
    for mode in cfg['query_modes']:
        unmatched[mode] = {}
        for name,arm in arms.items():
            observed = [search(name,arm,q,mode,1,position,lookup) for q in unknown]
            unmatched[mode][name] = {'accepted':sum(bool(len(order)) for order,_ in observed),
                'total':len(unknown), 'top_scores':[float(s[0]) if len(s) else None for _,s in observed]}
    timing = protocol['latency']
    samples = {name:[] for name in arms}
    names = list(arms)
    assert primary_queries is not None
    for name in names:
        for q in primary_queries[:timing['warmup_queries_per_arm']]:
            search(name,arms[name],q,'native',timing['top_k'],position,lookup)
    for repetition in range(timing['repetitions']):
        for index,q in enumerate(primary_queries[:timing['queries_per_seed']]):
            shift = (index+repetition)%len(names)
            for name in names[shift:]+names[:shift]:
                start = time.perf_counter_ns()
                search(name,arms[name],q,'native',timing['top_k'],position,lookup)
                samples[name].append(time.perf_counter_ns()-start)
    latency = {name:{'nanoseconds':values, 'median_ns':float(np.median(values)),
        'p95_ns':float(np.quantile(values,.95))} for name,values in samples.items()}
    return {'seed':seed, 'data_hashes':hashes, 'storage':storage, 'cells':cells,
            'unmatched_queries':unmatched, 'latency':latency}


def interval(values, indices):
    values = np.asarray(values,dtype=float)
    means = values[indices].mean(axis=1)
    return {'mean':float(values.mean()), 'ci90':np.quantile(means,[.05,.95]).tolist(),
            'ci95':np.quantile(means,[.025,.975]).tolist(), 'values_by_seed':values.tolist()}


def decisions(delta, margin):
    lo,hi = delta['ci90']
    return {'equivalence_within_margin': bool(lo > -margin and hi < margin),
            'noninferiority_within_margin': bool(lo > -margin),
            'deficit_exceeds_margin': bool(hi < -margin),
            'lower_mean_accuracy_ci95': bool(delta['ci95'][1] < 0),
            'higher_mean_accuracy_ci95': bool(delta['ci95'][0] > 0)}


def analyze(runs, protocol):
    rng = np.random.default_rng(protocol['statistics']['bootstrap_seed'])
    indices = rng.integers(0,len(runs),size=(protocol['statistics']['bootstrap_resamples'],len(runs)))
    summaries = []
    for sigma in protocol['dataset']['noise_sigmas']:
        for mode in protocol['dataset']['query_modes']:
            cells = [next(c for c in r['cells'] if c['query_mode']==mode and c['noise_sigma']==sigma) for r in runs]
            arms = {name:{metric:interval([c['arms'][name][metric] for c in cells],indices)
                         for metric in protocol['secondary']['metrics']} for name in protocol['arms']}
            contrasts = {f'{left}_minus_{right}':{metric:interval(
                [c['arms'][left][metric]-c['arms'][right][metric] for c in cells],indices)
                for metric in protocol['secondary']['metrics']} for left,right in protocol['secondary']['contrasts']}
            summaries.append({'query_mode':mode, 'noise_sigma':sigma, 'arms':arms, 'contrasts':contrasts})
    cfg = protocol['primary']
    primary = next(c for c in summaries if c['query_mode']==cfg['condition']['query_mode'] and c['noise_sigma']==cfg['condition']['noise_sigma'])
    delta = primary['contrasts']['hme_signed_minus_nn_cosine']['top1_accuracy']
    storage = {name:{'median_persistent_bytes':float(np.median([r['storage'][name]['persistent_bytes'] for r in runs])),
        'max_persistent_bytes':max(r['storage'][name]['persistent_bytes'] for r in runs),
        'numeric_array_bytes':[r['storage'][name]['numeric_array_bytes'] for r in runs]} for name in protocol['arms']}
    within = all(s['max_persistent_bytes'] <= protocol['budget']['persistent_bytes_cap_per_arm'] for s in storage.values())
    flags = decisions(delta,cfg['equivalence_margin'])
    flags['equivalence_within_margin'] &= within
    latency = {name:{'median_of_seed_medians_ns':float(np.median([r['latency'][name]['median_ns'] for r in runs])),
        'median_of_seed_p95_ns':float(np.median([r['latency'][name]['p95_ns'] for r in runs])),
        'median_paired_ratio_to_nn':float(np.median([r['latency'][name]['median_ns']/r['latency']['nn_cosine']['median_ns'] for r in runs]))}
        for name in protocol['arms']}
    return {'primary':{'condition':cfg['condition'], 'equivalence_margin':cfg['equivalence_margin'],
                       'paired_delta':delta, 'decisions':flags}, 'conditions':summaries,
            'storage':storage, 'latency':latency, 'all_arms_within_budget':within}


def verify_registration(commit, protocol):
    if not re.fullmatch(r'[0-9a-f]{40}',commit):
        raise ValueError('Pass the full 40-character public registration commit SHA')
    hashes = {}
    for path in FROZEN_PATHS:
        frozen = subprocess.check_output(['git','show',f'{commit}:{path}'],cwd=ROOT)
        current = (ROOT/path).read_bytes()
        if frozen != current:
            raise RuntimeError(f'Frozen source changed: {path}')
        hashes[path] = base.sha(current)
    if hashes['hme_engine.py'] != protocol['engine_sha256']:
        raise RuntimeError('Engine differs from registered pin')
    hashes['generated_signed_engine'] = base.sha(variant.transformed_source().encode('utf-8'))
    return hashes


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--registration-commit',required=True)
    parser.add_argument('--output',required=True)
    args = parser.parse_args()
    protocol = json.loads((HERE/'protocol.json').read_text())
    hashes = verify_registration(args.registration_commit,protocol)
    out = Path(args.output).resolve()
    out.mkdir(parents=True,exist_ok=False)
    started = datetime.now(timezone.utc).isoformat()
    config = io.StringIO()
    with redirect_stdout(config):
        np.show_config()
    runs = []
    try:
        for seed in protocol['seeds']:
            run = one_seed(seed,protocol)
            runs.append(run)
            base.write_json(out/f'seed_{seed}.json',run)
            print(f'Completed seed {seed} ({len(runs)}/{len(protocol["seeds"])})',flush=True)
        analysis = analyze(runs,protocol)
        result = {'protocol_id':protocol['protocol_id'], 'registration_commit':args.registration_commit,
            'registration_url':f'https://github.com/donaldtuttle/HME/commit/{args.registration_commit}',
            'started_at_utc':started, 'finished_at_utc':datetime.now(timezone.utc).isoformat(),
            'source_hashes':hashes, 'protocol':protocol, 'deviations':[],
            'environment':{'python':platform.python_version(), 'numpy':np.__version__, 'platform':platform.platform(),
                'cpu_count':os.cpu_count(), 'thread_environment':THREAD_ENV, 'numpy_build_configuration':config.getvalue()},
            'completed_seeds':[r['seed'] for r in runs],
            'raw_files':{f'seed_{r["seed"]}.json':base.sha((out/f'seed_{r["seed"]}.json').read_bytes()) for r in runs},
            'analysis':analysis}
        base.write_json(out/'results.json',result,pretty=True)
        print(json.dumps(analysis['primary'],indent=2),flush=True)
    except Exception:
        base.write_json(out/'FAILURE.json',{'registration_commit':args.registration_commit,
            'started_at_utc':started, 'completed_seeds':[r['seed'] for r in runs],
            'error':traceback.format_exc()},pretty=True)
        raise
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
