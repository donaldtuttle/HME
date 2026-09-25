"""Experimental sign ablation: one guarded expression change in the pinned core.

The public engine file is never edited. The generated module executes the same
source with abs(vdot) replaced by real(vdot) in the item/query score only.
All field terms, clipping, thresholds, API outputs and defaults are retained.
"""
from pathlib import Path
import hashlib
import sys
from types import ModuleType

ROOT = Path(__file__).resolve().parents[2]
ENGINE_SHA256 = '080a20056c6c5c88e49c6307845277002ad2091a6a1d7dec66961317bc2c0167'
ORIGINAL = 'float(abs(np.vdot(payload, query_vector)) / denom)'
REPLACEMENT = 'float(np.real(np.vdot(payload, query_vector)) / denom)'
_MODULE = None


def transformed_source():
    data = (ROOT/'hme_engine.py').read_bytes()
    if hashlib.sha256(data).hexdigest() != ENGINE_SHA256:
        raise RuntimeError('The source engine differs from the registered pin')
    source = data.decode('utf-8')
    if source.count(ORIGINAL) != 1:
        raise RuntimeError('Expected exactly one item/query score expression')
    return source.replace(ORIGINAL, REPLACEMENT)


def signed_module():
    global _MODULE
    if _MODULE is None:
        source = transformed_source()
        module = ModuleType('hme_nn2a_signed_experiment')
        module.__file__ = str(ROOT/'hme_engine.py')
        sys.modules[module.__name__] = module
        exec(compile(source, '<HME-NN-2A signed engine>', 'exec'), module.__dict__)
        _MODULE = module
    return _MODULE
