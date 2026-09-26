"""Compare the browser model with the unchanged, pinned Python engine.

The fixture contains inputs, not self-generated expected answers. Symbols and
artifact IDs intentionally use a different viewer contract (see SOURCE.md).
"""
import hashlib
import json
from pathlib import Path
import platform
import subprocess
import sys

import numpy as np

DEMO = Path(__file__).resolve().parents[1]
ROOT = DEMO.parents[1]
ENGINE_SHA256 = '080a20056c6c5c88e49c6307845277002ad2091a6a1d7dec66961317bc2c0167'
actual_pin = hashlib.sha256((ROOT / 'hme_engine.py').read_bytes()).hexdigest()
if actual_pin != ENGINE_SHA256:
    raise SystemExit('Engine source pin changed: review the compatibility contract before updating fixtures.')
sys.path.insert(0, str(ROOT))
from hme_engine import HME, HMEConfig  # noqa: E402

cases = json.loads((DEMO / 'tests/fixtures/numeric-cases.json').read_text())
observed = json.loads(subprocess.check_output(
    ['node', str(DEMO / 'scripts/numeric-runner.mjs')],
    input=json.dumps(cases).encode(), cwd=DEMO,
))
assert len(cases) == len(observed)
errors = dict(field=0., scores=0., decoded_vector=0., surface_magnitude=0.)
for index, (c, result) in enumerate(zip(cases, observed)):
    m = HME(config=HMEConfig(use_hann_window=c['hann']))
    for i, (data, position) in enumerate(zip(c['inputs'], c['positions'])):
        m.encode(data, tuple(position), tag=f'item-{i}')
    if c['erase']:
        m.clear(keep_records=True)
    expected = m.retrieve(tuple(c['positions'][0]), query=c['query'],
                          top_k=len(c['inputs']), relevance_threshold=c['threshold'])
    assert [m.records[h.artifact_id].tag for h in expected.hits] == result['tags'], index
    assert expected.outcome == result['outcome'], index
    pairs = {
        'field': (m.field.ravel(), np.array(result['fieldRe']) + 1j*np.array(result['fieldIm'])),
        'scores': (np.array([[h.base_score, h.distance_score, h.query_score, h.pattern_score]
                             for h in expected.hits]), np.array(result['scores'])),
        'decoded_vector': (expected.decoded_vector, np.array(result['decoded'])),
        'surface_magnitude': (np.abs(expected.decoded_surface).ravel(), np.array(result['surface'])),
    }
    for name, (a, b) in pairs.items():
        assert a.shape == b.shape, (index, name, a.shape, b.shape)
        delta = float(np.max(np.abs(a-b))) if a.size else 0.
        errors[name] = max(errors[name], delta)
        assert np.allclose(a, b, atol=1e-10, rtol=0), (index, name, delta)
summary = dict(cases_passed=len(cases), cases_total=len(cases), atol=1e-10, rtol=0,
               maximum_absolute_errors=errors, engine_sha256=actual_pin,
               python=platform.python_version(), numpy=np.__version__,
               scope='Real numeric input compatibility; not symbol/hash equivalence, browser rendering, or performance evidence.')
(DEMO / 'outputs').mkdir(exist_ok=True)
(DEMO / 'outputs/parity.json').write_text(json.dumps(summary, indent=2)+'\n')
print(json.dumps(summary, indent=2))
