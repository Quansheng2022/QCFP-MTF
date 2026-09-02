# coding: utf-8
"""Market Session Time Contract 测试（新 33 号）"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[4]
CORE_DIR = PROJECT_ROOT / "Core"
if str(CORE_DIR) not in sys.path:
    sys.path.insert(0, str(CORE_DIR))

from QCFP_MTF.data.asof_contract import MARKET_SESSIONS, \
    execution_time_resolution, trading_session_contract


def test_after_close_requires_next_session():
    r = trading_session_contract("2026-08-21", "2026-08-21",
                                 session="after_close")
    assert r["next_tradable_session_required"] is True
    assert r["execution_time"] is None


def test_continuous_session_executable_same_day():
    r = trading_session_contract("2026-08-21", "2026-08-21",
                                 session="continuous_session")
    assert r["next_tradable_session_required"] is False
    assert r["execution_time"] == "2026-08-21"


def test_execution_resolution_inconsistent():
    r = execution_time_resolution("2026-08-21", "2026-08-21",
                                  "2026-08-21", session="after_close")
    assert r["consistent"] is False
    r2 = execution_time_resolution("2026-08-21", "2026-08-21",
                                   "2026-08-22", session="after_close")
    assert r2["consistent"] is True


def test_sessions_defined():
    assert "lunch_break" in MARKET_SESSIONS
    assert "suspension" in MARKET_SESSIONS
