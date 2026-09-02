# coding: utf-8
"""DSS 历史报告 PIT 一致性（integration：依赖真实数据库）"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[4]
CORE_DIR = PROJECT_ROOT / "Core"
if str(CORE_DIR) not in sys.path:
    sys.path.insert(0, str(CORE_DIR))

from QCFP_MTF.common.db import connect
from QCFP_MTF.scripts.dss_report import _row

try:
    import pytest
    pytestmark = pytest.mark.integration
except ImportError:
    pass


def test_dss_row_uses_available_date():
    # 01951 在 2026-07-10：2026Q2（available 2026-08-14）不可用，
    # DSS 必须使用 2026Q1（available 2026-05-15），而非 period_end<=07-10 的 Q2
    conn = connect()
    try:
        row = _row(conn, "01951", "2026-07-10")
    finally:
        conn.close()
    assert row is not None
    assert row.get("available_date") is not None
    assert row["available_date"] <= "2026-07-10"
    assert row.get("period_end") != "2026-06-30"


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print(f"PASS {name}")
    print("test_dss_pit 全部通过 ✅")
