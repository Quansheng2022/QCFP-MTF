# coding: utf-8
"""R2-14 successor test-only current governance identity resolver
(H1H base + successor activation evidence 44). Resolver/verifier only.

It resolves current Manifest/Baseline/Acceptance/commit identities from the
Human-accepted governance chain (successor R2-14 acceptance record + active
files + git) and fails closed on any binding inconsistency. It is NOT an
authority source. Historical evidence record 31 is never modified.
"""
from __future__ import annotations

import hashlib
import json
import subprocess
from pathlib import Path


def _sha256(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def current_identity(project_root: Path) -> dict:
    root = Path(project_root)
    accept_path = root / "audit/phase5/phase5_governance_acceptance.json"
    baseline_path = root / "audit/phase5/phase5_governance_baseline.json"
    manifest_path = root / "audit/phase5/frozen_surface_manifest.json"
    evidence_path = root / "audit/phase5/p5f_r2/54_r2_15f_successor_evidence.json"
    a = json.loads(accept_path.read_text(encoding="utf-8"))
    b = json.loads(baseline_path.read_text(encoding="utf-8"))
    m = json.loads(manifest_path.read_text(encoding="utf-8"))
    ev = json.loads(evidence_path.read_text(encoding="utf-8"))
    manifest_sha = _sha256(manifest_path)
    baseline_sha = _sha256(baseline_path)
    acceptance_sha = _sha256(accept_path)
    commit = str(a.get("governance_commit", ""))
    pins = {e["path"]: e["sha256"] for e in b.get("governance_files", [])}
    problems = []
    if a.get("decision") != "APPROVE" or a.get("accepted_by") != "HUMAN":
        problems.append("invalid human acceptance")
    if a.get("governance_baseline_sha256") != baseline_sha:
        problems.append("acceptance/baseline mismatch")
    if a.get("governance_manifest_sha256") != manifest_sha:
        problems.append("acceptance/manifest mismatch")
    if pins.get("audit/phase5/frozen_surface_manifest.json") != manifest_sha:
        problems.append("baseline manifest pin mismatch")
    if b.get("frozen_surface_manifest_sha256") != manifest_sha:
        problems.append("baseline top manifest mismatch")
    if not commit:
        problems.append("missing governance commit")
    else:
        check = subprocess.run(
            ["git", "-C", str(root), "rev-parse", "--verify", commit + "^{commit}"],
            capture_output=True)
        if check.returncode != 0:
            problems.append("invalid governance commit")
    if str(ev.get("completed_acceptance_sha256", "")) != acceptance_sha:
        problems.append("acceptance evidence mismatch")
    if problems:
        raise AssertionError("GOVERNANCE_CURRENT_STATE_CONFLICT: " + "; ".join(problems))
    return {
        "manifest": manifest_sha,
        "baseline": baseline_sha,
        "acceptance": acceptance_sha,
        "governance_commit": commit,
        "acceptance_commit": str(ev.get("A2", "")),
        "pins": pins,
        "manifest_revision": m.get("revision"),
    }
