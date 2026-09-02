# coding: utf-8
"""Alpha Correlation Monitor 测试（82 号）"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[4]
CORE_DIR = PROJECT_ROOT / "Core"
if str(CORE_DIR) not in sys.path:
    sys.path.insert(0, str(CORE_DIR))

from QCFP_MTF.alpha.correlation import alpha_correlation_report, \
    effective_alpha_count


def test_independent_signals():
    series = {"A": [1, 0, 1, 0, 1], "B": [1, 1, 0, 0, 1]}
    r = effective_alpha_count(series)
    assert r["n_signals"] == 2
    assert r["effective_count"] <= 2.0


def test_duplicate_signals_detected():
    x = [1, 0, 1, 1, 0, 1]
    series = {"A": x, "B": list(x), "C": [1, 1, 0, 0, 1, 1]}
    r = effective_alpha_count(series)
    assert r["duplicate_risk"] is True
    assert any(p[0] == "A" and p[1] == "B" for p in
               r["high_correlation_pairs"])
    assert r["effective_count"] < 3.0


def test_alpha_correlation_report():
    r = alpha_correlation_report({"A": [1, 0, 1], "B": [0, 1, 0]})
    assert "interpretation" in r
    assert "有效独立信号" in r["interpretation"]
