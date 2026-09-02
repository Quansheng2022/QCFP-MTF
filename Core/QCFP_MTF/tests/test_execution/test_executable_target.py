# coding: utf-8
"""ExecutableTarget 链测试（Release 2：新 15 号）"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[4]
CORE_DIR = PROJECT_ROOT / "Core"
if str(CORE_DIR) not in sys.path:
    sys.path.insert(0, str(CORE_DIR))

from QCFP_MTF.execution.executable_target import executable_target_chain


def test_suspended_no_order():
    r = executable_target_chain(0.3, tradability_state="SUSPENDED")
    assert r["blocked"] is True
    assert r["executable_target"] == 0.0


def test_delisting_no_order():
    assert executable_target_chain(0.3, "DELISTING")["executable_target"] \
        == 0.0


def test_corporate_action_reduced():
    r = executable_target_chain(0.3,
                                tradability_state="CORPORATE_ACTION_PENDING")
    assert r["executable_target"] < 0.3
    assert r["blocked"] is False


def test_half_day_reduced_capacity():
    r = executable_target_chain(0.3, tradability_state="NORMAL",
                                session="half_day")
    assert r["session_scale"] == 0.5
    assert r["executable_target"] == 0.15


def test_after_close_next_session():
    r = executable_target_chain(0.3, tradability_state="NORMAL",
                                session="after_close",
                                available_time="2026-08-21",
                                decision_time="2026-08-21")
    assert r["next_session_required"] is True
