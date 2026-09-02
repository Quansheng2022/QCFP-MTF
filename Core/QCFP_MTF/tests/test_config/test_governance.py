# coding: utf-8
"""Config Governance 测试（32 号）"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[4]
CORE_DIR = PROJECT_ROOT / "Core"
if str(CORE_DIR) not in sys.path:
    sys.path.insert(0, str(CORE_DIR))

from QCFP_MTF.config.governance import (DECISION_CRITICAL_PARAMS,
                                        InvalidConfigError,
                                        assert_config_valid,
                                        classify_param,
                                        validate_config_governance)


def _full_config():
    return {p: "set" for p in DECISION_CRITICAL_PARAMS}


def test_valid_config():
    r = validate_config_governance(_full_config())
    assert r["valid"] is True
    assert r["status"] == "VALID"
    assert_config_valid(_full_config())


def test_missing_critical_invalid():
    r = validate_config_governance({"permission_policy": "x"})
    assert r["valid"] is False
    assert r["status"] == "INVALID_CONFIG"
    assert "risk_caps" in r["missing_critical_params"]
    try:
        assert_config_valid({"permission_policy": "x"})
        raise AssertionError("should raise")
    except InvalidConfigError:
        pass


def test_param_classification():
    assert classify_param("permission_policy") == "DECISION_CRITICAL"
    assert classify_param("display_title") == "DISPLAY_ONLY"
    assert classify_param("lookback") == "RESEARCH_ONLY"
