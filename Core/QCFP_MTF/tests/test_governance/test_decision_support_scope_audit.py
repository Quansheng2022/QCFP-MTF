# coding: utf-8
"""Decision Support Scope Audit 测试（P1-10）"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[4]
CORE_DIR = PROJECT_ROOT / "Core"
if str(CORE_DIR) not in sys.path:
    sys.path.insert(0, str(CORE_DIR))

from QCFP_MTF.governance.decision_support_scope_audit import (
    audit_scope, classify)


def test_classification_rules():
    assert classify("decision.engine") == "CORE_DECISION"
    assert classify("monitoring.runtime_evidence") == "CORE_EVIDENCE"
    assert classify("execution.broker_adapter") == "OPTIONAL_EXECUTION"
    assert classify("ablation.matrix") == "RESEARCH_ONLY"
    assert classify("common.paths") == "SUPPORT"


def test_scope_audit_gates():
    r = audit_scope()
    assert r["decision_critical_loc_down"] is True
    assert r["active_features"]["not_increased"] is True
    # Broker 模块不得出现在 Production Reachable 集合
    assert r["optional_execution_in_production"] == []
    assert all(r["gates"].values())
    assert r["schema"] == "DECISION-SUPPORT-SCOPE-AUDIT-1"
