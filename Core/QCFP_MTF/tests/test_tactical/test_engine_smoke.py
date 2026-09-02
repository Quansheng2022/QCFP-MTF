# coding: utf-8
"""周线战术引擎集成冒烟测试（真实数据，00700，--dry-run）"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[4]
CORE_DIR = PROJECT_ROOT / "Core"
if str(CORE_DIR) not in sys.path:
    sys.path.insert(0, str(CORE_DIR))

from QCFP_MTF.config.settings import load_qcfp_settings
from QCFP_MTF.data.loader import load_kline
from QCFP_MTF.tactical.weekly_signal import build_signal
from QCFP_MTF.tactical.weekly_turnover import build_turnover_factors
from QCFP_MTF.tactical.weekly_volume import build_volume_factors
from QCFP_MTF.tactical.weekly_vwap import build_vwap_factors
from QCFP_MTF.scripts.weekly_tactical_engine import main
from QCFP_MTF.scripts.daily_tactical_engine import main as daily_main

try:
    import pytest
    pytestmark = pytest.mark.integration
except ImportError:
    pass


def test_factors_for_00700():
    settings = load_qcfp_settings()
    w = load_kline("weekly", stocks=["00700"])
    vol = build_volume_factors(w, settings)
    turn = build_turnover_factors(w, settings)
    vwap = build_vwap_factors(w, settings)
    sig = build_signal(w, vol, vwap, settings)
    assert len(sig) == len(w)
    assert set(sig["tactical_signal"].dropna()) <= {"Breakout", "Pullback",
                                                    "Consolidation", "Breakdown"}
    assert sig["w_breakout"].isin([0, 1]).all()


def test_engine_dry_run():
    rc = main(["--stock", "00700", "--dry-run"])
    assert rc == 0


def test_daily_engine_dry_run():
    rc = daily_main(["--stock", "00700", "--dry-run"])
    assert rc == 0


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print(f"PASS {name}")
    print("test_engine_smoke 全部通过 ✅")
