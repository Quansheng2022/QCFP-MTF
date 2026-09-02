# coding: utf-8
"""风险评估测试"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[4]
CORE_DIR = PROJECT_ROOT / "Core"
if str(CORE_DIR) not in sys.path:
    sys.path.insert(0, str(CORE_DIR))

from QCFP_MTF.config.settings import DEFAULT_SETTINGS
from QCFP_MTF.decision.risk_evaluator import evaluate_risk


def test_low_risk():
    level, score, _ = evaluate_risk("BULLISH_STABLE", "Aligned", "risk_on", "A", "High",
                                    DEFAULT_SETTINGS)
    assert level == "Low" and score <= 2


def test_medium_risk():
    level, score, _ = evaluate_risk("BULLISH_WARNING", "Aligned", "neutral", "C", "Medium",
                                    DEFAULT_SETTINGS)
    # base 2 + dqC 1 = 3 → Medium
    assert level == "Medium" and score == 3


def test_high_risk():
    level, score, _ = evaluate_risk("BEARISH_CONFIRMED", "Divergence", "risk_off", "C", "Low",
                                    DEFAULT_SETTINGS)
    # base 3 + 1 + 1 + 1 + 1 = 7 → Extreme；改低加成验证 High
    assert level == "Extreme"


def test_extreme_insufficient():
    level, score, _ = evaluate_risk("DATA_INSUFFICIENT", "Unknown", "neutral", "D", None,
                                    DEFAULT_SETTINGS)
    assert level == "Extreme"


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print(f"PASS {name}")
    print("test_risk_evaluator 全部通过 ✅")
