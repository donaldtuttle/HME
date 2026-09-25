"""Frozen HME-NN-1 evaluator. Run only after the registration commit is public."""
from __future__ import annotations

import os
# Set before importing NumPy so the registered online latency uses one BLAS thread.
THREAD_ENV = {name: '1' for name in ('OPENBLAS_NUM_THREADS', 'OMP_NUM_THREADS',
    'MKL_NUM_THREADS', 'VECLIB_MAXIMUM_THREADS', 'NUMEXPR_NUM_THREADS')}
os.environ.update(THREAD_ENV)

import argparse
import copy
from dataclasses import fields, is_dataclass
from datetime import datetime, timezone
import hashlib
import io
import json
from pathlib import Path
import platform
import re
import subprocess
import sys
import time
import traceback
from contextlib import redirect_stdout

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from hme_engine import HMEConfig, HMEEngine

HERE = Path(__file__).resolve().parent
FROZEN_PATHS = ('hme_engine.py', 'experiments/nn_baseline_v1/protocol.json',
    'experiments/nn_baseline_v1/PROTOCOL.md', 'experiments/nn_baseline_v1/evaluate.py',
    'tests/test_nn_baseline.py')
EPS = 1e-12


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def array_hash(array: np.ndarray) -> str:
    a = np.ascontiguousarray(array)
    return sha(str(a.dtype).encode() + b'|' + str(a.shape).encode() + b'|' + a.tobytes())


def query_input(query: np.ndarray, mode: str) -> np.ndarray:
    q = np.asarray(query, dtype=np.complex128)
    if mode == 'symmetric':
        return q * np.hanning(q.size)
    if mode != 'native':
        raise ValueError(mode)
    return q


class ExactNN:
    """Independent exact search; retains the same item/provenance information."""
    def __init__(self, engine: HMEEngine, absolute: bool):
        self.vectors = np.stack(list(engine.hme._payloads.values())).copy()
        self.norms = np.linalg.norm(self.vectors, axis=1)
        self.records = copy.deepcopy(list(engine.hme.records.values()))
        self.lineage = copy.deepcopy(engine.lineage)
        self.absolute = absolute

    def search(self, query: np.ndarray, mode: str, top_k: int):
        q = query_input(query, mode).copy()
        qnorm = float(np.linalg.norm(q))
        if qnorm > EPS:
            q /= qnorm
        denominator = self.norms * float(np.linalg.norm(q))
        dots = self.vectors.conj() @ q
        numerator = np.abs(dots) if self.absolute else dots.real
        scores = np.divide(numerator, denominator, out=np.zeros_like(denominator),
                           where=denominator > EPS)
        order = np.argsort(-scores, kind='stable')[:top_k]
        return order, scores[order]


def hme_search(engine, query, mode, top_k, position, id_to_index):
    result = engine.retrieve_memory(position, query=query_input(query, mode), top_k=top_k)
    return (np.asarray([id_to_index[h.artifact_id] for h in result.hits], dtype=np.int64),
            np.asarray([h.final_score for h in result.hits]))


def persistent_size(value) -> dict:
    """Owned reachable Python objects and arrays; excludes interpreter/workspace."""
    seen = set()
    numeric_bytes = 0
    def walk(obj):
        nonlocal numeric_bytes
        identity = id(obj)
        if identity in seen:
            return 0
        seen.add(identity)
        size = sys.getsizeof(obj)
        if isinstance(obj, np.ndarray):
            if obj.base is None:
                numeric_bytes += obj.nbytes
            else:
                size += walk(obj.base)
            return size
        if isinstance(obj, dict):
            return size + sum(walk(k) + walk(v) for k, v in obj.items())
        if isinstance(obj, (tuple, list, set, frozenset)):
            return size + sum(walk(v) for v in obj)
        if is_dataclass(obj) and not isinstance(obj, type):
            return size + sum(walk(getattr(obj, f.name)) for f in fields(obj))
        if hasattr(obj, '__dict__') and not isinstance(obj, type):
            return size + walk(vars(obj))
        return size
    total = walk(value)
    return {'persistent_bytes': total, 'numeric_array_bytes': numeric_bytes,
            'unique_python_objects': len(seen)}


def ranked_metrics(ranks):
    ranks = np.asarray(ranks)
    positive = ranks > 0
    rr = np.divide(1., ranks, out=np.zeros(ranks.shape, dtype=float), where=positive)
    return {'top1_accuracy': float(np.mean(ranks == 1)),
            'top5_accuracy': float(np.mean(positive & (ranks <= 5))),
            'mean_reciprocal_rank': float(np.mean(rr))}


def bootstrap_interval(values, samples):
    x = np.asarray(values, dtype=float)
    means = x[samples].mean(axis=1)
    return {'mean': float(x.mean()), 'ci95': np.quantile(means, [0.025, 0.975]).tolist(),
            'values_by_seed': x.tolist()}


def decision(delta, minimum):
    if delta['ci95'][0] > minimum:
        return 'registered_practical_advantage_supported'
    if delta['ci95'][1] < 0:
        return 'hme_lower_accuracy_in_primary_condition'
    return 'registered_practical_advantage_not_established'


def build_arms(vectors, seed, cfg):
    position = tuple(cfg['position'])
    engine = HMEEngine(hme_config=HMEConfig(memory_size=cfg['memory_size'],
        encoding_resolution=cfg['dimension']), seed=seed)
    ids = []
    for i, vector in enumerate(vectors):
        artifact = engine.encode_memory(vector, position, strength=cfg['write_strength'],
                                         tag=f'item-{i:04d}', t=i)
        ids.append(artifact.artifact_id)
    erased = copy.deepcopy(engine)
    erased.hme.field.fill(0)
    arms = {'hme': engine, 'nn_cosine': ExactNN(engine, False),
            'nn_absolute': ExactNN(engine, True), 'hme_field_erased': erased}
    return arms, ids


def search(name, arm, query, mode, top_k, position, lookup):
    if name.startswith('nn_'):
        return arm.search(query, mode, top_k)
    return hme_search(arm, query, mode, top_k, position, lookup)


def one_seed(seed, protocol):
    cfg = protocol['dataset']
    n, d = cfg['items_per_seed'], cfg['dimension']
    position = tuple(cfg['position'])
    vectors = np.random.default_rng(seed).standard_normal((n, d))
    arms, ids = build_arms(vectors, seed, cfg)
    lookup = {identifier: i for i, identifier in enumerate(ids)}
    storage = {name: persistent_size(arm) for name, arm in arms.items()}
    for name, measured in storage.items():
        if measured['persistent_bytes'] > protocol['budget']['persistent_bytes_cap_per_arm']:
            raise RuntimeError(f'{name} exceeds the registered storage cap at seed {seed}')
    data_hashes = {'source_vectors': array_hash(vectors),
                   'processed_vectors': array_hash(arms['nn_cosine'].vectors)}
    cells = []
    primary_queries = None
    for noise_index, sigma in enumerate(cfg['noise_sigmas']):
        rng = np.random.default_rng(np.random.SeedSequence([seed, 1, noise_index]))
        queries = vectors + sigma * rng.standard_normal(vectors.shape)
        data_hashes[f'queries_sigma_{sigma:g}'] = array_hash(queries)
        if sigma == protocol['primary']['condition']['noise_sigma']:
            primary_queries = queries
        for mode in cfg['query_modes']:
            results = {}
            for name, arm in arms.items():
                ranks, predictions = [], []
                for truth, query in enumerate(queries):
                    order, _ = search(name, arm, query, mode, n, position, lookup)
                    at = np.flatnonzero(order == truth)
                    ranks.append(int(at[0])+1 if at.size else 0)
                    predictions.append(int(order[0]) if order.size else -1)
                results[name] = {**ranked_metrics(ranks), 'target_ranks': ranks,
                                 'top1_indices': predictions}
            # At a common position with salience off, erased-field HME must have
            # exactly the absolute-NN ordering. This checks the implemented control.
            if results['nn_absolute']['target_ranks'] != results['hme_field_erased']['target_ranks']:
                raise RuntimeError('Absolute NN and field-erased HME disagree')
            cells.append({'query_mode': mode, 'noise_sigma': sigma, 'arms': results})

    unknown = np.random.default_rng(np.random.SeedSequence([seed, 2])).standard_normal(
        (cfg['unmatched_queries_per_seed'], d))
    data_hashes['unmatched_queries'] = array_hash(unknown)
    unmatched = {}
    for mode in cfg['query_modes']:
        unmatched[mode] = {}
        for name, arm in arms.items():
            observations = [search(name, arm, q, mode, 1, position, lookup) for q in unknown]
            accepted = sum(bool(len(order)) for order, _ in observations)
            unmatched[mode][name] = {'accepted': accepted, 'total': len(unknown),
                'false_acceptance_fraction': accepted/len(unknown),
                'top_scores': [float(scores[0]) if len(scores) else None for _, scores in observations]}

    field_only = copy.deepcopy(arms['hme'])
    field_only.hme.records.clear()
    field_only.hme._payloads.clear()
    field_only.hme._patterns.clear()
    result = field_only.retrieve_memory(position, query=vectors[0], top_k=1)
    structural = {'hit_count': len(result.hits), 'outcome': result.outcome,
                  'decoded_surface_norm': float(np.linalg.norm(result.decoded_surface))}

    timing = protocol['latency']
    timings = {name: [] for name in arms}
    names = list(arms)
    assert primary_queries is not None
    for name in names:
        for q in primary_queries[:timing['warmup_queries_per_arm']]:
            search(name, arms[name], q, 'native', timing['top_k'], position, lookup)
    for repetition in range(timing['repetitions']):
        for index, q in enumerate(primary_queries[:timing['queries_per_seed']]):
            shift = (index + repetition) % len(names)
            for name in names[shift:] + names[:shift]:
                start = time.perf_counter_ns()
                search(name, arms[name], q, 'native', timing['top_k'], position, lookup)
                timings[name].append(time.perf_counter_ns()-start)
    latency = {name: {'nanoseconds': values, 'median_ns': float(np.median(values)),
                      'p95_ns': float(np.quantile(values, .95))} for name, values in timings.items()}
    return {'seed': seed, 'data_hashes': data_hashes, 'storage': storage, 'cells': cells,
            'unmatched_queries': unmatched, 'field_only_check': structural, 'latency': latency}


def analyze(runs, protocol):
    samples = np.random.default_rng(protocol['statistics']['bootstrap_seed']).integers(
        0, len(runs), size=(protocol['statistics']['bootstrap_resamples'], len(runs)))
    summaries = []
    for sigma in protocol['dataset']['noise_sigmas']:
        for mode in protocol['dataset']['query_modes']:
            cells = [next(c for c in run['cells'] if c['noise_sigma'] == sigma and
                           c['query_mode'] == mode) for run in runs]
            arms = {}
            contrasts = {}
            for name in protocol['arms']:
                arms[name] = {metric: bootstrap_interval([c['arms'][name][metric] for c in cells], samples)
                              for metric in protocol['secondary']['metrics']}
            for name in protocol['arms'][1:]:
                contrasts[name] = {metric: bootstrap_interval([
                    c['arms']['hme'][metric]-c['arms'][name][metric] for c in cells], samples)
                    for metric in protocol['secondary']['metrics']}
            summaries.append({'query_mode': mode, 'noise_sigma': sigma,
                              'arms': arms, 'hme_minus': contrasts})
    primary_cfg = protocol['primary']
    primary = next(c for c in summaries if c['query_mode'] == primary_cfg['condition']['query_mode']
                   and c['noise_sigma'] == primary_cfg['condition']['noise_sigma'])
    delta = primary['hme_minus']['nn_cosine']['top1_accuracy']
    storage = {name: {'median_persistent_bytes': float(np.median([r['storage'][name]['persistent_bytes'] for r in runs])),
                      'max_persistent_bytes': max(r['storage'][name]['persistent_bytes'] for r in runs),
                      'numeric_array_bytes': [r['storage'][name]['numeric_array_bytes'] for r in runs]}
               for name in protocol['arms']}
    latency = {name: {'median_of_seed_medians_ns': float(np.median([r['latency'][name]['median_ns'] for r in runs])),
                      'median_of_seed_p95_ns': float(np.median([r['latency'][name]['p95_ns'] for r in runs]))}
               for name in protocol['arms']}
    ratios = [r['latency']['hme']['median_ns']/r['latency']['nn_cosine']['median_ns'] for r in runs]
    return {'primary': {'condition': primary_cfg['condition'], 'minimum_mean_benefit': primary_cfg['minimum_mean_benefit'],
                        'hme': primary['arms']['hme']['top1_accuracy'],
                        'nn_cosine': primary['arms']['nn_cosine']['top1_accuracy'],
                        'paired_delta': delta, 'decision': decision(delta, primary_cfg['minimum_mean_benefit'])},
            'conditions': summaries, 'storage': storage, 'latency': latency,
            'hme_over_nn_cosine_latency_ratio': {'by_seed': ratios, 'median': float(np.median(ratios))},
            'all_arms_within_budget': all(s['max_persistent_bytes'] <= protocol['budget']['persistent_bytes_cap_per_arm'] for s in storage.values())}


def verify_registration(commit, protocol):
    if not re.fullmatch(r'[0-9a-f]{40}', commit):
        raise ValueError('Pass the full 40-character public registration commit SHA')
    hashes = {}
    for path in FROZEN_PATHS:
        frozen = subprocess.check_output(['git', 'show', f'{commit}:{path}'], cwd=ROOT)
        current = (ROOT/path).read_bytes()
        if current != frozen:
            raise RuntimeError(f'Frozen source changed: {path}')
        hashes[path] = sha(current)
    if hashes['hme_engine.py'] != protocol['engine_sha256']:
        raise RuntimeError('Engine pin differs from registration')
    return hashes


def write_json(path, value, pretty=False):
    path.write_text(json.dumps(value, indent=2 if pretty else None,
        separators=None if pretty else (',', ':'), allow_nan=False)+'\n')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--registration-commit', required=True)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    protocol = json.loads((HERE/'protocol.json').read_text())
    hashes = verify_registration(args.registration_commit, protocol)
    out = Path(args.output).resolve()
    out.mkdir(parents=True, exist_ok=False)
    started = datetime.now(timezone.utc).isoformat()
    config = io.StringIO()
    with redirect_stdout(config):
        np.show_config()
    environment = {'python': platform.python_version(), 'numpy': np.__version__,
        'platform': platform.platform(), 'machine': platform.machine(), 'cpu_count': os.cpu_count(),
        'thread_environment': THREAD_ENV, 'numpy_build_configuration': config.getvalue()}
    runs = []
    try:
        for seed in protocol['seeds']:
            run = one_seed(seed, protocol)
            runs.append(run)
            write_json(out/f'seed_{seed}.json', run)
            print(f'Completed seed {seed} ({len(runs)}/{len(protocol["seeds"])})', flush=True)
        analysis = analyze(runs, protocol)
        result = {'protocol_id': protocol['protocol_id'], 'registration_commit': args.registration_commit,
            'registration_url': f'https://github.com/donaldtuttle/HME/commit/{args.registration_commit}',
            'started_at_utc': started, 'finished_at_utc': datetime.now(timezone.utc).isoformat(),
            'source_hashes': hashes, 'environment': environment, 'protocol': protocol,
            'completed_seeds': [r['seed'] for r in runs], 'deviations': [],
            'raw_files': {f'seed_{r["seed"]}.json': sha((out/f'seed_{r["seed"]}.json').read_bytes()) for r in runs},
            'analysis': analysis}
        write_json(out/'results.json', result, pretty=True)
        print(json.dumps(analysis['primary'], indent=2), flush=True)
    except Exception:
        write_json(out/'FAILURE.json', {'registration_commit': args.registration_commit,
            'started_at_utc': started, 'completed_seeds': [r['seed'] for r in runs],
            'error': traceback.format_exc()}, pretty=True)
        raise
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
