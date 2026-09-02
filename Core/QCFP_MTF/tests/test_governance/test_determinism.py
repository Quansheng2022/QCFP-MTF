# coding: utf-8
"""DeterminismContract 测试（43 号：Production 禁止随机）"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[4]
CORE_DIR = PROJECT_ROOT / "Core"
if str(CORE_DIR) not in sys.path:
    sys.path.insert(0, str(CORE_DIR))

from QCFP_MTF.governance.determinism import audit_random_usage, \
    assert_deterministic, determinism_contract


def test_production_no_seed_deterministic():
    c = determinism_contract("ev1", "code1", "cfg1", "v1", seed=None)
    assert c["production_deterministic"] is True
    assert c["contract_ok"] is True
    assert_deterministic(c)  # 不应抛异常


def test_research_seed_flagged_non_production():
    c = determinism_contract("ev1", "code1", "cfg1", "v1", seed=42)
    assert c["production_deterministic"] is False
    assert c["contract_ok"] is False
    try:
        assert_deterministic(c)
        raise AssertionError("should raise ValueError")
    except ValueError:
        pass


def test_replay_context_preserved():
    c = determinism_contract("ev1", "code1", "cfg1", "v1",
                             replay_context={"bootstrap_seed": 7})
    assert c["replay_context"]["bootstrap_seed"] == 7


def test_audit_random_usage():
    r = audit_random_usage({"module_a": ["random.random()",
                                         "np.random.choice"]})
    assert r["requires_seed"] is True
    assert len(r["random_usages"]) == 2
    assert audit_random_usage({})["requires_seed"] is False
