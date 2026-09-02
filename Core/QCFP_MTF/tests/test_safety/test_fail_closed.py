# coding: utf-8
"""Fail-Closed Validation 测试（P0-5 号）"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[4]
CORE_DIR = PROJECT_ROOT / "Core"
if str(CORE_DIR) not in sys.path:
    sys.path.insert(0, str(CORE_DIR))

from QCFP_MTF.safety.continuous_validation import fail_closed_validation


def test_all_pass_normal():
    r = fail_closed_validation({"ledger": True, "replay": True,
                                "pit": True, "execution": True})
    assert r["overall"] == "NORMAL"
    assert r["display_normal"] is True


def test_unknown_never_normal():
    r = fail_closed_validation({"ledger": None, "replay": True,
                                "pit": True, "execution": True})
    assert "ledger" in r["unknown_metrics"]
    assert r["overall"] == "SAFE_MODE"
    assert r["display_normal"] is False


def test_missing_key_evidence_safe_mode():
    r = fail_closed_validation({})    # 全部缺失
    assert r["overall"] == "SAFE_MODE"
    assert set(r["unknown_metrics"]) == {"ledger", "replay", "pit",
                                         "execution"}


def test_fail_ledger_blocks():
    r = fail_closed_validation({"ledger": False, "replay": True,
                                "pit": True, "execution": True})
    assert r["overall"] == "SAFE_MODE"
    assert "ledger" in r["failed_metrics"]
