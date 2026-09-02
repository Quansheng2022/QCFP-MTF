# coding: utf-8
"""Negative Result Registry 测试（56 号：负结果登记）"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[4]
CORE_DIR = PROJECT_ROOT / "Core"
if str(CORE_DIR) not in sys.path:
    sys.path.insert(0, str(CORE_DIR))

from QCFP_MTF.research.negative_result_registry import \
    NegativeResultRegistry, normalize_hypothesis


def _entry():
    return {
        "hypothesis": "Wave acceleration filter 提升波段捕获",
        "experiment": "EXP-NEG-01",
        "oos_result": "Sharpe -0.05",
        "ablation_result": "无增量",
        "failure_reason": "OOS 无风险调整后增量",
        "retired_version": "2.5.0",
    }


def test_normalize_hypothesis():
    assert normalize_hypothesis("Wave acceleration filter "
                                "提升波段捕获!") == \
        normalize_hypothesis("wave acceleration filter 提升波段捕获")


def test_record_and_exact_match():
    reg = NegativeResultRegistry()
    reg.record(_entry())
    hit = reg.find_prior_failure(
        "Wave acceleration filter 提升波段捕获")
    assert hit["found"] is True
    assert hit["match"] == "EXACT"
    assert hit["record"]["retired_version"] == "2.5.0"


def test_reintroduction_rejected():
    reg = NegativeResultRegistry()
    reg.record(_entry())
    r = reg.check_reintroduction(
        "Wave acceleration filter 提升波段捕获（新版本）")
    assert r["verdict"] == "REJECT_REINTRODUCTION"


def test_new_hypothesis_no_prior_failure():
    reg = NegativeResultRegistry()
    reg.record(_entry())
    r = reg.check_reintroduction("全新的流动性冲击过滤器")
    assert r["verdict"] == "NO_PRIOR_FAILURE"
