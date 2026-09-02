# coding: utf-8
"""StrategyLifecycle Provenance 保留测试（P0-6 号）"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[4]
CORE_DIR = PROJECT_ROOT / "Core"
if str(CORE_DIR) not in sys.path:
    sys.path.insert(0, str(CORE_DIR))

from QCFP_MTF.governance.lifecycle import StrategyLifecycle, \
    StrategyVersion


def _version():
    return StrategyVersion(
        version="v2.0", strategy_id="S1", engine_version="QCFP-MTF-2.5.0",
        commit_hash="abc123", config_hash="cfg1", data_snapshot_id="ds1",
        feature_version="fv1", parameter_version="pv1",
        rule_version="GOV-2.5.0",
        approval_status="candidate")


def test_promote_preserves_provenance():
    lc = StrategyLifecycle()
    v = _version()
    lc.register_v2(v)
    promoted = lc.promote("S1:v2.0", "production")
    assert promoted.commit_hash == "abc123"
    assert promoted.config_hash == "cfg1"
    assert promoted.data_snapshot_id == "ds1"
    assert promoted.strategy_id == "S1"
    assert promoted.engine_version == "QCFP-MTF-2.5.0"
    assert promoted.feature_version == "fv1"
    lc.assert_provenance_preserved("S1:v2.0")


def test_retire_preserves_provenance():
    lc = StrategyLifecycle()
    v = _version()
    lc.register_v2(v)
    lc.promote("S1:v2.0", "production")
    retired = lc.retire("S1:v2.0", "2026-12-31")
    assert retired.commit_hash == "abc123"
    assert retired.retirement_date == "2026-12-31"
