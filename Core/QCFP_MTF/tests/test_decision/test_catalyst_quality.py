# coding: utf-8
"""催化剂质量评分（CQS）测试"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[4]
CORE_DIR = PROJECT_ROOT / "Core"
if str(CORE_DIR) not in sys.path:
    sys.path.insert(0, str(CORE_DIR))

from QCFP_MTF.config.settings import DEFAULT_SETTINGS
from QCFP_MTF.decision.catalyst_quality import (calc_catalyst_quality,
                                                catalyst_type,
                                                observation_position,
                                                time_stop_weeks)


def test_high_quality_reversal():
    # F 连续两季 ↑、趋势好、CBI 稳定 → +2+1+1=4 → 封顶 +3
    score = calc_catalyst_quality("F↑", "F↑", 75.0, 0.3, "CBI_STABLE")
    assert score == 3
    assert catalyst_type(score) == "高质量反转"
    assert observation_position(score, DEFAULT_SETTINGS) == 0.35
    assert time_stop_weeks(score, DEFAULT_SETTINGS) is None


def test_neutral():
    score = calc_catalyst_quality("F↑", "F→", 50.0, 0.4, "CBI_ACTIVE")
    assert score == 1
    assert catalyst_type(score) == "中性偏强"
    assert observation_position(score, DEFAULT_SETTINGS) == 0.20
    # 中性偏强改用移动止损（不再固定 4 周到点清仓）
    assert time_stop_weeks(score, DEFAULT_SETTINGS) is None


def test_pure_pulse():
    # 单季 F↑ 但趋势差且 52W 位置已高、CBI 动荡 → +1-1-1=-1
    score = calc_catalyst_quality("F↑", "F↓", 25.0, 0.7, "CBI_TURBULENT")
    assert score == -1
    assert catalyst_type(score) == "纯脉冲/噪音"
    assert observation_position(score, DEFAULT_SETTINGS) == 0.05
    assert time_stop_weeks(score, DEFAULT_SETTINGS) == 2


def test_bounds():
    assert calc_catalyst_quality("F↑", "F↑", 90.0, 0.1, "CBI_STABLE") == 3
    assert calc_catalyst_quality("F↓", "F↓", 10.0, 0.9, "CBI_TURBULENT") == -2


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print(f"PASS {name}")
    print("test_catalyst_quality 全部通过 ✅")
