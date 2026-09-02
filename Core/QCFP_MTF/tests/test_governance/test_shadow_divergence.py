# coding: utf-8
"""Shadow-Production Divergence Monitor 测试（36 号）"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[4]
CORE_DIR = PROJECT_ROOT / "Core"
if str(CORE_DIR) not in sys.path:
    sys.path.insert(0, str(CORE_DIR))

from QCFP_MTF.governance.shadow_divergence import shadow_divergence_monitor


def test_identical_no_divergence():
    r = shadow_divergence_monitor(
        {"target_position": 0.05, "permission": "ALLOW",
         "config_hash": "C1", "data_snapshot_id": "D1",
         "version": "V1"},
        {"target_position": 0.05, "permission": "ALLOW",
         "config_hash": "C1", "data_snapshot_id": "D1",
         "version": "V1"})
    assert r["divergence_classifications"] == []
    assert r["explained"] is True


def test_governance_interception():
    r = shadow_divergence_monitor(
        {"target_position": 0.08, "permission": "ALLOW"},
        {"target_position": 0.0, "permission": "BLOCK"})
    assert "GOVERNANCE_INTERCEPTION" in r["divergence_classifications"]
    assert r["governance_alert"] is False   # 治理拦截是预期行为


def test_model_delta_alert():
    r = shadow_divergence_monitor(
        {"target_position": 0.08, "permission": "ALLOW",
         "config_hash": "C1", "data_snapshot_id": "D1", "version": "V1"},
        {"target_position": 0.03, "permission": "ALLOW",
         "config_hash": "C1", "data_snapshot_id": "D1", "version": "V1"})
    assert r["divergence_classifications"] == ["MODEL_DELTA"]
    assert r["governance_alert"] is True
