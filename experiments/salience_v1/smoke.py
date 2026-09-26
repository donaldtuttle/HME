"""Deterministic contract demonstration only, not a SAL-1 evaluation."""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
import platform
import sys

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
import numpy as np
from experiments.salience_v1.configuration import build_fixed_memory, policy_constants


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        parser.error('output already exists; use a fresh development output file')
    report = {'status': 'DEVELOPMENT_ONLY_NOT_PREREGISTERED',
              'python': platform.python_version(), 'numpy': np.__version__,
              'base_commit': '3e93c66f0a2eadf7ad840d963276cdfead4836c7',
              'byte_cap': 8192, 'arms': {}, 'source_sha256': {},
              'policy': policy_constants()}
    for path in ['hme_engine.py', 'hme_consolidation.py', 'experiments/salience_v1/memory.py',
                 'experiments/salience_v1/smoke.py', 'tests/test_salience_memory.py',
                 'experiments/salience_v1/PROTOCOL_DRAFT.md',
                 'experiments/salience_v1/configuration.py',
                 'experiments/salience_v1/POLICY_CONSTANTS.json',
                 'experiments/salience_v1/radius_selection.py',
                 'tests/test_salience_radius_review.py']:
        report['source_sha256'][path] = hashlib.sha256((ROOT/path).read_bytes()).hexdigest()
    basis = np.eye(8)
    for name in ('field', 'direct_moment', 'rls'):
        memory = build_fixed_memory(name)
        initial = memory.storage_report()
        for i in range(200):
            x = basis[i % 3]
            memory.observe(x, x, eligible=False)
        event = memory.observe(basis[0], -basis[0])
        admitted = memory.storage_report()['admissions']
        repeated_events = [memory.observe(basis[0]+i*1e-6*basis[4], -basis[0])
                           for i in range(1, 6)]
        repeated = memory.storage_report()
        for i in range(1000):
            x = basis[1+i % 2]
            memory.observe(x, x)
        final = memory.storage_report()
        checks = {
            'admitted_surprising_reversal': event['admitted'],
            'six_sightings_one_entry': repeated['occupied'] == 1,
            'no_repeat_admissions': repeated['admissions'] == admitted,
            'buffer_aware_repeat_error_zero': all(e['pre_update_hybrid_nmse'] == 0 for e in repeated_events),
            'exact_corrected_cue_hit': bool(np.array_equal(memory.predict(basis[0]), -basis[0])),
            'off_scope_uses_current_base': bool(np.array_equal(memory.predict(basis[3]), memory.base.predict(basis[3]))),
            'owned_bytes_constant': initial['instance_owned_bytes'] == final['instance_owned_bytes'],
            'array_bytes_constant': initial['retained_array_bytes'] == final['retained_array_bytes'],
            'within_cap': final['instance_owned_bytes'] <= 8192,
        }
        assert all(checks.values()), (name, checks)
        report['arms'][name] = {'storage': final, 'checks': checks}
    from experiments.salience_v1.memory import DirectMoment, SurpriseMemory
    import math
    report['radius_geometry'] = {}
    for sigma in (.01, .05):
        a = .1**2/(4*sigma*sigma)
        report['radius_geometry'][str(sigma)] = 1-math.exp(-a)*sum(a**k/math.factorial(k) for k in range(4))
    report['eviction_ablation'] = {}
    for backend in ('field', 'direct_moment', 'rls'):
        pair = [build_fixed_memory(backend, eviction=mode)
                for mode in ('fifo', 'confirmation_refresh')]
        assert pair[0].storage_report() == pair[1].storage_report()
        report['eviction_ablation'][backend] = {'same_retained_bytes': True,
                                                'storage': pair[0].storage_report()}
    pair = [SurpriseMemory(DirectMoment(2, 1), capacity=2, radius=.1,
                          refresh_on_confirmation=flag) for flag in (False, True)]
    for m in pair:
        m.observe([1,0], [1], gain=0); m.observe([0,1], [2], gain=0)
        for _ in range(100): m.observe([1,0], [1], gain=0)
        m.observe([-1,0], [3], gain=0)
    assert pair[0]._match(np.array([1,0])) is None
    assert np.array_equal(pair[1].predict([1,0]), [1])
    report['eviction_fixture'] = {'fifo_evicts_confirmed_old_entry': True,
                                 'refresh_retains_confirmed_entry': True,
                                 'scope': 'constructed correctness fixture, no efficacy claim'}
    report['limitations'] = ('Exact-cue and off-scope routing checks only. No held-out accuracy, '
                             'semantic truth, gain/decay efficacy sweep, or statistical PASS.')
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open('x') as f:
        json.dump(report, f, indent=2, allow_nan=False); f.write('\n')
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
