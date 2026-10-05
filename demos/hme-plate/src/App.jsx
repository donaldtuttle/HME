/* Ported from the user-owned HME Plate deployment captured 2026-09-26.
 * See SOURCE.md for hashes, transformation scope and compatibility boundaries. */
import {
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
} from "./model.js";
import * as React from "react";
var FIELD_BACKGROUND = [16, 20, 17],
  FIELD_BRASS = [196, 163, 90],
  FIELD_PAPER = [231, 239, 230];
function mixColor(e, t, n) {
  return [
    Math.round(e[0] + (t[0] - e[0]) * n),
    Math.round(e[1] + (t[1] - e[1]) * n),
    Math.round(e[2] + (t[2] - e[2]) * n),
  ];
}
function magnitudeColor(e) {
  return e < 0.55
    ? mixColor(FIELD_BACKGROUND, FIELD_BRASS, e / 0.55)
    : mixColor(FIELD_BRASS, FIELD_PAPER, (e - 0.55) / 0.45);
}
function renderFieldImage(e, t, n, r, i, u, d, f, p) {
  let m = document.createElement(`canvas`),
    h = Math.min(window.devicePixelRatio || 1, 2);
  ((m.width = Math.round(t * h)), (m.height = Math.round(t * h)));
  let g = m.getContext(`2d`);
  if (!g) return ``;
  g.setTransform(h, 0, 0, h, 0, 0);
  let _ = e.memorySize,
    v = t / _,
    y = e.maxMag();
  ((g.fillStyle = `#101411`), g.fillRect(0, 0, t, t));
  for (let t = 0; t < _; t++)
    for (let r = 0; r < _; r++) {
      let i = e.magAt(t, r);
      if (i <= 1e-8 || y <= 1e-8) continue;
      let u =
        n === `phase`
          ? mixColor(
              FIELD_BACKGROUND,
              mixColor(
                FIELD_BRASS,
                FIELD_PAPER,
                0.5 + 0.5 * Math.cos(e.phaseAt(t, r)),
              ),
              Math.min(1, i / y),
            )
          : magnitudeColor(Math.log1p(i) / Math.log1p(y));
      ((g.fillStyle = `rgb(${u[0]} ${u[1]} ${u[2]})`),
        g.fillRect(r * v, t * v, Math.ceil(v), Math.ceil(v)));
    }
  ((g.strokeStyle = `rgba(231,239,230,0.08)`),
    (g.lineWidth = 1),
    g.beginPath());
  for (let e = 0; e <= _; e += 8)
    (g.moveTo(e * v + 0.5, 0),
      g.lineTo(e * v + 0.5, t),
      g.moveTo(0, e * v + 0.5),
      g.lineTo(t, e * v + 0.5));
  g.stroke();
  let b = e.config.encodingResolution;
  for (let t of e.records) {
    let n = e.patchOf(t.position, b, b),
      r = t.artifactId === f;
    ((g.strokeStyle = r ? `#c4a35a` : `rgba(196,163,90,0.35)`),
      (g.lineWidth = r ? 1.5 : 1),
      g.strokeRect(
        n.gy0 * v + 0.5,
        n.gx0 * v + 0.5,
        (n.gy1 - n.gy0) * v - 1,
        (n.gx1 - n.gx0) * v - 1,
      ));
  }
  let x = Math.max(0, u - p),
    S = Math.max(0, d - p),
    C = Math.min(_, u + p + 1),
    w = Math.min(_, d + p + 1);
  (g.setLineDash([3, 3]),
    (g.strokeStyle = `rgba(231,239,230,0.85)`),
    (g.lineWidth = 1),
    g.strokeRect(S * v + 0.5, x * v + 0.5, (w - S) * v - 1, (C - x) * v - 1),
    g.setLineDash([]));
  let T = (e, t, n) => {
    let r = (t + 0.5) * v,
      i = (e + 0.5) * v;
    ((g.strokeStyle = n),
      (g.lineWidth = 1.25),
      g.beginPath(),
      g.moveTo(r - 5, i),
      g.lineTo(r + 5, i),
      g.moveTo(r, i - 5),
      g.lineTo(r, i + 5),
      g.stroke());
  };
  return (T(r, i, `#c4a35a`), T(u, d, `#e7efe6`), m.toDataURL(`image/png`));
}
function FieldCanvas(e) {
  let t = (0, React.useRef)(null),
    [n, a] = (0, React.useState)(``);
  (0, React.useEffect)(() => {
    let n = t.current;
    if (!n) return;
    let r = () => {
      let t = n.clientWidth;
      t < 8 ||
        a(
          renderFieldImage(
            e.engine,
            t,
            e.view,
            e.writeRow,
            e.writeCol,
            e.queryRow,
            e.queryCol,
            e.selectedId,
            e.radius,
          ),
        );
    };
    r();
    let i = new ResizeObserver(r);
    return (i.observe(n), () => i.disconnect());
  }, [e]);
  let o = (t, n, r) => {
    let i = e.engine.memorySize,
      a = Math.min(
        i - 1,
        Math.max(0, Math.floor(((t - r.left) / r.width) * i)),
      ),
      o = Math.min(
        i - 1,
        Math.max(0, Math.floor(((n - r.top) / r.height) * i)),
      );
    e.onPick(o, a);
  };
  return (
    <div
      ref={t}
      role={`application`}
      tabIndex={0}
      aria-label={`Holographic memory field. Click or use arrow keys to place the active position. Row increases downward.`}
      className={`aspect-square w-full touch-none rounded-lg bg-bg`}
      onPointerDown={(e) => {
        (o(e.clientX, e.clientY, e.currentTarget.getBoundingClientRect()),
          e.currentTarget.focus());
      }}
    >
      {n ? (
        <img
          src={n}
          alt={``}
          className={`plate-img h-full w-full rounded-lg`}
        />
      ) : null}
    </div>
  );
}
function plainQueryNote(mode) {
  if (mode === `noisy`)
    return `The selected memory was distorted, then searched for at the paper cross.`;
  if (mode === `vector`)
    return `Searching with the values you typed, at the paper cross.`;
  if (mode === `symbol`)
    return `Searching for that exact symbol. Similar wording is not a similar pattern.`;
  return `Searching by place only.`;
}
function HMEPlate() {
  let initialState = (0, React.useMemo)(() => createDemoState(), []),
    checks = (0, React.useMemo)(() => runViewerChecks(), []),
    [engine] = (0, React.useState)(() => initialState.engine),
    [queryForm, setQueryForm] = (0, React.useState)(() => initialState.form),
    [revision, setRevision] = (0, React.useState)(0),
    [fieldView, setFieldView] = (0, React.useState)(`magnitude`),
    [placementMode, setPlacementMode] = (0, React.useState)(`write`),
    [writeRow, setWriteRow] = (0, React.useState)(30),
    [writeCol, setWriteCol] = (0, React.useState)(34),
    [tag, setTag] = (0, React.useState)(`reading-004`),
    [writeKind, setWriteKind] = (0, React.useState)(`vector`),
    [vectorText, setVectorText] = (0, React.useState)(`0.3, 0.1, 0.6, 0.8`),
    [symbolText, setSymbolText] = (0, React.useState)(`dock`),
    [strength, setStrength] = (0, React.useState)(0.1),
    [useHann, setUseHann] = (0, React.useState)(!0),
    [writeError, setWriteError] = (0, React.useState)(null),
    [probeResult, setProbeResult] = (0, React.useState)(null),
    [layer, setLayer] = (0, React.useState)(`explore`),
    showDetails = layer === `details`,
    queryResult = resolveQuery(engine, queryForm),
    updateQuery = (e) => {
      (e &&
        setQueryForm((t) => ({
          ...t,
          ...e,
        })),
        setRevision((e) => e + 1));
    },
    placePosition = (e, t) => {
      placementMode === `write`
        ? (setWriteRow(e), setWriteCol(t))
        : updateQuery({
            queryRow: e,
            queryCol: t,
          });
    },
    movePosition = (e, t) => {
      let r = engine.memorySize;
      placementMode === `write`
        ? (setWriteRow((t) => Math.max(0, Math.min(r - 1, t + e))),
          setWriteCol((e) => Math.max(0, Math.min(r - 1, e + t))))
        : updateQuery({
            queryRow: Math.max(0, Math.min(r - 1, queryForm.queryRow + e)),
            queryCol: Math.max(0, Math.min(r - 1, queryForm.queryCol + t)),
          });
    },
    encodeWrite = () => {
      try {
        engine.config.useHannWindow = useHann;
        let e;
        if (writeKind === `symbol`) {
          let t = symbolText.trim();
          if (!t) {
            setWriteError(`Enter an exact symbol.`);
            return;
          }
          e = engine.encodeSymbol(t, [writeRow, writeCol], {
            strength: strength,
          });
        } else {
          let t = parseNumericInput(vectorText);
          if (!t) {
            setWriteError(`Vector needs finite numbers, separated by commas.`);
            return;
          }
          e = engine.encode(t, [writeRow, writeCol], {
            tag: tag.trim() || void 0,
            strength: strength,
          });
        }
        (setWriteError(null),
          setProbeResult(null),
          updateQuery({
            selectedId: e.artifactId,
            mode: writeKind === `symbol` ? `symbol` : queryForm.mode,
            symbolText:
              writeKind === `symbol` ? symbolText.trim() : queryForm.symbolText,
          }));
      } catch (e) {
        setWriteError(e instanceof Error ? e.message : `Write failed`);
      }
    },
    selectedRecord = queryForm.selectedId
      ? engine.record(queryForm.selectedId)
      : void 0,
    plateStatus =
      engine.records.length === 0 && engine.energy() > 1e-8
        ? `Ledger dropped. The plate still holds interference, but identity retrieval is gone.`
        : engine.records.length > 0 && engine.energy() <= 1e-8
          ? `Field erased. Pattern correlation is zero. Ranking uses the ledger only.`
          : `Plate and ledger are both live.`;
  return (
    <main className={`mx-auto max-w-6xl px-4 py-5 sm:px-6 sm:py-6`}>
      <header className={`mb-5`}>
        <div className={`flex flex-wrap items-start justify-between gap-3`}>
          <p className={`font-mono text-xs tracking-widest text-accent uppercase`}>
            {`HME Plate · Interactive memory demo`}
          </p>
          <div
            className={`flex rounded-lg bg-bg p-1`}
            role={`group`}
            aria-label={`How much machinery to show`}
          >
            <button
              type={`button`}
              className={`seg`}
              aria-pressed={layer === `explore`}
              onClick={() => setLayer(`explore`)}
            >{`Explore`}</button>
            <button
              type={`button`}
              className={`seg`}
              aria-pressed={layer === `details`}
              onClick={() => setLayer(`details`)}
            >{`Details`}</button>
          </div>
        </div>
        <h1 className={`mt-2 text-balance text-3xl font-medium tracking-tight sm:text-4xl`}>
          {`Explore HME`}
        </h1>
        <div className={`mt-3 grid max-w-2xl gap-2 text-sm leading-relaxed text-muted`}>
          <p>{`HME Plate lets you store, search, and disrupt memories to see how the Holographic Memory Engine retrieves information.`}</p>
          <p>{`Not a chatbot: this is the actual numerical memory mechanism that an AI application could connect to.`}</p>
        </div>
        <p className={`mt-3 font-mono text-xs text-muted tabular-nums`}>
          {engine.memorySize}
          {`² complex · `}
          {engine.config.encodingResolution}
          {`-point patterns · `}
          {engine.records.length}
          {` records · energy `}
          {engine.energy().toFixed(3)}
        </p>
      </header>

      <details className={`panel px-4 py-3 text-sm`} style={{ marginBottom: `1rem` }}>
        <summary className={`cursor-pointer font-medium`}>{`Quick start`}</summary>
        {showDetails ? (
          <ol className={`mt-3 grid gap-3`}>
            <li><p className={`font-medium`}>{`1. Start with a memory`}</p><p className={`text-muted`}>{`The demo begins with four example memories already stored. Their patterns appear on the plate.`}</p></li>
            <li><p className={`font-medium`}>{`2. Query a memory`}</p><p className={`text-muted`}>{`Select Place search, then tap somewhere on the plate. Watch the result change as you move the search.`}</p></li>
            <li><p className={`font-medium`}>{`3. Make the clue imperfect`}</p><p className={`text-muted`}>{`Choose Noisy memory and increase Noise level. See how much distortion the system can tolerate while still retrieving the intended memory.`}</p></li>
            <li><p className={`font-medium`}>{`4. See why it chose something`}</p><p className={`text-muted`}>{`The result shows how proximity, similarity, and the field contributed to the ranking.`}</p></li>
            <li><p className={`font-medium`}>{`5. Break it on purpose`}</p><p className={`text-muted`}>{`Try Erase field, keep records and Remove records, keep field. These experiments show what each part of HME contributes. Hit Restore the demo whenever you want to start over.`}</p></li>
          </ol>
        ) : (
          <ol className={`mt-3 grid gap-3`}>
            <li><p className={`font-medium`}>{`1. Search a memory`}</p><p className={`text-muted`}>{`Choose Place search and tap the plate to search the four example memories.`}</p></li>
            <li><p className={`font-medium`}>{`2. Add noise`}</p><p className={`text-muted`}>{`Choose Noisy memory and raise Noise level to see whether HME still finds the intended memory.`}</p></li>
            <li><p className={`font-medium`}>{`3. Break it on purpose`}</p><p className={`text-muted`}>{`Remove the field or the records and see what changes. Restore the demo whenever you want to start over.`}</p></li>
          </ol>
        )}
      </details>

      <div className={`hme-main-grid`}>
        <section className={`panel hme-plate-cell p-3 sm:p-4`}>
          <div className={`mb-3 flex flex-wrap items-center justify-between gap-3`}>
            <div className={`flex rounded-lg bg-bg p-1`} role={`group`} aria-label={`Field view`}>
              <button type={`button`} className={`seg`} aria-pressed={fieldView === `magnitude`} onClick={() => setFieldView(`magnitude`)}>{`Magnitude`}</button>
              <button type={`button`} className={`seg`} aria-pressed={fieldView === `phase`} onClick={() => setFieldView(`phase`)}>{`Phase`}</button>
            </div>
            <div className={`flex rounded-lg bg-bg p-1`} role={`group`} aria-label={`What a click places`}>
              <button type={`button`} className={`seg`} aria-pressed={placementMode === `write`} onClick={() => setPlacementMode(`write`)}>{`Place memory`}</button>
              <button type={`button`} className={`seg`} aria-pressed={placementMode === `query`} onClick={() => setPlacementMode(`query`)}>{`Place search`}</button>
            </div>
          </div>
          <div
            onKeyDown={(e) => {
              let t = e.shiftKey ? 4 : 1;
              if (e.key === `ArrowUp`) movePosition(-t, 0);
              else if (e.key === `ArrowDown`) movePosition(t, 0);
              else if (e.key === `ArrowLeft`) movePosition(0, -t);
              else if (e.key === `ArrowRight`) movePosition(0, t);
              else return;
              e.preventDefault();
            }}
          >
            <FieldCanvas
              engine={engine}
              rev={revision}
              view={fieldView}
              writeRow={writeRow}
              writeCol={writeCol}
              queryRow={queryForm.queryRow}
              queryCol={queryForm.queryCol}
              selectedId={queryForm.selectedId}
              radius={queryForm.radius}
              onPick={placePosition}
            />
          </div>
          <ul className={`mt-3 flex flex-wrap gap-x-4 gap-y-1 text-xs text-muted`}>
            <li><span className={`font-mono text-accent`}>{`+`}</span>{` Memory position `}<span className={`font-mono tabular-nums`}>({writeRow}, {writeCol})</span></li>
            <li><span className={`font-mono text-fg`}>{`+`}</span>{` Search position `}<span className={`font-mono tabular-nums`}>({queryForm.queryRow}, {queryForm.queryCol})</span></li>
            <li><span className={`legend-box legend-selected`} aria-hidden={`true`} />{`Selected memory`}</li>
            <li><span className={`legend-box legend-other`} aria-hidden={`true`} />{`Other memories`}</li>
            <li><span className={`legend-box legend-search`} aria-hidden={`true`} />{`Search window`}</li>
          </ul>
          <p className={`mt-2 text-xs text-muted`}>
            {fieldView === `magnitude` ? `Magnitude: where field activity is strongest.` : `Phase: the underlying complex-valued alignment.`}
            {showDetails ? ` Row down, column across.` : ``}
          </p>
          <p className={`mt-1 text-sm text-muted`}>{plateStatus}</p>
        </section>

        <div className={`hme-side-cell grid gap-4`}>
          <section className={`panel grid gap-3 p-4`}>
            <h2 className={`flex items-baseline gap-2 text-sm font-medium`}>
              <span className={`font-mono text-xs text-accent`}>{`1`}</span>
              {`Store`}
              {showDetails ? <span className={`font-mono text-xs text-muted`}>{`write`}</span> : null}
            </h2>
            <div className={`flex rounded-lg bg-bg p-1`} role={`group`} aria-label={`Write kind`}>
              <button type={`button`} className={`seg flex-1`} aria-pressed={writeKind === `vector`} onClick={() => setWriteKind(`vector`)}>{`Vector`}</button>
              <button type={`button`} className={`seg flex-1`} aria-pressed={writeKind === `symbol`} onClick={() => setWriteKind(`symbol`)}>{`Symbol`}</button>
            </div>
            {writeKind === `vector` ? (
              <React.Fragment>
                <label className={`grid gap-1 text-xs text-muted`}>
                  {`Tag`}
                  <input className={`field`} value={tag} onChange={(e) => setTag(e.target.value)} />
                </label>
                <label className={`grid gap-1 text-xs text-muted`}>
                  {`Values`}
                  {showDetails ? <span className={`font-mono`}>{`numeric vector`}</span> : null}
                  <input className={`field`} value={vectorText} onChange={(e) => setVectorText(e.target.value)} spellCheck={!1} />
                </label>
              </React.Fragment>
            ) : (
              <label className={`grid gap-1 text-xs text-muted`}>
                {`Exact symbol`}
                <input className={`field`} value={symbolText} onChange={(e) => setSymbolText(e.target.value)} spellCheck={!1} />
              </label>
            )}
            <label className={`grid gap-1 text-xs text-muted`}>
              {`Strength `}{strength.toFixed(2)}
              <input type={`range`} min={0.02} max={0.4} step={0.01} value={strength} onChange={(e) => setStrength(Number(e.target.value))} />
            </label>
            <label className={`flex min-h-11 items-center gap-2 text-sm`}>
              <input
                type={`checkbox`}
                checked={useHann}
                onChange={(e) => {
                  let t = e.target.checked;
                  (setUseHann(t), (engine.config.useHannWindow = t));
                }}
              />
              {`Soften edges on later stores`}
              {showDetails ? <span className={`font-mono text-xs text-muted`}>{`Hann window`}</span> : null}
            </label>
            {writeError ? <p className={`text-sm text-accent`}>{writeError}</p> : null}
            <button type={`button`} className={`btn btn-accent`} onClick={encodeWrite}>{`Store memory`}</button>
          </section>

          <section className={`panel grid gap-3 p-4`}>
            <h2 className={`flex items-baseline gap-2 text-sm font-medium`}>
              <span className={`font-mono text-xs text-accent`}>{`2`}</span>
              {`Search`}
              {showDetails ? <span className={`font-mono text-xs text-muted`}>{`query`}</span> : null}
            </h2>
            <div className={`search-mode-grid rounded-lg bg-bg p-1`} role={`group`} aria-label={`Search mode`}>
              {[
                [`noisy`, `Noisy memory`],
                [`vector`, `Vector`],
                [`symbol`, `Symbol`],
                [`spatial`, `Spatial`],
              ].map(([e, t]) => (
                <button type={`button`} className={`seg`} aria-pressed={queryForm.mode === e} onClick={() => updateQuery({ mode: e })} key={e}>{t}</button>
              ))}
            </div>
            {queryForm.mode === `vector` ? (
              <label className={`grid gap-1 text-xs text-muted`}>
                {`Search values`}
                {showDetails ? <span className={`font-mono`}>{`query vector`}</span> : null}
                <input className={`field`} value={queryForm.vectorText} spellCheck={!1} onChange={(e) => updateQuery({ vectorText: e.target.value })} />
              </label>
            ) : null}
            {queryForm.mode === `symbol` ? (
              <label className={`grid gap-1 text-xs text-muted`}>
                {`Search symbol`}
                <input className={`field`} value={queryForm.symbolText} spellCheck={!1} onChange={(e) => updateQuery({ symbolText: e.target.value })} />
              </label>
            ) : null}
            {queryForm.mode === `noisy` ? (
              <div className={`grid gap-3`}>
                <label className={`grid gap-1 text-xs text-muted`}>
                  {`Noise level `}{queryForm.sigma.toFixed(2)}
                  {showDetails ? <span className={`font-mono`}>{`sigma`}</span> : null}
                  <input type={`range`} min={0} max={1.25} step={0.01} value={queryForm.sigma} onChange={(e) => updateQuery({ sigma: Number(e.target.value) })} />
                </label>
                <label className={`grid gap-1 text-xs text-muted`}>
                  {`Seed`}
                  <input className={`field`} type={`number`} value={queryForm.seed} onChange={(e) => updateQuery({ seed: Number(e.target.value) || 0 })} />
                </label>
              </div>
            ) : null}
            <div className={`grid grid-cols-2 gap-3`}>
              <label className={`grid gap-1 text-xs text-muted`}>
                {`Results`}
                {showDetails ? <span className={`font-mono`}>{`top k`}</span> : null}
                <input className={`field`} type={`number`} min={1} max={8} value={queryForm.topK} onChange={(e) => updateQuery({ topK: Math.max(1, Math.min(8, Number(e.target.value) || 1)) })} />
              </label>
              <label className={`grid gap-1 text-xs text-muted`}>
                {`Threshold`}
                <input className={`field`} type={`number`} min={0} max={1} step={0.05} value={queryForm.threshold} onChange={(e) => updateQuery({ threshold: Math.max(0, Math.min(1, Number(e.target.value) || 0)) })} />
              </label>
            </div>
            <p className={`text-xs text-muted`}>
              {showDetails
                ? `Threshold eligibility is not proof. Default is zero, so almost any candidate can MATCH.`
                : `Raise this and a weak match becomes no match. The default is zero, so almost anything passes.`}
            </p>
          </section>

          <LedgerPanel
            engine={engine}
            selectedId={queryForm.selectedId}
            showDetails={showDetails}
            onSelect={(e) => {
              let t = engine.record(e);
              (setProbeResult(null),
                updateQuery({
                  selectedId: e,
                  queryRow: t?.position[0] ?? queryForm.queryRow,
                  queryCol: t?.position[1] ?? queryForm.queryCol,
                }));
            }}
          />
        </div>

        <div className={`hme-result-cell`}>
          <RetrievalPanel
            retrieval={queryResult.retrieval}
            error={queryResult.error}
            note={queryResult.queryNote}
            plain={plainQueryNote(queryForm.mode)}
            engine={engine}
            showDetails={showDetails}
          />
        </div>
      </div>

      <div className={`hme-experiments`}>
        <section className={`panel grid gap-3 p-4`}>
          <p className={`font-mono text-xs tracking-widest text-accent uppercase`}>{`Experiment`}</p>
          <h2 className={`text-sm font-medium`}>{`What does the memory need?`}</h2>
          <p className={`text-sm text-muted`}>{`Remove one part of HME and see what happens to retrieval.`}</p>
          <button type={`button`} className={`btn`} onClick={() => { (engine.eraseField(), setProbeResult(null), updateQuery()); }}>{`Erase field, keep records`}</button>
          <button type={`button`} className={`btn`} onClick={() => { (engine.dropLedger(), setProbeResult(null), updateQuery({ selectedId: null, mode: `spatial` })); }}>{`Remove records, keep field`}</button>
          <button
            type={`button`}
            className={`btn`}
            onClick={() => {
              ((engine.config.useHannWindow = !0), setUseHann(!0));
              let e = resetDemoPlate(engine);
              (setProbeResult(null),
                setWriteError(null),
                setQueryForm({
                  queryRow: 20,
                  queryCol: 22,
                  mode: `noisy`,
                  sigma: 0.15,
                  seed: 7,
                  vectorText: `0.12, 0.39, 0.88, 0.21`,
                  symbolText: `beacon`,
                  topK: 4,
                  threshold: 0,
                  selectedId: e.artifactId,
                  radius: 4,
                }),
                setRevision((e) => e + 1));
            }}
          >{`Restore the demo`}</button>
          {showDetails ? <p className={`text-xs text-muted`}>{`Ablation. Erase field, keep ledger: pattern correlation goes to zero. Drop ledger, keep field: identity retrieval stops. An evicted record would leave its field contribution behind.`}</p> : null}
        </section>

        <section className={`panel grid gap-3 p-4`}>
          <p className={`font-mono text-xs tracking-widest text-accent uppercase`}>{`Experiment`}</p>
          <h2 className={`text-sm font-medium`}>{`How much noise can it handle?`}</h2>
          <p className={`text-sm text-muted`}>{`Gradually distort a stored memory and test whether HME still retrieves the intended item first.`}</p>
          <button
            type={`button`}
            className={`btn`}
            disabled={!selectedRecord?.raw}
            onClick={() => {
              queryForm.selectedId &&
                setProbeResult(
                  runNoiseProbe(engine, queryForm.selectedId, [0, 0.25, 0.5, 1], 8, {
                    threshold: queryForm.threshold,
                    radius: queryForm.radius,
                  }),
                );
            }}
          >{`Run the test`}</button>
          {!selectedRecord?.raw ? <p className={`text-xs text-muted`}>{`Pick a numeric memory. A symbol has no raw values to distort.`}</p> : null}
          {showDetails && !probeResult ? <p className={`text-xs text-muted`}>{`Seeds 1–8 at the selected memory’s own position, top-1, using the retrieval threshold and window radius. Not the search seed or noise level, and not the published HME-NN study.`}</p> : null}
          {probeResult ? (
            <React.Fragment>
              <p className={`font-mono text-xs text-muted tabular-nums`}>
                {`Counted at threshold `}{probeResult.threshold.toFixed(2)}{` · window radius `}{probeResult.radius}
                {probeResult.threshold === queryForm.threshold ? `` : `. Retrieval threshold is now ${queryForm.threshold.toFixed(2)}; run again to use it.`}
              </p>
              {showDetails ? <p className={`text-xs text-muted`}>{`Seeds 1–8 at the item’s own position. A trial counts only when that item is top-1 and clears the threshold. Not the search sigma or seed.`}</p> : null}
              <table className={`w-full text-left text-sm`}>
                <thead className={`text-xs text-muted`}>
                  <tr>
                    <th className={`py-1 font-medium`}>{showDetails ? `Sigma` : `Noise`}</th>
                    <th className={`py-1 font-medium`}>{showDetails ? `Top-1 ≥ ${probeResult.threshold.toFixed(2)}` : `Still first`}</th>
                  </tr>
                </thead>
                <tbody className={`font-mono tabular-nums`}>
                  {probeResult.cells.map((e) => (
                    <tr className={`border-t border-line`} key={e.sigma}>
                      <td className={`py-1.5`}>{e.sigma.toFixed(2)}</td>
                      <td className={`py-1.5`}>{e.hits}{`/`}{e.trials}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </React.Fragment>
          ) : null}
        </section>
      </div>

      {showDetails ? (
        <section className={`panel mt-4 px-4 py-3 text-sm`}>
          <h2 className={`font-medium`}>{`Scoring`}</h2>
          <ul className={`mt-3 grid gap-2 text-muted`}>
            <li>{`Rank = 0.38 proximity + 0.42 absolute item/query similarity + 0.20 field/pattern correlation.`}</li>
            <li>{`relevance_score is the top hit’s base score. It is not a probability of being correct.`}</li>
            <li>{`MATCH means the hit cleared the threshold. It does not certify identity.`}</li>
            <li>{`decoded_vector blends retained payloads. The inverse-FFT surface is not that vector.`}</li>
            <li>{`Strings hash to seeded vectors. Similar wording is not similar geometry. This viewer is not bit-identical to the NumPy engine.`}</li>
          </ul>
          {checks.every((e) => e.pass) ? <p className={`mt-3 text-xs text-muted`}>{checks.length}{` viewer checks passed, including the readme probe, field erase, and ledger drop.`}</p> : null}
        </section>
      ) : null}

      <details className={`panel mt-4 px-4 py-3 text-sm`}>
        <summary className={`cursor-pointer font-medium`}>{`Technical details`}</summary>
        <h2 className={`mt-3 text-sm font-medium`}>{`Model scope`}</h2>
        <p className={`mt-2 leading-relaxed text-muted`}>{`Released field-plus-ledger model: spatial FFT-pattern superposition plus a retained artifact ledger. Not consolidation, not SAL-1, not standard HRR binding, and not field-only identity recovery.`}</p>
      </details>

      <footer className={`mt-6 grid gap-3 border-t border-line pt-4 text-xs text-muted`}>
        {!checks.every((e) => e.pass) ? <p>{`Viewer checks failed: `}{checks.filter((e) => !e.pass).map((e) => e.name).join(`, `)}{`.`}</p> : null}
        <p>
          {`Browser instrument of the released field-plus-ledger model from `}
          <a className={`text-fg underline decoration-line underline-offset-2`} href={`https://github.com/donaldtuttle/HME`}>{`donaldtuttle/HME`}</a>
          {`. It does not visualize consolidation or SAL-1.`}
          {showDetails ? ` Salience stays off. Artifact ids are viewer insertion ids, not NumPy byte hashes. The lineage graph is insertion order, not a Merkle chain.` : ``}
        </p>
      </footer>
    </main>
  );
}
function RetrievalPanel({
  retrieval,
  error,
  note,
  plain,
  engine,
  showDetails,
}) {
  if (error || !retrieval)
    return (
      <section className={`panel p-4`}>
        <h2 className={`flex items-baseline gap-2 text-sm font-medium`}>
          <span className={`font-mono text-xs text-accent`}>{`3`}</span>
          {`Result`}
        </h2>
        <p className={`mt-2 text-sm text-muted`}>{error ?? `No search yet.`}</p>
      </section>
    );
  let top = retrieval.hits[0],
    cleared = retrieval.outcome === `MATCH`;
  return (
    <section className={`panel grid gap-4 p-4`}>
      <div className={`flex flex-wrap items-end justify-between gap-3`}>
        <h2 className={`flex items-baseline gap-2 text-sm font-medium`}>
          <span className={`font-mono text-xs text-accent`}>{`3`}</span>
          {`Result`}
          {showDetails ? <span className={`font-mono text-xs text-muted`}>{`retrieval`}</span> : null}
        </h2>
        <p className={`inline-block rounded-md px-2 py-1 font-mono text-xs ${cleared ? `bg-accent text-ink` : `bg-elevated text-fg`}`}>
          {retrieval.outcome}
        </p>
      </div>
      {top ? (
        <div className={`grid gap-1`}>
          <p className={`text-xs text-muted`}>{`Best match`}</p>
          <p className={`text-lg font-medium tracking-tight`}>{top.tag}</p>
          <p className={`font-mono text-sm tabular-nums`}>{`Match score `}{top.baseScore.toFixed(3)}</p>
          <p className={`text-sm ${cleared ? `text-accent` : `text-muted`}`}>
            {cleared ? `✓ Cleared the retrieval threshold` : `Below the retrieval threshold`}
          </p>
        </div>
      ) : (
        <div className={`grid gap-1`}>
          <p className={`text-lg font-medium tracking-tight`}>{`No match`}</p>
          <p className={`text-sm text-muted`}>{`Nothing cleared the retrieval threshold.`}</p>
        </div>
      )}
      <p className={`text-sm text-muted`}>{plain}</p>
      {showDetails ? <p className={`text-xs text-muted`}>{note}</p> : null}
      {top ? (
        <div>
          <p className={`text-sm font-medium`}>{`Why it ranked first`}</p>
          <p className={`mt-1 font-mono text-xs text-muted tabular-nums`}>
            {`Similarity `}{top.queryScore.toFixed(2)}{` · Proximity `}{top.distanceScore.toFixed(2)}{` · Field `}{top.patternScore.toFixed(2)}
          </p>
          <p className={`mt-2 text-xs text-muted`}>{`Scores rank candidates. They are not probabilities.`}</p>
        </div>
      ) : (
        <p className={`text-xs text-muted`}>{`Scores rank candidates. They are not probabilities.`}</p>
      )}
      {showDetails && top ? <ScoreMix hit={top} /> : null}
      {showDetails ? (
        <p className={`font-mono text-xs text-muted tabular-nums`}>
          {`relevance `}{retrieval.relevanceScore.toFixed(3)}{` · window radius `}{retrieval.radius}{` at (`}{retrieval.position[0]}{`, `}{retrieval.position[1]}{`)`}
        </p>
      ) : null}
      {retrieval.hits.length > 1 ? (
        <ul className={`grid gap-2`}>
          {retrieval.hits.slice(1).map((hit, index) => (
            <li className={`rounded-lg bg-bg px-3 py-2`} key={hit.artifactId}>
              <div className={`flex items-baseline justify-between gap-3`}>
                <p className={`truncate text-sm`}>{index + 2}{`. `}{hit.tag}</p>
                <p className={`font-mono text-xs tabular-nums text-muted`}>{hit.baseScore.toFixed(3)}</p>
              </div>
              {showDetails ? (
                <p className={`mt-1 font-mono text-xs text-muted tabular-nums`}>
                  {`prox `}{hit.distanceScore.toFixed(2)}{` · sim `}{hit.queryScore.toFixed(2)}{` · field `}{hit.patternScore.toFixed(2)}{` · d `}{hit.distance.toFixed(1)}
                </p>
              ) : null}
            </li>
          ))}
        </ul>
      ) : null}
      {showDetails ? (
        <React.Fragment>
          <div className={`grid gap-3 sm:grid-cols-2`}>
            <VectorBars title={`Decoded vector`} hint={`Weighted average of retained payloads`} values={retrieval.decodedRe} />
            <VectorBars title={`Top stored payload`} hint={top ? `Processed vector, not the raw input` : `No hit`} values={top ? Array.from(engine.payload(top.artifactId)?.re ?? []) : []} />
          </div>
          <DecodedSurface retrieval={retrieval} />
        </React.Fragment>
      ) : null}
    </section>
  );
}
function ScoreMix({ hit: e }) {
  let t = [
      {
        label: `0.38 proximity`,
        value: 0.38 * e.distanceScore,
        className: `bg-accent`,
      },
      {
        label: `0.42 similarity`,
        value: 0.42 * e.queryScore,
        className: `bg-fg/80`,
      },
      {
        label: `0.20 pattern`,
        value: 0.2 * e.patternScore,
        className: `bg-muted`,
      },
    ],
    n = t.reduce((e, t) => e + t.value, 0) || 1;
  return (
    <div>
      <div
        className={`flex h-2 overflow-hidden rounded-full bg-bg`}
        aria-hidden={`true`}
      >
        {t.map((e) => (
          <div
            className={e.className}
            style={{
              width: `${((e.value / n) * 100).toFixed(2)}%`,
            }}
            key={e.label}
          />
        ))}
      </div>
      <p
        className={`mt-2 text-xs text-muted`}
      >{`Top hit mix before clipping. Brass proximity, paper similarity, muted pattern.`}</p>
    </div>
  );
}
function VectorBars({ title: e, hint: t, values: n }) {
  let r = n.reduce((e, t) => Math.max(e, Math.abs(t)), 0),
    a = n.length > 0 && r <= 1e-12;
  return (
    <div>
      <p className={`text-sm font-medium`}>{e}</p>
      <p className={`text-xs text-muted`}>{t}</p>
      {a ? (
        <p
          className={`mt-2 flex h-16 items-end font-mono text-xs text-muted`}
        >{`All zeros`}</p>
      ) : (
        <div className={`mt-2 flex h-16 items-end gap-px`} aria-hidden={`true`}>
          {n.map((e, t) => {
            let n = Math.abs(e),
              a = n <= 1e-12 ? 0 : Math.max(6, (n / r) * 100);
            return (
              <div className={`flex h-full flex-1 items-end`} key={t}>
                <div
                  className={e >= 0 ? `w-full bg-accent` : `w-full bg-fg/50`}
                  style={{
                    height: `${a.toFixed(2)}%`,
                  }}
                />
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
function DecodedSurface({ retrieval: e }) {
  let t = e.surfaceMag.reduce((e, t) => Math.max(e, t), 0) || 1;
  return (
    <div>
      <p className={`text-sm font-medium`}>{`Decoded surface`}</p>
      <p
        className={`text-xs text-muted`}
      >{`Inverse FFT of the field window. Separate from the decoded vector.`}</p>
      <div
        className={`mt-2 grid max-w-48 gap-px`}
        style={{
          gridTemplateColumns: `repeat(${e.surfaceW}, minmax(0, 1fr))`,
        }}
        aria-hidden={`true`}
      >
        {e.surfaceMag.map((e, n) => {
          let r = Math.log1p(e) / Math.log1p(t);
          return (
            <div
              className={`aspect-square bg-accent`}
              style={{
                opacity: (0.15 + 0.85 * r).toFixed(3),
              }}
              key={n}
            />
          );
        })}
      </div>
    </div>
  );
}
function LedgerPanel({ engine, selectedId, showDetails, onSelect }) {
  return (
    <section className={`panel p-4`}>
      <h2 className={`text-sm font-medium`}>{`On the plate`}</h2>
      {showDetails ? <p className={`mt-1 font-mono text-xs text-muted`}>{`ledger`}</p> : null}
      {engine.records.length === 0 ? <p className={`mt-2 text-sm text-muted`}>{`No retained records.`}</p> : null}
      <ul className={`mt-2 grid gap-1`}>
        {engine.records.map((artifact) => (
          <li key={artifact.artifactId}>
            <button
              type={`button`}
              onClick={() => onSelect(artifact.artifactId)}
              className={`flex min-h-11 w-full items-center justify-between gap-3 rounded-lg px-2 text-left ${artifact.artifactId === selectedId ? `bg-elevated` : ``}`}
            >
              <span className={`truncate text-sm`}>{artifact.tag}</span>
              <span className={`font-mono text-xs text-muted tabular-nums`}>({artifact.position[0]}, {artifact.position[1]})</span>
            </button>
          </li>
        ))}
      </ul>
      {showDetails && engine.edges.length ? (
        <ol className={`mt-3 grid gap-1 border-t border-line pt-3`}>
          {engine.nodes.map((node, index) => (
            <li className={`font-mono text-xs text-muted`} key={node.nodeId}>
              {index > 0 ? `next_memory → ` : ``}{node.tag}
            </li>
          ))}
        </ol>
      ) : null}
    </section>
  );
}
export default HMEPlate;
