# coding: utf-8
"""Negative Result Registry → Feature Proposal 门测试（新 56 号）"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[4]
CORE_DIR = PROJECT_ROOT / "Core"
if str(CORE_DIR) not in sys.path:
    sys.path.insert(0, str(CORE_DIR))

from QCFP_MTF.research.negative_result_registry import \
    NegativeResultRegistry, feature_proposal_gate


def _registry():
    reg = NegativeResultRegistry()
    reg.record({
        "hypothesis": "Wave acceleration filter 提升波段捕获",
        "failure_reason": "OOS 无风险调整后增量",
        "retired_version": "2.5.0"})
    return reg


def test_new_hypothesis_allowed():
    r = feature_proposal_gate("全新流动性冲击过滤器", _registry())
    assert r["verdict"] == "PROPOSAL_ALLOWED"


def test_prior_failure_blocked_without_justification():
    r = feature_proposal_gate(
        "Wave acceleration filter 提升波段捕获（新版本）",
        _registry())
    assert r["verdict"] == "BLOCKED_NO_JUSTIFICATION"
    assert r["allowed"] is False


def test_prior_failure_allowed_with_justification():
    r = feature_proposal_gate(
        "Wave acceleration filter 提升波段捕获（新版本）",
        _registry(),
        justification="2026 年市场结构变化，旧 OOS 窗口不再适用")
    assert r["verdict"] == "PROPOSAL_ALLOWED_WITH_JUSTIFICATION"
    assert r["allowed"] is True
