# coding: utf-8
"""Critical Path Observability 测试（57 号）"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[4]
CORE_DIR = PROJECT_ROOT / "Core"
if str(CORE_DIR) not in sys.path:
    sys.path.insert(0, str(CORE_DIR))

from QCFP_MTF.monitoring.critical_path_observability import \
    critical_path_observability


def _steps():
    return {stage: {"status": "OK", "latency_ms": 3, "version": "v1",
                    "io_hash": f"h-{stage}"}
            for stage in ("evidence_available", "pit_valid",
                          "permission_generated", "wave_generated",
                          "governance_finalized", "snapshot_committed",
                          "ledger_hash_committed",
                          "execution_instruction_generated")}


def test_full_path_ok():
    r = critical_path_observability(_steps())
    assert r["all_ok"] is True
    assert r["first_blocker"] is None
    assert len(r["path"]) == 8
    assert r["hint"] == "决策链完整"


def test_locate_blocker_at_ledger():
    steps = _steps()
    steps["ledger_hash_committed"] = {"status": "FAIL",
                                      "latency_ms": None,
                                      "version": "v1"}
    r = critical_path_observability(steps)
    assert r["all_ok"] is False
    assert r["first_blocker"] == "ledger_hash_committed"
    assert "LEDGER" in r["hint"]


def test_first_blocker_not_later_failure():
    steps = _steps()
    steps["pit_valid"] = {"status": "FAIL"}
    steps["wave_generated"] = {"status": "FAIL"}
    r = critical_path_observability(steps)
    assert r["first_blocker"] == "pit_valid"


def test_missing_step_detected():
    steps = _steps()
    del steps["snapshot_committed"]
    r = critical_path_observability(steps)
    assert r["first_blocker"] == "snapshot_committed"
    assert r["path"][5]["status"] == "MISSING"
