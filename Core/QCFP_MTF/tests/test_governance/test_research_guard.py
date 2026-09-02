# coding: utf-8
"""Autonomous Research Guard 测试（50 号）"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[4]
CORE_DIR = PROJECT_ROOT / "Core"
if str(CORE_DIR) not in sys.path:
    sys.path.insert(0, str(CORE_DIR))

from QCFP_MTF.governance.research_guard import (ResearchGuard,
                                                ResearchGuardError)


def test_begin_search_and_trials():
    g = ResearchGuard()
    s = g.begin_search("SRCH-1", "测试假设", {"lr": [0.01, 0.05]},
                       max_trials=5)
    g.record_trial("SRCH-1", "v1", 0.12, "best_ci")
    g.record_trial("SRCH-1", "v2", 0.15, "best_ci")
    assert len(g.sessions["SRCH-1"].trials) == 2


def test_max_trials_enforced():
    g = ResearchGuard()
    g.begin_search("SRCH-2", "h", {}, max_trials=2)
    g.record_trial("SRCH-2", "v1", 0.1, "best")
    g.record_trial("SRCH-2", "v2", 0.1, "best")
    try:
        g.record_trial("SRCH-2", "v3", 0.1, "best")
        raise AssertionError("should raise")
    except ResearchGuardError:
        pass


def test_promote_requires_gates():
    g = ResearchGuard()
    g.begin_search("SRCH-3", "h", {})
    try:
        g.promote_candidate("SRCH-3", "v9")
        raise AssertionError("should raise")
    except ResearchGuardError as exc:
        assert "NOT_PRE_REGISTERED" in str(exc)
        assert "NO_HUMAN_APPROVAL" in str(exc)


def test_promote_after_full_gates():
    g = ResearchGuard()
    g.begin_search("SRCH-4", "h", {}, max_trials=3)
    g.record_trial("SRCH-4", "v1", 0.05, "best")
    g.pre_register("SRCH-4")
    g.approve("SRCH-4")
    r = g.promote_candidate("SRCH-4", "v2", ablation_ok=True, oos_ok=True,
                            statistical_ok=True)
    assert r["status"] == "CANDIDATE"


def test_multiple_testing_check():
    g = ResearchGuard()
    g.begin_search("SRCH-5", "h", {}, max_trials=30)
    for i in range(20):
        g.record_trial("SRCH-5", f"v{i}", 0.1, "best")
    mt = g.multiple_testing_check("SRCH-5")
    assert mt["trials"] == 20
    assert mt["risk"] == "HIGH"
    assert mt["alpha_effective"] < 0.05
