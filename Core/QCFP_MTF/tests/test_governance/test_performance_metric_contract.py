# coding: utf-8
"""PerformanceMetricContract 唯一指标层测试（Release 2：新 18 号）"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[4]
CORE_DIR = PROJECT_ROOT / "Core"
if str(CORE_DIR) not in sys.path:
    sys.path.insert(0, str(CORE_DIR))

from QCFP_MTF.governance.performance_metric_contract import \
    metric_authority, metric_authority_check, same_returns_same_metrics


def test_single_authority():
    r = metric_authority()
    assert r["metric_authority_count"] == 1
    assert r["authority"] == "backtest.performance.evaluate"


def test_self_computed_metrics_violation():
    r = metric_authority_check({"backtest.py": ["sharpe", "mdd"],
                                "report.py": ["cagr"]})
    assert r["verdict"] == "METRIC_AUTHORITY_VIOLATION"
    assert len(r["violations"]) == 2


def test_no_violation():
    r = metric_authority_check({"report.py": ["layout"]})
    assert r["verdict"] == "SINGLE_METRIC_AUTHORITY"


def test_same_returns_same_metrics():
    r = same_returns_same_metrics([0.01, -0.005, 0.02, 0.01, -0.01, 0.02])
    assert r["consistent"] is True
