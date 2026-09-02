# coding: utf-8
"""月线行为引擎集成冒烟测试（真实数据，00700，--dry-run）"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[4]
CORE_DIR = PROJECT_ROOT / "Core"
if str(CORE_DIR) not in sys.path:
    sys.path.insert(0, str(CORE_DIR))

from QCFP_MTF.config.settings import load_qcfp_settings
from QCFP_MTF.data.loader import load_kline
from QCFP_MTF.behavioral.cbi import build_cbi
from QCFP_MTF.behavioral.cost_position import build_cost_position
from QCFP_MTF.behavioral.turnover_factors import build_turnover_factors
from QCFP_MTF.behavioral.volume_factors import build_volume_factors
from QCFP_MTF.behavioral.vp_matrix import build_vp_regime
from QCFP_MTF.scripts.monthly_behavior_engine import main

try:
    import pytest
    pytestmark = pytest.mark.integration
except ImportError:
    pass


def test_factors_for_00700():
    settings = load_qcfp_settings()
    m = load_kline("monthly", stocks=["00700"])
    w = load_kline("weekly", stocks=["00700"])
    q = load_kline("quarterly", stocks=["00700"])
    turn = build_turnover_factors(m, settings)
    vol = build_volume_factors(m, settings)
    vp = build_vp_regime(m, vol, settings)
    cbi = build_cbi(m, settings)
    cost = build_cost_position(m, w, q, settings)
    assert len(turn) > 100
    assert len(vp) == len(turn)
    assert cbi["cbi_score"].dropna().between(0, 100).all()
    assert (cost["cost_position"].isna() |
            cost["cost_position"].isin(["COST_ADVANTAGE", "COST_NEUTRAL",
                                        "COST_DISADVANTAGE"])).all()


def test_engine_dry_run():
    rc = main(["--stock", "00700", "--dry-run"])
    assert rc == 0


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print(f"PASS {name}")
    print("test_engine_smoke 全部通过 ✅")
