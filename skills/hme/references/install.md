# Install (model-agnostic)

This pack follows the [Agent Skills](https://agentskills.io/specification) open standard.

Folder must be named `hme` to match the YAML `name` field.

```
hme/
├── SKILL.md
├── agents/
│   └── openai.yaml
└── references/
    ├── architecture.md
    ├── changelog.md
    └── install.md
```

HME is a DEVELOP typed realization with no canonical weight. Pair explicitly
with the qoft-qosmos Kernel v1.1 DEVELOP candidate, which remains pending
formal adoption beside the authoritative root v1.0 contract.

## Claude

- **Claude.ai Skills:** Settings → Capabilities → Skills → Upload the `hme` folder (or zip).
- **Claude Code:** copy to `~/.claude/skills/hme/` or `.claude/skills/hme/`.
- **Claude Projects:** attach `SKILL.md` and add: “HME is a DEVELOP realization.
  Do not promote it to QOFT canon. Default write glyph is Σ◯. Compute
  Ψmeta_pre fields before Λψ and finalize the HME record after.”

## ChatGPT

- **Native Skills:** upload the same folder. Optional UI chrome in `agents/openai.yaml`.
- **Codex:** `$HOME/.agents/skills/hme/` or `$REPO_ROOT/.agents/skills/hme/`.
- **Custom GPT / Project:** paste `SKILL.md` into Instructions and prepend: “This SKILL.md is canonical for HME work. Follow the firewall. HME is not QOFT canon.”

## Pairing

Install the `qoft-qosmos` Kernel v1.1 DEVELOP candidate beside this skill when
it is explicitly required. Calculus operators live there. Memory
encode/retrieve/overlay ticks live here.

Tick pairing: HME computes Ψmeta_pre fields before Λψ and finalizes its tick
record after the decision. The candidate kernel requires Ψmeta_post after Λψ.
To satisfy both, use an explicit adapter to emit Ψmeta_post; the finalized HME
pre record does not replace it.

HME source is proprietary. The skill teaches the public contract; it does not relicense the engine.
