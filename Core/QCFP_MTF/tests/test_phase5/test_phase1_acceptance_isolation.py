# coding: utf-8
"""FIX-02B — Frozen Evidence Test-Side-Effect Isolation.

Root cause (PROVEN, recorded in audit/phase5):
    Core/QCFP_MTF/tests/test_governance/test_phase1.py::
    test_phase1_acceptance_pending_baseline() calls
    phase1_acceptance() WITHOUT out_dir, so the production default path
    regenerates frozen audit/phase1/phase1_acceptance.json during pytest.

Phase 5 remediation:
    * The frozen historical test is NOT modified.
    * Production governance/phase1.py is NOT modified.
    * This file preserves the original behavioral assertions but invokes
      phase1_acceptance(out_dir=tmp_path), and proves the frozen evidence
      file is byte-identical before/after.
"""

import hashlib
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[4]
CORE_DIR = PROJECT_ROOT / "Core"
if str(CORE_DIR) not in sys.path:
    sys.path.insert(0, str(CORE_DIR))


def _frozen_phase1_acceptance() -> Path:
    return PROJECT_ROOT / "audit" / "phase1" / "phase1_acceptance.json"


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_phase1_acceptance_pending_baseline_isolated(tmp_path):
    """FIX-02B equivalent of the historical Phase 1 acceptance test.

    Original assertions preserved verbatim from
    test_governance/test_phase1.py::
    test_phase1_acceptance_pending_baseline(); the only change is
    out_dir=tmp_path so no frozen evidence is regenerated.
    """
    from QCFP_MTF.governance.phase1 import phase1_acceptance

    acceptance = phase1_acceptance(out_dir=tmp_path)
    gates = acceptance["gates"]
    for name in ("version_authority", "freeze_scope", "canonical_spec",
                 "decision_authority", "traceability"):
        assert gates[name]["pass"], (name, gates[name].get("problems"))
    baseline = gates["baseline"]
    assert baseline["verdict"] in ("BASELINE_PASS", "BASELINE_CHANGED")
    if baseline["verdict"] == "BASELINE_CHANGED":
        assert "phase1_authority_surface_hash" in baseline.get("drift", {})
    assert acceptance["phase1_authority_surface_sha256"]
    # The isolated call must still write its evidence — into tmp_path only.
    assert (tmp_path / "phase1_acceptance.json").exists()
    assert (tmp_path / "phase1_acceptance.md").exists()


def test_phase1_acceptance_isolated_does_not_touch_frozen_evidence(tmp_path):
    """FIX-02B immutability proof: isolated call leaves frozen evidence intact."""
    frozen = _frozen_phase1_acceptance()
    assert frozen.exists(), "frozen phase1 acceptance evidence must exist"
    before = _sha256(frozen)

    from QCFP_MTF.governance.phase1 import phase1_acceptance

    acceptance = phase1_acceptance(out_dir=tmp_path)
    assert acceptance["gates"]

    after = _sha256(frozen)
    assert after == before, (
        "phase1_acceptance(out_dir=tmp_path) must never regenerate the frozen "
        "audit/phase1/phase1_acceptance.json"
    )
    assert (tmp_path / "phase1_acceptance.json").exists()
    assert (tmp_path / "phase1_acceptance.md").exists()
