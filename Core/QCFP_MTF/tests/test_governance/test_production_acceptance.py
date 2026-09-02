# coding: utf-8
"""Production Acceptance Contract 测试（51 号）"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[4]
CORE_DIR = PROJECT_ROOT / "Core"
if str(CORE_DIR) not in sys.path:
    sys.path.insert(0, str(CORE_DIR))

from QCFP_MTF.governance.production_acceptance import \
    PRODUCTION_ACCEPTANCE_GATES, production_acceptance_contract


def _all_ok():
    return {gate: {"ok": True, "evidence": f"ref-{gate}"}
            for gate in PRODUCTION_ACCEPTANCE_GATES}


def test_all_gates_pass_accepted():
    r = production_acceptance_contract(_all_ok())
    assert r["verdict"] == "ACCEPTED"
    assert r["failures"] == []
    assert r["binary_verdict"] is True


def test_single_governance_failure_rejects():
    gates = _all_ok()
    gates["GOVERNANCE"] = {"ok": False, "evidence": "越权 1 次"}
    r = production_acceptance_contract(gates)
    assert r["verdict"] == "REJECTED"
    assert r["failures"] == ["GOVERNANCE"]


def test_high_sharpe_cannot_override_governance():
    """Sharpe 再漂亮也不能覆盖治理失败（OOS PASS 但 Governance FAIL）。"""
    gates = _all_ok()
    gates["OOS"] = {"ok": True, "evidence": "Sharpe=3.0"}
    gates["GOVERNANCE"] = {"ok": False, "evidence": "非法权限跳变"}
    r = production_acceptance_contract(gates)
    assert r["verdict"] == "REJECTED"


def test_missing_unknown_gate_rejects():
    gates = _all_ok()
    gates["NO_CRITICAL_UNKNOWN"] = False
    r = production_acceptance_contract(gates)
    assert "NO_CRITICAL_UNKNOWN" in r["failures"]
    assert r["verdict"] == "REJECTED"
