# coding: utf-8
"""ABSTAIN / NO_DECISION 一级语义测试（新 47 号）"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[4]
CORE_DIR = PROJECT_ROOT / "Core"
if str(CORE_DIR) not in sys.path:
    sys.path.insert(0, str(CORE_DIR))

from QCFP_MTF.decision.abstain import abstain_semantics, \
    never_map_to_hold


def test_four_distinct_semantics():
    assert abstain_semantics("HOLD")["meaning"].startswith("系统完成可信判断")
    assert "没有值得参与" in abstain_semantics("NO_TRADE")["meaning"]
    assert "没有足够证据" in abstain_semantics("ABSTAIN")["meaning"]
    assert "禁止产生正式新决策" in abstain_semantics(
        "DECISION_HALTED")["meaning"]


def test_unknown_status():
    r = abstain_semantics("WEIRD")
    assert r["known"] is False


def test_pit_unknown_not_hold():
    r = never_map_to_hold("PIT_UNKNOWN")
    assert r["must_not_be_hold"] is True
    assert r["violation"] is True


def test_normal_reason_can_be_hold():
    r = never_map_to_hold("WAVE_ABSENT")
    assert r["must_not_be_hold"] is False
