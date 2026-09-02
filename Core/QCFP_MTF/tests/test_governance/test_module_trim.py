# coding: utf-8
"""Module Trim Execution 测试（20 号）"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[4]
CORE_DIR = PROJECT_ROOT / "Core"
if str(CORE_DIR) not in sys.path:
    sys.path.insert(0, str(CORE_DIR))

from QCFP_MTF.governance.module_trim import module_trim_execute, \
    quarterly_trim_report


def _modules():
    return {
        "Wave": {"alpha_improvement": 0.08, "risk_reduction": 0.02,
                 "execution_improvement": 0.0,
                 "governance_necessity": 0.0, "complexity_cost": 0.01},
        "LegacyScore": {"alpha_improvement": 0.0, "risk_reduction": 0.0,
                        "execution_improvement": 0.0,
                        "governance_necessity": 0.0,
                        "complexity_cost": 0.05},
        "Regime": {"alpha_improvement": 0.03, "risk_reduction": 0.0,
                   "execution_improvement": 0.0,
                   "governance_necessity": 0.0, "complexity_cost": 0.02},
    }


def test_module_trim_executes_deletion():
    ledger = []
    r = module_trim_execute(_modules(), deletion_ledger=ledger)
    assert "Wave" in r["kept"]
    assert "LegacyScore" in r["dropped"]
    assert "Regime" in r["review"]
    assert len(ledger) == 1
    assert ledger[0]["action"] == "RETIRED"


def test_quarterly_trim_report():
    ledger = [{"module": "LegacyScore", "action": "RETIRED"}]
    r = quarterly_trim_report(ledger, period="2026-Q3")
    assert r["deleted_modules"] == ["LegacyScore"]
    assert r["deletion_count"] == 1
    assert "删除了什么" in r["principle"] or "删除" in r["principle"]
