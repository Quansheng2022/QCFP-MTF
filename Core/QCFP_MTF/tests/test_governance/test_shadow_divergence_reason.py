# coding: utf-8
"""Shadow–Production Divergence Reason 测试（新 36 号）"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[4]
CORE_DIR = PROJECT_ROOT / "Core"
if str(CORE_DIR) not in sys.path:
    sys.path.insert(0, str(CORE_DIR))

from QCFP_MTF.governance.shadow_divergence import shadow_divergence_reason


def _prod(**kw):
    base = {"target_position": 0.1, "permission": "ALLOW",
            "config_hash": "C1", "data_snapshot_id": "D1",
            "version": "v2", "engine_version": "e2",
            "execution_cap": 1.0}
    base.update(kw)
    return base


def test_no_divergence():
    r = shadow_divergence_reason(_prod(), _prod())
    assert r["reason_code"] == "NO_DIVERGENCE"
    assert r["diverged"] is False


def test_governance_interception_reason():
    shadow = _prod(target_position=0.3, permission="ALLOW")
    prod = _prod(target_position=0.0, permission="BLOCK")
    r = shadow_divergence_reason(shadow, prod)
    assert r["reason_code"] == "GOVERNANCE_INTERCEPTION"
    assert r["decision_delta"] == -0.3


def test_execution_constraint_reason():
    shadow = _prod(target_position=0.3, execution_cap=1.0)
    prod = _prod(target_position=0.05, execution_cap=0.2)
    r = shadow_divergence_reason(shadow, prod)
    assert r["reason_code"] == "EXECUTION_CONSTRAINT"


def test_model_delta_fallback():
    shadow = _prod(target_position=0.3)
    prod = _prod(target_position=0.2)
    r = shadow_divergence_reason(shadow, prod)
    assert r["reason_code"] == "MODEL_DELTA"
