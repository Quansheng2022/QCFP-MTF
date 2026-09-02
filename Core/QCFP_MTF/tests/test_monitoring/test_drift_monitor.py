# coding: utf-8
"""Production Drift Monitor 测试（30 号）"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[4]
CORE_DIR = PROJECT_ROOT / "Core"
if str(CORE_DIR) not in sys.path:
    sys.path.insert(0, str(CORE_DIR))

from QCFP_MTF.monitoring.drift_monitor import drift_monitor, drift_to_md


def _metrics(**kw):
    m = {"data_missing_rate": 0.02, "data_avail_lag": 3,
         "permission_dist_shift": 0.05, "wave_dist_shift": 0.05,
         "win_rate_trend": 1.0, "mfe_capture_trend": 1.0,
         "slippage_ratio": 1.0, "drawdown": -0.02, "exposure": 0.4,
         "liquidity_flag": "LIQUIDITY_OK"}
    m.update(kw)
    return m


def test_healthy():
    r = drift_monitor(_metrics())
    assert r.overall == "HEALTHY"
    assert r.safety_status == "NORMAL"


def test_warning():
    r = drift_monitor(_metrics(data_missing_rate=0.08))
    assert r.overall in ("WARNING", "DEGRADED")


def test_degraded_maps_safe_mode():
    r = drift_monitor(_metrics(win_rate_trend=0.4,
                               mfe_capture_trend=0.3,
                               slippage_ratio=5.0))
    assert r.overall == "DEGRADED"
    assert r.safety_status == "SAFE_MODE"


def test_halted():
    r = drift_monitor(_metrics(halted=True))
    assert r.overall == "HALTED"
    assert r.safety_status == "HALTED"


def test_drift_to_md():
    md = drift_to_md(drift_monitor(_metrics()))
    assert "Drift Monitor" in md
