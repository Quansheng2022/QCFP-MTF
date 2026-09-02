# coding: utf-8
"""Wave Quality Matrix 测试（27 号）"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[4]
CORE_DIR = PROJECT_ROOT / "Core"
if str(CORE_DIR) not in sys.path:
    sys.path.insert(0, str(CORE_DIR))

from QCFP_MTF.evaluation.wave_quality_matrix import wave_quality_matrix


def test_wave_quality():
    realized = [{"wave_id": f"W{i}"} for i in range(10)]
    predicted = {f"W{i}" for i in range(8)} | {"WX", "WY"}
    captured = {f"W{i}" for i in range(6)}
    r = wave_quality_matrix(realized, predicted, captured,
                            miss_reasons={"W6": "PERMISSION",
                                          "W7": "ENTRY_LATE"})
    assert r["wave_recall"] == 0.6
    assert r["capture_ratio"] == 0.6
    assert r["false_entry_rate"] > 0
    assert r["missed_wave_rate"] == 0.4
    assert "W6" in r["missed_waves"]
