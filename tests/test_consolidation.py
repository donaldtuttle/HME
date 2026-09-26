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
    allocation = id(memory._field)
    before = memory.storage_report()
    after = memory.consolidate()
    gc.collect()
    assert engine_ref() is vector_ref() is pattern_ref() is lineage_ref() is None
    assert id(memory._field) == allocation
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
    assert empty['field_bytes'] == 64 * 64 * 16
    assert empty['control_bytes'] == _CONTROL.itemsize == 48
    assert empty['retained_array_bytes'] == 65584
    for i in range(1000):
        memory.write(np.arange(16) + (i % 13), gain=1. + (i % 7))
        if i in (0, 9, 99, 999):
            assert memory.storage_report() == empty
    out = memory.save(tmp_path/'state.hme')
    assert out.stat().st_size == empty['consolidated_checkpoint_bytes'] == 65624


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
        data[len(_MAGIC)] = 2
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
