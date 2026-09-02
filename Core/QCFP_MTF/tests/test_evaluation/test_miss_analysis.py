# coding: utf-8
"""Opportunity Miss Analysis 测试（97 号）"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[4]
CORE_DIR = PROJECT_ROOT / "Core"
if str(CORE_DIR) not in sys.path:
    sys.path.insert(0, str(CORE_DIR))

from QCFP_MTF.evaluation.miss_analysis import capture_summary, miss_analysis


def _waves():
    return [{"wave_id": f"W{i}", "mfe_peak": 0.20} for i in range(10)]


def test_miss_analysis():
    waves = _waves()
    captured = {"W0", "W1", "W2", "W3", "W4", "W5"}
    reasons = {"W6": "PERMISSION", "W7": "RISK", "W8": "ENTRY_LATE",
               "W9": "LIQUIDITY"}
    r = miss_analysis(waves, captured, reasons)
    assert r["capture_rate"] == 0.6
    assert r["missed"] == 4
    assert r["miss_reason_distribution"]["PERMISSION"] == 1
    assert r["missed_alpha"] > 0


def test_capture_summary():
    s = capture_summary(_waves(), {"W0", "W1", "W2", "W3", "W4", "W5"},
                        {"W6": "PERMISSION"})
    assert s["capture_rate"] == 0.6
    assert s["miss_reason_top"][0][0] == "PERMISSION"
