# coding: utf-8
"""Config Governance 决策关键参数测试（新 32 号）"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[4]
CORE_DIR = PROJECT_ROOT / "Core"
if str(CORE_DIR) not in sys.path:
    sys.path.insert(0, str(CORE_DIR))

from QCFP_MTF.config.governance import DECISION_CRITICAL_PARAMS, \
    assert_decision_critical_config, decision_critical_hidden_default_count


def _valid_config():
    return {p: "configured" for p in DECISION_CRITICAL_PARAMS}


def test_valid_config_normal():
    r = assert_decision_critical_config(_valid_config())
    assert r["status"] == "VALID"
    assert r["decision_mode"] == "NORMAL"
    assert r["valid"] is True


def test_missing_critical_param_safe_mode():
    cfg = _valid_config()
    del cfg["liquidity_caps"]
    r = assert_decision_critical_config(cfg)
    assert r["status"] == "INVALID_CONFIG"
    assert r["decision_mode"] == "NO_DECISION"
    assert r["safety_mode"] == "SAFE_MODE"
    assert r["missing_critical_params"] == ["liquidity_caps"]


def test_hidden_default_count():
    cfg = _valid_config()
    used = {"liquidity_caps": 0.1, "risk_caps": 0.2}
    r = decision_critical_hidden_default_count(cfg, used)
    assert r["hidden_default_count"] == 0
    cfg2 = {}
    r2 = decision_critical_hidden_default_count(cfg2, used)
    assert r2["hidden_default_count"] == 2
    assert r2["decision_critical_clean"] is False
