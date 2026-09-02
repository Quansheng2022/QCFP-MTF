# coding: utf-8
"""引擎集成冒烟测试（真实数据，00700，--dry-run）"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[4]
CORE_DIR = PROJECT_ROOT / "Core"
if str(CORE_DIR) not in sys.path:
    sys.path.insert(0, str(CORE_DIR))

from QCFP_MTF.config.settings import load_qcfp_settings
from QCFP_MTF.data.loader import load_derived, load_kline
from QCFP_MTF.scripts.structural_engine import build_merged, main

try:
    import pytest
    pytestmark = pytest.mark.integration
except ImportError:
    pass


def test_merged_for_00700():
    settings = load_qcfp_settings()
    ih = load_derived("quarterly_institutional_holdings_analysis", )
    chip = load_derived("quarterly_chip_analysis")
    q = load_kline("quarterly", stocks=["00700"])
    d = load_kline("daily", stocks=["00700"])
    merged, *_ = build_merged(ih[ih["stock_code"] == "00700"],
                              chip[chip["stock_code"] == "00700"], q, d, settings)
    assert len(merged) > 20  # 00700 季度数
    assert {"c_state", "f_state", "p_state"} <= set(merged.columns)


def test_engine_dry_run():
    rc = main(["--stock", "00700", "--dry-run"])
    assert rc == 0


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print(f"PASS {name}")
    print("test_engine_smoke 全部通过 ✅")
