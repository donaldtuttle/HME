# HME Plate source and port boundary

Owner-authorized port of https://hme-plate.grok.me/, captured 2026-09-26 after
the reset, probe-threshold and zero-vector fixes. The source app was inspected
in the browser. Assets were downloaded from URLs exposed by its document.

| Captured resource | SHA-256 |
| --- | --- |
| `assets/routes-B7NKVTR_.js` | `f1fc26e6bb45a2fba28fbb50a74b773245f162a946a50f8babe462d0394454c3` |
| `assets/styles-CzJ4nOJd.css` | `ff2064e40a2bcb6c7b4f4f7db1e67ef9a7487cd5d098bea514d0736c01785d4b` |
| `favicon.svg` | `e2db327f268ab31c62ee0f2544e95f2c6e9fd5790274f1da341f3b851fa00086` |

## Changes made during recovery

The deployed route module was parsed into an AST. Compiler JSX calls were
converted to JSX with their original property, child and key expressions.
Top-level names and application-state variables were renamed, numerical code
was separated into `model.js`, and a normal React entry point replaced the
Grok route/bootstrap dependency. Original copy, colors, dimensions, controls
and the corrected source behavior were retained. Source CSS was formatted,
not redesigned. Fonts are the same IBM Plex families/weights, downloaded and
bundled locally with their license texts. No proprietary Grok bootstrap,
app-builder extension, remote runtime or analytics script is included.

The enclosing Vite starter supports a relative static build. Build outputs and
npm dependencies are excluded from the repository payload. This port does not
modify HME's Python algorithms, published experiments, source pins or defaults.

## Python comparison boundary

Reference repository commit: `3e93c66f0a2eadf7ad840d963276cdfead4836c7`.
Reference `hme_engine.py` SHA-256:
`080a20056c6c5c88e49c6307845277002ad2091a6a1d7dec66961317bc2c0167`.

Numeric resampling, Hann-on writes, normalization, Fourier outer-product
patterns, patch clipping, absolute query similarity, field correlation,
0.38/0.42/0.20 scoring, threshold selection and decoded outputs are compared
on the committed input fixtures. Queries do not receive the write-time Hann
window, preserving the published asymmetry. This does not switch the engine
to the experimental signed score or Hann-off default.

Intentional differences inherited from the source viewer:

- Direct DFT loops replace NumPy FFT calls. This preserves the tested numerical
  transform within tolerance, not runtime performance.
- Input controls accept real numbers, not arbitrary complex vectors.
- Symbols use four SHA-256 digest bytes to seed a 32-bit PRNG plus a Gaussian
  transform. Python uses eight digest bytes with NumPy's generator.
- Viewer hashes serialize rounded real/imaginary arrays to JSON. They do not
  hash exact NumPy dtype/shape/bytes. IDs use `hme-viewer`, not `hme-v3`.
- Salience is off. The optional runtime, spatial dynamics and consolidation
  adapter are not ported. Insertion lineage is not a Merkle chain.
- Form bounds define the browser control surface; this module is not advertised
  as a drop-in replacement for every Python validation/API edge case.

Source chart scaling is retained: near-zero vector entries draw no bars;
nonzero entries have the viewer's small visibility floor. Decoded-surface
opacity follows the source's magnitude visualization and is not a numeric scale.
