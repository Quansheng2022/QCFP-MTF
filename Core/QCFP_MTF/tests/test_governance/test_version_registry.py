# coding: utf-8
"""Strategy Version Registry 测试（36 号）"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[4]
CORE_DIR = PROJECT_ROOT / "Core"
if str(CORE_DIR) not in sys.path:
    sys.path.insert(0, str(CORE_DIR))

from QCFP_MTF.governance.lifecycle import (StrategyLifecycle,
                                           StrategyLifecycleError,
                                           StrategyVersion)


def test_register_v2_and_bind_decision():
    lc = StrategyLifecycle()
    v = StrategyVersion(
        version="v2.0", strategy_id="S1", engine_version="QCFP-MTF-2.5.0",
        commit_hash="abc123", config_hash="cfg1", data_snapshot_id="ds1",
        approval_status="production", effective_date="2026-08-01")
    lc.register_v2(v)
    reg = []
    rec = lc.bind_decision("S1:v2.0", "01951_2026-08-21", "2026-08-21",
                           registry=reg)
    assert rec["strategy_id"] == "S1"
    assert rec["version"] == "v2.0"
    assert rec["commit_hash"] == "abc123"
    assert len(reg) == 1


def test_bind_rejects_non_production():
    lc = StrategyLifecycle()
    v = StrategyVersion(version="v1.0", strategy_id="S1",
                        approval_status="candidate")
    lc.register_v2(v)
    try:
        lc.bind_decision("S1:v1.0", "d1", "2026-08-21")
        raise AssertionError("should raise")
    except StrategyLifecycleError:
        pass


def test_duplicate_register_v2():
    lc = StrategyLifecycle()
    v1 = StrategyVersion(version="v1.0", strategy_id="S1")
    lc.register_v2(v1)
    try:
        lc.register_v2(v1)
        raise AssertionError("should raise")
    except StrategyLifecycleError:
        pass
