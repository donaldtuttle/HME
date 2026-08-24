# HME Agent Skill

The portable HME Agent Skill is located at
[`skills/hme/SKILL.md`](../skills/hme/SKILL.md).

It defines the agent-facing encode, retrieve, replay, overlay telemetry, and
QMesh lineage contract for the pinned HME realization. It is not the engine
implementation, an independent rerun of the evidence, or QOFT canon.

Status: DEVELOP Typed Realization  
Canonical weight: none  
Engine pin: `f81fb49e265d83f5206220584dfc6cabf28aeee5266aca33654182be1549c080`  
Companion calculus: `qoft-qosmos` Kernel v1.1 DEVELOP candidate (pending adoption)  
License: [`skills/hme/LICENSE.txt`](../skills/hme/LICENSE.txt)

The source pin was verified against `qosmos_hme_engine.py` on repository commit
`64e3bba879bc9c29a4721081351b43871f8a9feb`. Reported retrieval figures are
traceable to
[`evidence/hme_independent_audit_2026-08-23.json`](../evidence/hme_independent_audit_2026-08-23.json);
this skill packaging change does not rerun that harness.
