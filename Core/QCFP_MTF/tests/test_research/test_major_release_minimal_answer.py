# coding: utf-8
"""Major Release Minimum Canonical 答案测试（Release 3：新 29 号）"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[4]
CORE_DIR = PROJECT_ROOT / "Core"
if str(CORE_DIR) not in sys.path:
    sys.path.insert(0, str(CORE_DIR))

from QCFP_MTF.research.minimum_viable_canonical import \
    major_release_minimal_answer


def test_minimal_sufficient_answer():
    full = {"sharpe": 1.31, "mdd": -0.10, "wave_capture": 0.72,
            "practicality": 0.80}
    minimal = {"sharpe": 1.29, "mdd": -0.11, "wave_capture": 0.70,
               "practicality": 0.85}
    r = major_release_minimal_answer(full, minimal,
                                     full_complexity=1.0,
                                     minimal_complexity=0.5)
    assert r["answer"] == "SIMPLIFY"
    assert r["required"] is True


def test_full_required_answer():
    full = {"sharpe": 0.85, "mdd": -0.10, "wave_capture": 0.72,
            "practicality": 0.80}
    minimal = {"sharpe": 0.40, "mdd": -0.25, "wave_capture": 0.35,
               "practicality": 0.80}
    r = major_release_minimal_answer(full, minimal)
    assert r["answer"] == "FULL_REQUIRED"
