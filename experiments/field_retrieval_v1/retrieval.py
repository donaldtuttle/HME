"""Experimental candidate-specific readout over fields written by the pinned HME.

The writer/encoder is unchanged. All search methods return candidate indices and
scores, scan every candidate, and never accept a target address. Snapshots retain
only the arrays they use, plus identical records, lineage and address maps.
"""
from __future__ import annotations
import copy
import numpy as np

EPS = 1e-12


def unit_rows(rows):
    x = np.asarray(rows,dtype=np.complex128).copy()
    norms = np.linalg.norm(x,axis=1,keepdims=True)
    return np.divide(x,norms,out=np.zeros_like(x),where=norms>EPS)


def preprocess(queries,mode):
    q = np.atleast_2d(np.asarray(queries,dtype=np.complex128))
    if mode == 'symmetric':
        q = q*np.hanning(q.shape[1])
    elif mode != 'native':
        raise ValueError(mode)
    return unit_rows(q)


def patterns(processed):
    """The core's spectral outer product, with no additional Hann window."""
    vectors = unit_rows(np.atleast_2d(processed))
    spectrum = np.fft.fft(vectors,axis=1)
    outer = spectrum[:,:,None]*spectrum[:,None,:].conj()
    fields = np.fft.ifft2(outer,axes=(-2,-1))
    return unit_rows(fields.reshape(len(fields),-1))


def assigned_positions(seed,cfg,spacing):
    rows,cols = cfg['grid_shape']
    n = rows*cols
    s,m = cfg['dimension'],cfg['memory_size']
    first_x = (m-((rows-1)*spacing+s))//2+s//2
    first_y = (m-((cols-1)*spacing+s))//2+s//2
    positions = np.asarray([(first_x+r*spacing,first_y+c*spacing)
                            for r in range(rows) for c in range(cols)],dtype=np.int64)
    order = np.random.default_rng(np.random.SeedSequence([seed,3])).permutation(n)
    positions = positions[order]
    if np.any(positions-s//2 < 0) or np.any(positions-s//2+s > m):
        raise ValueError('Registered layout would clip a patch')
    return positions


class Snapshot:
    def __init__(self,engine):
        self.records = copy.deepcopy(list(engine.hme.records.values()))
        self.lineage = copy.deepcopy(engine.lineage)
        self.positions = np.array([r.position for r in self.records],dtype=np.int64)
        self.ids = [r.artifact_id for r in self.records]
        self.dimension = engine.hme.encoding_resolution


class ExactNN(Snapshot):
    def __init__(self,engine,absolute=False):
        super().__init__(engine)
        self.vectors = unit_rows(np.stack(list(engine.hme._payloads.values())))
        self.absolute = absolute

    def scores(self,queries,mode='native'):
        dots = preprocess(queries,mode).conj()@self.vectors.T
        return np.abs(dots) if self.absolute else dots.real

    def search(self,query,mode='native',top_k=5):
        values = self.scores(query,mode)[0]
        order = np.argsort(-values,kind='stable')[:top_k]
        return order,values[order]


class FieldRetrieval(Snapshot):
    def __init__(self,engine,hybrid=False,a=.42,b=.20,permutation=None):
        super().__init__(engine)
        self.hybrid,self.a,self.b = hybrid,float(a),float(b)
        if not self.a > 0 or not self.b >= 0:
            raise ValueError('Require a > 0 and b >= 0')
        self.vectors = unit_rows(np.stack(list(engine.hme._payloads.values()))) if hybrid else None
        self.permutation = None if permutation is None else np.asarray(permutation,dtype=np.int64).copy()
        if self.permutation is not None and sorted(self.permutation.tolist()) != list(range(len(self.ids))):
            raise ValueError('Readout permutation must contain every candidate once')
        self.shared_position = bool(np.all(self.positions == self.positions[0]))
        self._field = None
        self._cache = None
        self.replace_field(engine.hme.field)

    def invalidate_cache(self):
        self._cache = None

    def replace_field(self,field):
        value = np.asarray(field,dtype=np.complex128)
        if value.ndim != 2 or not np.all(np.isfinite(value)):
            raise ValueError('Expected a finite 2D field')
        if self._field is not None and value.shape != self._field.shape:
            raise ValueError('Field dimensions must remain fixed')
        self._field = value.copy()
        self._field.flags.writeable = False
        self.invalidate_cache()

    def _readouts(self):
        s,h = self.dimension,self.dimension//2
        patches = [self._field[x-h:x-h+s,y-h:y-h+s].reshape(-1) for x,y in self.positions]
        return unit_rows(np.stack(patches))

    def prepare_cache(self):
        self._cache = self._readouts()

    def field_scores(self,processed,cached=True):
        if cached:
            if self._cache is None:
                self.prepare_cache()
            readouts = self._cache
        else:
            readouts = self._readouts()
        query_patterns = patterns(processed)
        if self.shared_position:
            value = np.abs(query_patterns.conj()@readouts[0])
            scores = np.repeat(value[:,None],len(self.ids),axis=1)
        else:
            scores = np.abs(query_patterns.conj()@readouts.T)
        return scores if self.permutation is None else scores[:,self.permutation]

    def scores(self,queries,mode='native',cached=True):
        q = preprocess(queries,mode)
        field = self.field_scores(q,cached=cached)
        if not self.hybrid:
            return field
        signed = (q.conj()@self.vectors.T).real
        # Rank-equivalent common-offset cancellation, exactly preserving signed
        # NN order in the shared-position or zero-field negative controls.
        if np.all(field == field[:,:1]):
            return signed
        return self.a*signed + self.b*field

    def search(self,query,mode='native',top_k=5,cached=True):
        values = self.scores(query,mode,cached=cached)[0]
        order = np.argsort(-values,kind='stable')[:top_k]
        return order,values[order]
