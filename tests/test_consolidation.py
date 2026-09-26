"""Step-0 correctness fixtures, not SAL-1/HOLO-1/REC-3 evaluation seeds."""
import gc
import hashlib
import weakref

import numpy as np
import pytest

from hme_engine import HMEConfig, HMEEngine
from hme_consolidation import ConsolidatingMemory, _CONTROL, _MAGIC


@pytest.mark.parametrize('dimension', [3, 8, 16])
@pytest.mark.parametrize('hann', [False, True])
@pytest.mark.parametrize('decay', [0., .07])
def test_transition_preserves_fft_field_and_continued_write_parity(dimension, hann, decay):
    cfg = HMEConfig(memory_size=32, encoding_resolution=dimension,
                    use_hann_window=hann, field_decay=decay)
    reference = HMEEngine(hme_config=cfg)
    memory = ConsolidatingMemory(memory_size=32, dimension=dimension,
                                 use_hann_window=hann, decay=decay)
    rng = np.random.default_rng(191)
    for i in range(24):
        x = rng.normal(size=dimension) + 1j * rng.normal(size=dimension)
        gain = 0. if i % 9 == 0 else 1. + (i % 3)
        if i == 10:
            before = memory.field_copy()
            memory.consolidate()
            np.testing.assert_array_equal(memory.field_copy(), before)
        memory.write(x, gain=gain)
        reference.encode_memory(x, (16, 16), strength=gain)
        np.testing.assert_array_equal(memory.field_copy(), reference.hme.field)
    assert memory.write_count == 24


def test_consolidation_releases_engine_payloads_patterns_and_lineage():
    memory = ConsolidatingMemory(dimension=8, use_hann_window=False)
    memory.write(np.arange(8))
    engine_ref = weakref.ref(memory._engine)
    vector_ref = weakref.ref(next(iter(memory._engine.hme._payloads.values())))
    pattern_ref = weakref.ref(next(iter(memory._engine.hme._patterns.values())))
    lineage_ref = weakref.ref(memory._engine.lineage)
    grid_ref = weakref.ref(memory._field)
    patch_bytes = memory.patch_copy().tobytes()
    before = memory.storage_report()
    after = memory.consolidate()
    gc.collect()
    assert engine_ref() is vector_ref() is pattern_ref() is lineage_ref() is None
    assert grid_ref() is None
    assert memory._field.base is None and memory._field.flags.owndata
    assert memory._field.shape == (8, 8)
    assert memory.patch_copy().tobytes() == patch_bytes
    for name in ('records', 'payloads', 'patterns', 'lineage_nodes', 'lineage_edges'):
        assert after[name] == 0
    assert after['retained_array_bytes'] < before['retained_array_bytes']
    assert after['instance_owned_bytes'] < before['instance_owned_bytes']
    assert memory.consolidate() == after
    with pytest.raises(RuntimeError, match='identity lookup unavailable'):
        memory.retrieve(np.arange(8))


def test_retained_bytes_are_constant_through_1000_field_only_writes(tmp_path):
    memory = ConsolidatingMemory(dimension=16, use_hann_window=False)
    memory.consolidate()
    empty = memory.storage_report()
    assert empty['field_bytes'] == 16 * 16 * 16
    assert empty['control_bytes'] == _CONTROL.itemsize == 48
    assert empty['retained_array_bytes'] == 4144
    for i in range(1000):
        memory.write(np.arange(16) + (i % 13), gain=1. + (i % 7))
        if i in (0, 9, 99, 999):
            assert memory.storage_report() == empty
    out = memory.save(tmp_path/'state.hme')
    assert out.stat().st_size == empty['consolidated_checkpoint_bytes'] == 4184


def test_weighted_decay_moment_and_effective_sample_size():
    memory = ConsolidatingMemory(dimension=8, use_hann_window=False, decay=.1)
    memory.consolidate()
    rng = np.random.default_rng(193)
    c, mass, squared = np.zeros((8, 8), dtype=complex), 0., 0.
    for gain in (1., 2., 0., 5., 1.):
        x = rng.normal(size=8) + 1j * rng.normal(size=8)
        x /= np.linalg.norm(x)
        memory.write(x, gain=gain)
        c = .9*c + gain * np.outer(x, x.conj())
        mass = .9*mass + gain
        squared = .81*squared + gain**2
        np.testing.assert_allclose(memory.moment(), c/mass, atol=1e-14)
        assert memory.weight_mass == pytest.approx(mass)
        assert memory.effective_sample_size == pytest.approx(mass**2/squared)


def test_reconstruction_ignores_hidden_values_and_survives_consolidation():
    memory = ConsolidatingMemory(dimension=8, use_hann_window=False)
    rng = np.random.default_rng(197)
    vectors = rng.normal(size=(12, 8))
    for x in vectors:
        memory.write(x)
    mask = np.arange(8) % 2 == 0
    y = vectors[0].copy(); y[~mask] = np.nan
    before = memory.reconstruct(y, mask)
    bytes_before = memory.field_copy()
    memory.consolidate()
    np.testing.assert_array_equal(memory.reconstruct(y, mask), before)
    y[~mask] = 1e100
    np.testing.assert_array_equal(memory.reconstruct(y, mask), before)
    np.testing.assert_array_equal(before[mask], y[mask])
    np.testing.assert_array_equal(memory.field_copy(), bytes_before)
    v = vectors / np.linalg.norm(vectors, axis=1, keepdims=True)
    c = v.T @ v / len(v)
    expected = c[np.ix_(~mask, mask)] @ np.linalg.solve(
        c[np.ix_(mask, mask)] + .01*np.trace(c)/8 * np.eye(mask.sum()), y[mask])
    np.testing.assert_allclose(before[~mask], expected, atol=1e-13)


@pytest.mark.parametrize('data', [[], [0.]*8, [np.nan]*8, [np.inf]*8, 'a text memory'])
def test_rejected_inputs_do_not_decay_field_or_change_counters(data):
    memory = ConsolidatingMemory(dimension=8, use_hann_window=False, decay=.1)
    memory.write(np.ones(8)); memory.consolidate()
    before, controls = memory.field_copy(), memory._control.tobytes()
    with pytest.raises((TypeError, ValueError, FloatingPointError)):
        memory.write(data)
    np.testing.assert_array_equal(before, memory.field_copy())
    assert controls == memory._control.tobytes()


@pytest.mark.parametrize('gain', [-1., np.nan, np.inf, 1e308])
def test_rejected_weights_do_not_change_state(gain):
    memory = ConsolidatingMemory(dimension=8, use_hann_window=False)
    memory.consolidate()
    before = memory._control.tobytes()
    with pytest.raises((ValueError, OverflowError)):
        memory.write(np.ones(8), gain=gain)
    assert memory._control.tobytes() == before
    assert not memory.field_copy().any()


def test_counter_exhaustion_is_explicit_not_unbounded_python_integer():
    memory = ConsolidatingMemory(dimension=8, use_hann_window=False)
    memory.consolidate()
    memory._control['writes'][0] = np.iinfo(np.uint64).max
    with pytest.raises(OverflowError, match='counter'):
        memory.write(np.ones(8))
    assert not memory.field_copy().any()


def test_checkpoint_roundtrip_resumes_without_records(tmp_path):
    memory = ConsolidatingMemory(dimension=7, use_hann_window=False, decay=.04)
    memory.write(np.arange(7), gain=3)
    memory.consolidate()
    original = memory.save(tmp_path/'memory.hme')
    loaded = ConsolidatingMemory.load(original)
    assert loaded.consolidated
    assert loaded._control.tobytes() == memory._control.tobytes()
    np.testing.assert_array_equal(loaded.field_copy(), memory.field_copy())
    assert loaded.storage_report() == memory.storage_report()
    for x in (np.ones(7), np.arange(7) + 1j):
        loaded.write(x, gain=2); memory.write(x, gain=2)
    np.testing.assert_array_equal(loaded.field_copy(), memory.field_copy())
    assert loaded._control.tobytes() == memory._control.tobytes()
    with pytest.raises(FileExistsError):
        loaded.save(original)


def test_save_requires_explicit_consolidation(tmp_path):
    memory = ConsolidatingMemory()
    with pytest.raises(RuntimeError, match='explicitly'):
        memory.save(tmp_path/'no.hme')
    assert not (tmp_path/'no.hme').exists()


@pytest.mark.parametrize('change', ['truncate', 'payload', 'version', 'nanmass', 'length'])
def test_bad_checkpoints_are_rejected(tmp_path, change):
    memory = ConsolidatingMemory(dimension=8, use_hann_window=False)
    memory.consolidate(); memory.write(np.ones(8))
    out = memory.save(tmp_path/'file.hme')
    data = bytearray(out.read_bytes())
    if change == 'truncate':
        data = data[:-9]
    elif change == 'payload':
        data[-40] ^= 1
    elif change == 'version':
        data[len(_MAGIC)] = 99
    elif change == 'nanmass':
        offset = len(_MAGIC) + _CONTROL.fields['mass'][1]
        data[offset:offset+8] = np.float64(np.nan).tobytes()
    else:
        data += b'extra'
    out.write_bytes(data)
    with pytest.raises(ValueError):
        ConsolidatingMemory.load(out)


def test_output_copies_cannot_mutate_memory():
    memory = ConsolidatingMemory(dimension=8, use_hann_window=False)
    memory.consolidate(); memory.write(np.ones(8))
    before = memory.field_copy()
    copy = memory.field_copy(); copy.fill(0)
    moment = memory.moment(); moment.fill(0)
    np.testing.assert_array_equal(memory.field_copy(), before)


def test_sign_reversal_is_unidentifiable_even_with_large_gain():
    left = ConsolidatingMemory(dimension=8, use_hann_window=False)
    right = ConsolidatingMemory(dimension=8, use_hann_window=False)
    left.consolidate(); right.consolidate()
    x = np.arange(1., 9.)
    left.write(x, gain=1000.)
    right.write(-x, gain=1000.)
    np.testing.assert_array_equal(left.field_copy(), right.field_copy())


@pytest.mark.parametrize('kwargs', [{'dimension':1}, {'dimension':65}, {'decay':1.},
                                    {'decay':np.nan}, {'dimension':2.5}, {'use_hann_window':'yes'}])
def test_configuration_validation(kwargs):
    with pytest.raises((ValueError, TypeError)):
        ConsolidatingMemory(**kwargs)


@pytest.mark.parametrize('mask', [np.ones(8, dtype=bool), np.zeros(8, dtype=bool),
                                np.ones(8), np.ones(7, dtype=bool)])
def test_bad_reconstruction_masks(mask):
    memory = ConsolidatingMemory(dimension=8, use_hann_window=False)
    memory.consolidate(); memory.write(np.ones(8))
    with pytest.raises(ValueError):
        memory.reconstruct(np.ones(8), mask)


def test_empty_moment_and_zero_gain_behavior():
    memory = ConsolidatingMemory(dimension=8, use_hann_window=False)
    memory.consolidate(); memory.write(np.ones(8), gain=0.)
    assert memory.write_count == 1 and memory.weight_mass == 0
    assert memory.effective_sample_size == 0
    with pytest.raises(ValueError, match='no positive'):
        memory.moment()


def test_default_hann_off_reconstructs_hidden_endpoints_low_rank(tmp_path):
    """Fixed development regression, not a SAL/REC efficacy result."""
    rng = np.random.default_rng(719)
    basis, _ = np.linalg.qr(rng.normal(size=(16, 3)))
    training = rng.normal(size=(300, 3)) @ basis.T
    memory = ConsolidatingMemory(dimension=16)
    assert not memory._config().use_hann_window
    for x in training:
        memory.write(x)
    truth = basis @ np.array([1.2, .5, -.9])
    truth /= np.linalg.norm(truth)
    mask = np.ones(16, dtype=bool)
    mask[[0, 5, 15]] = False
    observed = truth.copy(); observed[~mask] = np.nan
    before = memory.reconstruct(observed, mask)
    assert np.all(np.abs(truth[[0, 15]]) > .05)
    np.testing.assert_allclose(before[~mask], truth[~mask], atol=.01, rtol=0)
    np.testing.assert_array_equal(before[mask], truth[mask])
    memory.consolidate()
    np.testing.assert_array_equal(memory.reconstruct(observed, mask), before)
    loaded = ConsolidatingMemory.load(memory.save(tmp_path/'low-rank.hme'))
    np.testing.assert_array_equal(loaded.reconstruct(observed, mask), before)


def test_hann_reconstruction_explicitly_refused_before_after_and_loaded(tmp_path):
    memory = ConsolidatingMemory(dimension=16, use_hann_window=True)
    memory.write(np.arange(1., 17.))
    mask = np.arange(16) % 2 == 0
    for _ in range(2):
        with pytest.raises(ValueError, match='use_hann_window=False'):
            memory.reconstruct(np.ones(16), mask)
        assert abs(memory.moment()[0, 0]) < 1e-14
        memory.consolidate()
    loaded = ConsolidatingMemory.load(memory.save(tmp_path/'hann.hme'))
    with pytest.raises(ValueError, match='use_hann_window=False'):
        loaded.reconstruct(np.ones(16), mask)


@pytest.mark.parametrize('side,dimension', [(4, 2), (7, 7), (8, 7), (16, 16), (64, 16)])
def test_compact_patch_is_owned_and_checkpoint_counts_are_exact(tmp_path, side, dimension):
    memory = ConsolidatingMemory(memory_size=side, dimension=dimension)
    memory.write(np.arange(1., dimension+1.))
    before = memory.field_copy()
    patch = memory.patch_copy()
    grid_ref = weakref.ref(memory._field)
    memory.consolidate(); gc.collect()
    assert grid_ref() is None
    assert memory._field.shape == (dimension, dimension)
    assert memory._field.base is None and memory._field.flags.c_contiguous
    assert memory.patch_copy().tobytes() == patch.tobytes()
    np.testing.assert_array_equal(memory.field_copy(), before)
    report = memory.storage_report()
    assert report['retained_array_bytes'] == dimension**2 * 16 + 48
    assert report['active_patch_bytes'] == dimension**2 * 16
    assert report['packed_real_symmetric_reference_bytes'] == dimension*(dimension+1)//2 * 8
    path = memory.save(tmp_path/'compact.hme')
    assert path.read_bytes()[:8] == b'HMEFC002'
    assert path.stat().st_size == report['consolidated_checkpoint_bytes'] == dimension**2*16 + 88
    loaded = ConsolidatingMemory.load(path)
    assert loaded._field.base is None and loaded._field.flags.owndata
    assert loaded.storage_report() == report
    np.testing.assert_array_equal(loaded.field_copy(), before)
    external = loaded.patch_copy(); external.fill(0)
    np.testing.assert_array_equal(loaded.patch_copy(), patch)


def _write_checkpoint_fixture(path, memory, *, version=2, controls=None, exterior=False):
    """Write a correctly hashed fixture, so tests reach structural validation."""
    control = memory._control.copy()
    control['version'] = version
    for key, value in (controls or {}).items():
        control[key] = value
    field = memory.field_copy() if version == 1 else memory.patch_copy()
    if exterior:
        field[0, 0] = .125
    payload = (b'HMEFC001' if version == 1 else b'HMEFC002') + control.tobytes()
    payload += field.astype('<c16', copy=False).tobytes()
    path.write_bytes(payload + hashlib.sha256(payload).digest())
    return path


@pytest.mark.parametrize('version', [1, 2])
@pytest.mark.parametrize('controls,match', [
    ({'dimension': 65}, 'dimension cannot exceed memory_size'),
    ({'dimension': 1}, 'encoding_resolution'),
    ({'memory_size': 2, 'dimension': 2}, 'memory_size'),
    ({'decay': np.nan}, 'field_decay'),
    ({'hann': 2}, 'control schema'),
])
def test_load_rejects_invalid_controls_even_with_correct_digest(tmp_path, version, controls, match):
    memory = ConsolidatingMemory(dimension=16)
    memory.consolidate(); memory.write(np.arange(1., 17.))
    path = _write_checkpoint_fixture(tmp_path/'bad.hme', memory, version=version, controls=controls)
    with pytest.raises(ValueError, match=match):
        ConsolidatingMemory.load(path)


@pytest.mark.parametrize('hann', [False, True])
def test_legacy_grid_checkpoint_is_validated_cropped_and_resumable(tmp_path, hann):
    memory = ConsolidatingMemory(dimension=7, use_hann_window=hann, decay=.05)
    memory.write(np.arange(1., 8.), gain=3.)
    memory.consolidate()
    old = _write_checkpoint_fixture(tmp_path/'v1.hme', memory, version=1)
    loaded = ConsolidatingMemory.load(old)
    np.testing.assert_array_equal(loaded.patch_copy(), memory.patch_copy())
    assert loaded._control.tobytes() == memory._control.tobytes()
    assert loaded._field.base is None and loaded._field.shape == (7, 7)
    assert loaded.storage_report() == memory.storage_report()
    loaded.write(np.arange(1., 8.) + 1j, gain=2.)
    memory.write(np.arange(1., 8.) + 1j, gain=2.)
    np.testing.assert_array_equal(loaded.field_copy(), memory.field_copy())
    new = loaded.save(tmp_path/'v2.hme')
    assert new.read_bytes().startswith(b'HMEFC002')
    assert new.stat().st_size < old.stat().st_size


def test_legacy_nonzero_exterior_is_not_silently_discarded(tmp_path):
    memory = ConsolidatingMemory(dimension=16)
    memory.write(np.arange(1., 17.)); memory.consolidate()
    old = _write_checkpoint_fixture(tmp_path/'nonzero.hme', memory, version=1, exterior=True)
    with pytest.raises(ValueError, match='outside the active patch'):
        ConsolidatingMemory.load(old)
