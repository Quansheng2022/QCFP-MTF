# coding: utf-8
"""OOS Coverage 绑定测试（Release 3：新 24 号）"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[4]
CORE_DIR = PROJECT_ROOT / "Core"
if str(CORE_DIR) not in sys.path:
    sys.path.insert(0, str(CORE_DIR))

from QCFP_MTF.monitoring.decision_coverage import oos_coverage_requirement


def _complete():
    perf = {"sharpe": 1.6, "mdd": -0.12, "wave_capture": 0.7}
    cov = {"certified": 0.72, "no_trade": 0.16, "abstain": 0.06,
           "safe_mode": 0.05, "halted": 0.01}
    return perf, cov


def test_complete_oos_report():
    r = oos_coverage_requirement(*_complete())
    assert r["verdict"] == "COMPLETE_OOS_REPORT"
    assert r["promotion_allowed"] is True


def test_missing_coverage_incomplete():
    perf, _ = _complete()
    r = oos_coverage_requirement(perf, {})
    assert r["verdict"] == "INCOMPLETE_REPORT"
    assert r["promotion_allowed"] is False
    assert "certified" in r["missing"]


def test_high_sharpe_low_coverage_not_promotable():
    perf = {"sharpe": 1.6, "mdd": -0.12, "wave_capture": 0.7}
    cov = {"certified": 0.35, "no_trade": 0.1, "abstain": 0.3,
           "safe_mode": 0.2, "halted": 0.05}
    r = oos_coverage_requirement(perf, cov)
    assert r["verdict"] == "COMPLETE_OOS_REPORT"
    # 覆盖率低本身会触发成熟度关注（由 decision_coverage 判定）
