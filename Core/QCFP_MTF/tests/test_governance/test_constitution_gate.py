# coding: utf-8
"""System Constitution 最高优先级 Regression Gate 测试（新 80 号）"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[4]
CORE_DIR = PROJECT_ROOT / "Core"
if str(CORE_DIR) not in sys.path:
    sys.path.insert(0, str(CORE_DIR))

from QCFP_MTF.governance.system_constitution import CONSTITUTION_PRINCIPLES, \
    constitution_gate


def test_twelve_principles():
    assert len(CONSTITUTION_PRINCIPLES) == 12
    keys = [k for k, _ in CONSTITUTION_PRINCIPLES]
    assert "LEDGER_HASH_REPLAY" in keys
    assert "OOS_ABLATION_STRESS_OVER_SUBJECTIVE" in keys
    assert "REPORT_CANNOT_CREATE_DECISION" in keys
    assert "RESEARCH_CANNOT_WRITE_PRODUCTION" in keys


def test_constitution_pass_allows():
    checks = {k: True for k, _ in CONSTITUTION_PRINCIPLES}
    r = constitution_gate(checks, {"sharpe": 0.8})
    assert r["verdict"] == "CONSTITUTION_PASS"
    assert r["promotion"] == "ALLOWED"


def test_constitution_fail_rejects_despite_performance():
    checks = {k: True for k, _ in CONSTITUTION_PRINCIPLES}
    checks["REPORT_CANNOT_CREATE_DECISION"] = False
    r = constitution_gate(checks, {"sharpe": 3.0})
    assert r["verdict"] == "CONSTITUTION_FAIL"
    assert r["promotion"] == "REJECTED"
    assert "Sharpe +30%" in r["rule"] or "破例" in r["rule"]
