#!/usr/bin/env python3
"""Deterministic Step-0 invariant evidence; no performance evaluation seeds."""
from __future__ import annotations
import argparse
import hashlib
import json
import platform
from pathlib import Path
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import numpy as np
from hme_consolidation import ConsolidatingMemory


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise FileExistsError('use a fresh output path')
    memory = ConsolidatingMemory(dimension=16, use_hann_window=False)
    for i in range(128):
        memory.write(np.arange(16.) + i % 11)
    field = memory.field_copy()
    before = memory.storage_report()
    memory.consolidate()
    after = memory.storage_report()
    np.testing.assert_array_equal(field, memory.field_copy())
    for i in range(1000):
        memory.write(np.arange(16.) + i % 11)
    later = memory.storage_report()
    assert after == later
    with tempfile.TemporaryDirectory() as tmp:
        checkpoint = memory.save(Path(tmp)/'state.hme')
        on_disk = checkpoint.stat().st_size
        loaded = ConsolidatingMemory.load(checkpoint)
        np.testing.assert_array_equal(loaded.field_copy(), memory.field_copy())
        assert loaded._control.tobytes() == memory._control.tobytes()
    report = {
        'kind': 'deterministic-development-invariants-not-efficacy',
        'python': platform.python_version(), 'numpy': np.__version__,
        'source_sha256': {name: hashlib.sha256((ROOT/name).read_bytes()).hexdigest()
                          for name in ('hme_engine.py', 'hme_consolidation.py',
                                       'tests/test_consolidation.py', 'scripts/check_consolidation.py')},
        'before_128_writes': before, 'after_consolidation': after,
        'after_1000_additional_writes': later,
        'checks': {'field_bytes_preserved': True, 'retained_bytes_constant': True,
                   'checkpoint_exact': True, 'no_records_or_caches': all(
                       later[key] == 0 for key in ('records','payloads','patterns',
                                                   'lineage_nodes','lineage_edges'))},
        'checkpoint_bytes_measured_on_disk': on_disk,
        'scope': 'Owned state only; not RSS, peak workspace, secure erase, or semantic retention.',
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2)+'\n', encoding='utf-8')
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
