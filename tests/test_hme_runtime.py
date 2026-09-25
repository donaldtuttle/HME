"""Numerical restoration checks against the immutable pre-extraction sources."""
from __future__ import annotations

import hashlib
import importlib.util
import itertools
import json
from pathlib import Path
import subprocess
import sys
from types import SimpleNamespace

import numpy as np
import pytest

from hme_engine import HMEEngine, SalienceConfig, _field_hash
from hme_runtime import AgentRuntime, EventConfig, FieldRuntime, HistoryBuffer
from hme_dynamics import AblationConfig, DynamicsConfig, FieldDynamics

ROOT = Path(__file__).resolve().parents[1]


def load_archived(name, relative, expected):
    path = ROOT / 'archive/v2.2' / relative
    assert hashlib.sha256(path.read_bytes()).hexdigest() == expected
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope='module')
def old():
    return load_archived('runtime_reference', 'qosmos_hme_engine.py',
        '1caff9577e8a4bdaa2b0510c79673035081a967a25f15067bfa8ce99ccca6d11')


@pytest.fixture(scope='module')
def old_dynamics():
    pytest.importorskip('PIL')
    manifest = (ROOT / 'archive/v2.2.sha256').read_text().splitlines()
    path = 'integrations/symbolic_field_dynamics.py'
    pin = next(line.split()[0] for line in manifest if line.endswith('/' + path))
    return load_archived('dynamics_reference', path, pin)


FRAME_NAMES = {
    'rho': 'coherence', 'phi_energy': 'field_rms', 'gamma_mag': 'state_change_norm',
    'reflex_conf': 'projection_stability', 'dS': 'entropy_change',
    'c_psi': 'write_salience', 'collapse_triggered': 'event_triggered',
    **{k: k for k in ['step', 'phase', 'entropy', 'drift', 'stable']},
}


@pytest.mark.parametrize('kind', ['field', 'agent'])
@pytest.mark.parametrize('event_mode', ['automatic', 'disabled', 'forced'])
@pytest.mark.parametrize('switches', list(itertools.product((False, True), repeat=3)))
def test_tick_sequences_match_archived_runtime(old, kind, event_mode, switches):
    write, rerank, reject = switches
    common = dict(memory_size=24, encoding_resolution=8, seed=13, run_id='parity')
    enabled = event_mode != 'disabled'
    salience = dict(influence_write_gain=write, influence_retrieval=rerank,
                    retrieval_weight=0.4, rejection_threshold=0.5)
    a = (old.QOSMOSHMEEngine if kind == 'field' else old.QOSMOSCoreHME)(
        **common, collapse_config=old.CollapseConfig(enabled=enabled,
        enable_inscription_rejection=reject, **salience))
    b = (FieldRuntime if kind == 'field' else AgentRuntime)(
        **common, event_config=EventConfig(enabled=enabled),
        salience_config=SalienceConfig(enable_salience_rejection=reject, **salience))
    rng = np.random.default_rng(51)
    id_map = {}
    last_payload = None
    for step in range(8):
        field = rng.normal(size=(12, 12)) + 1j*rng.normal(size=(12, 12))
        payload = rng.normal(size=8)
        last_payload = payload
        override = True if event_mode == 'forced' else None
        kwargs = dict(input_field=field, input_blend=0.6, memory_gain=0.2,
                      record_frame=step % 2 == 0)
        if kind == 'field':
            ra = a.step(**kwargs, memory_payload=payload, memory_position=(12, 12),
                        collapse_override=override, observer_weight=1.2)
            rb = b.step(**kwargs, memory_payload=payload, memory_position=(12, 12),
                        event_override=override, write_weight=1.2)
        else:
            # Identical literal inputs isolate renaming from changes to the hash encoder.
            symbol = ['Ξ', 'Σ◯', 'Π↺'][step % 3]
            kwargs.update(position=(12, 12), payload=payload,
                          neighbor_deltas={'peer': 0.3}, neighbor_weights={'peer': 0.7})
            ra = a.step_core(symbol, **kwargs, delta_psi=0.2,
                             collapse_override=override, observer_weight=1.2)
            rb = b.step_symbol(symbol, **kwargs, state_delta=0.2,
                               event_override=override, write_weight=1.2)
            assert a.stack.get_trace() == b.stack.get_trace()
            assert ra.meta.scalars['psi_meta'] == rb.meta.scalars['activity']
            assert ra.meta.scalars['w_drift_sum'] == rb.meta.scalars['neighbor_transfer_sum']
            assert ra.meta.scalars['CR_stack'] == rb.meta.scalars['history_compression']
        np.testing.assert_array_equal(a.psi_field, b.state_field)
        np.testing.assert_array_equal(a.hme.field, b.hme.field)
        np.testing.assert_array_equal(ra.W_t, rb.projection)
        for old_name, new_name in FRAME_NAMES.items():
            assert getattr(ra.meta, old_name) == getattr(rb.meta, new_name)
        assert len(b.telemetry) == step + 1  # One finalized record, including no-event ticks.
        assert rb.meta.event_triggered == (rb.field_event is not None)
        assert (ra.collapse_event is None) == (rb.field_event is None)
        if rb.field_event is not None:
            for name in ['center', 'radius', 'score', 'threshold', 'pre_hash', 'post_hash']:
                assert getattr(ra.collapse_event, name) == getattr(rb.field_event, name)
            assert rb.field_event.pre_hash != rb.field_event.post_hash
            assert rb.field_event.post_hash == _field_hash(b.state_field)
        aa, ab = ra.memory_artifact, rb.memory_artifact
        id_map[aa.artifact_id] = ab.artifact_id
        assert (aa.gain, aa.payload_hash, aa.pattern_hash) == (ab.gain, ab.payload_hash, ab.pattern_hash)
        assert ab.metadata['write_salience'] == rb.meta.write_salience
    assert len(a.event_log) == len(b.event_log)
    if event_mode != 'disabled':
        assert b.event_log
    else:
        assert not b.event_log
    assert len(a.qmesh.nodes) == len(b.lineage.nodes)
    assert len(a.qmesh.edges) == len(b.lineage.edges)
    np.testing.assert_array_equal(a.frame_history, b.frame_history)
    assert a.frame_steps == b.frame_steps
    ra = a.retrieve_memory((12, 12), query=last_payload)
    rb = b.retrieve_memory((12, 12), query=last_payload)
    assert [id_map[h.artifact_id] for h in ra.hits] == [h.artifact_id for h in rb.hits]
    assert ra.confidence == rb.relevance_score
    assert ra.rejected == rb.rejected
    np.testing.assert_array_equal(ra.decoded_vector, rb.decoded_vector)


def test_automatic_priority_changes_gain_only_when_enabled():
    a = FieldRuntime(event_config=EventConfig(enabled=False))
    b = FieldRuntime(event_config=EventConfig(enabled=False),
                     salience_config=SalienceConfig(influence_write_gain=True))
    for engine in (a, b):
        result = engine.step(np.full((64, 64), 4.0), memory_payload='sample',
                             memory_position=(32, 32))
        assert result.memory_artifact.metadata['write_salience'] > 0
    assert b.hme.records[next(iter(b.hme.records))].gain > a.hme.records[next(iter(a.hme.records))].gain
    assert np.linalg.norm(b.hme.field) > np.linalg.norm(a.hme.field)
    np.testing.assert_array_equal(a.state_field, b.state_field)


def test_threshold_cooldown_and_rearming(old):
    a = old.QOSMOSHMEEngine(memory_size=24, encoding_resolution=8)
    b = FieldRuntime(memory_size=24, encoding_resolution=8)
    expected = [True, False, False, False, True]
    for amplitude, fire in zip([3., 3., 0., 0., 3.], expected):
        ra = a.step(np.full((24, 24), amplitude))
        rb = b.step(np.full((24, 24), amplitude))
        assert ra.meta.collapse_triggered == rb.meta.event_triggered == fire


def test_seeded_replay_and_exports(tmp_path):
    a, b = AgentRuntime(seed=32), AgentRuntime(seed=32)
    for symbol in ['sample', 'update', 'sample']:
        a.step_symbol(symbol, field_rms=3.0, coherence=0.5)
        b.step_symbol(symbol, field_rms=3.0, coherence=0.5)
    assert a.state_summary() == b.state_summary()
    assert [f.to_dict() for f in a.telemetry] == [f.to_dict() for f in b.telemetry]
    frames = [json.loads(line) for line in a.export_telemetry_jsonl(tmp_path/'frames.jsonl').read_text().splitlines()]
    events = [json.loads(line) for line in a.export_events_jsonl(tmp_path/'events.jsonl').read_text().splitlines()]
    assert len(frames) == 3
    assert sum(f['event_triggered'] for f in frames) == len(events)
    assert all(e['operation'] == 'phase_lock' for e in events)
    assert any(e.relation == 'event_to_memory' for e in a.lineage.edges)


@pytest.mark.parametrize('bad', [np.full((4, 4), np.nan), np.full((4, 4), np.inf), np.empty((0, 0))])
def test_bad_state_does_not_poison_runtime(bad):
    runtime = FieldRuntime()
    with pytest.raises(ValueError):
        runtime.set_state_field(bad)
    assert not np.any(runtime.state_field)
    assert not runtime.telemetry


def test_host_and_agent_adapters():
    host = SimpleNamespace(hme=HMEEngine().hme, lineage=HMEEngine().lineage,
                           state_field=np.ones((64, 64)))
    runtime = AgentRuntime()
    runtime.step_symbol('sample')
    report = runtime.attach_to_host(host, merge_existing_hme=True, merge_state_field=True)
    assert report['hme_merged'] and report['lineage_merged'] and report['state_field_merged']
    assert host.hme_overlay is runtime
    assert host.lineage.nodes
    history = HistoryBuffer()
    agent = SimpleNamespace(stack=history, projection_field=np.ones((64, 64)), hme_bundles=[])
    assert runtime.bind_agent(agent)['stack_bound']
    runtime.step_symbol('next')
    assert history.get_trace() == ['next']
    assert runtime.sync_bound_agent(export_projection_field=True)['projection_field_exported']
    assert agent.hme_bundles
    with pytest.raises(AttributeError):
        FieldRuntime().attach_to_host(host)


FEATURES = {
    'symbol_seed': 'glyph_seed', 'initial_noise': 'initial_noise',
    'phase_modulation': 'observer_modulation', 'periodic_drive': 'recursive_drive',
    'diffusion': 'diffusion', 'damping': 'damping',
}


@pytest.mark.parametrize('mode', ['stable', 'legacy'])
@pytest.mark.parametrize('disabled', [None, *FEATURES])
def test_spatial_dynamics_match_archive(old_dynamics, mode, disabled):
    args = dict(grid_size=48, num_steps=36, lattice_size=4, seed=71, integration_mode=mode)
    old_ablation = old_dynamics.AblationConfig(**({FEATURES[disabled]: False} if disabled else {}))
    new_ablation = AblationConfig(**({disabled: False} if disabled else {}))
    a = old_dynamics.SymbolicFieldDynamicsEngine(old_dynamics.SymbolicFieldConfig(**args), ablation=old_ablation)
    b = FieldDynamics(DynamicsConfig(**args), ablation=new_ablation)
    wave = np.sin(np.linspace(0, 3, 48))
    xa, ya, ma = a.evolve(wave)
    xb, yb, mb = b.evolve(wave)
    np.testing.assert_array_equal(xa, xb)
    np.testing.assert_array_equal(ya, yb)
    sa, sb = a.compute_hme_spectrum(ya), b.compute_hme_spectrum(yb)
    np.testing.assert_array_equal(sa, sb)
    np.testing.assert_array_equal(a.build_signature(wave, ya, sa, ma), b.build_signature(wave, yb, sb, mb))
    for fa, fb in zip(ma, mb):
        assert fa.c_psi_proxy == fb.event_score
        assert fa.collapse_proxy_triggered == fb.threshold_exceeded


def test_diffusion_has_measurable_effect():
    config = DynamicsConfig(grid_size=32, num_steps=24)
    a = FieldDynamics(config)
    b = FieldDynamics(config, ablation=AblationConfig(diffusion=False))
    wave = np.cos(np.linspace(0, 9, 32))
    assert np.linalg.norm(a.evolve(wave)[1] - b.evolve(wave)[1]) > 0.01


def test_raster_signature_bridge_matches_archive(old_dynamics, old):
    args = dict(grid_size=96, num_steps=120, lattice_size=6, seed=7312026, signature_size=24)
    a = old_dynamics.SymbolicFieldDynamicsEngine(old_dynamics.SymbolicFieldConfig(**args))
    b = FieldDynamics(DynamicsConfig(**args))
    ra, rb = a.run(glyph='Ξ'), b.run(symbol='Ξ')
    assert ra.trajectory_hash == rb.trajectory_hash
    assert ra.signature_hash == rb.signature_hash
    old_memory, new_memory = old.QOSMOSCoreHME(), FieldRuntime()
    aa = a.commit_to_hme(old_memory, ra, position=(32, 32), recursive_factor=0.15)
    ab = b.commit_to_hme(new_memory, rb, position=(32, 32), strength=0.15)
    assert aa.payload_hash == ab.payload_hash
    assert aa.pattern_hash == ab.pattern_hash
    np.testing.assert_array_equal(old_memory.hme.field, new_memory.hme.field)
    result = new_memory.retrieve_memory((32, 32), query=b.to_hme_payload(rb, dimensions=16))
    assert result.hits[0].artifact_id == ab.artifact_id
    assert ab.metadata['source_trajectory_hash'] == rb.trajectory_hash


def test_numpy_only_import_and_evolution():
    code = '''
import sys
class Block:
    def find_spec(self, fullname, *args):
        if fullname.split('.')[0] in {'core', 'qosmos', 'archive', 'PIL', 'matplotlib'}:
            raise ImportError(fullname)
sys.meta_path.insert(0, Block())
from hme_runtime import AgentRuntime
from hme_dynamics import FieldDynamics, DynamicsConfig
AgentRuntime().step_symbol('plain input')
FieldDynamics(DynamicsConfig(grid_size=32, num_steps=8)).evolve([0, 1, 0, -1])
'''
    subprocess.run([sys.executable, '-c', code], cwd=ROOT, check=True)


def test_visualization_uses_recorded_state(tmp_path):
    matplotlib = pytest.importorskip('matplotlib')
    pytest.importorskip('PIL')
    matplotlib.use('Agg')
    runtime = AgentRuntime(memory_size=24, encoding_resolution=8)
    for symbol in ['one', 'two']:
        runtime.step_symbol(symbol, event_override=True)
    before = runtime.state_summary()
    for mode in ['projection', 'memory', 'state']:
        runtime.render_overlay(field_mode=mode, save_path=tmp_path/f'{mode}.png', close=True)
    runtime.animate(tmp_path/'runtime.gif', fps=2, dpi=30)
    dynamics = FieldDynamics(DynamicsConfig(grid_size=32, num_steps=8))
    result = dynamics.run(symbol='A')
    paths = dynamics.save_diagnostics(result, tmp_path/'dynamics')
    assert paths and all(p.exists() for p in paths.values())
    assert (tmp_path/'runtime.gif').stat().st_size > 100
    assert runtime.state_summary() == before
