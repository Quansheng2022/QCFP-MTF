# coding: utf-8
"""Continuous Validation + Safety State 测试（30 号）"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[4]
CORE_DIR = PROJECT_ROOT / "Core"
if str(CORE_DIR) not in sys.path:
    sys.path.insert(0, str(CORE_DIR))

from QCFP_MTF.safety.continuous_validation import (continuous_validation,
                                                   continuous_validation_gate,
                                                   monitor_flags,
                                                   validation_to_md)


def _metrics(**kw):
    m = {"data_missing_rate": 0.0, "pit_grade": "B", "settings_drift": 0.0,
         "permission_flip_rate": 0.0, "wave_capture_trend": 1.0,
         "slippage_ratio": 1.0, "liquidity_flag": "LIQUIDITY_OK",
         "mfe_bias": 0.0, "mae_bias": 0.0, "false_entry_rate": 0.0,
         "governance_violations": False, "ledger_integrity": True,
         "replay_consistent": True, "risk_budget_breach": 0.0,
         "abnormal_market": False}
    m.update(kw)
    return m


def test_normal():
    r = continuous_validation(_metrics())
    assert r.status == "NORMAL"
    assert r.triggered == ()


def test_warning_on_drift():
    r = continuous_validation(_metrics(permission_flip_rate=0.2,
                                       wave_capture_trend=0.3))
    assert r.status == "WARNING"
    assert "permission_drift" in r.triggered


def test_safe_mode_on_governance():
    r = continuous_validation(_metrics(governance_violations=True))
    assert r.status == "SAFE_MODE"


def test_halted_on_ledger_failure():
    r = continuous_validation(_metrics(ledger_integrity=False))
    assert r.status == "HALTED"


def test_halted_on_replay_mismatch():
    r = continuous_validation(_metrics(replay_consistent=False))
    assert r.status == "HALTED"


def test_gate_blocks_new_risk_in_safe_mode():
    g = continuous_validation_gate(_metrics(governance_violations=True),
                                   target=0.3, previous_position=0.0)
    assert g["gate"]["status"] == "SAFE_MODE"
    assert g["gate"]["target"] == 0.0


def test_monitor_flags():
    flags = monitor_flags(_metrics(false_entry_rate=0.5,
                                   liquidity_flag="LIQUIDITY_LOW"))
    assert flags.get("false_entry_high") is True
    assert flags.get("liquidity_low") is True


def test_validation_to_md():
    md = validation_to_md(continuous_validation(_metrics()))
    assert "安全状态" in md
