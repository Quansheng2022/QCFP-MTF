# coding: utf-8
"""Live-vs-Backtest Gap Monitor 测试（59 号）"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[4]
CORE_DIR = PROJECT_ROOT / "Core"
if str(CORE_DIR) not in sys.path:
    sys.path.insert(0, str(CORE_DIR))

from QCFP_MTF.monitoring.gap_monitor import gap_monitor, gap_to_md


def _bt():
    return {"return": 0.20, "mfe": 0.25, "mae": -0.05, "slippage": 0.005,
            "entry": 0.0, "exit": 0.0, "holding": 4.0, "cost": 0.01}


def test_healthy_no_gap():
    r = gap_monitor(_bt(), dict(_bt()))
    assert r.status == "HEALTHY"


def test_warning_on_mild_gap():
    live = dict(_bt())
    live["mfe"] = 0.20     # 20% 偏差
    r = gap_monitor(_bt(), live, warn_threshold=0.15, degrade_threshold=0.30)
    assert r.status == "WARNING"


def test_model_review_on_multiple_gaps():
    live = dict(_bt())
    live.update({"return": 0.10, "mfe": 0.12, "slippage": 0.01,
                 "cost": 0.02})
    r = gap_monitor(_bt(), live, warn_threshold=0.15,
                    degrade_threshold=0.30)
    assert r.status == "MODEL_REVIEW"
    assert len(r.degraded_fields) >= 3


def test_gap_to_md():
    md = gap_to_md(gap_monitor(_bt(), dict(_bt())))
    assert "Gap Monitor" in md
