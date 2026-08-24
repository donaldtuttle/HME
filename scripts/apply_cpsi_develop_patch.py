from pathlib import Path
import hashlib
import re


def replace_once(text: str, old: str, new: str, label: str) -> str:
    if old not in text:
        raise SystemExit(f"anchor missing: {label}")
    if text.count(old) != 1:
        raise SystemExit(f"anchor not unique: {label} ({text.count(old)})")
    return text.replace(old, new, 1)


engine_path = Path("qosmos_hme_engine.py")
engine = engine_path.read_text(encoding="utf-8")

engine = replace_once(
    engine,
    "    retrieval_distance_scale: float = 0.25\n\n    def __post_init__(self) -> None:\n",
    "    retrieval_distance_scale: float = 0.25\n    relevance_threshold: float = 0.0\n\n    def __post_init__(self) -> None:\n",
    "HMEConfig relevance_threshold",
)
engine = replace_once(
    engine,
    '        if self.retrieval_distance_scale <= 0.0:\n            raise ValueError("retrieval_distance_scale must be positive")\n\n\n@dataclass(slots=True)\nclass CollapseConfig:\n',
    '        if self.retrieval_distance_scale <= 0.0:\n            raise ValueError("retrieval_distance_scale must be positive")\n        if not np.isfinite(self.relevance_threshold) or not 0.0 <= self.relevance_threshold <= 1.0:\n            raise ValueError("relevance_threshold must be finite and in [0, 1]")\n\n\n@dataclass(slots=True)\nclass CollapseConfig:\n',
    "HMEConfig relevance validation",
)

engine = replace_once(
    engine,
    "    quantization_levels: int = 12\n    stable_drift_max: float = 0.08\n\n    def __post_init__(self) -> None:\n",
    "    quantization_levels: int = 12\n    stable_drift_max: float = 0.08\n\n    # DEVELOP realization-only salience switches. Disabled by default.\n    influence_write_gain: bool = False\n    influence_retrieval: bool = False\n    enable_inscription_rejection: bool = False\n    write_gain_scale: float = 0.25\n    write_gain_floor: float = 0.05\n    write_gain_ceiling: float = 1.5\n    retrieval_weight: float = 0.15\n    rejection_threshold: float | None = None\n\n    def __post_init__(self) -> None:\n",
    "CollapseConfig salience fields",
)
engine = replace_once(
    engine,
    '        if self.quantization_levels < 2:\n            raise ValueError("quantization_levels must be at least 2")\n\n\n@dataclass(slots=True)\nclass HMEArtifact:\n',
    '        if self.quantization_levels < 2:\n            raise ValueError("quantization_levels must be at least 2")\n        if not np.isfinite(self.write_gain_scale) or self.write_gain_scale < 0.0:\n            raise ValueError("write_gain_scale must be finite and non-negative")\n        if not np.isfinite(self.write_gain_floor) or self.write_gain_floor < 0.0:\n            raise ValueError("write_gain_floor must be finite and non-negative")\n        if not np.isfinite(self.write_gain_ceiling) or self.write_gain_ceiling < self.write_gain_floor:\n            raise ValueError("write_gain_ceiling must be finite and >= write_gain_floor")\n        if not np.isfinite(self.retrieval_weight) or not 0.0 <= self.retrieval_weight <= 1.0:\n            raise ValueError("retrieval_weight must be finite and in [0, 1]")\n        if self.rejection_threshold is not None and not np.isfinite(self.rejection_threshold):\n            raise ValueError("rejection_threshold must be finite or None")\n\n\n@dataclass(slots=True)\nclass HMEArtifact:\n',
    "CollapseConfig salience validation",
)

old_records = '''@dataclass(slots=True)
class RetrievalHit:
    artifact_id: str
    score: float
    distance_score: float
    query_score: float
    pattern_score: float

    def to_dict(self) -> dict[str, Any]:
        return _jsonable(asdict(self))


@dataclass(slots=True)
class HMERetrieval:
    position: tuple[int, int]
    radius: int
    window: ComplexArray
    decoded_surface: ComplexArray
    decoded_vector: ComplexArray
    confidence: float
    hits: list[RetrievalHit]
'''
new_records = '''@dataclass(slots=True)
class RetrievalHit:
    artifact_id: str
    base_score: float
    collapse_salience: float
    final_score: float
    distance_score: float
    query_score: float
    pattern_score: float

    @property
    def score(self) -> float:
        """Legacy alias: score is the ephemeral final retrieval score."""
        return self.final_score

    def to_dict(self) -> dict[str, Any]:
        data = _jsonable(asdict(self))
        data["score"] = self.final_score
        return data


@dataclass(slots=True)
class HMERetrieval:
    position: tuple[int, int]
    radius: int
    window: ComplexArray
    decoded_surface: ComplexArray
    decoded_vector: ComplexArray
    confidence: float
    hits: list[RetrievalHit]
    outcome: str = "MATCH"
    rejected: bool = False
    rejection_reason: str | None = None
'''
engine = replace_once(engine, old_records, new_records, "retrieval records")
engine = replace_once(
    engine,
    '            "confidence": self.confidence,\n            "hits": [hit.to_dict() for hit in self.hits],\n            "decoded_vector": _jsonable(self.decoded_vector),\n',
    '            "confidence": self.confidence,\n            "outcome": self.outcome,\n            "rejected": self.rejected,\n            "rejection_reason": self.rejection_reason,\n            "hits": [hit.to_dict() for hit in self.hits],\n            "decoded_vector": _jsonable(self.decoded_vector),\n',
    "retrieval receipt serialization",
)

retrieve_pattern = re.compile(
    r'''    def retrieve\(\n        self,\n        position: tuple\[int, int\],\n        resolution_scale: int = 4,\n        \*,\n        query: ArrayLike \| str \| None = None,\n        top_k: int = 5,\n    \) -> HMERetrieval:\n.*?\n        return HMERetrieval\(\n            position=position,\n            radius=int\(resolution_scale\),\n            window=window,\n            decoded_surface=decoded_surface,\n            decoded_vector=decoded_vector,\n            confidence=confidence,\n            hits=hits,\n        \)\n''',
    re.S,
)
m = retrieve_pattern.search(engine)
if not m:
    raise SystemExit("retrieve implementation anchor missing")
new_retrieve = '''    def retrieve(
        self,
        position: tuple[int, int],
        resolution_scale: int = 4,
        *,
        query: ArrayLike | str | None = None,
        top_k: int = 5,
        relevance_threshold: float | None = None,
        influence_retrieval: bool = False,
        retrieval_weight: float = 0.15,
        enable_inscription_rejection: bool = False,
        rejection_threshold: float | None = None,
    ) -> HMERetrieval:
        if top_k < 1:
            raise ValueError("top_k must be positive")
        threshold = (
            self.config.relevance_threshold
            if relevance_threshold is None
            else float(relevance_threshold)
        )
        if not np.isfinite(threshold) or not 0.0 <= threshold <= 1.0:
            raise ValueError("relevance_threshold must be finite and in [0, 1]")
        if not np.isfinite(retrieval_weight) or not 0.0 <= retrieval_weight <= 1.0:
            raise ValueError("retrieval_weight must be finite and in [0, 1]")
        if rejection_threshold is not None and not np.isfinite(rejection_threshold):
            raise ValueError("rejection_threshold must be finite or None")

        position = (int(position[0]), int(position[1]))
        window, _ = self._extract_window(position, resolution_scale)
        decoded_surface = np.fft.ifft2(window)

        query_vector: ComplexArray | None = None
        if isinstance(query, str):
            query_vector = deterministic_symbol_vector(
                query, self.encoding_resolution
            ).astype(np.complex128)
        elif query is not None:
            query_vector = _as_1d_complex(
                query, target_size=self.encoding_resolution
            )
            query_vector = _normalize(query_vector).astype(np.complex128)

        candidates: list[RetrievalHit] = []
        field_norm = float(np.linalg.norm(self.field))
        distance_sigma = max(
            self.memory_size * self.config.retrieval_distance_scale, 1.0
        )

        for artifact_id, artifact in self.records.items():
            dx = artifact.position[0] - position[0]
            dy = artifact.position[1] - position[1]
            distance = math.sqrt(dx * dx + dy * dy)
            distance_score = math.exp(-0.5 * (distance / distance_sigma) ** 2)

            payload = self._payloads[artifact_id]
            if query_vector is None:
                query_score = 1.0
            else:
                denom = float(np.linalg.norm(payload) * np.linalg.norm(query_vector))
                query_score = (
                    float(abs(np.vdot(payload, query_vector)) / denom)
                    if denom > _EPS
                    else 0.0
                )

            pattern = self._patterns[artifact_id]
            grid_slice, pattern_slice = self._patch_slices(
                artifact.position, pattern.shape
            )
            field_patch = self.field[grid_slice]
            pattern_patch = pattern[pattern_slice]
            denom = float(np.linalg.norm(field_patch) * np.linalg.norm(pattern_patch))
            pattern_score = (
                float(abs(np.vdot(field_patch, pattern_patch)) / denom)
                if denom > _EPS and field_norm > _EPS
                else 0.0
            )

            base_score = float(np.clip(
                0.38 * distance_score + 0.42 * query_score + 0.20 * pattern_score,
                0.0,
                1.0,
            ))
            if base_score < threshold:
                continue

            raw_c = artifact.metadata.get("c_psi")
            if raw_c is None:
                collapse_salience = 0.0
            else:
                try:
                    c_value = float(raw_c)
                except (TypeError, ValueError):
                    c_value = 0.0
                if not np.isfinite(c_value):
                    c_value = 0.0
                positive_c = max(c_value, 0.0)
                collapse_salience = positive_c / (1.0 + positive_c)

            final_score = base_score
            if influence_retrieval:
                final_score = base_score + (
                    retrieval_weight
                    * collapse_salience
                    * (1.0 - base_score)
                )
            final_score = float(np.clip(final_score, 0.0, 1.0))

            candidates.append(
                RetrievalHit(
                    artifact_id=artifact_id,
                    base_score=base_score,
                    collapse_salience=collapse_salience,
                    final_score=final_score,
                    distance_score=distance_score,
                    query_score=query_score,
                    pattern_score=pattern_score,
                )
            )

        candidates.sort(key=lambda hit: hit.final_score, reverse=True)
        hits = candidates[:top_k]

        if hits:
            weights = np.asarray([max(hit.final_score, _EPS) for hit in hits])
            payloads = np.stack([self._payloads[hit.artifact_id] for hit in hits])
            decoded_vector = np.average(payloads, axis=0, weights=weights)
            confidence = float(hits[0].final_score)
            outcome = "MATCH"
        else:
            decoded_vector = np.zeros(
                self.encoding_resolution, dtype=np.complex128
            )
            confidence = 0.0
            outcome = "NO_MATCH"

        rejected = False
        rejection_reason: str | None = None
        if (
            hits
            and enable_inscription_rejection
            and rejection_threshold is not None
        ):
            best_artifact = self.records[hits[0].artifact_id]
            raw_c = best_artifact.metadata.get("c_psi")
            try:
                origin_c = float(raw_c) if raw_c is not None else None
            except (TypeError, ValueError):
                origin_c = None
            if origin_c is not None and np.isfinite(origin_c) and origin_c < rejection_threshold:
                rejected = True
                outcome = "LOW_INSCRIPTION_SALIENCE"
                rejection_reason = (
                    f"originating c_psi {origin_c:.6g} below "
                    f"rejection_threshold {float(rejection_threshold):.6g}"
                )

        return HMERetrieval(
            position=position,
            radius=int(resolution_scale),
            window=window,
            decoded_surface=decoded_surface,
            decoded_vector=decoded_vector,
            confidence=confidence,
            hits=hits,
            outcome=outcome,
            rejected=rejected,
            rejection_reason=rejection_reason,
        )
'''
engine = engine[:m.start()] + new_retrieve + engine[m.end():]

engine = replace_once(
    engine,
    "    def encode_memory(\n        self,\n        data: ArrayLike | str,\n",
    '''    def _write_gain_multiplier(self, c_psi: Any) -> float:
        cfg = self.collapse_config
        if not cfg.influence_write_gain or c_psi is None:
            return 1.0
        try:
            value = float(c_psi)
        except (TypeError, ValueError):
            return 1.0
        if not np.isfinite(value):
            return 1.0
        raw = 1.0 + cfg.write_gain_scale * max(value, 0.0)
        return float(np.clip(raw, cfg.write_gain_floor, cfg.write_gain_ceiling))

    def encode_memory(
        self,
        data: ArrayLike | str,
''',
    "write gain helper",
)
engine = replace_once(
    engine,
    "    ) -> HMEArtifact:\n        tick = self.step_index if t is None else int(t)\n        if isinstance(data, str):\n",
    '''    ) -> HMEArtifact:
        tick = self.step_index if t is None else int(t)
        durable_metadata = dict(metadata or {})
        effective_recursive_factor = float(recursive_factor) * self._write_gain_multiplier(
            durable_metadata.get("c_psi")
        )
        if isinstance(data, str):
''',
    "encode_memory gain prelude",
)
engine = replace_once(
    engine,
    "                recursive_factor,\n                glyph=glyph,\n                observer_weight=observer_weight,\n                t=tick,\n                metadata=metadata,\n",
    "                effective_recursive_factor,\n                glyph=glyph,\n                observer_weight=observer_weight,\n                t=tick,\n                metadata=durable_metadata,\n",
    "encode_symbol write gain",
)
engine = replace_once(
    engine,
    "                recursive_factor,\n                tag=tag,\n                glyph=glyph,\n                observer_weight=observer_weight,\n                t=tick,\n                metadata=metadata,\n",
    "                effective_recursive_factor,\n                tag=tag,\n                glyph=glyph,\n                observer_weight=observer_weight,\n                t=tick,\n                metadata=durable_metadata,\n",
    "encode vector write gain",
)
engine = replace_once(
    engine,
    "        return self.hme.retrieve(\n            position,\n            resolution_scale,\n            query=query,\n            top_k=top_k,\n        )\n",
    "        return self.hme.retrieve(\n            position,\n            resolution_scale,\n            query=query,\n            top_k=top_k,\n            relevance_threshold=self.hme.config.relevance_threshold,\n            influence_retrieval=self.collapse_config.influence_retrieval,\n            retrieval_weight=self.collapse_config.retrieval_weight,\n            enable_inscription_rejection=self.collapse_config.enable_inscription_rejection,\n            rejection_threshold=self.collapse_config.rejection_threshold,\n        )\n",
    "retrieve wrapper config",
)
engine = replace_once(
    engine,
    '                metadata={\n                    "committed_after_collapse": collapse_event is not None,\n                    **dict(metadata or {}),\n                },\n',
    '                metadata={\n                    "committed_after_collapse": collapse_event is not None,\n                    "c_psi": float(meta_pre.c_psi),\n                    **dict(metadata or {}),\n                },\n',
    "step c_psi persistence",
)
engine = replace_once(
    engine,
    '                "psi_meta": psi_meta_value,\n                "C_psi": c_psi,\n                "collapsed": collapse_event is not None,\n',
    '                "psi_meta": psi_meta_value,\n                "c_psi": float(c_psi),\n                "collapsed": collapse_event is not None,\n',
    "step_core c_psi persistence",
)
engine_path.write_text(engine, encoding="utf-8")

skill_path = Path("skills/hme/SKILL.md")
skill = skill_path.read_text(encoding="utf-8")
skill = replace_once(
    skill,
    "11. No LaTeX. Unicode glyphs only.\n",
    '''11. No LaTeX. Unicode glyphs only.
12. C(ψ) may drive the collapse trigger, optional inscription/write-gain salience,
    and optional retrieval salience. It must never determine semantic match
    eligibility. `NO_MATCH` is decided solely from base relevance.
13. Anti-drift: do not infer that stronger C(ψ) means a memory is more
    semantically relevant, more accurate, more truthful, or higher-confidence.
    C(ψ)-derived salience is realization-local provenance about the originating
    collapse/inscription event only.
''',
    "skill non-negotiable rules",
)
old_retrieve = '''Retrieve path:

    position + optional query
      → local field decode
      → candidate artifacts from the ledger
      → 0.38 distance + 0.42 query + 0.20 pattern
      → ranked HMERetrieval (confidence = top hit score)
'''
new_retrieve_skill = '''Retrieve (ordered pipeline — do not reorder):

    position + optional query
      → local field decode
      → base semantic relevance (distance + query + pattern)
      → relevance eligibility / NO_MATCH          ← gate first
      → eligible candidate set
      → optional C(ψ) salience reranking          ← headroom form only
      → best relevant hit
      → optional artifact-relative inscription rejection
      → ranked HMERetrieval receipt

Persistent vs ephemeral data ownership:

Durable (`artifact.metadata` only):

    "c_psi"          — write-time collapse diagnostic, if present

Ephemeral (`RetrievalHit` / `HMERetrieval` only):

    base_score
    collapse_salience
    final_score

Never write query-dependent scores back onto `HMEArtifact`.

Three distinct outcomes — do not conflate:

`NO_MATCH`
: No artifact passed semantic relevance. `hits = []`.

`LOW_INSCRIPTION_SALIENCE`
: A relevant artifact exists, but inscription policy rejected it on the basis of
  its originating C(ψ). Hits are retained; `rejected=True`;
  `rejection_reason` is set.

`MATCH`
: A relevant artifact exists and was not policy-rejected.

Forbidden: turning `LOW_INSCRIPTION_SALIENCE` into `NO_MATCH` or deleting the
hits under an inscription-policy rejection.
'''
skill = replace_once(skill, old_retrieve, new_retrieve_skill, "skill retrieve path")
skill = replace_once(
    skill,
    "Default class λ_c ≈ 1.67, κ_damp ≈ 0.15 when v27 constants are absent.\nDemo / test thresholds are local and must be labeled as such.\n",
    '''Default class λ_c ≈ 1.67, κ_damp ≈ 0.15 when v27 constants are absent.
Demo / test thresholds are local and must be labeled as such.

Current realization defaults (implementation settings, not HME invariants):

    write_gain_scale      = 0.25
    write_gain_floor      = 0.05
    write_gain_ceiling    = 1.5
    retrieval_weight      = 0.15
    relevance_threshold   = 0.0   (preserves prior “always return top_k”)
    rejection_threshold   = None
    influence_* flags     = False

Salience mechanisms (write-gain, retrieval salience, inscription rejection) are
optional DEVELOP switches. Before any claim that they improve HME behavior, run
the full C0–C7 ablation family and report main effects plus interactions. Until
then they remain experimental machinery with no efficacy claim.
''',
    "skill defaults and claim gate",
)
skill = replace_once(
    skill,
    '''- Do not interpret a top-1 hit as identity without a declared threshold.
  Reported repository audit (linked below; not rerun for this packaging change):
  unrelated query scored ~0.733; σ=0.50 noise yielded 119/128 correct; σ=1.00
  yielded 59/128. `NO_MATCH` policy is UNDEFINED.
''',
    '''- Do not interpret a top-1 hit as identity without a declared base-relevance
  threshold. `NO_MATCH` is now a base-relevance outcome; C(ψ) cannot create or
  erase semantic eligibility. Reported historical audit figures below predate
  the optional salience switches and are not evidence of efficacy.
''',
    "skill public API note",
)
skill_path.write_text(skill, encoding="utf-8")

tests_path = Path("tests/test_hme_engine.py")
tests = tests_path.read_text(encoding="utf-8")
if "test_no_match_gate_precedes_cpsi_salience" not in tests:
    tests += '''

def test_no_match_gate_precedes_cpsi_salience() -> None:
    engine = hme.QOSMOSHMEEngine(
        memory_size=24,
        encoding_resolution=8,
        hme_config=hme.HMEConfig(memory_size=24, encoding_resolution=8, relevance_threshold=0.99),
        collapse_config=hme.CollapseConfig(influence_retrieval=True, retrieval_weight=1.0),
        seed=1,
    )
    artifact = engine.encode_memory(
        "alpha", (12, 12), metadata={"c_psi": 1.0e6}
    )
    result = engine.retrieve_memory((0, 0), query="unrelated")
    assert result.outcome == "NO_MATCH"
    assert result.hits == []
    assert "base_score" not in artifact.metadata
    assert "collapse_salience" not in artifact.metadata
    assert "final_score" not in artifact.metadata


def test_retrieval_salience_uses_headroom_after_eligibility() -> None:
    engine = hme.QOSMOSHMEEngine(
        memory_size=24,
        encoding_resolution=8,
        collapse_config=hme.CollapseConfig(influence_retrieval=True, retrieval_weight=0.5),
        seed=2,
    )
    artifact = engine.encode_memory("alpha", (12, 12), metadata={"c_psi": 2.0})
    result = engine.retrieve_memory((12, 12), query="alpha")
    hit = next(hit for hit in result.hits if hit.artifact_id == artifact.artifact_id)
    expected_salience = 2.0 / 3.0
    expected = hit.base_score + 0.5 * expected_salience * (1.0 - hit.base_score)
    assert np.isclose(hit.collapse_salience, expected_salience)
    assert np.isclose(hit.final_score, expected)
    assert hit.final_score >= hit.base_score


def test_low_inscription_salience_retains_relevant_hits() -> None:
    engine = hme.QOSMOSHMEEngine(
        memory_size=24,
        encoding_resolution=8,
        collapse_config=hme.CollapseConfig(
            enable_inscription_rejection=True,
            rejection_threshold=0.5,
        ),
        seed=3,
    )
    artifact = engine.encode_memory("alpha", (12, 12), metadata={"c_psi": 0.1})
    result = engine.retrieve_memory((12, 12), query="alpha")
    assert result.outcome == "LOW_INSCRIPTION_SALIENCE"
    assert result.rejected is True
    assert result.rejection_reason
    assert result.hits
    assert result.hits[0].artifact_id == artifact.artifact_id


def test_write_gain_is_optional_bounded_and_cpsi_is_durable() -> None:
    base = hme.QOSMOSHMEEngine(memory_size=24, encoding_resolution=8, seed=4)
    influenced = hme.QOSMOSHMEEngine(
        memory_size=24,
        encoding_resolution=8,
        collapse_config=hme.CollapseConfig(
            influence_write_gain=True,
            write_gain_scale=0.25,
            write_gain_floor=0.05,
            write_gain_ceiling=1.5,
        ),
        seed=4,
    )
    a = base.encode_memory("alpha", (12, 12), recursive_factor=0.2, metadata={"c_psi": 4.0})
    b = influenced.encode_memory("alpha", (12, 12), recursive_factor=0.2, metadata={"c_psi": 4.0})
    assert np.isclose(a.gain, 0.2)
    assert np.isclose(b.gain, 0.3)
    assert b.metadata["c_psi"] == 4.0


def test_step_persists_lowercase_cpsi_only_for_new_salience_contract() -> None:
    engine = hme.QOSMOSHMEEngine(memory_size=24, encoding_resolution=8, seed=5)
    result = engine.step(
        np.ones((24, 24), dtype=np.complex128),
        memory_payload="tick-memory",
        memory_position=(12, 12),
        collapse_override=False,
    )
    assert result.memory_artifact is not None
    assert "c_psi" in result.memory_artifact.metadata
    assert "C_psi" not in result.memory_artifact.metadata
'''
tests_path.write_text(tests, encoding="utf-8")

engine_hash = hashlib.sha256(engine_path.read_bytes()).hexdigest()
old_hash = "f81fb49e265d83f5206220584dfc6cabf28aeee5266aca33654182be1549c080"
skill_path.write_text(skill_path.read_text(encoding="utf-8").replace(old_hash, engine_hash), encoding="utf-8")
tests_path.write_text(tests_path.read_text(encoding="utf-8").replace(old_hash, engine_hash), encoding="utf-8")

doc_path = Path("docs/agent-skill.md")
doc = doc_path.read_text(encoding="utf-8").replace(old_hash, engine_hash)
old_doc_note = '''The source pin was verified against `qosmos_hme_engine.py` on repository commit
`64e3bba879bc9c29a4721081351b43871f8a9feb`.'''
new_doc_note = '''The source pin above identifies the current DEVELOP realization after the paired
C(ψ) salience contract patch. The C0–C7 efficacy gate has not been executed by
this documentation/runtime update.'''
doc = replace_once(doc, old_doc_note, new_doc_note, "agent skill source note")
doc_path.write_text(doc, encoding="utf-8")

manifest_path = Path("MANIFEST.sha256")
manifest = manifest_path.read_text(encoding="utf-8").splitlines()
changed = [
    "qosmos_hme_engine.py",
    "skills/hme/SKILL.md",
    "tests/test_hme_engine.py",
    "docs/agent-skill.md",
]
digests = {p: hashlib.sha256(Path(p).read_bytes()).hexdigest() for p in changed}
out = []
seen = set()
for line in manifest:
    parts = line.split("  ", 1)
    if len(parts) == 2 and parts[1] in digests:
        out.append(f"{digests[parts[1]]}  {parts[1]}")
        seen.add(parts[1])
    else:
        out.append(line)
missing = set(changed) - seen
if missing:
    raise SystemExit(f"manifest paths missing: {sorted(missing)}")
manifest_path.write_text("\n".join(out) + "\n", encoding="utf-8")

print("engine_sha256", engine_hash)
