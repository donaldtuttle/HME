/* Ported from the user-owned HME Plate deployment captured 2026-09-26.
 * See SOURCE.md for hashes, transformation scope and compatibility boundaries. */
function complexZeros(e) {
  return {
    re: new Float64Array(e),
    im: new Float64Array(e),
  };
}
function dft(e, t, n) {
  let r = e.length,
    i = new Float64Array(r),
    a = new Float64Array(r),
    o = n ? 1 : -1;
  for (let n = 0; n < r; n++) {
    let s = 0,
      c = 0;
    for (let i = 0; i < r; i++) {
      let a = (o * 2 * Math.PI * n * i) / r,
        l = Math.cos(a),
        u = Math.sin(a);
      ((s += e[i] * l - t[i] * u), (c += e[i] * u + t[i] * l));
    }
    ((i[n] = s), (a[n] = c));
  }
  if (n && r > 0) for (let e = 0; e < r; e++) ((i[e] /= r), (a[e] /= r));
  return {
    re: i,
    im: a,
  };
}
function dft2(e, t, n, r) {
  let i = complexZeros(t * n),
    a = new Float64Array(n),
    o = new Float64Array(n);
  for (let s = 0; s < t; s++) {
    for (let t = 0; t < n; t++)
      ((a[t] = e.re[s * n + t]), (o[t] = e.im[s * n + t]));
    let t = dft(a, o, r);
    for (let e = 0; e < n; e++)
      ((i.re[s * n + e] = t.re[e]), (i.im[s * n + e] = t.im[e]));
  }
  let s = new Float64Array(t),
    c = new Float64Array(t);
  for (let e = 0; e < n; e++) {
    for (let r = 0; r < t; r++)
      ((s[r] = i.re[r * n + e]), (c[r] = i.im[r * n + e]));
    let a = dft(s, c, r);
    for (let r = 0; r < t; r++)
      ((i.re[r * n + e] = a.re[r]), (i.im[r * n + e] = a.im[r]));
  }
  return i;
}
var SHA256_CONSTANTS = new Uint32Array([
  1116352408, 1899447441, 3049323471, 3921009573, 961987163, 1508970993,
  2453635748, 2870763221, 3624381080, 310598401, 607225278, 1426881987,
  1925078388, 2162078206, 2614888103, 3248222580, 3835390401, 4022224774,
  264347078, 604807628, 770255983, 1249150122, 1555081692, 1996064986,
  2554220882, 2821834349, 2952996808, 3210313671, 3336571891, 3584528711,
  113926993, 338241895, 666307205, 773529912, 1294757372, 1396182291,
  1695183700, 1986661051, 2177026350, 2456956037, 2730485921, 2820302411,
  3259730800, 3345764771, 3516065817, 3600352804, 4094571909, 275423344,
  430227734, 506948616, 659060556, 883997877, 958139571, 1322822218, 1537002063,
  1747873779, 1955562222, 2024104815, 2227730452, 2361852424, 2428436474,
  2756734187, 3204031479, 3329325298,
]);
function rotateRight(e, t) {
  return (e >>> t) | (e << (32 - t));
}
function sha256Bytes(e) {
  let t = e.length * 8,
    n = (64 - ((e.length + 1 + 8) % 64)) % 64,
    r = new Uint8Array(e.length + 1 + n + 8);
  (r.set(e), (r[e.length] = 128));
  let i = new DataView(r.buffer);
  (i.setUint32(r.length - 8, Math.floor(t / 2 ** 32)),
    i.setUint32(r.length - 4, t >>> 0));
  let a = 1779033703,
    o = 3144134277,
    s = 1013904242,
    c = 2773480762,
    l = 1359893119,
    u = 2600822924,
    d = 528734635,
    f = 1541459225,
    p = new Uint32Array(64);
  for (let e = 0; e < r.length; e += 64) {
    for (let t = 0; t < 16; t++) p[t] = i.getUint32(e + t * 4);
    for (let e = 16; e < 64; e++) {
      let t =
          rotateRight(p[e - 15], 7) ^
          rotateRight(p[e - 15], 18) ^
          (p[e - 15] >>> 3),
        n =
          rotateRight(p[e - 2], 17) ^
          rotateRight(p[e - 2], 19) ^
          (p[e - 2] >>> 10);
      p[e] = (p[e - 16] + t + p[e - 7] + n) >>> 0;
    }
    let t = a,
      n = o,
      r = s,
      m = c,
      _ = l,
      v = u,
      y = d,
      b = f;
    for (let e = 0; e < 64; e++) {
      let i = rotateRight(_, 6) ^ rotateRight(_, 11) ^ rotateRight(_, 25),
        a = (_ & v) ^ (~_ & y),
        o = (b + i + a + SHA256_CONSTANTS[e] + p[e]) >>> 0,
        s =
          ((rotateRight(t, 2) ^ rotateRight(t, 13) ^ rotateRight(t, 22)) +
            ((t & n) ^ (t & r) ^ (n & r))) >>>
          0;
      ((b = y),
        (y = v),
        (v = _),
        (_ = (m + o) >>> 0),
        (m = r),
        (r = n),
        (n = t),
        (t = (o + s) >>> 0));
    }
    ((a = (a + t) >>> 0),
      (o = (o + n) >>> 0),
      (s = (s + r) >>> 0),
      (c = (c + m) >>> 0),
      (l = (l + _) >>> 0),
      (u = (u + v) >>> 0),
      (d = (d + y) >>> 0),
      (f = (f + b) >>> 0));
  }
  let m = new Uint8Array(32),
    _ = new DataView(m.buffer);
  return ([a, o, s, c, l, u, d, f].forEach((e, t) => _.setUint32(t * 4, e)), m);
}
function bytesToHex(e) {
  return [...sha256Bytes(e)]
    .map((e) => e.toString(16).padStart(2, `0`))
    .join(``);
}
function hashText(e) {
  return bytesToHex(new TextEncoder().encode(e));
}
var EPSILON = 1e-12,
  VIEWER_SCHEMA = `hme-viewer`,
  DEFAULT_CONFIG = {
    memorySize: 64,
    encodingResolution: 16,
    useHannWindow: !0,
    normalizePatterns: !0,
    retrievalDistanceScale: 0.25,
    relevanceThreshold: 0,
    maxRecords: 4096,
  };
function linspace(e) {
  let t = new Float64Array(e);
  if (e <= 1) return t;
  for (let n = 0; n < e; n++) t[n] = n / (e - 1);
  return t;
}
function interpolate(e, t, n) {
  let r = new Float64Array(e.length);
  for (let i = 0; i < e.length; i++) {
    let a = e[i];
    if (a <= t[0]) {
      r[i] = n[0];
      continue;
    }
    if (a >= t[t.length - 1]) {
      r[i] = n[n.length - 1];
      continue;
    }
    let o = 0,
      s = t.length - 1;
    for (; s - o > 1;) {
      let e = (o + s) >> 1;
      t[e] <= a ? (o = e) : (s = e);
    }
    let c = t[s] - t[o],
      l = c === 0 ? 0 : (a - t[o]) / c;
    r[i] = n[o] * (1 - l) + n[s] * l;
  }
  return r;
}
function complexNorm(e) {
  let t = 0;
  for (let n = 0; n < e.re.length; n++)
    t += e.re[n] * e.re[n] + e.im[n] * e.im[n];
  return Math.sqrt(t);
}
function normalize(e) {
  let t = complexNorm(e);
  if (t <= EPSILON)
    return {
      re: e.re.slice(),
      im: e.im.slice(),
    };
  let n = new Float64Array(e.re.length),
    r = new Float64Array(e.im.length);
  for (let i = 0; i < e.re.length; i++)
    ((n[i] = e.re[i] / t), (r[i] = e.im[i] / t));
  return {
    re: n,
    im: r,
  };
}
function hannWindow(e) {
  let t = new Float64Array(e);
  if (e === 1) return ((t[0] = 1), t);
  for (let n = 0; n < e; n++)
    t[n] = 0.5 - 0.5 * Math.cos((2 * Math.PI * n) / (e - 1));
  return t;
}
function resampleReal(e, t) {
  let n = e.length;
  if (n < 1) throw Error(`data must contain at least one value`);
  for (let t = 0; t < n; t++)
    if (!Number.isFinite(e[t]))
      throw Error(`data contains NaN or infinite values`);
  let r = linspace(n);
  return {
    re: interpolate(linspace(t), r, e),
    im: new Float64Array(t),
  };
}
function seededRandom(e) {
  let t = e >>> 0;
  return () => {
    t = (t + 1831565813) >>> 0;
    let e = Math.imul(t ^ (t >>> 15), 1 | t);
    return (
      (e = (e + Math.imul(e ^ (e >>> 7), 61 | e)) ^ e),
      ((e ^ (e >>> 14)) >>> 0) / 4294967296
    );
  };
}
function symbolVector(e, t) {
  let n = sha256Bytes(new TextEncoder().encode(e)),
    r = seededRandom(((n[0] << 24) | (n[1] << 16) | (n[2] << 8) | n[3]) >>> 0),
    i = new Float64Array(t),
    a = new Float64Array(t);
  for (let e = 0; e < t; e++) {
    let t = Math.max(r(), 1e-12),
      n = r();
    i[e] = Math.sqrt(-2 * Math.log(t)) * Math.cos(2 * Math.PI * n);
  }
  return normalize({
    re: i,
    im: a,
  });
}
function addNoise(e, t, n) {
  if (t === 0) return e.slice();
  let r = seededRandom(n >>> 0);
  return e.map((e) => {
    let n = Math.max(r(), 1e-12),
      i = r();
    return e + t * (Math.sqrt(-2 * Math.log(n)) * Math.cos(2 * Math.PI * i));
  });
}
function hashVector(e) {
  let t = [],
    n = [];
  for (let r = 0; r < e.re.length; r++)
    (t.push(Math.round(e.re[r] * 1e9) / 1e9),
      n.push(Math.round(e.im[r] * 1e9) / 1e9));
  return hashText(
    JSON.stringify({
      im: n,
      re: t,
    }),
  );
}
function artifactId(e) {
  return hashText(JSON.stringify(e)).slice(0, 20);
}
function absoluteInnerProduct(e, t) {
  let n = 0,
    r = 0,
    i = Math.min(e.re.length, t.re.length);
  for (let a = 0; a < i; a++) {
    let i = e.re[a],
      o = -e.im[a];
    ((n += i * t.re[a] - o * t.im[a]), (r += i * t.im[a] + o * t.re[a]));
  }
  return Math.hypot(n, r);
}
var ViewerEngine = class {
  config;
  re;
  im;
  records = [];
  nodes = [];
  edges = [];
  payloads = new Map();
  patterns = new Map();
  counter = 0;
  lastNode = null;
  constructor(e = {}) {
    this.config = {
      ...DEFAULT_CONFIG,
      ...e,
    };
    let { memorySize: t, encodingResolution: n } = this.config;
    if (t < 4) throw Error(`memory_size must be at least 4`);
    if (n < 2 || n > t)
      throw Error(`encoding_resolution must be in [2, memory_size]`);
    ((this.re = new Float64Array(t * t)), (this.im = new Float64Array(t * t)));
  }
  get memorySize() {
    return this.config.memorySize;
  }
  energy() {
    return complexNorm({
      re: this.re,
      im: this.im,
    });
  }
  record(e) {
    return this.records.find((t) => t.artifactId === e);
  }
  payload(e) {
    return this.payloads.get(e);
  }
  at(e, t) {
    return e * this.memorySize + t;
  }
  magAt(e, t) {
    let n = this.at(e, t);
    return Math.hypot(this.re[n], this.im[n]);
  }
  phaseAt(e, t) {
    let n = this.at(e, t);
    return Math.atan2(this.im[n], this.re[n]);
  }
  maxMag() {
    let e = 0;
    for (let t = 0; t < this.re.length; t++)
      e = Math.max(e, Math.hypot(this.re[t], this.im[t]));
    return e;
  }
  patchOf(e, t, n) {
    let [r, i] = e,
      a = r - Math.floor(t / 2),
      o = i - Math.floor(n / 2),
      s = Math.max(0, a),
      c = Math.max(0, o);
    return {
      gx0: s,
      gy0: c,
      gx1: Math.min(this.memorySize, a + t),
      gy1: Math.min(this.memorySize, o + n),
      px0: s - a,
      py0: c - o,
    };
  }
  generate(e) {
    let t = resampleReal(e, this.config.encodingResolution);
    if (this.config.useHannWindow) {
      let e = hannWindow(t.re.length),
        n = new Float64Array(t.re.length),
        r = new Float64Array(t.im.length);
      for (let i = 0; i < e.length; i++)
        ((n[i] = t.re[i] * e[i]), (r[i] = t.im[i] * e[i]));
      t = {
        re: n,
        im: r,
      };
    }
    t = normalize(t);
    let n = dft(t.re, t.im, !1),
      r = n.re.length,
      i = complexZeros(r * r);
    for (let e = 0; e < r; e++)
      for (let t = 0; t < r; t++) {
        let a = n.re[e],
          o = n.im[e],
          s = n.re[t],
          c = -n.im[t],
          l = e * r + t;
        ((i.re[l] = a * s - o * c), (i.im[l] = a * c + o * s));
      }
    let a = dft2(i, r, r, !0);
    return (
      this.config.normalizePatterns && (a = normalize(a)),
      {
        vector: t,
        pattern: a,
      }
    );
  }
  encode(e, t, n = {}) {
    let r = n.strength ?? 0.1;
    if (!Number.isFinite(r)) throw Error(`strength must be finite`);
    let [i, a] = t;
    if (i < 0 || a < 0 || i >= this.memorySize || a >= this.memorySize)
      throw Error(`position ${i},${a} is outside the field`);
    let { vector: o, pattern: s } = this.generate(e),
      c = r,
      l = this.config.encodingResolution,
      u = this.patchOf(t, l, l);
    for (let e = u.gx0; e < u.gx1; e++)
      for (let t = u.gy0; t < u.gy1; t++) {
        let n = (u.px0 + (e - u.gx0)) * l + (u.py0 + (t - u.gy0)),
          r = this.at(e, t);
        ((this.re[r] += c * s.re[n]), (this.im[r] += c * s.im[n]));
      }
    this.counter += 1;
    let d = n.tag?.trim() || `hme:${String(this.counter).padStart(6, `0`)}`,
      f = hashVector(o),
      p = hashVector(s),
      m = {
        artifactId: artifactId({
          schema: VIEWER_SCHEMA,
          counter: this.counter,
          t: 0,
          tag: d,
          operation: n.operation ?? `write`,
          position: t,
          payloadHash: f,
          patternHash: p,
        }),
        t: 0,
        tag: d,
        operation: n.operation ?? `write`,
        position: [i, a],
        gain: c,
        writeWeight: 1,
        payloadSize: o.re.length,
        payloadHash: f,
        patternHash: p,
        metadata: {
          ...(n.metadata ?? {}),
        },
        raw: n.raw === void 0 ? e.slice() : n.raw,
        symbol: n.symbol ?? null,
      };
    for (
      this.records.push(m),
        this.payloads.set(m.artifactId, o),
        this.patterns.set(m.artifactId, s);
      this.records.length > this.config.maxRecords;
    ) {
      let e = this.records.shift();
      if (!e) break;
      (this.payloads.delete(e.artifactId), this.patterns.delete(e.artifactId));
    }
    let h = `memory:${m.artifactId}`;
    return (
      this.nodes.push({
        nodeId: h,
        tag: m.tag,
        position: m.position,
        operation: m.operation,
      }),
      this.lastNode &&
        this.edges.push({
          source: this.lastNode,
          target: h,
          relation: `next_memory`,
        }),
      (this.lastNode = h),
      m
    );
  }
  encodeSymbol(e, t, n = {}) {
    let r = symbolVector(e, this.config.encodingResolution),
      i = Array.from(r.re);
    return this.encode(i, t, {
      ...n,
      tag: `symbol:${e}`,
      symbol: e,
      raw: null,
      metadata: {
        symbol: e,
        ...(n.metadata ?? {}),
      },
    });
  }
  retrieve(e, t = {}) {
    let n = t.topK ?? 5,
      r = t.threshold ?? this.config.relevanceThreshold,
      i = Math.max(1, t.radius ?? 4),
      [a, o] = e,
      s = Math.max(0, a - i),
      c = Math.min(this.memorySize, a + i + 1),
      l = Math.max(0, o - i),
      u = Math.min(this.memorySize, o + i + 1),
      d = c - s,
      p = u - l,
      h = complexZeros(d * p);
    for (let e = 0; e < d; e++)
      for (let t = 0; t < p; t++) {
        let n = this.at(s + e, l + t);
        ((h.re[e * p + t] = this.re[n]), (h.im[e * p + t] = this.im[n]));
      }
    let g = dft2(h, d, p, !0),
      _ = Array.from(g.re, (e, t) => Math.hypot(e, g.im[t])),
      v = null;
    typeof t.query == `string`
      ? (v = symbolVector(t.query, this.config.encodingResolution))
      : t.query &&
        (v = normalize(resampleReal(t.query, this.config.encodingResolution)));
    let y = this.energy(),
      x = Math.max(this.memorySize * this.config.retrievalDistanceScale, 1),
      S = [];
    for (let e of this.records) {
      let t = this.payloads.get(e.artifactId),
        n = this.patterns.get(e.artifactId);
      if (!t || !n) continue;
      let i = e.position[0] - a,
        s = e.position[1] - o,
        c = Math.hypot(i, s),
        l = Math.exp(-0.5 * (c / x) ** 2),
        u = 1;
      if (v) {
        let e = complexNorm(t) * complexNorm(v);
        u = e > EPSILON ? absoluteInnerProduct(t, v) / e : 0;
      }
      let d = this.patchOf(
          e.position,
          this.config.encodingResolution,
          this.config.encodingResolution,
        ),
        p = d.gx1 - d.gx0,
        m = d.gy1 - d.gy0,
        h = complexZeros(p * m),
        g = complexZeros(p * m),
        _ = this.config.encodingResolution;
      for (let e = 0; e < p; e++)
        for (let t = 0; t < m; t++) {
          let r = e * m + t,
            i = this.at(d.gx0 + e, d.gy0 + t),
            a = (d.px0 + e) * _ + (d.py0 + t);
          ((h.re[r] = this.re[i]),
            (h.im[r] = this.im[i]),
            (g.re[r] = n.re[a]),
            (g.im[r] = n.im[a]));
        }
      let C = complexNorm(h) * complexNorm(g),
        w = C > EPSILON && y > EPSILON ? absoluteInnerProduct(h, g) / C : 0,
        E = Math.min(1, Math.max(0, 0.38 * l + 0.42 * u + 0.2 * w));
      E < r ||
        S.push({
          artifactId: e.artifactId,
          tag: e.tag,
          baseScore: E,
          finalScore: E,
          distanceScore: l,
          queryScore: u,
          patternScore: w,
          distance: c,
        });
    }
    S.sort((e, t) => t.finalScore - e.finalScore);
    let C = S.slice(0, n),
      w = new Float64Array(this.config.encodingResolution),
      D = 0,
      k = `NO_MATCH`;
    if (C.length) {
      ((k = `MATCH`), (D = C[0].baseScore));
      let e = 0;
      for (let t of C) e += Math.max(t.finalScore, EPSILON);
      for (let t of C) {
        let n = this.payloads.get(t.artifactId);
        if (!n) continue;
        let r = Math.max(t.finalScore, EPSILON) / e;
        for (let e = 0; e < w.length; e++) w[e] += r * n.re[e];
      }
    }
    return {
      position: [a, o],
      radius: i,
      relevanceScore: D,
      outcome: k,
      hits: C,
      decodedRe: Array.from(w),
      surfaceMag: _,
      surfaceH: d,
      surfaceW: p,
      queryRe: v ? Array.from(v.re) : null,
    };
  }
  eraseField() {
    (this.re.fill(0), this.im.fill(0));
  }
  dropLedger() {
    ((this.records = []),
      this.payloads.clear(),
      this.patterns.clear(),
      (this.nodes = []),
      (this.edges = []),
      (this.lastNode = null));
  }
  clear() {
    (this.eraseField(), this.dropLedger(), (this.counter = 0));
  }
};
function resetDemoPlate(e) {
  e.clear();
  let t = e.encode([0.1, 0.4, 0.9, 0.2], [20, 22], {
    tag: `reading-001`,
    metadata: {
      source: `sensor-A`,
    },
  });
  return (
    e.encode([0.85, -0.15, 0.05, 0.55], [46, 18], {
      tag: `reading-002`,
      metadata: {
        source: `sensor-B`,
      },
    }),
    e.encode([0.15, 0.72, -0.35, 0.28], [24, 27], {
      tag: `reading-003`,
      metadata: {
        source: `sensor-A`,
      },
    }),
    e.encodeSymbol(`beacon`, [52, 40], {
      metadata: {
        source: `label`,
      },
    }),
    t
  );
}
function parseNumericInput(e) {
  let t = e
    .trim()
    .split(/[\s,]+/)
    .filter(Boolean);
  if (!t.length) return null;
  let n = t.map((e) => Number(e));
  return n.some((e) => !Number.isFinite(e)) ? null : n;
}
function resolveQuery(e, t) {
  let n = [
      clampPosition(t.queryRow, e.memorySize),
      clampPosition(t.queryCol, e.memorySize),
    ],
    r = {
      topK: t.topK,
      threshold: t.threshold,
      radius: t.radius,
    };
  if (t.mode === `spatial`)
    return {
      retrieval: e.retrieve(n, {
        ...r,
        query: null,
      }),
      error: null,
      queryNote: `No query vector. Item similarity is defined as 1, so rank is proximity plus pattern correlation.`,
    };
  if (t.mode === `symbol`) {
    let i = t.symbolText.trim();
    return i
      ? {
          retrieval: e.retrieve(n, {
            ...r,
            query: i,
          }),
          error: null,
          queryNote: `Symbol queries use the raw seeded vector. Stored symbol payloads were Hann-windowed on write when that switch is on. Wording similarity is not vector similarity.`,
        }
      : {
          retrieval: null,
          error: `Enter a symbol to query.`,
          queryNote: ``,
        };
  }
  if (t.mode === `vector`) {
    let i = parseNumericInput(t.vectorText);
    return i
      ? {
          retrieval: e.retrieve(n, {
            ...r,
            query: i,
          }),
          error: null,
          queryNote: `Numeric queries are resampled and normalized. They do not receive the write-time Hann window.`,
        }
      : {
          retrieval: null,
          error: `Query vector needs finite numbers.`,
          queryNote: ``,
        };
  }
  let i = t.selectedId ? e.record(t.selectedId) : void 0;
  if (!i?.raw)
    return {
      retrieval: null,
      error: `Select a numeric ledger item to noise.`,
      queryNote: ``,
    };
  let a = addNoise(i.raw, t.sigma, t.seed);
  return {
    retrieval: e.retrieve(n, {
      ...r,
      query: a,
    }),
    error: null,
    queryNote: `Noise N(0, ${t.sigma.toFixed(2)}²) added to the raw input of ${i.tag}, seed ${t.seed}. The engine then normalizes, without a Hann window.`,
  };
}
function clampPosition(e, t) {
  return Number.isFinite(e) ? Math.max(0, Math.min(t - 1, Math.round(e))) : 0;
}
function runNoiseProbe(e, t, n, r, i) {
  let a = e.record(t),
    o = a?.raw,
    s = i.threshold,
    c = i.radius;
  return !a || !o
    ? {
        threshold: s,
        radius: c,
        trials: r,
        cells: [],
      }
    : {
        threshold: s,
        radius: c,
        trials: r,
        cells: n.map((n) => {
          let i = 0;
          for (let l = 1; l <= r; l++) {
            let r = e.retrieve(a.position, {
              query: addNoise(o, n, l),
              topK: 1,
              threshold: s,
              radius: c,
            });
            r.outcome === `MATCH` && r.hits[0]?.artifactId === t && (i += 1);
          }
          return {
            sigma: n,
            hits: i,
            trials: r,
          };
        }),
      };
}
function runViewerChecks() {
  let e = [],
    t = hashText(`abc`);
  e.push({
    name: `sha256`,
    pass:
      t === `ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad`,
    detail: t.slice(0, 12),
  });
  let n = dft(Float64Array.of(1, 0, 0, 0), Float64Array.of(0, 0, 0, 0), !1),
    r =
      n.re.every((e) => Math.abs(e - 1) < 1e-9) &&
      n.im.every((e) => Math.abs(e) < 1e-9);
  e.push({
    name: `dft impulse`,
    pass: r,
    detail: r ? `flat spectrum` : `mismatch`,
  });
  let i = new ViewerEngine(),
    a = i.encode([0.1, 0.4, 0.9, 0.2], [20, 22], {
      tag: `reading-001`,
      metadata: {
        source: `sensor-A`,
      },
    }),
    o = i.retrieve([20, 22], {
      query: [0.12, 0.39, 0.88, 0.21],
      topK: 1,
    });
  e.push({
    name: `readme probe`,
    pass: o.hits[0]?.artifactId === a.artifactId && o.outcome === `MATCH`,
    detail: o.outcome,
  });
  let s = new ViewerEngine(),
    c = s.encode([0.1, 0.4, 0.9, 0.2], [20, 22], {
      tag: `A`,
    });
  s.encode([0.9, 0.05, -0.8, 0.1], [21, 23], {
    tag: `B`,
  });
  let l = s.retrieve([20, 22], {
    query: [0.1, 0.4, 0.9, 0.2],
    topK: 1,
  });
  e.push({
    name: `overlap prefers query`,
    pass: l.hits[0]?.artifactId === c.artifactId,
    detail: l.hits[0]?.tag ?? `none`,
  });
  let u = c.artifactId;
  s.eraseField();
  let d = s.retrieve([20, 22], {
    query: [0.1, 0.4, 0.9, 0.2],
    topK: 1,
  });
  (e.push({
    name: `field erase zeros pattern`,
    pass:
      d.hits[0]?.artifactId === u &&
      Math.abs(d.hits[0].patternScore) < 1e-9 &&
      d.outcome === `MATCH`,
    detail: `pattern ${d.hits[0]?.patternScore ?? `na`}`,
  }),
    s.dropLedger());
  let f = new ViewerEngine();
  (f.encode([0.2, 0.2, 0.2, 0.9], [8, 8], {
    tag: `stay`,
  }),
    f.dropLedger());
  let m = f.retrieve([8, 8], {
    query: [0.2, 0.2, 0.2, 0.9],
    topK: 1,
  });
  e.push({
    name: `ledger drop is NO_MATCH`,
    pass: m.outcome === `NO_MATCH` && m.hits.length === 0 && f.energy() > 0,
    detail: m.outcome,
  });
  let h = i.retrieve([20, 22], {
    query: null,
    topK: 1,
  });
  e.push({
    name: `missing query scores 1`,
    pass: h.hits[0]?.queryScore === 1,
    detail: String(h.hits[0]?.queryScore ?? `na`),
  });
  let g = new ViewerEngine({
      useHannWindow: !0,
    }),
    _ = new ViewerEngine({
      useHannWindow: !1,
    }),
    v = g.encode([0.1, 0.4, 0.9, 0.2], [4, 4], {
      tag: `h`,
    }).payloadHash,
    b = _.encode([0.1, 0.4, 0.9, 0.2], [4, 4], {
      tag: `h`,
    }).payloadHash;
  e.push({
    name: `hann changes payload`,
    pass: v !== b,
    detail: `${v.slice(0, 6)}/${b.slice(0, 6)}`,
  });
  let x = new ViewerEngine();
  x.encode([0.1, 0.4, 0.9, 0.2], [4, 4], {
    tag: `near`,
  });
  let S = x.retrieve([60, 60], {
    query: [1, -1, 1, -1],
    topK: 1,
    threshold: 0.99,
  });
  e.push({
    name: `threshold can reject`,
    pass: S.outcome === `NO_MATCH`,
    detail: S.outcome,
  });
  let C = new ViewerEngine(),
    w = C.encodeSymbol(`beacon`, [10, 10]),
    T = C.retrieve([10, 10], {
      query: `other-word`,
      topK: 1,
    }),
    E = C.retrieve([10, 10], {
      query: `beacon`,
      topK: 1,
    }),
    D = E.hits[0] ? E.hits[0].queryScore.toFixed(2) : `na`,
    O = T.hits[0] ? T.hits[0].queryScore.toFixed(2) : `na`;
  e.push({
    name: `symbols are exact, not paraphrase`,
    pass:
      w.tag === `symbol:beacon` &&
      E.hits[0]?.artifactId === w.artifactId &&
      (T.hits[0]?.queryScore ?? 1) < 0.85,
    detail: `same ${D} other ${O}`,
  });
  let k = new ViewerEngine(),
    A = resetDemoPlate(k),
    j = runNoiseProbe(k, A.artifactId, [0], 4, {
      threshold: 0,
      radius: 4,
    }),
    M = runNoiseProbe(k, A.artifactId, [0], 4, {
      threshold: 0.999,
      radius: 4,
    });
  return (
    e.push({
      name: `probe uses threshold`,
      pass:
        j.cells[0]?.hits === 4 &&
        M.cells[0]?.hits === 0 &&
        M.threshold === 0.999,
      detail: `${j.cells[0]?.hits ?? `na`}/4 open, ${M.cells[0]?.hits ?? `na`}/4 shut`,
    }),
    e
  );
}
function defaultQueryForm(e) {
  return {
    queryRow: 20,
    queryCol: 22,
    mode: `noisy`,
    sigma: 0.15,
    seed: 7,
    vectorText: `0.12, 0.39, 0.88, 0.21`,
    symbolText: `beacon`,
    topK: 4,
    threshold: 0,
    selectedId: e,
    radius: 4,
  };
}
function createDemoState() {
  let e = new ViewerEngine();
  return {
    engine: e,
    form: defaultQueryForm(resetDemoPlate(e).artifactId),
  };
}
export {
  complexZeros,
  dft,
  dft2,
  SHA256_CONSTANTS,
  rotateRight,
  sha256Bytes,
  bytesToHex,
  hashText,
  EPSILON,
  VIEWER_SCHEMA,
  DEFAULT_CONFIG,
  linspace,
  interpolate,
  complexNorm,
  normalize,
  hannWindow,
  resampleReal,
  seededRandom,
  symbolVector,
  addNoise,
  hashVector,
  artifactId,
  absoluteInnerProduct,
  ViewerEngine,
  resetDemoPlate,
  parseNumericInput,
  resolveQuery,
  clampPosition,
  runNoiseProbe,
  runViewerChecks,
  defaultQueryForm,
  createDemoState,
};
