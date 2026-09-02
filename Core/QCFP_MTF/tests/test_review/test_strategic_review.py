# coding: utf-8
"""Strategic Decision Review 测试（80 号）"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[4]
CORE_DIR = PROJECT_ROOT / "Core"
if str(CORE_DIR) not in sys.path:
    sys.path.insert(0, str(CORE_DIR))

from QCFP_MTF.review.strategic_review import (GOVERNANCE_PATH,
                                              MUST_NOT_CHANGE,
                                              review_to_md,
                                              strategic_review)


def _scores():
    return {"permission": 90, "wave": 85, "entry": 75, "exit": 30,
            "risk": 88, "execution": 25, "portfolio": 70}


def test_strategic_review():
    r = strategic_review("2026-Q2", _scores())
    assert "permission" in r.worked
    assert "exit" in r.failed and "execution" in r.failed
    assert "exit" in r.should_test
    assert "permission_gate" in r.must_not_change
    assert r.governance_path == GOVERNANCE_PATH


def test_decayed_modules_retired():
    r = strategic_review("2026-Q2", _scores(),
                         decayed_modules=("execution",))
    assert "execution" in r.should_retire
    assert "execution" not in r.should_test


def test_review_to_md():
    md = review_to_md(strategic_review("2026-Q2", _scores()))
    assert "Strategic Decision Review" in md
    assert "What Must NOT Be Changed" in md
    assert "治理路径" in md
