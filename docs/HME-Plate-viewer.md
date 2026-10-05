# HME Plate viewer

GitHub-portable source of the live Grok HME Plate demo. Copy each fenced block into the path in its heading. `@/` means `src/`.

Source date: 2026-09-27.

This is a browser reimplementation of the released field-plus-ledger contract. It is not the NumPy engine and it is not bit-identical to it. It does not visualize consolidation or SAL-1.

## Files changed

UI pass only:

- `src/routes/index.tsx`
- `src/styles.css`

Included unchanged, so the viewer can be reconstructed without guessing:

- `src/lib/hme/fft.ts`
- `src/lib/hme/sha256.ts`
- `src/lib/hme/engine.ts`
- `src/lib/hme/check.ts`
- `src/components/hme/plate.tsx`

## UI-only changes

- Hero heading is `Explore HME`. Two short sentences replace the longer intro and the separate “What am I testing?” block. The size and energy line stays under the intro.
- Quick start is collapsed by default. Explore shows three steps. Details still shows the five-step version.
- Plate legend adds selected memory (solid brass), other memories (faint brass), and the search window (dashed).
- Search modes are a 2×2 grid on small screens and in the desktop sidebar, and one row between those widths. Buttons share one size.
- Range sliders and the checkbox use `accent-color: var(--color-accent)`.

Explore stays the default. Details still shows write/query, sigma, top k, Hann window, the scoring equation, hashes, decoded vector, decoded surface, and model scope.

## Behavior changes

None. The numerical engine, retrieval scoring, FFT, field and ledger semantics, noise-probe counting, reset order, seeded examples, threshold logic, and mathematical outputs were not changed.

## Checks run

`node --experimental-strip-types` imported `runChecks`, `bootDemo`, `executeQuery`, `seedDemo`, and `noiseProbe` on 2026-09-27. All 11 viewer checks passed:

- sha256
- dft impulse
- readme probe
- overlap prefers query
- field erase zeros pattern
- ledger drop is NO_MATCH
- missing query scores 1
- hann changes payload
- threshold can reject
- symbols are exact, not paraphrase
- probe uses threshold

Seeded default, Hann on, noisy query of `reading-001` at sigma 0.15 seed 7, threshold 0:

- 4 records
- field energy 0.195509
- outcome MATCH
- score 0.890906
- proximity 1, similarity 0.835809, field 0.799328

Reset path used by the page (Hann forced on, then reseed) reproduced energy 0.195509 and score 0.890906.

Noise probe at threshold 1.00, seeds 1–8, radius 4: 0/8 at sigma 0, 0.25, 0.5, and 1.

Field erase: energy 0, pattern score 0, outcome still MATCH for the retained record.

Ledger drop: 0 records, energy still 0.195509, outcome NO_MATCH, 0 hits.

These checks do not claim full numerical parity with the Python engine. Direct DFT is the viewer transform. Symbol RNG and artifact ids differ from NumPy on purpose.

Mobile check at 390×844: Quick start `open` is false, the plate starts inside the first viewport, search modes measure as a 2×2 grid of equal 157×44 buttons, and range/checkbox computed `accent-color` is `rgb(196, 163, 90)`. No horizontal overflow. No console errors.

## Model scope

Released field-plus-ledger model: spatial FFT-pattern superposition plus a retained artifact ledger. Not consolidation, not SAL-1, not standard HRR binding, and not field-only identity recovery.

## `src/lib/hme/fft.ts`

Separable 2D DFT. Forward is unnormalized; inverse divides by length, matching NumPy along one axis.

```ts
export type Vec = { re: Float64Array; im: Float64Array };

export function zeros(n: number): Vec {
  return { re: new Float64Array(n), im: new Float64Array(n) };
}

/** Unnormalized forward DFT, or 1/n inverse DFT. Matches NumPy along one axis. */
export function dft(reIn: Float64Array, imIn: Float64Array, inverse: boolean): Vec {
  const n = reIn.length;
  const re = new Float64Array(n);
  const im = new Float64Array(n);
  const sign = inverse ? 1 : -1;
  for (let k = 0; k < n; k++) {
    let sr = 0;
    let si = 0;
    for (let t = 0; t < n; t++) {
      const theta = (sign * 2 * Math.PI * k * t) / n;
      const c = Math.cos(theta);
      const s = Math.sin(theta);
      sr += reIn[t] * c - imIn[t] * s;
      si += reIn[t] * s + imIn[t] * c;
    }
    re[k] = sr;
    im[k] = si;
  }
  if (inverse && n > 0) {
    for (let k = 0; k < n; k++) {
      re[k] /= n;
      im[k] /= n;
    }
  }
  return { re, im };
}

export function fft2(src: Vec, height: number, width: number, inverse: boolean): Vec {
  const out = zeros(height * width);
  const rowRe = new Float64Array(width);
  const rowIm = new Float64Array(width);
  for (let y = 0; y < height; y++) {
    for (let x = 0; x < width; x++) {
      rowRe[x] = src.re[y * width + x];
      rowIm[x] = src.im[y * width + x];
    }
    const t = dft(rowRe, rowIm, inverse);
    for (let x = 0; x < width; x++) {
      out.re[y * width + x] = t.re[x];
      out.im[y * width + x] = t.im[x];
    }
  }
  const colRe = new Float64Array(height);
  const colIm = new Float64Array(height);
  for (let x = 0; x < width; x++) {
    for (let y = 0; y < height; y++) {
      colRe[y] = out.re[y * width + x];
      colIm[y] = out.im[y * width + x];
    }
    const t = dft(colRe, colIm, inverse);
    for (let y = 0; y < height; y++) {
      out.re[y * width + x] = t.re[y];
      out.im[y * width + x] = t.im[y];
    }
  }
  return out;
}
```
## `src/lib/hme/sha256.ts`

SHA-256 used for viewer insertion ids and payload hashes. These are not NumPy byte hashes.

```ts
const K = new Uint32Array([
  0x428a2f98, 0x71374491, 0xb5c0fbcf, 0xe9b5dba5, 0x3956c25b, 0x59f111f1, 0x923f82a4, 0xab1c5ed5,
  0xd807aa98, 0x12835b01, 0x243185be, 0x550c7dc3, 0x72be5d74, 0x80deb1fe, 0x9bdc06a7, 0xc19bf174,
  0xe49b69c1, 0xefbe4786, 0x0fc19dc6, 0x240ca1cc, 0x2de92c6f, 0x4a7484aa, 0x5cb0a9dc, 0x76f988da,
  0x983e5152, 0xa831c66d, 0xb00327c8, 0xbf597fc7, 0xc6e00bf3, 0xd5a79147, 0x06ca6351, 0x14292967,
  0x27b70a85, 0x2e1b2138, 0x4d2c6dfc, 0x53380d13, 0x650a7354, 0x766a0abb, 0x81c2c92e, 0x92722c85,
  0xa2bfe8a1, 0xa81a664b, 0xc24b8b70, 0xc76c51a3, 0xd192e819, 0xd6990624, 0xf40e3585, 0x106aa070,
  0x19a4c116, 0x1e376c08, 0x2748774c, 0x34b0bcb5, 0x391c0cb3, 0x4ed8aa4a, 0x5b9cca4f, 0x682e6ff3,
  0x748f82ee, 0x78a5636f, 0x84c87814, 0x8cc70208, 0x90befffa, 0xa4506ceb, 0xbef9a3f7, 0xc67178f2,
]);

function rotr(x: number, n: number): number {
  return (x >>> n) | (x << (32 - n));
}

export function sha256Bytes(data: Uint8Array): Uint8Array {
  const bitLen = data.length * 8;
  const pad = (64 - ((data.length + 1 + 8) % 64)) % 64;
  const buf = new Uint8Array(data.length + 1 + pad + 8);
  buf.set(data);
  buf[data.length] = 0x80;
  const view = new DataView(buf.buffer);
  view.setUint32(buf.length - 8, Math.floor(bitLen / 2 ** 32));
  view.setUint32(buf.length - 4, bitLen >>> 0);

  let h0 = 0x6a09e667;
  let h1 = 0xbb67ae85;
  let h2 = 0x3c6ef372;
  let h3 = 0xa54ff53a;
  let h4 = 0x510e527f;
  let h5 = 0x9b05688c;
  let h6 = 0x1f83d9ab;
  let h7 = 0x5be0cd19;
  const w = new Uint32Array(64);

  for (let i = 0; i < buf.length; i += 64) {
    for (let t = 0; t < 16; t++) w[t] = view.getUint32(i + t * 4);
    for (let t = 16; t < 64; t++) {
      const s0 = rotr(w[t - 15], 7) ^ rotr(w[t - 15], 18) ^ (w[t - 15] >>> 3);
      const s1 = rotr(w[t - 2], 17) ^ rotr(w[t - 2], 19) ^ (w[t - 2] >>> 10);
      w[t] = (w[t - 16] + s0 + w[t - 7] + s1) >>> 0;
    }
    let a = h0;
    let b = h1;
    let c = h2;
    let d = h3;
    let e = h4;
    let f = h5;
    let g = h6;
    let h = h7;
    for (let t = 0; t < 64; t++) {
      const s1 = rotr(e, 6) ^ rotr(e, 11) ^ rotr(e, 25);
      const ch = (e & f) ^ (~e & g);
      const temp1 = (h + s1 + ch + K[t] + w[t]) >>> 0;
      const s0 = rotr(a, 2) ^ rotr(a, 13) ^ rotr(a, 22);
      const maj = (a & b) ^ (a & c) ^ (b & c);
      const temp2 = (s0 + maj) >>> 0;
      h = g;
      g = f;
      f = e;
      e = (d + temp1) >>> 0;
      d = c;
      c = b;
      b = a;
      a = (temp1 + temp2) >>> 0;
    }
    h0 = (h0 + a) >>> 0;
    h1 = (h1 + b) >>> 0;
    h2 = (h2 + c) >>> 0;
    h3 = (h3 + d) >>> 0;
    h4 = (h4 + e) >>> 0;
    h5 = (h5 + f) >>> 0;
    h6 = (h6 + g) >>> 0;
    h7 = (h7 + h) >>> 0;
  }

  const out = new Uint8Array(32);
  const ov = new DataView(out.buffer);
  [h0, h1, h2, h3, h4, h5, h6, h7].forEach((v, i) => ov.setUint32(i * 4, v));
  return out;
}

export function sha256Hex(data: Uint8Array): string {
  return [...sha256Bytes(data)].map((b) => b.toString(16).padStart(2, "0")).join("");
}

export function sha256Text(text: string): string {
  return sha256Hex(new TextEncoder().encode(text));
}
```
## `src/lib/hme/engine.ts`

Field-plus-ledger engine. Not modified in the 2026-09-27 UI pass.

```ts
import { fft2, dft, zeros, type Vec } from "./fft.ts";
import { sha256Bytes, sha256Text } from "./sha256.ts";

const EPS = 1e-12;
export const VIEWER_SCHEMA = "hme-viewer";

export type HmeConfig = {
  memorySize: number;
  encodingResolution: number;
  useHannWindow: boolean;
  normalizePatterns: boolean;
  retrievalDistanceScale: number;
  relevanceThreshold: number;
  maxRecords: number;
};

export type Artifact = {
  artifactId: string;
  t: number;
  tag: string;
  operation: string;
  position: [number, number];
  gain: number;
  writeWeight: number;
  payloadSize: number;
  payloadHash: string;
  patternHash: string;
  metadata: Record<string, string | number>;
  /** Original numeric input. Absent for symbols. Not part of the insertion id. */
  raw: number[] | null;
  symbol: string | null;
};

export type Hit = {
  artifactId: string;
  tag: string;
  baseScore: number;
  finalScore: number;
  distanceScore: number;
  queryScore: number;
  patternScore: number;
  distance: number;
};

export type Retrieval = {
  position: [number, number];
  radius: number;
  relevanceScore: number;
  outcome: "MATCH" | "NO_MATCH";
  hits: Hit[];
  decodedRe: number[];
  /** Magnitude of ifft2(field window). Not an identity. */
  surfaceMag: number[];
  surfaceH: number;
  surfaceW: number;
  queryRe: number[] | null;
};

export type LineageNode = {
  nodeId: string;
  tag: string;
  position: [number, number];
  operation: string;
};

export type LineageEdge = { source: string; target: string; relation: "next_memory" };

const DEFAULTS: HmeConfig = {
  memorySize: 64,
  encodingResolution: 16,
  useHannWindow: true,
  normalizePatterns: true,
  retrievalDistanceScale: 0.25,
  relevanceThreshold: 0,
  maxRecords: 4096,
};

function linspace(n: number): Float64Array {
  const out = new Float64Array(n);
  if (n <= 1) return out;
  for (let i = 0; i < n; i++) out[i] = i / (n - 1);
  return out;
}

function interp(dst: Float64Array, src: Float64Array, values: ArrayLike<number>): Float64Array {
  const out = new Float64Array(dst.length);
  for (let i = 0; i < dst.length; i++) {
    const x = dst[i];
    if (x <= src[0]) {
      out[i] = values[0];
      continue;
    }
    if (x >= src[src.length - 1]) {
      out[i] = values[values.length - 1];
      continue;
    }
    let lo = 0;
    let hi = src.length - 1;
    while (hi - lo > 1) {
      const mid = (lo + hi) >> 1;
      if (src[mid] <= x) lo = mid;
      else hi = mid;
    }
    const span = src[hi] - src[lo];
    const t = span === 0 ? 0 : (x - src[lo]) / span;
    out[i] = values[lo] * (1 - t) + values[hi] * t;
  }
  return out;
}

function l2(v: Vec): number {
  let s = 0;
  for (let i = 0; i < v.re.length; i++) s += v.re[i] * v.re[i] + v.im[i] * v.im[i];
  return Math.sqrt(s);
}

function normalize(v: Vec): Vec {
  const n = l2(v);
  if (n <= EPS) return { re: v.re.slice(), im: v.im.slice() };
  const re = new Float64Array(v.re.length);
  const im = new Float64Array(v.im.length);
  for (let i = 0; i < v.re.length; i++) {
    re[i] = v.re[i] / n;
    im[i] = v.im[i] / n;
  }
  return { re, im };
}

/** NumPy np.hanning: 0.5 - 0.5 cos(2π n / (M-1)), endpoints zero when M > 1. */
export function hanning(m: number): Float64Array {
  const w = new Float64Array(m);
  if (m === 1) {
    w[0] = 1;
    return w;
  }
  for (let n = 0; n < m; n++) w[n] = 0.5 - 0.5 * Math.cos((2 * Math.PI * n) / (m - 1));
  return w;
}

function resample(real: ArrayLike<number>, target: number): Vec {
  const srcN = real.length;
  if (srcN < 1) throw new Error("data must contain at least one value");
  for (let i = 0; i < srcN; i++) {
    if (!Number.isFinite(real[i])) throw new Error("data contains NaN or infinite values");
  }
  const srcX = linspace(srcN);
  const dstX = linspace(target);
  return { re: interp(dstX, srcX, real), im: new Float64Array(target) };
}

function mulberry32(seed: number): () => number {
  let a = seed >>> 0;
  return () => {
    a = (a + 0x6d2b79f5) >>> 0;
    let t = Math.imul(a ^ (a >>> 15), 1 | a);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

/** Deterministic, paraphrase-blind symbol map. Not NumPy Generator bit-compatible. */
export function symbolVector(symbol: string, dimension: number): Vec {
  const digest = sha256Bytes(new TextEncoder().encode(symbol));
  const seed = ((digest[0] << 24) | (digest[1] << 16) | (digest[2] << 8) | digest[3]) >>> 0;
  const rng = mulberry32(seed);
  const re = new Float64Array(dimension);
  const im = new Float64Array(dimension);
  for (let i = 0; i < dimension; i++) {
    const u = Math.max(rng(), 1e-12);
    const v = rng();
    re[i] = Math.sqrt(-2 * Math.log(u)) * Math.cos(2 * Math.PI * v);
  }
  return normalize({ re, im });
}

export function noisyCopy(raw: number[], sigma: number, seed: number): number[] {
  if (sigma === 0) return raw.slice();
  const rng = mulberry32(seed >>> 0);
  return raw.map((value) => {
    const u = Math.max(rng(), 1e-12);
    const v = rng();
    const g = Math.sqrt(-2 * Math.log(u)) * Math.cos(2 * Math.PI * v);
    return value + sigma * g;
  });
}

function contentHash(v: Vec): string {
  const re: number[] = [];
  const im: number[] = [];
  for (let i = 0; i < v.re.length; i++) {
    re.push(Math.round(v.re[i] * 1e9) / 1e9);
    im.push(Math.round(v.im[i] * 1e9) / 1e9);
  }
  return sha256Text(JSON.stringify({ im, re }));
}

function stableId(body: unknown): string {
  return sha256Text(JSON.stringify(body)).slice(0, 20);
}

function vdotAbs(a: Vec, b: Vec): number {
  let re = 0;
  let im = 0;
  const n = Math.min(a.re.length, b.re.length);
  for (let i = 0; i < n; i++) {
    const cr = a.re[i];
    const ci = -a.im[i];
    re += cr * b.re[i] - ci * b.im[i];
    im += cr * b.im[i] + ci * b.re[i];
  }
  return Math.hypot(re, im);
}

export class HmeEngine {
  config: HmeConfig;
  readonly re: Float64Array;
  readonly im: Float64Array;
  records: Artifact[] = [];
  nodes: LineageNode[] = [];
  edges: LineageEdge[] = [];
  private payloads = new Map<string, Vec>();
  private patterns = new Map<string, Vec>();
  private counter = 0;
  private lastNode: string | null = null;

  constructor(config: Partial<HmeConfig> = {}) {
    this.config = { ...DEFAULTS, ...config };
    const { memorySize, encodingResolution } = this.config;
    if (memorySize < 4) throw new Error("memory_size must be at least 4");
    if (encodingResolution < 2 || encodingResolution > memorySize) {
      throw new Error("encoding_resolution must be in [2, memory_size]");
    }
    this.re = new Float64Array(memorySize * memorySize);
    this.im = new Float64Array(memorySize * memorySize);
  }

  get memorySize(): number {
    return this.config.memorySize;
  }

  energy(): number {
    return l2({ re: this.re, im: this.im });
  }

  record(id: string): Artifact | undefined {
    return this.records.find((item) => item.artifactId === id);
  }

  payload(id: string): Vec | undefined {
    return this.payloads.get(id);
  }

  private at(x: number, y: number): number {
    return x * this.memorySize + y;
  }

  magAt(x: number, y: number): number {
    const i = this.at(x, y);
    return Math.hypot(this.re[i], this.im[i]);
  }

  phaseAt(x: number, y: number): number {
    const i = this.at(x, y);
    return Math.atan2(this.im[i], this.re[i]);
  }

  maxMag(): number {
    let m = 0;
    for (let i = 0; i < this.re.length; i++) m = Math.max(m, Math.hypot(this.re[i], this.im[i]));
    return m;
  }

  patchOf(position: [number, number], height: number, width: number): {
    gx0: number;
    gy0: number;
    gx1: number;
    gy1: number;
    px0: number;
    py0: number;
  } {
    const [x, y] = position;
    const rawX0 = x - Math.floor(height / 2);
    const rawY0 = y - Math.floor(width / 2);
    const gx0 = Math.max(0, rawX0);
    const gy0 = Math.max(0, rawY0);
    const gx1 = Math.min(this.memorySize, rawX0 + height);
    const gy1 = Math.min(this.memorySize, rawY0 + width);
    return { gx0, gy0, gx1, gy1, px0: gx0 - rawX0, py0: gy0 - rawY0 };
  }

  private generate(data: ArrayLike<number>): { vector: Vec; pattern: Vec } {
    let vector = resample(data, this.config.encodingResolution);
    if (this.config.useHannWindow) {
      const w = hanning(vector.re.length);
      const re = new Float64Array(vector.re.length);
      const im = new Float64Array(vector.im.length);
      for (let i = 0; i < w.length; i++) {
        re[i] = vector.re[i] * w[i];
        im[i] = vector.im[i] * w[i];
      }
      vector = { re, im };
    }
    vector = normalize(vector);
    const spectrum = dft(vector.re, vector.im, false);
    const n = spectrum.re.length;
    const outer = zeros(n * n);
    for (let i = 0; i < n; i++) {
      for (let j = 0; j < n; j++) {
        const ar = spectrum.re[i];
        const ai = spectrum.im[i];
        const br = spectrum.re[j];
        const bi = -spectrum.im[j];
        const k = i * n + j;
        outer.re[k] = ar * br - ai * bi;
        outer.im[k] = ar * bi + ai * br;
      }
    }
    let pattern = fft2(outer, n, n, true);
    if (this.config.normalizePatterns) pattern = normalize(pattern);
    return { vector, pattern };
  }

  encode(
    data: number[],
    position: [number, number],
    options: {
      tag?: string;
      strength?: number;
      operation?: string;
      metadata?: Record<string, string | number>;
      symbol?: string | null;
      raw?: number[] | null;
    } = {},
  ): Artifact {
    const strength = options.strength ?? 0.1;
    if (!Number.isFinite(strength)) throw new Error("strength must be finite");
    const [x, y] = position;
    if (x < 0 || y < 0 || x >= this.memorySize || y >= this.memorySize) {
      throw new Error(`position ${x},${y} is outside the field`);
    }
    const { vector, pattern } = this.generate(data);
    const gain = strength;
    const n = this.config.encodingResolution;
    const slice = this.patchOf(position, n, n);
    for (let i = slice.gx0; i < slice.gx1; i++) {
      for (let j = slice.gy0; j < slice.gy1; j++) {
        const pi = (slice.px0 + (i - slice.gx0)) * n + (slice.py0 + (j - slice.gy0));
        const gi = this.at(i, j);
        this.re[gi] += gain * pattern.re[pi];
        this.im[gi] += gain * pattern.im[pi];
      }
    }
    this.counter += 1;
    const tag = options.tag?.trim() || `hme:${String(this.counter).padStart(6, "0")}`;
    const payloadHash = contentHash(vector);
    const patternHash = contentHash(pattern);
    const artifact: Artifact = {
      artifactId: stableId({
        schema: VIEWER_SCHEMA,
        counter: this.counter,
        t: 0,
        tag,
        operation: options.operation ?? "write",
        position,
        payloadHash,
        patternHash,
      }),
      t: 0,
      tag,
      operation: options.operation ?? "write",
      position: [x, y],
      gain,
      writeWeight: 1,
      payloadSize: vector.re.length,
      payloadHash,
      patternHash,
      metadata: { ...(options.metadata ?? {}) },
      raw: options.raw === undefined ? data.slice() : options.raw,
      symbol: options.symbol ?? null,
    };
    this.records.push(artifact);
    this.payloads.set(artifact.artifactId, vector);
    this.patterns.set(artifact.artifactId, pattern);
    while (this.records.length > this.config.maxRecords) {
      const evicted = this.records.shift();
      if (!evicted) break;
      this.payloads.delete(evicted.artifactId);
      this.patterns.delete(evicted.artifactId);
    }
    const nodeId = `memory:${artifact.artifactId}`;
    this.nodes.push({
      nodeId,
      tag: artifact.tag,
      position: artifact.position,
      operation: artifact.operation,
    });
    if (this.lastNode) {
      this.edges.push({ source: this.lastNode, target: nodeId, relation: "next_memory" });
    }
    this.lastNode = nodeId;
    return artifact;
  }

  encodeSymbol(
    symbol: string,
    position: [number, number],
    options: { strength?: number; metadata?: Record<string, string | number> } = {},
  ): Artifact {
    const vector = symbolVector(symbol, this.config.encodingResolution);
    const raw = Array.from(vector.re);
    return this.encode(raw, position, {
      ...options,
      tag: `symbol:${symbol}`,
      symbol,
      raw: null,
      metadata: { symbol, ...(options.metadata ?? {}) },
    });
  }

  retrieve(
    position: [number, number],
    options: {
      query?: number[] | string | null;
      topK?: number;
      threshold?: number;
      radius?: number;
    } = {},
  ): Retrieval {
    const topK = options.topK ?? 5;
    const threshold = options.threshold ?? this.config.relevanceThreshold;
    const radius = Math.max(1, options.radius ?? 4);
    const [qx, qy] = position;
    const x0 = Math.max(0, qx - radius);
    const x1 = Math.min(this.memorySize, qx + radius + 1);
    const y0 = Math.max(0, qy - radius);
    const y1 = Math.min(this.memorySize, qy + radius + 1);
    const h = x1 - x0;
    const w = y1 - y0;
    const window = zeros(h * w);
    for (let i = 0; i < h; i++) {
      for (let j = 0; j < w; j++) {
        const gi = this.at(x0 + i, y0 + j);
        window.re[i * w + j] = this.re[gi];
        window.im[i * w + j] = this.im[gi];
      }
    }
    const surface = fft2(window, h, w, true);
    const surfaceMag = Array.from(surface.re, (re, i) => Math.hypot(re, surface.im[i]));

    let queryVector: Vec | null = null;
    if (typeof options.query === "string") {
      queryVector = symbolVector(options.query, this.config.encodingResolution);
    } else if (options.query) {
      queryVector = normalize(resample(options.query, this.config.encodingResolution));
    }

    const fieldNorm = this.energy();
    const sigma = Math.max(this.memorySize * this.config.retrievalDistanceScale, 1);
    const hits: Hit[] = [];
    for (const artifact of this.records) {
      const payload = this.payloads.get(artifact.artifactId);
      const pattern = this.patterns.get(artifact.artifactId);
      if (!payload || !pattern) continue;
      const dx = artifact.position[0] - qx;
      const dy = artifact.position[1] - qy;
      const distance = Math.hypot(dx, dy);
      const distanceScore = Math.exp(-0.5 * (distance / sigma) ** 2);
      let queryScore = 1;
      if (queryVector) {
        const denom = l2(payload) * l2(queryVector);
        queryScore = denom > EPS ? vdotAbs(payload, queryVector) / denom : 0;
      }
      const slice = this.patchOf(artifact.position, this.config.encodingResolution, this.config.encodingResolution);
      const ph = slice.gx1 - slice.gx0;
      const pw = slice.gy1 - slice.gy0;
      const fieldPatch = zeros(ph * pw);
      const patternPatch = zeros(ph * pw);
      const n = this.config.encodingResolution;
      for (let i = 0; i < ph; i++) {
        for (let j = 0; j < pw; j++) {
          const k = i * pw + j;
          const gi = this.at(slice.gx0 + i, slice.gy0 + j);
          const pi = (slice.px0 + i) * n + (slice.py0 + j);
          fieldPatch.re[k] = this.re[gi];
          fieldPatch.im[k] = this.im[gi];
          patternPatch.re[k] = pattern.re[pi];
          patternPatch.im[k] = pattern.im[pi];
        }
      }
      const denom = l2(fieldPatch) * l2(patternPatch);
      const patternScore = denom > EPS && fieldNorm > EPS ? vdotAbs(fieldPatch, patternPatch) / denom : 0;
      const baseScore = Math.min(1, Math.max(0, 0.38 * distanceScore + 0.42 * queryScore + 0.2 * patternScore));
      if (baseScore < threshold) continue;
      hits.push({
        artifactId: artifact.artifactId,
        tag: artifact.tag,
        baseScore,
        finalScore: baseScore,
        distanceScore,
        queryScore,
        patternScore,
        distance,
      });
    }
    hits.sort((a, b) => b.finalScore - a.finalScore);
    const kept = hits.slice(0, topK);
    let decoded = new Float64Array(this.config.encodingResolution);
    let relevanceScore = 0;
    let outcome: Retrieval["outcome"] = "NO_MATCH";
    if (kept.length) {
      outcome = "MATCH";
      relevanceScore = kept[0].baseScore;
      let weightSum = 0;
      for (const hit of kept) weightSum += Math.max(hit.finalScore, EPS);
      for (const hit of kept) {
        const payload = this.payloads.get(hit.artifactId);
        if (!payload) continue;
        const wgt = Math.max(hit.finalScore, EPS) / weightSum;
        for (let i = 0; i < decoded.length; i++) decoded[i] += wgt * payload.re[i];
      }
    }
    return {
      position: [qx, qy],
      radius,
      relevanceScore,
      outcome,
      hits: kept,
      decodedRe: Array.from(decoded),
      surfaceMag,
      surfaceH: h,
      surfaceW: w,
      queryRe: queryVector ? Array.from(queryVector.re) : null,
    };
  }

  eraseField(): void {
    this.re.fill(0);
    this.im.fill(0);
  }

  dropLedger(): void {
    this.records = [];
    this.payloads.clear();
    this.patterns.clear();
    this.nodes = [];
    this.edges = [];
    this.lastNode = null;
  }

  clear(): void {
    this.eraseField();
    this.dropLedger();
    this.counter = 0;
  }
}

export function seedDemo(engine: HmeEngine): Artifact {
  engine.clear();
  const first = engine.encode([0.1, 0.4, 0.9, 0.2], [20, 22], {
    tag: "reading-001",
    metadata: { source: "sensor-A" },
  });
  engine.encode([0.85, -0.15, 0.05, 0.55], [46, 18], {
    tag: "reading-002",
    metadata: { source: "sensor-B" },
  });
  engine.encode([0.15, 0.72, -0.35, 0.28], [24, 27], {
    tag: "reading-003",
    metadata: { source: "sensor-A" },
  });
  engine.encodeSymbol("beacon", [52, 40], { metadata: { source: "label" } });
  return first;
}

export type QueryMode = "noisy" | "vector" | "symbol" | "spatial";

export type QueryForm = {
  queryRow: number;
  queryCol: number;
  mode: QueryMode;
  sigma: number;
  seed: number;
  vectorText: string;
  symbolText: string;
  topK: number;
  threshold: number;
  selectedId: string | null;
  radius: number;
};

export function parseVector(text: string): number[] | null {
  const parts = text.trim().split(/[\s,]+/).filter(Boolean);
  if (!parts.length) return null;
  const nums = parts.map((part) => Number(part));
  if (nums.some((n) => !Number.isFinite(n))) return null;
  return nums;
}

export function executeQuery(engine: HmeEngine, form: QueryForm): { retrieval: Retrieval | null; error: string | null; queryNote: string } {
  const position: [number, number] = [
    clampIndex(form.queryRow, engine.memorySize),
    clampIndex(form.queryCol, engine.memorySize),
  ];
  const base = { topK: form.topK, threshold: form.threshold, radius: form.radius };
  if (form.mode === "spatial") {
    return {
      retrieval: engine.retrieve(position, { ...base, query: null }),
      error: null,
      queryNote: "No query vector. Item similarity is defined as 1, so rank is proximity plus pattern correlation.",
    };
  }
  if (form.mode === "symbol") {
    const symbol = form.symbolText.trim();
    if (!symbol) return { retrieval: null, error: "Enter a symbol to query.", queryNote: "" };
    return {
      retrieval: engine.retrieve(position, { ...base, query: symbol }),
      error: null,
      queryNote: "Symbol queries use the raw seeded vector. Stored symbol payloads were Hann-windowed on write when that switch is on. Wording similarity is not vector similarity.",
    };
  }
  if (form.mode === "vector") {
    const vector = parseVector(form.vectorText);
    if (!vector) return { retrieval: null, error: "Query vector needs finite numbers.", queryNote: "" };
    return {
      retrieval: engine.retrieve(position, { ...base, query: vector }),
      error: null,
      queryNote: "Numeric queries are resampled and normalized. They do not receive the write-time Hann window.",
    };
  }
  const selected = form.selectedId ? engine.record(form.selectedId) : undefined;
  if (!selected?.raw) {
    return { retrieval: null, error: "Select a numeric ledger item to noise.", queryNote: "" };
  }
  const query = noisyCopy(selected.raw, form.sigma, form.seed);
  return {
    retrieval: engine.retrieve(position, { ...base, query }),
    error: null,
    queryNote: `Noise N(0, ${form.sigma.toFixed(2)}²) added to the raw input of ${selected.tag}, seed ${form.seed}. The engine then normalizes, without a Hann window.`,
  };
}

function clampIndex(value: number, size: number): number {
  if (!Number.isFinite(value)) return 0;
  return Math.max(0, Math.min(size - 1, Math.round(value)));
}

export type ProbeCell = { sigma: number; hits: number; trials: number };

export type ProbeReport = {
  threshold: number;
  radius: number;
  trials: number;
  cells: ProbeCell[];
};

export function noiseProbe(
  engine: HmeEngine,
  artifactId: string,
  sigmas: number[],
  trials: number,
  options: { threshold: number; radius: number },
): ProbeReport {
  const artifact = engine.record(artifactId);
  const raw = artifact?.raw;
  const threshold = options.threshold;
  const radius = options.radius;
  if (!artifact || !raw) return { threshold, radius, trials, cells: [] };
  const cells = sigmas.map((sigma) => {
    let hits = 0;
    for (let seed = 1; seed <= trials; seed++) {
      const result = engine.retrieve(artifact.position, {
        query: noisyCopy(raw, sigma, seed),
        topK: 1,
        threshold,
        radius,
      });
      if (result.outcome === "MATCH" && result.hits[0]?.artifactId === artifactId) hits += 1;
    }
    return { sigma, hits, trials };
  });
  return { threshold, radius, trials, cells };
}
```
## `src/lib/hme/check.ts`

Viewer checks and the four-memory demo. Not modified in the 2026-09-27 UI pass.

```ts
import { HmeEngine, noiseProbe, seedDemo, type QueryForm } from "./engine.ts";
import { sha256Text } from "./sha256.ts";
import { dft } from "./fft.ts";

export type Check = { name: string; pass: boolean; detail: string };

export function runChecks(): Check[] {
  const checks: Check[] = [];
  const sha = sha256Text("abc");
  checks.push({
    name: "sha256",
    pass: sha === "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad",
    detail: sha.slice(0, 12),
  });

  const impulse = dft(Float64Array.of(1, 0, 0, 0), Float64Array.of(0, 0, 0, 0), false);
  const flat = impulse.re.every((v) => Math.abs(v - 1) < 1e-9) && impulse.im.every((v) => Math.abs(v) < 1e-9);
  checks.push({ name: "dft impulse", pass: flat, detail: flat ? "flat spectrum" : "mismatch" });

  const engine = new HmeEngine();
  const item = engine.encode([0.1, 0.4, 0.9, 0.2], [20, 22], {
    tag: "reading-001",
    metadata: { source: "sensor-A" },
  });
  const alone = engine.retrieve([20, 22], { query: [0.12, 0.39, 0.88, 0.21], topK: 1 });
  checks.push({
    name: "readme probe",
    pass: alone.hits[0]?.artifactId === item.artifactId && alone.outcome === "MATCH",
    detail: alone.outcome,
  });

  const crowded = new HmeEngine();
  const a = crowded.encode([0.1, 0.4, 0.9, 0.2], [20, 22], { tag: "A" });
  crowded.encode([0.9, 0.05, -0.8, 0.1], [21, 23], { tag: "B" });
  const picked = crowded.retrieve([20, 22], { query: [0.1, 0.4, 0.9, 0.2], topK: 1 });
  checks.push({
    name: "overlap prefers query",
    pass: picked.hits[0]?.artifactId === a.artifactId,
    detail: picked.hits[0]?.tag ?? "none",
  });

  const keptId = a.artifactId;
  crowded.eraseField();
  const ledgerOnly = crowded.retrieve([20, 22], { query: [0.1, 0.4, 0.9, 0.2], topK: 1 });
  checks.push({
    name: "field erase zeros pattern",
    pass:
      ledgerOnly.hits[0]?.artifactId === keptId &&
      Math.abs(ledgerOnly.hits[0].patternScore) < 1e-9 &&
      ledgerOnly.outcome === "MATCH",
    detail: `pattern ${ledgerOnly.hits[0]?.patternScore ?? "na"}`,
  });

  crowded.dropLedger();
  const fieldless = new HmeEngine();
  fieldless.encode([0.2, 0.2, 0.2, 0.9], [8, 8], { tag: "stay" });
  fieldless.dropLedger();
  const noLedger = fieldless.retrieve([8, 8], { query: [0.2, 0.2, 0.2, 0.9], topK: 1 });
  checks.push({
    name: "ledger drop is NO_MATCH",
    pass: noLedger.outcome === "NO_MATCH" && noLedger.hits.length === 0 && fieldless.energy() > 0,
    detail: noLedger.outcome,
  });

  const spatial = engine.retrieve([20, 22], { query: null, topK: 1 });
  checks.push({
    name: "missing query scores 1",
    pass: spatial.hits[0]?.queryScore === 1,
    detail: String(spatial.hits[0]?.queryScore ?? "na"),
  });

  const hannOn = new HmeEngine({ useHannWindow: true });
  const hannOff = new HmeEngine({ useHannWindow: false });
  const pOn = hannOn.encode([0.1, 0.4, 0.9, 0.2], [4, 4], { tag: "h" }).payloadHash;
  const pOff = hannOff.encode([0.1, 0.4, 0.9, 0.2], [4, 4], { tag: "h" }).payloadHash;
  checks.push({
    name: "hann changes payload",
    pass: pOn !== pOff,
    detail: `${pOn.slice(0, 6)}/${pOff.slice(0, 6)}`,
  });

  const far = new HmeEngine();
  far.encode([0.1, 0.4, 0.9, 0.2], [4, 4], { tag: "near" });
  const rejected = far.retrieve([60, 60], { query: [1, -1, 1, -1], topK: 1, threshold: 0.99 });
  checks.push({
    name: "threshold can reject",
    pass: rejected.outcome === "NO_MATCH",
    detail: rejected.outcome,
  });

  const sym = new HmeEngine();
  const beacon = sym.encodeSymbol("beacon", [10, 10]);
  const other = sym.retrieve([10, 10], { query: "other-word", topK: 1 });
  const same = sym.retrieve([10, 10], { query: "beacon", topK: 1 });
  const sameScore = same.hits[0] ? same.hits[0].queryScore.toFixed(2) : "na";
  const otherScore = other.hits[0] ? other.hits[0].queryScore.toFixed(2) : "na";
  checks.push({
    name: "symbols are exact, not paraphrase",
    pass:
      beacon.tag === "symbol:beacon" &&
      same.hits[0]?.artifactId === beacon.artifactId &&
      (other.hits[0]?.queryScore ?? 1) < 0.85,
    detail: `same ${sameScore} other ${otherScore}`,
  });

  const probeEngine = new HmeEngine();
  const target = seedDemo(probeEngine);
  const open = noiseProbe(probeEngine, target.artifactId, [0], 4, { threshold: 0, radius: 4 });
  const shut = noiseProbe(probeEngine, target.artifactId, [0], 4, { threshold: 0.999, radius: 4 });
  checks.push({
    name: "probe uses threshold",
    pass: open.cells[0]?.hits === 4 && shut.cells[0]?.hits === 0 && shut.threshold === 0.999,
    detail: `${open.cells[0]?.hits ?? "na"}/4 open, ${shut.cells[0]?.hits ?? "na"}/4 shut`,
  });

  return checks;
}

export function demoForm(selectedId: string): QueryForm {
  return {
    queryRow: 20,
    queryCol: 22,
    mode: "noisy",
    sigma: 0.15,
    seed: 7,
    vectorText: "0.12, 0.39, 0.88, 0.21",
    symbolText: "beacon",
    topK: 4,
    threshold: 0,
    selectedId,
    radius: 4,
  };
}

export function bootDemo(): { engine: HmeEngine; form: QueryForm } {
  const engine = new HmeEngine();
  const first = seedDemo(engine);
  return { engine, form: demoForm(first.artifactId) };
}
```
## `src/components/hme/plate.tsx`

Offscreen canvas painted to an image. Brass cross is a memory. Paper cross is a search. Solid brass box is the selected memory. Faint brass boxes are the others. Dashed box is the search window.

```tsx
import { useEffect, useRef, useState } from "react";
import type { HmeEngine } from "@/lib/hme/engine";

type PlateProps = {
  engine: HmeEngine;
  rev: number;
  view: "magnitude" | "phase";
  writeRow: number;
  writeCol: number;
  queryRow: number;
  queryCol: number;
  selectedId: string | null;
  radius: number;
  onPick: (row: number, col: number) => void;
};

const INK: [number, number, number] = [16, 20, 17];
const BRASS: [number, number, number] = [196, 163, 90];
const PAPER: [number, number, number] = [231, 239, 230];

function mix(a: [number, number, number], b: [number, number, number], t: number): [number, number, number] {
  return [
    Math.round(a[0] + (b[0] - a[0]) * t),
    Math.round(a[1] + (b[1] - a[1]) * t),
    Math.round(a[2] + (b[2] - a[2]) * t),
  ];
}

function magColor(t: number): [number, number, number] {
  if (t < 0.55) return mix(INK, BRASS, t / 0.55);
  return mix(BRASS, PAPER, (t - 0.55) / 0.45);
}

function paint(
  engine: HmeEngine,
  css: number,
  view: PlateProps["view"],
  writeRow: number,
  writeCol: number,
  queryRow: number,
  queryCol: number,
  selectedId: string | null,
  radius: number,
): string {
  const canvas = document.createElement("canvas");
  const dpr = Math.min(window.devicePixelRatio || 1, 2);
  canvas.width = Math.round(css * dpr);
  canvas.height = Math.round(css * dpr);
  const ctx = canvas.getContext("2d");
  if (!ctx) return "";
  ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
  const n = engine.memorySize;
  const cell = css / n;
  const peak = engine.maxMag();
  ctx.fillStyle = "#101411";
  ctx.fillRect(0, 0, css, css);
  for (let row = 0; row < n; row++) {
    for (let col = 0; col < n; col++) {
      const mag = engine.magAt(row, col);
      if (mag <= 1e-8 || peak <= 1e-8) continue;
      const rgb =
        view === "phase"
          ? mix(INK, mix(BRASS, PAPER, 0.5 + 0.5 * Math.cos(engine.phaseAt(row, col))), Math.min(1, mag / peak))
          : magColor(Math.log1p(mag) / Math.log1p(peak));
      ctx.fillStyle = `rgb(${rgb[0]} ${rgb[1]} ${rgb[2]})`;
      ctx.fillRect(col * cell, row * cell, Math.ceil(cell), Math.ceil(cell));
    }
  }
  ctx.strokeStyle = "rgba(231,239,230,0.08)";
  ctx.lineWidth = 1;
  ctx.beginPath();
  for (let g = 0; g <= n; g += 8) {
    ctx.moveTo(g * cell + 0.5, 0);
    ctx.lineTo(g * cell + 0.5, css);
    ctx.moveTo(0, g * cell + 0.5);
    ctx.lineTo(css, g * cell + 0.5);
  }
  ctx.stroke();

  const res = engine.config.encodingResolution;
  for (const artifact of engine.records) {
    const slice = engine.patchOf(artifact.position, res, res);
    const selected = artifact.artifactId === selectedId;
    ctx.strokeStyle = selected ? "#c4a35a" : "rgba(196,163,90,0.35)";
    ctx.lineWidth = selected ? 1.5 : 1;
    ctx.strokeRect(
      slice.gy0 * cell + 0.5,
      slice.gx0 * cell + 0.5,
      (slice.gy1 - slice.gy0) * cell - 1,
      (slice.gx1 - slice.gx0) * cell - 1,
    );
  }

  const qx0 = Math.max(0, queryRow - radius);
  const qy0 = Math.max(0, queryCol - radius);
  const qx1 = Math.min(n, queryRow + radius + 1);
  const qy1 = Math.min(n, queryCol + radius + 1);
  ctx.setLineDash([3, 3]);
  ctx.strokeStyle = "rgba(231,239,230,0.85)";
  ctx.lineWidth = 1;
  ctx.strokeRect(qy0 * cell + 0.5, qx0 * cell + 0.5, (qy1 - qy0) * cell - 1, (qx1 - qx0) * cell - 1);
  ctx.setLineDash([]);

  const cross = (row: number, col: number, color: string) => {
    const cx = (col + 0.5) * cell;
    const cy = (row + 0.5) * cell;
    ctx.strokeStyle = color;
    ctx.lineWidth = 1.25;
    ctx.beginPath();
    ctx.moveTo(cx - 5, cy);
    ctx.lineTo(cx + 5, cy);
    ctx.moveTo(cx, cy - 5);
    ctx.lineTo(cx, cy + 5);
    ctx.stroke();
  };
  cross(writeRow, writeCol, "#c4a35a");
  cross(queryRow, queryCol, "#e7efe6");
  return canvas.toDataURL("image/png");
}

export function Plate(props: PlateProps) {
  const host = useRef<HTMLDivElement>(null);
  const [src, setSrc] = useState("");

  useEffect(() => {
    const node = host.current;
    if (!node) return;
    const draw = () => {
      const css = node.clientWidth;
      if (css < 8) return;
      setSrc(
        paint(
          props.engine,
          css,
          props.view,
          props.writeRow,
          props.writeCol,
          props.queryRow,
          props.queryCol,
          props.selectedId,
          props.radius,
        ),
      );
    };
    draw();
    const observer = new ResizeObserver(draw);
    observer.observe(node);
    return () => observer.disconnect();
  }, [props]);

  const pickAt = (clientX: number, clientY: number, rect: DOMRect) => {
    const n = props.engine.memorySize;
    const col = Math.min(n - 1, Math.max(0, Math.floor(((clientX - rect.left) / rect.width) * n)));
    const row = Math.min(n - 1, Math.max(0, Math.floor(((clientY - rect.top) / rect.height) * n)));
    props.onPick(row, col);
  };

  return (
    <div
      ref={host}
      role="application"
      tabIndex={0}
      aria-label="Holographic memory field. Click or use arrow keys to place the active position. Row increases downward."
      className="aspect-square w-full touch-none rounded-lg bg-bg"
      onPointerDown={(event) => {
        pickAt(event.clientX, event.clientY, event.currentTarget.getBoundingClientRect());
        event.currentTarget.focus();
      }}
    >
      {src ? (
        <img src={src} alt="" className="plate-img h-full w-full rounded-lg" />
      ) : null}
    </div>
  );
}
```
## `src/routes/index.tsx`

Explore / Details page. Updated 2026-09-27. `@/` is the `src/` alias. `Check` comes from `lucide-react`.

```tsx
import { createFileRoute } from "@tanstack/react-router";
import { Check } from "lucide-react";
import { useMemo, useState } from "react";
import { Plate } from "@/components/hme/plate";
import {
  executeQuery,
  noiseProbe,
  parseVector,
  seedDemo,
  type HmeEngine,
  type ProbeReport,
  type QueryForm,
  type Retrieval,
} from "@/lib/hme/engine";
import { bootDemo, runChecks } from "@/lib/hme/check";

export const Route = createFileRoute("/")({ component: Home });

type Place = "write" | "query";
type View = "magnitude" | "phase";
type Layer = "explore" | "details";

function plainNote(mode: QueryForm["mode"]): string {
  if (mode === "noisy") return "The selected memory was distorted, then searched for at the paper cross.";
  if (mode === "vector") return "Searching with the values you typed, at the paper cross.";
  if (mode === "symbol") return "Searching for that exact symbol. Similar wording is not a similar pattern.";
  return "Searching by place only.";
}

function Home() {
  const boot = useMemo(() => bootDemo(), []);
  const checks = useMemo(() => runChecks(), []);
  const [engine] = useState<HmeEngine>(() => boot.engine);
  const [form, setForm] = useState<QueryForm>(() => boot.form);
  const [rev, setRev] = useState(0);
  const [view, setView] = useState<View>("magnitude");
  const [place, setPlace] = useState<Place>("write");
  const [writeRow, setWriteRow] = useState(30);
  const [writeCol, setWriteCol] = useState(34);
  const [tag, setTag] = useState("reading-004");
  const [kind, setKind] = useState<"vector" | "symbol">("vector");
  const [vectorText, setVectorText] = useState("0.3, 0.1, 0.6, 0.8");
  const [symbolText, setSymbolText] = useState("dock");
  const [strength, setStrength] = useState(0.1);
  const [hann, setHann] = useState(true);
  const [writeError, setWriteError] = useState<string | null>(null);
  const [probe, setProbe] = useState<ProbeReport | null>(null);
  const [layer, setLayer] = useState<Layer>("explore");
  const opened = executeQuery(engine, form);
  const showDetails = layer === "details";

  const refresh = (next?: Partial<QueryForm>) => {
    if (next) setForm((current) => ({ ...current, ...next }));
    setRev((value) => value + 1);
  };

  const pick = (row: number, col: number) => {
    if (place === "write") {
      setWriteRow(row);
      setWriteCol(col);
    } else {
      refresh({ queryRow: row, queryCol: col });
    }
  };

  const nudge = (dRow: number, dCol: number) => {
    const n = engine.memorySize;
    if (place === "write") {
      setWriteRow((row) => Math.max(0, Math.min(n - 1, row + dRow)));
      setWriteCol((col) => Math.max(0, Math.min(n - 1, col + dCol)));
    } else {
      refresh({
        queryRow: Math.max(0, Math.min(n - 1, form.queryRow + dRow)),
        queryCol: Math.max(0, Math.min(n - 1, form.queryCol + dCol)),
      });
    }
  };

  const write = () => {
    try {
      engine.config.useHannWindow = hann;
      let artifact;
      if (kind === "symbol") {
        const symbol = symbolText.trim();
        if (!symbol) {
          setWriteError("Enter an exact symbol.");
          return;
        }
        artifact = engine.encodeSymbol(symbol, [writeRow, writeCol], { strength });
      } else {
        const vector = parseVector(vectorText);
        if (!vector) {
          setWriteError("Vector needs finite numbers, separated by commas.");
          return;
        }
        artifact = engine.encode(vector, [writeRow, writeCol], {
          tag: tag.trim() || undefined,
          strength,
        });
      }
      setWriteError(null);
      setProbe(null);
      refresh({
        selectedId: artifact.artifactId,
        mode: kind === "symbol" ? "symbol" : form.mode,
        symbolText: kind === "symbol" ? symbolText.trim() : form.symbolText,
      });
    } catch (error) {
      setWriteError(error instanceof Error ? error.message : "Write failed");
    }
  };

  const selected = form.selectedId ? engine.record(form.selectedId) : undefined;
  const status =
    engine.records.length === 0 && engine.energy() > 1e-8
      ? "Records removed. The picture remains, but a search can no longer name a memory."
      : engine.records.length > 0 && engine.energy() <= 1e-8
        ? "Field erased. Records remain, so a search can still name a memory, but the field score is zero."
        : "The field and the records are both in play.";

  return (
    <main className="mx-auto max-w-6xl px-4 py-4 sm:px-6 sm:py-6">
      <header className="mb-4">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <p className="font-mono text-xs tracking-widest text-accent uppercase">HME Plate · Interactive memory demo</p>
          <div className="flex rounded-lg bg-surface p-1" role="group" aria-label="How much machinery to show">
            <button type="button" className="seg" aria-pressed={layer === "explore"} onClick={() => setLayer("explore")}>
              Explore
            </button>
            <button type="button" className="seg" aria-pressed={layer === "details"} onClick={() => setLayer("details")}>
              Details
            </button>
          </div>
        </div>
        <h1 className="mt-2 max-w-xl text-balance text-3xl font-medium tracking-tight sm:text-4xl">Explore HME</h1>
        <div className="mt-3 grid max-w-2xl gap-2 text-sm leading-relaxed text-muted">
          <p>HME Plate lets you store, search, and disrupt memories to see how the Holographic Memory Engine retrieves information.</p>
          <p>Not a chatbot: this is the actual numerical memory mechanism that an AI application could connect to.</p>
        </div>
        <p className="mt-3 font-mono text-xs text-muted tabular-nums">
          {engine.memorySize}² complex · {engine.config.encodingResolution}-point patterns · {engine.records.length} records · energy {engine.energy().toFixed(3)}
        </p>
      </header>

      <details className="panel mb-4 px-4 py-3 text-sm">
        <summary className="cursor-pointer font-medium">Quick start</summary>
        {showDetails ? (
          <ol className="mt-3 grid gap-3">
            <li>
              <p className="font-medium">1. Start with a memory</p>
              <p className="text-muted">The demo begins with four example memories already stored. Their patterns appear on the plate.</p>
            </li>
            <li>
              <p className="font-medium">2. Query a memory</p>
              <p className="text-muted">Select Place search, then tap somewhere on the plate. Watch the result change as you move the search.</p>
            </li>
            <li>
              <p className="font-medium">3. Make the clue imperfect</p>
              <p className="text-muted">Choose Noisy memory and increase Noise level. See how much distortion the system can tolerate while still retrieving the intended memory.</p>
            </li>
            <li>
              <p className="font-medium">4. See why it chose something</p>
              <p className="text-muted">The result shows how proximity, similarity, and the field contributed to the ranking.</p>
            </li>
            <li>
              <p className="font-medium">5. Break it on purpose</p>
              <p className="text-muted">
                Try Erase field, keep records and Remove records, keep field. These experiments show what each part of HME contributes. Hit Restore the demo whenever you want to start over.
              </p>
            </li>
          </ol>
        ) : (
          <ol className="mt-3 grid gap-3">
            <li>
              <p className="font-medium">1. Search a memory</p>
              <p className="text-muted">Choose Place search and tap the plate to search the four example memories.</p>
            </li>
            <li>
              <p className="font-medium">2. Add noise</p>
              <p className="text-muted">Choose Noisy memory and raise Noise level to see whether HME still finds the intended memory.</p>
            </li>
            <li>
              <p className="font-medium">3. Break it on purpose</p>
              <p className="text-muted">Remove the field or the records and see what changes. Restore the demo whenever you want to start over.</p>
            </li>
          </ol>
        )}
      </details>

      <div className="grid items-start gap-4 lg:grid-cols-[minmax(0,1.25fr)_minmax(18rem,0.8fr)]">
        <section className="panel order-1 p-3 sm:p-4 lg:col-start-1 lg:row-start-1">
            <div className="mb-3 flex flex-wrap items-center justify-between gap-3">
              <div className="flex rounded-lg bg-bg p-1" role="group" aria-label="Field view">
                <button type="button" className="seg" aria-pressed={view === "magnitude"} onClick={() => setView("magnitude")}>
                  Magnitude
                </button>
                <button type="button" className="seg" aria-pressed={view === "phase"} onClick={() => setView("phase")}>
                  Phase
                </button>
              </div>
              <div className="flex rounded-lg bg-bg p-1" role="group" aria-label="What a click places">
                <button type="button" className="seg" aria-pressed={place === "write"} onClick={() => setPlace("write")}>
                  Place memory
                </button>
                <button type="button" className="seg" aria-pressed={place === "query"} onClick={() => setPlace("query")}>
                  Place search
                </button>
              </div>
            </div>
            <div
              onKeyDown={(event) => {
                const step = event.shiftKey ? 4 : 1;
                if (event.key === "ArrowUp") nudge(-step, 0);
                else if (event.key === "ArrowDown") nudge(step, 0);
                else if (event.key === "ArrowLeft") nudge(0, -step);
                else if (event.key === "ArrowRight") nudge(0, step);
                else return;
                event.preventDefault();
              }}
            >
              <Plate
                engine={engine}
                rev={rev}
                view={view}
                writeRow={writeRow}
                writeCol={writeCol}
                queryRow={form.queryRow}
                queryCol={form.queryCol}
                selectedId={form.selectedId}
                radius={form.radius}
                onPick={pick}
              />
            </div>
            <ul className="mt-3 flex flex-wrap gap-x-4 gap-y-1 text-xs text-muted">
              <li>
                <span className="font-mono text-accent">+</span> Memory position{" "}
                <span className="font-mono tabular-nums">({writeRow}, {writeCol})</span>
              </li>
              <li>
                <span className="font-mono text-fg">+</span> Search position{" "}
                <span className="font-mono tabular-nums">({form.queryRow}, {form.queryCol})</span>
              </li>
              <li className="inline-flex items-center gap-1.5">
                <span className="inline-block size-3 rounded-sm border-2 border-accent" aria-hidden="true" />
                Selected memory
              </li>
              <li className="inline-flex items-center gap-1.5">
                <span className="inline-block size-3 rounded-sm border border-accent/40" aria-hidden="true" />
                Other memories
              </li>
              <li className="inline-flex items-center gap-1.5">
                <span className="inline-block size-3 rounded-sm border border-dashed border-fg/80" aria-hidden="true" />
                Search window
              </li>
            </ul>
            <p className="mt-2 text-xs text-muted">
              {view === "magnitude" ? "Magnitude: where field activity is strongest." : "Phase: the underlying complex-valued alignment."}
              {showDetails ? " Row down, column across." : ""}
            </p>
            <p className="mt-1 text-sm text-muted">{status}</p>
          </section>

        <div className="order-2 grid content-start gap-4 lg:col-start-2 lg:row-span-2 lg:row-start-1">
          <section className="panel grid gap-3 p-4">
            <h2 className="flex items-baseline gap-2 text-sm font-medium">
              <span className="font-mono text-xs text-accent">1</span>
              Store
              {showDetails ? <span className="font-mono text-xs font-normal text-muted">write</span> : null}
            </h2>
            <div className="flex rounded-lg bg-bg p-1" role="group" aria-label="Write kind">
              <button type="button" className="seg flex-1" aria-pressed={kind === "vector"} onClick={() => setKind("vector")}>
                Vector
              </button>
              <button type="button" className="seg flex-1" aria-pressed={kind === "symbol"} onClick={() => setKind("symbol")}>
                Symbol
              </button>
            </div>
            {kind === "vector" ? (
              <>
                <label className="grid gap-1 text-xs text-muted">
                  Tag
                  <input className="field" value={tag} onChange={(event) => setTag(event.target.value)} />
                </label>
                <label className="grid gap-1 text-xs text-muted">
                  Values
                  {showDetails ? <span className="font-mono"> numeric vector</span> : null}
                  <input className="field" value={vectorText} onChange={(event) => setVectorText(event.target.value)} spellCheck={false} />
                </label>
              </>
            ) : (
              <label className="grid gap-1 text-xs text-muted">
                Exact symbol
                <input className="field" value={symbolText} onChange={(event) => setSymbolText(event.target.value)} spellCheck={false} />
              </label>
            )}
            <label className="grid gap-1 text-xs text-muted">
              Strength {strength.toFixed(2)}
              <input
                type="range"
                min={0.02}
                max={0.4}
                step={0.01}
                value={strength}
                onChange={(event) => setStrength(Number(event.target.value))}
              />
            </label>
            <label className="flex min-h-11 items-center gap-2 text-sm">
              <input
                type="checkbox"
                checked={hann}
                onChange={(event) => {
                  const next = event.target.checked;
                  setHann(next);
                  engine.config.useHannWindow = next;
                }}
              />
              Soften edges on later stores
              {showDetails ? <span className="font-mono text-xs text-muted">Hann window</span> : null}
            </label>
            {writeError ? <p className="text-sm text-accent">{writeError}</p> : null}
            <button type="button" className="btn btn-accent" onClick={write}>
              Store memory
            </button>
          </section>

          <section className="panel grid gap-3 p-4">
            <h2 className="flex items-baseline gap-2 text-sm font-medium">
              <span className="font-mono text-xs text-accent">2</span>
              Search
              {showDetails ? <span className="font-mono text-xs font-normal text-muted">query</span> : null}
            </h2>
            <div className="grid grid-cols-2 gap-1 rounded-lg bg-bg p-1 sm:grid-cols-4 lg:grid-cols-2" role="group" aria-label="Search mode">
              {(
                [
                  ["noisy", "Noisy memory"],
                  ["vector", "Vector"],
                  ["symbol", "Symbol"],
                  ["spatial", "Spatial"],
                ] as const
              ).map(([mode, label]) => (
                <button key={mode} type="button" className="seg w-full px-2 text-center" aria-pressed={form.mode === mode} onClick={() => refresh({ mode })}>
                  {label}
                </button>
              ))}
            </div>
            {form.mode === "vector" ? (
              <label className="grid gap-1 text-xs text-muted">
                Search values
                {showDetails ? <span className="font-mono"> query vector</span> : null}
                <input className="field" value={form.vectorText} spellCheck={false} onChange={(event) => refresh({ vectorText: event.target.value })} />
              </label>
            ) : null}
            {form.mode === "symbol" ? (
              <label className="grid gap-1 text-xs text-muted">
                Exact symbol
                <input className="field" value={form.symbolText} spellCheck={false} onChange={(event) => refresh({ symbolText: event.target.value })} />
              </label>
            ) : null}
            {form.mode === "noisy" ? (
              <div className="grid gap-3">
                <label className="grid gap-1 text-xs text-muted">
                  Noise level {form.sigma.toFixed(2)}
                  {showDetails ? <span className="font-mono"> sigma</span> : null}
                  <input type="range" min={0} max={1.25} step={0.01} value={form.sigma} onChange={(event) => refresh({ sigma: Number(event.target.value) })} />
                </label>
                <label className="grid gap-1 text-xs text-muted">
                  Seed
                  <input className="field" type="number" value={form.seed} onChange={(event) => refresh({ seed: Number(event.target.value) || 0 })} />
                </label>
              </div>
            ) : null}
            <div className="grid grid-cols-2 gap-3">
              <label className="grid gap-1 text-xs text-muted">
                Results
                {showDetails ? <span className="font-mono"> top k</span> : null}
                <input className="field" type="number" min={1} max={8} value={form.topK} onChange={(event) => refresh({ topK: Math.max(1, Math.min(8, Number(event.target.value) || 1)) })} />
              </label>
              <label className="grid gap-1 text-xs text-muted">
                Threshold
                <input className="field" type="number" min={0} max={1} step={0.05} value={form.threshold} onChange={(event) => refresh({ threshold: Math.max(0, Math.min(1, Number(event.target.value) || 0)) })} />
              </label>
            </div>
            <p className="text-xs text-muted">
              {showDetails
                ? "Threshold eligibility is not proof. Default is zero, so almost any candidate can MATCH."
                : "Raise this and a weak match becomes no match. The default is zero, so almost anything passes."}
            </p>
          </section>

          <Ledger
            engine={engine}
            selectedId={form.selectedId}
            showDetails={showDetails}
            onSelect={(id) => {
              const artifact = engine.record(id);
              setProbe(null);
              refresh({
                selectedId: id,
                queryRow: artifact?.position[0] ?? form.queryRow,
                queryCol: artifact?.position[1] ?? form.queryCol,
              });
            }}
          />
        </div>

        <div className="order-3 lg:col-start-1 lg:row-start-2">
          <Readout
            retrieval={opened.retrieval}
            error={opened.error}
            note={opened.queryNote}
            plain={plainNote(form.mode)}
            engine={engine}
            showDetails={showDetails}
          />
        </div>
      </div>

      <div className="mt-4 grid items-start gap-4 lg:grid-cols-2">
        <section className="panel grid gap-3 p-4">
          <p className="font-mono text-xs tracking-widest text-accent uppercase">Experiment</p>
          <h2 className="text-sm font-medium">What does the memory need?</h2>
          <p className="text-sm text-muted">Remove one part of HME and see what happens to retrieval.</p>
          <button
            type="button"
            className="btn"
            onClick={() => {
              engine.eraseField();
              setProbe(null);
              refresh();
            }}
          >
            Erase field, keep records
          </button>
          <button
            type="button"
            className="btn"
            onClick={() => {
              engine.dropLedger();
              setProbe(null);
              refresh({ selectedId: null, mode: "spatial" });
            }}
          >
            Remove records, keep field
          </button>
          <button
            type="button"
            className="btn"
            onClick={() => {
              engine.config.useHannWindow = true;
              setHann(true);
              const first = seedDemo(engine);
              setProbe(null);
              setWriteError(null);
              setForm({
                queryRow: 20,
                queryCol: 22,
                mode: "noisy",
                sigma: 0.15,
                seed: 7,
                vectorText: "0.12, 0.39, 0.88, 0.21",
                symbolText: "beacon",
                topK: 4,
                threshold: 0,
                selectedId: first.artifactId,
                radius: 4,
              });
              setRev((value) => value + 1);
            }}
          >
            Restore the demo
          </button>
          {showDetails ? (
            <p className="text-xs text-muted">
              Ablation. Erase field, keep ledger: pattern correlation goes to zero. Drop ledger, keep field: identity retrieval stops. An evicted record would leave its field contribution behind.
            </p>
          ) : null}
        </section>

        <section className="panel grid gap-3 p-4">
          <p className="font-mono text-xs tracking-widest text-accent uppercase">Experiment</p>
          <h2 className="text-sm font-medium">How much noise can it handle?</h2>
          <p className="text-sm text-muted">Gradually distort a stored memory and test whether HME still retrieves the intended item first.</p>
          <button
            type="button"
            className="btn"
            disabled={!selected?.raw}
            onClick={() => {
              if (!form.selectedId) return;
              setProbe(noiseProbe(engine, form.selectedId, [0, 0.25, 0.5, 1], 8, { threshold: form.threshold, radius: form.radius }));
            }}
          >
            Run the test
          </button>
          {!selected?.raw ? <p className="text-xs text-muted">Pick a numeric memory. A symbol has no raw values to distort.</p> : null}
          {showDetails && !probe ? (
            <p className="text-xs text-muted">
              Seeds 1–8 at the selected memory’s own position, top-1, using the retrieval threshold and window radius. Not the search seed or noise level, and not the published HME-NN study.
            </p>
          ) : null}
          {probe ? (
            <>
              <p className="font-mono text-xs text-muted tabular-nums">
                Counted at threshold {probe.threshold.toFixed(2)} · window radius {probe.radius}
                {probe.threshold !== form.threshold
                  ? `. Retrieval threshold is now ${form.threshold.toFixed(2)}; run again to use it.`
                  : ""}
              </p>
              {showDetails ? (
                <p className="text-xs text-muted">Seeds 1–8 at the item’s own position. A trial counts only when that item is top-1 and clears the threshold. Not the search sigma or seed.</p>
              ) : null}
              <table className="w-full text-left text-sm">
                <thead className="text-xs text-muted">
                  <tr>
                    <th className="py-1 font-medium">{showDetails ? "Sigma" : "Noise"}</th>
                    <th className="py-1 font-medium">{showDetails ? `Top-1 ≥ ${probe.threshold.toFixed(2)}` : "Still first"}</th>
                  </tr>
                </thead>
                <tbody className="font-mono tabular-nums">
                  {probe.cells.map((cell) => (
                    <tr key={cell.sigma} className="border-t border-line">
                      <td className="py-1.5">{cell.sigma.toFixed(2)}</td>
                      <td className="py-1.5">
                        {cell.hits}/{cell.trials}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </>
          ) : null}
        </section>
      </div>

      {showDetails ? (
        <section className="panel mt-4 px-4 py-3 text-sm">
          <h2 className="font-medium">Scoring</h2>
          <ul className="mt-3 grid gap-2 text-muted">
            <li>Rank = 0.38 proximity + 0.42 absolute item/query similarity + 0.20 field/pattern correlation.</li>
            <li>relevance_score is the top hit’s base score. It is not a probability of being correct.</li>
            <li>MATCH means the hit cleared the threshold. It does not certify identity.</li>
            <li>decoded_vector blends retained payloads. The inverse-FFT surface is not that vector.</li>
            <li>Strings hash to seeded vectors. Similar wording is not similar geometry. This viewer is not bit-identical to the NumPy engine.</li>
          </ul>
          {checks.every((check) => check.pass) ? (
            <p className="mt-3 text-xs text-muted">{checks.length} viewer checks passed, including the readme probe, field erase, and ledger drop.</p>
          ) : null}
        </section>
      ) : null}

      <details className="panel mt-4 px-4 py-3 text-sm">
        <summary className="cursor-pointer font-medium">Technical details</summary>
        <h2 className="mt-3 text-sm font-medium">Model scope</h2>
        <p className="mt-2 leading-relaxed text-muted">
          Released field-plus-ledger model: spatial FFT-pattern superposition plus a retained artifact ledger. Not consolidation, not SAL-1, not standard HRR binding, and not field-only identity recovery.
        </p>
      </details>

      <footer className="mt-6 grid gap-3 border-t border-line pt-4 text-xs text-muted">
        {!checks.every((check) => check.pass) ? (
          <p>
            Viewer checks failed:{" "}
            {checks
              .filter((check) => !check.pass)
              .map((check) => check.name)
              .join(", ")}
            .
          </p>
        ) : null}
        <p>
          Browser instrument of the released field-plus-ledger model from{" "}
          <a className="text-fg underline decoration-line underline-offset-2" href="https://github.com/donaldtuttle/HME">
            donaldtuttle/HME
          </a>
          . It does not visualize consolidation or SAL-1.
          {showDetails
            ? " Salience stays off. Artifact ids are viewer insertion ids, not NumPy byte hashes. The lineage graph is insertion order, not a Merkle chain."
            : ""}
        </p>
      </footer>
    </main>
  );
}

function Readout({
  retrieval,
  error,
  note,
  plain,
  engine,
  showDetails,
}: {
  retrieval: Retrieval | null;
  error: string | null;
  note: string;
  plain: string;
  engine: HmeEngine;
  showDetails: boolean;
}) {
  if (error || !retrieval) {
    return (
      <section className="panel p-4">
        <h2 className="flex items-baseline gap-2 text-sm font-medium">
          <span className="font-mono text-xs text-accent">3</span>
          Result
        </h2>
        <p className="mt-2 text-sm text-muted">{error ?? "No search yet."}</p>
      </section>
    );
  }
  const top = retrieval.hits[0];
  const cleared = retrieval.outcome === "MATCH";
  return (
    <section className="panel grid gap-4 p-4">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <h2 className="flex items-baseline gap-2 text-sm font-medium">
          <span className="font-mono text-xs text-accent">3</span>
          Result
          {showDetails ? <span className="font-mono text-xs font-normal text-muted">retrieval</span> : null}
        </h2>
        <p className={`inline-block rounded-md px-2 py-1 font-mono text-xs ${cleared ? "bg-accent text-ink" : "bg-elevated text-fg"}`}>
          {retrieval.outcome}
        </p>
      </div>
      {top ? (
        <div className="grid gap-1">
          <p className="text-xs text-muted">Best match</p>
          <p className="text-lg font-medium tracking-tight">{top.tag}</p>
          <p className="font-mono text-sm tabular-nums">Match score {top.baseScore.toFixed(3)}</p>
          <p className={`flex items-center gap-1.5 text-sm ${cleared ? "text-accent" : "text-muted"}`}>
            {cleared ? <Check className="size-4" aria-hidden="true" /> : null}
            {cleared ? "Cleared the retrieval threshold" : "Below the retrieval threshold"}
          </p>
        </div>
      ) : (
        <div className="grid gap-1">
          <p className="text-lg font-medium tracking-tight">No match</p>
          <p className="text-sm text-muted">Nothing cleared the retrieval threshold.</p>
        </div>
      )}
      <p className="text-sm text-muted">{plain}</p>
      {showDetails ? <p className="text-xs text-muted">{note}</p> : null}
      {top ? (
        <div>
          <p className="text-sm font-medium">Why it ranked first</p>
          <p className="mt-1 font-mono text-xs text-muted tabular-nums">
            Similarity {top.queryScore.toFixed(2)} · Proximity {top.distanceScore.toFixed(2)} · Field {top.patternScore.toFixed(2)}
          </p>
          <p className="mt-2 text-xs text-muted">Scores rank candidates. They are not probabilities.</p>
        </div>
      ) : (
        <p className="text-xs text-muted">Scores rank candidates. They are not probabilities.</p>
      )}
      {showDetails && top ? <MixBar hit={top} /> : null}
      {showDetails ? (
        <p className="font-mono text-xs text-muted tabular-nums">
          relevance {retrieval.relevanceScore.toFixed(3)} · window radius {retrieval.radius} at ({retrieval.position[0]}, {retrieval.position[1]})
        </p>
      ) : null}
      {retrieval.hits.length > 1 ? (
        <ul className="grid gap-2">
          {retrieval.hits.slice(1).map((hit, index) => (
            <li key={hit.artifactId} className="rounded-lg bg-bg px-3 py-2">
              <div className="flex items-baseline justify-between gap-3">
                <p className="truncate text-sm">
                  {index + 2}. {hit.tag}
                </p>
                <p className="font-mono text-xs tabular-nums text-muted">{hit.baseScore.toFixed(3)}</p>
              </div>
              {showDetails ? (
                <p className="mt-1 font-mono text-xs text-muted tabular-nums">
                  prox {hit.distanceScore.toFixed(2)} · sim {hit.queryScore.toFixed(2)} · field {hit.patternScore.toFixed(2)} · d {hit.distance.toFixed(1)}
                </p>
              ) : null}
            </li>
          ))}
        </ul>
      ) : null}
      {showDetails ? (
        <>
          <div className="grid gap-3 sm:grid-cols-2">
            <Trace title="Decoded vector" hint="Weighted average of retained payloads" values={retrieval.decodedRe} />
            <Trace
              title="Top stored payload"
              hint={top ? "Processed vector, not the raw input" : "No hit"}
              values={top ? Array.from(engine.payload(top.artifactId)?.re ?? []) : []}
            />
          </div>
          <Surface retrieval={retrieval} />
        </>
      ) : null}
    </section>
  );
}

function MixBar({ hit }: { hit: Retrieval["hits"][number] }) {
  const parts = [
    { label: "0.38 proximity", value: 0.38 * hit.distanceScore, className: "bg-accent" },
    { label: "0.42 similarity", value: 0.42 * hit.queryScore, className: "bg-fg/80" },
    { label: "0.20 pattern", value: 0.2 * hit.patternScore, className: "bg-muted" },
  ];
  const sum = parts.reduce((total, part) => total + part.value, 0) || 1;
  return (
    <div>
      <div className="flex h-2 overflow-hidden rounded-full bg-bg" aria-hidden="true">
        {parts.map((part) => (
          <div key={part.label} className={part.className} style={{ width: `${((part.value / sum) * 100).toFixed(2)}%` }} />
        ))}
      </div>
      <p className="mt-2 text-xs text-muted">Top hit mix before clipping. Brass proximity, paper similarity, muted pattern.</p>
    </div>
  );
}

function Trace({ title, hint, values }: { title: string; hint: string; values: number[] }) {
  const peak = values.reduce((max, value) => Math.max(max, Math.abs(value)), 0);
  const silent = values.length > 0 && peak <= 1e-12;
  return (
    <div>
      <p className="text-sm font-medium">{title}</p>
      <p className="text-xs text-muted">{hint}</p>
      {silent ? (
        <p className="mt-2 flex h-16 items-end font-mono text-xs text-muted">All zeros</p>
      ) : (
        <div className="mt-2 flex h-16 items-end gap-px" aria-hidden="true">
          {values.map((value, index) => {
            const magnitude = Math.abs(value);
            const height = magnitude <= 1e-12 ? 0 : Math.max(6, (magnitude / peak) * 100);
            return (
              <div key={index} className="flex h-full flex-1 items-end">
                <div
                  className={value >= 0 ? "w-full bg-accent" : "w-full bg-fg/50"}
                  style={{ height: `${height.toFixed(2)}%` }}
                />
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}

function Surface({ retrieval }: { retrieval: Retrieval }) {
  const peak = retrieval.surfaceMag.reduce((max, value) => Math.max(max, value), 0) || 1;
  return (
    <div>
      <p className="text-sm font-medium">Decoded surface</p>
      <p className="text-xs text-muted">Inverse FFT of the field window. Separate from the decoded vector.</p>
      <div
        className="mt-2 grid max-w-48 gap-px"
        style={{ gridTemplateColumns: `repeat(${retrieval.surfaceW}, minmax(0, 1fr))` }}
        aria-hidden="true"
      >
        {retrieval.surfaceMag.map((value, index) => {
          const t = Math.log1p(value) / Math.log1p(peak);
          return <div key={index} className="aspect-square bg-accent" style={{ opacity: (0.15 + 0.85 * t).toFixed(3) }} />;
        })}
      </div>
    </div>
  );
}

function Ledger({
  engine,
  selectedId,
  showDetails,
  onSelect,
}: {
  engine: HmeEngine;
  selectedId: string | null;
  showDetails: boolean;
  onSelect: (id: string) => void;
}) {
  return (
    <section className="panel p-4">
      <h2 className="text-sm font-medium">On the plate</h2>
      {showDetails ? <p className="mt-1 font-mono text-xs text-muted">ledger</p> : null}
      {engine.records.length === 0 ? <p className="mt-2 text-sm text-muted">No retained records.</p> : null}
      <ul className="mt-2 grid gap-1">
        {engine.records.map((artifact) => (
          <li key={artifact.artifactId}>
            <button
              type="button"
              onClick={() => onSelect(artifact.artifactId)}
              className={`flex min-h-11 w-full items-center justify-between gap-3 rounded-lg px-2 text-left ${artifact.artifactId === selectedId ? "bg-elevated" : ""}`}
            >
              <span className="min-w-0">
                <span className="block truncate text-sm">{artifact.tag}</span>
                {showDetails ? (
                  <span className="block truncate font-mono text-[11px] text-muted">
                    {artifact.artifactId.slice(0, 10)} · {artifact.payloadHash.slice(0, 10)}
                  </span>
                ) : null}
              </span>
              <span className="font-mono text-xs text-muted tabular-nums">
                ({artifact.position[0]}, {artifact.position[1]})
              </span>
            </button>
          </li>
        ))}
      </ul>
      {showDetails && engine.edges.length ? (
        <ol className="mt-3 grid gap-1 border-t border-line pt-3">
          {engine.nodes.map((node, index) => (
            <li key={node.nodeId} className="font-mono text-xs text-muted">
              {index > 0 ? "next_memory → " : ""}
              {node.tag}
            </li>
          ))}
        </ol>
      ) : null}
    </section>
  );
}
```
## `src/styles.css`

Tailwind v4 theme. Updated 2026-09-27 so range and checkbox use the brass accent.

```css
@import "tailwindcss";

@theme {
  --color-bg: #101411;
  --color-surface: #171d19;
  --color-elevated: #212923;
  --color-fg: #e7efe6;
  --color-muted: #8e9a90;
  --color-accent: #c4a35a;
  --color-ink: #1a1408;
  --color-line: #2c352e;
  --font-sans: "IBM Plex Sans", ui-sans-serif, system-ui, sans-serif;
  --font-mono: "IBM Plex Mono", ui-monospace, monospace;
}

@layer base {
  html {
    -webkit-font-smoothing: antialiased;
    background: var(--color-bg);
    color: var(--color-fg);
  }
  body {
    font-family: var(--font-sans);
    background: var(--color-bg);
    color: var(--color-fg);
    min-height: 100vh;
  }
  button:not(:disabled),
  [role="button"]:not(:disabled) {
    cursor: pointer;
  }
  :focus-visible {
    outline: 2px solid var(--color-accent);
    outline-offset: 2px;
  }
  input,
  textarea {
    color-scheme: dark;
  }
  input[type="range"],
  input[type="checkbox"] {
    accent-color: var(--color-accent);
  }
  ::selection {
    background: var(--color-accent);
    color: var(--color-ink);
  }
}

@layer components {
  .panel {
    background: var(--color-surface);
    border-radius: 0.75rem;
    box-shadow: 0 0 0 1px rgba(231, 239, 230, 0.08);
  }
  .btn {
    min-height: 2.75rem;
    padding-inline: 0.875rem;
    border-radius: 0.625rem;
    background: var(--color-elevated);
    color: var(--color-fg);
    font-size: 0.875rem;
    font-weight: 500;
    box-shadow: 0 0 0 1px rgba(231, 239, 230, 0.08);
    transition: box-shadow 160ms ease;
  }
  .btn:hover:not(:disabled) {
    box-shadow: 0 0 0 1px rgba(231, 239, 230, 0.18);
  }
  .btn:disabled {
    opacity: 0.4;
    cursor: not-allowed;
  }
  .btn-accent {
    background: var(--color-accent);
    color: var(--color-ink);
    box-shadow: none;
  }
  .btn-accent:hover:not(:disabled) {
    box-shadow: none;
    filter: brightness(1.06);
  }
  .field {
    min-height: 2.75rem;
    width: 100%;
    border-radius: 0.625rem;
    background: var(--color-bg);
    color: var(--color-fg);
    padding-inline: 0.75rem;
    box-shadow: inset 0 0 0 1px rgba(231, 239, 230, 0.12);
    font-family: var(--font-mono);
    font-size: 0.875rem;
  }
  .seg {
    min-height: 2.75rem;
    padding-inline: 0.75rem;
    border-radius: 0.5rem;
    color: var(--color-muted);
    font-size: 0.875rem;
    font-weight: 500;
  }
  .seg[aria-pressed="true"] {
    background: var(--color-elevated);
    color: var(--color-fg);
    box-shadow: 0 0 0 1px rgba(196, 163, 90, 0.45);
  }
  .plate-img {
    image-rendering: pixelated;
  }
}
```
