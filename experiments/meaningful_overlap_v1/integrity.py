"""Fail-closed source/registration checks before any reserved corpus is created."""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import subprocess

from .dataset import _TestPermit

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
IMPORTED = ("hme_engine.py", "experiments/field_retrieval_v1/retrieval.py",
            "experiments/nn_baseline_v1/evaluate.py")


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def source_hashes():
    paths = sorted(set([*IMPORTED, "tests/test_meaningful_overlap.py",
                       *[str(p.relative_to(ROOT)) for p in HERE.glob("*.py")],
                       *[str(p.relative_to(ROOT)) for p in HERE.glob("*.json")
                         if p.name != "REGISTRATION_APPROVAL.json"],
                       *[str(p.relative_to(ROOT)) for p in HERE.glob("*.md")
                         if p.name != "DEVELOPMENT_REPORT.md"]]))
    return {name: digest(ROOT/name) for name in paths}


def verify_imports():
    provenance = json.loads((HERE/"SOURCE_PROVENANCE.json").read_text())
    for name in IMPORTED:
        if digest(ROOT/name) != provenance["files"][name]["sha256"]:
            raise RuntimeError(f"Imported source changed: {name}")
    return provenance


def git(*args):
    return subprocess.check_output(["git", *args], cwd=ROOT, stderr=subprocess.PIPE).decode().strip()


def verify_registration(commit, approval_path):
    """No network or generation until syntax and proposed-status gates pass.

    An approval document is a review artifact, not an authentication system.
    It must be explicitly supplied after user approval, committed and remotely
    published before execution. This build contains no such approval.
    """
    protocol = json.loads((HERE/"protocol.json").read_text())
    if protocol["status"] != "REGISTERED":
        raise PermissionError("Protocol is DESIGN / DEVELOP; approval and registration required")
    if not re.fullmatch(r"[0-9a-f]{40}", commit or ""):
        raise ValueError("Expected full immutable registration commit")
    path = Path(approval_path).resolve()
    if path != HERE/"REGISTRATION_APPROVAL.json":
        raise ValueError("Approval must be the designated committed registration artifact")
    approval = json.loads(path.read_text())
    required = {"status", "approved_by", "approval_reference", "approved_at_utc", "protocol_id",
                "source_sha256", "reserved_namespace", "prior_test_exposure", "contamination_decision"}
    if not required <= approval.keys() or approval["status"] != "APPROVED" or approval["protocol_id"] != "HME-MO-1":
        raise PermissionError("Incomplete or unapproved registration")
    if not all(isinstance(approval[k], str) and approval[k].strip()
               for k in ("approved_by", "approval_reference", "approved_at_utc", "contamination_decision")):
        raise PermissionError("Approval reference, time and contamination decision required")
    if approval["prior_test_exposure"] is not False or approval["reserved_namespace"] != "HME-MO-1/reserved_test/000..049":
        raise PermissionError("Exposed test namespace needs a separately reviewed amendment and fresh namespace")
    selected = json.loads((HERE/"FROZEN_BASELINE.json").read_text())
    if selected["status"] != "FROZEN_AFTER_VALIDATION_TUNING":
        raise PermissionError("Vector baseline has not been frozen")
    current = source_hashes()
    if current != approval["source_sha256"]:
        raise RuntimeError("Exact configuration/source hash set mismatch")
    verify_imports()
    git("merge-base", "--is-ancestor", commit, "HEAD")
    for name, sha in {**current, str(path.relative_to(ROOT)): digest(path)}.items():
        raw = subprocess.check_output(["git", "show", f"{commit}:{name}"], cwd=ROOT)
        if hashlib.sha256(raw).hexdigest() != sha:
            raise RuntimeError(f"Registered bytes differ: {name}")
    # Fresh canonical-origin evidence; do not trust a local branch or local ref.
    canonical = "https://github.com/donaldtuttle/HME.git"
    remote_refs = git("ls-remote", "--heads", canonical)
    git("fetch", "--prune", "--no-tags", canonical, "+refs/heads/*:refs/hme-mo-registration/*")
    containing = git("for-each-ref", f"--contains={commit}", "--format=%(objectname) %(refname)", "refs/hme-mo-registration/")
    published_tips = {line.split()[0] for line in remote_refs.splitlines() if line.strip()}
    containing = "\n".join(line for line in containing.splitlines() if line.split()[0] in published_tips)
    if not containing:
        raise PermissionError("Registration is not visible on canonical remote branches")
    return _TestPermit(commit), {"commit": commit, "source_sha256": current,
        "approval_sha256": digest(path), "remote_refs": remote_refs, "containing_refs": containing,
        "verified_utc": datetime.now(timezone.utc).isoformat()}
