# coding: utf-8
"""防 Look-ahead 过滤器测试"""

import sys
from pathlib import Path

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[4]
CORE_DIR = PROJECT_ROOT / "Core"
if str(CORE_DIR) not in sys.path:
    sys.path.insert(0, str(CORE_DIR))

from QCFP_MTF.backtest.lookahead_filter import (assert_no_lookahead,
                                                filter_available,
                                                validate_timeline)


def _df():
    return pd.DataFrame({
        "decision_date": ["2026-05-01", "2026-06-15", "2026-08-14"],
        "structural_available_date": ["2026-04-15", "2026-06-30", "2026-08-14"],
    })


def test_validate():
    v = validate_timeline(_df())
    assert list(v) == [True, False, True]


def test_filter():
    out = filter_available(_df())
    assert len(out) == 2


def test_assert_raises():
    try:
        assert_no_lookahead(_df())
        raised = False
    except ValueError:
        raised = True
    assert raised


def test_assert_ok_after_filter():
    assert assert_no_lookahead(filter_available(_df())) is True


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print(f"PASS {name}")
    print("test_lookahead_filter 全部通过 ✅")
