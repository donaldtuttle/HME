"""Collect current-release evidence without attributing archived results to it.

The retrieval experiment reuses the established audit on five preselected seeds.
Runtime traces are functional observations, not comparative efficacy evidence.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import importlib.util
import json
from pathlib import Path
import platform
import subprocess
import sys
import tempfile
import xml.etree.ElementTree as ET

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from hme_engine import ENGINE_ID as CORE_ID, SalienceConfig, _field_hash
from hme_runtime import AgentRuntime, FieldRuntime
from hme_dynamics import DynamicsConfig, FieldDynamics

# Fixed before running the experiment. First seed reproduces the published audit.
SEEDS = (7312026, 7312027, 7312028, 7312029, 7312030)
NOISE = (0.0, 0.05, 0.1, 0.25, 0.5, 1.0)


def file_hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run_tests(cwd: Path, report_path: Path) -> dict:
    command = [sys.executable, '-m', 'pytest', '-q', f'--junitxml={report_path}']
    completed = subprocess.run(command, cwd=cwd, capture_output=True, text=True)
    if completed.returncode:
        raise RuntimeError(completed.stdout + completed.stderr)
    suite = ET.parse(report_path).getroot().find('testsuite')
    counts = {key: int(suite.attrib[key]) for key in ('tests', 'failures', 'errors', 'skipped')}
    if counts['failures'] or counts['errors'] or counts['skipped']:
        raise RuntimeError(f'Incomplete evidence suite: {counts}')
    return {'command': 'python -m pytest -q', 'cwd': str(cwd.relative_to(ROOT)) or '.', **counts}


def runtime_trace(seed: int, kind: str, weight_writes: bool) -> dict:
    cls = FieldRuntime if kind == 'field' else AgentRuntime
    engine = cls(memory_size=24, encoding_resolution=8, seed=seed,
                 salience_config=SalienceConfig(influence_write_gain=weight_writes))
    rng = np.random.default_rng(seed)
    traces = []
    payloads, artifact_ids = [], []
    for step in range(16):
        # Identical input streams across controllers/settings; no semantic claim.
        state = rng.normal(size=(24, 24)) + 1j * rng.normal(size=(24, 24))
        payload = rng.normal(size=8)
        if kind == 'field':
            result = engine.step(state, memory_payload=payload, memory_position=(12, 12))
        else:
            result = engine.step_symbol(f'item-{step}', input_field=state,
                                         position=(12, 12), payload=payload)
        payloads.append(payload)
        artifact_ids.append(result.memory_artifact.artifact_id)
        event = result.field_event
        traces.append({
            'step': step,
            'write_salience': result.meta.write_salience,
            'artifact_salience': result.memory_artifact.metadata['write_salience'],
            'gain': result.memory_artifact.gain,
            'event_triggered': result.meta.event_triggered,
            'event_pre_hash': event.pre_hash if event else None,
            'event_post_hash': event.post_hash if event else None,
            'state_hash': _field_hash(engine.state_field),
            'memory_hash': _field_hash(engine.hme.field),
            'artifact_id': result.memory_artifact.artifact_id,
        })
        assert traces[-1]['write_salience'] == traces[-1]['artifact_salience']
        assert result.meta.event_triggered == (event is not None)
        if event:
            assert event.post_hash == traces[-1]['state_hash']
    hits = [engine.retrieve_memory((12, 12), query=p, top_k=1).hits for p in payloads]
    correct = sum(bool(h) and h[0].artifact_id == expected for h, expected in zip(hits, artifact_ids))
    return {
        'controller': cls.__name__, 'seed': seed, 'influence_write_gain': weight_writes,
        'configuration': {'memory_size': 24, 'encoding_resolution': 8, 'writes': 16,
                          'memory_gain': 0.1, 'position': [12, 12], 'events': 'automatic defaults'},
        'telemetry_count': len(engine.telemetry), 'event_count': len(engine.event_log),
        'total_stored_gain': sum(a.gain for a in engine.hme.records.values()),
        'gain_ceiling_writes': sum(bool(np.isclose(a.gain, 0.1 * engine.salience_config.write_gain_ceiling))
                                  for a in engine.hme.records.values()),
        'memory_field_energy': float(np.linalg.norm(engine.hme.field)**2),
        'exact_query_top1': {'correct': int(correct), 'total': len(payloads)},
        'state': engine.state_summary(), 'ticks': traces,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', default='outputs/current_release_v3_1.json')
    args = parser.parse_args()
    output = Path(args.output).resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    (ROOT/'outputs').mkdir(parents=True, exist_ok=True)
    provenance = json.loads((ROOT/'SOURCE_PROVENANCE.json').read_text())
    commit = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip()
    source_paths = ['hme_engine.py', 'hme_runtime.py', 'hme_dynamics.py']
    hashes = {p: file_hash(ROOT/p) for p in source_paths}
    matches = {p: hashes[p] == hashlib.sha256(subprocess.check_output(
        ['git', 'show', f'{commit}:{p}'], cwd=ROOT)).hexdigest() for p in source_paths}
    if not all(matches.values()):
        raise RuntimeError('Commit the engine modules before collecting release evidence')
    for key in ('active_engine', 'active_runtime', 'active_dynamics'):
        entry = provenance[key]
        if hashes[entry['path']] != entry['sha256']:
            raise RuntimeError(f'Stale source pin: {key}')

    with tempfile.TemporaryDirectory(prefix='release-evidence-', dir=ROOT/'outputs') as tmp:
        current_tests = run_tests(ROOT, Path(tmp)/'current.xml')
        historical_tests = run_tests(ROOT/'archive/v2.2', Path(tmp)/'historical.xml')
    print(f"Active tests: {current_tests['tests']}; archived tests: {historical_tests['tests']}", flush=True)

    path = ROOT/'tests/hme_independent_audit.py'
    spec = importlib.util.spec_from_file_location('release_audit', path)
    audit = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(audit)
    reports = []
    for seed in SEEDS:
        config = audit.build_parser().parse_args(['--engine', str(ROOT/'hme_engine.py'), '--seed', str(seed)])
        report = audit.run_audit(config)
        reports.append(report)
        print(f"Retrieval seed {seed}: {[r['correct'] for r in report['numeric_top1_retrieval']]}", flush=True)
    summary = []
    for index, sigma in enumerate(NOISE):
        rows = [r['numeric_top1_retrieval'][index] for r in reports]
        assert all(r['noise_sigma'] == sigma for r in rows)
        accuracies = np.asarray([r['accuracy'] for r in rows])
        # Student-t interval over independent corpus/noise seeds, df=4. Descriptive
        # small-sample estimate; querying one memory field does not create 128 seeds.
        half = 2.7764451051977987 * float(np.std(accuracies, ddof=1)) / np.sqrt(len(SEEDS))
        mean = float(np.mean(accuracies))
        summary.append({'noise_sigma': sigma, 'correct_by_seed': [r['correct'] for r in rows],
                        'total_per_seed': 128, 'pooled_correct': sum(r['correct'] for r in rows),
                        'pooled_total': sum(r['total'] for r in rows), 'mean_accuracy': mean,
                        'mean_accuracy_95pct_t_interval': [max(0., mean-half), min(1., mean+half)]})

    traces = [runtime_trace(seed, kind, weighted) for seed in SEEDS
              for kind in ('field', 'agent') for weighted in (False, True)]
    simulation = FieldDynamics(DynamicsConfig(grid_size=48, num_steps=36, seed=SEEDS[0]))
    _, trajectory, metrics = simulation.evolve([0., 1., 0., -1.])
    report = {
        'report_schema': 'hme-current-release-evidence-v1',
        'generated_at_utc': datetime.now(timezone.utc).isoformat(),
        'release': {'package_version': provenance['version'], 'source_commit': commit,
                    'engine_modules_match_commit': matches, 'source_hashes': hashes,
                    'memory_component_id': CORE_ID,
                    'component_id_note': 'The unchanged memory component retains hme-3.0.0; the package and optional runtimes are 3.1.0.'},
        'harness_hashes': {str(p.relative_to(ROOT)): file_hash(p) for p in
            [Path(__file__).resolve(), path, ROOT/'tests/test_hme_runtime.py', ROOT/'tests/test_hme_standalone.py']},
        'environment': {'python': platform.python_version(), 'numpy': np.__version__, 'platform': platform.platform()},
        'current_engine_tests': current_tests,
        'historical_engine_tests': {**historical_tests, 'engine': 'archived v2.2',
                                    'scope': 'Preservation check; not v3.1 performance evidence'},
        'retrieval': {'target': 'v3.1 package memory core (hme_engine.py)', 'seeds': list(SEEDS),
                      'configuration': reports[0]['configuration'],
                      'interval_method': 'Two-sided Student-t interval on five per-seed accuracies; df=4; clipped to [0,1]. Approximate with five seeds; all-correct samples yield zero width without proving population perfection.',
                      'summary': summary, 'raw_runs': reports},
        'runtime_observations': {'scope': 'Functional traces of current controllers, 16 writes per run. Gains and field energy differ between settings; these are not a budget-matched efficacy comparison. Inspect gain_ceiling_writes: saturation tests wiring but cannot establish selective prioritization.',
                                 'runs': traces},
        'dynamics_observation': {'shape': list(trajectory.shape), 'trajectory_hash': _field_hash(trajectory),
                                 'final_metrics': metrics[-1].to_dict()},
        'limits': ['Fresh execution is not evidence of improvement over v2.2, nearest neighbors or HRR.',
                   'Retrieval experiment uses synthetic Gaussian vectors, one load (128 items), one position and five seeds.',
                   'Absolute similarity and retained-vector ranking remain; this is not field-only semantic decoding.',
                   'No ECE/Brier result is reported because scores remain uncalibrated and no probability calibrator was fitted.',
                   'Current test suite includes comparisons with archived code; only the separately labelled historical suite tests the old engine alone.'],
    }
    output.write_text(json.dumps(report, indent=2, allow_nan=False)+'\n')
    print(f'Saved {output}', flush=True)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
