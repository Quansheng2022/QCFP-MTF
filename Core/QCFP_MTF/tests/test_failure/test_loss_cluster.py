# coding: utf-8
"""Loss Cluster Detector 测试（45 号）"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[4]
CORE_DIR = PROJECT_ROOT / "Core"
if str(CORE_DIR) not in sys.path:
    sys.path.insert(0, str(CORE_DIR))

from QCFP_MTF.failure.loss_cluster import detect_loss_cluster


def _trades(net, mfe=0.05, mae=-0.03, false=False):
    return [{"net_return": x, "mfe": mfe, "mae": mae,
             "false_entry": false} for x in net]


def test_no_cluster_normal():
    t = _trades([0.03, -0.01, 0.02, 0.01, -0.005, 0.02, 0.01, -0.01])
    c = detect_loss_cluster(t)
    assert c.cluster_triggered is False
    assert c.strategy_confidence_scale == 1.0


def test_consecutive_losses_trigger():
    t = _trades([-0.02, -0.03, -0.01, -0.04, -0.02, -0.01])
    c = detect_loss_cluster(t, consecutive_threshold=3)
    assert c.consecutive_losses == 6
    assert c.cluster_triggered is True
    assert c.risk_budget_scale < 1.0
    assert any(r.startswith("CONSECUTIVE_LOSSES") for r in c.reasons)


def test_low_hit_mfe_declining():
    # 前 10 笔 MFE=0.05 全亏，后 10 笔 MFE=0.02 全亏 → 胜率 0 且 MFE 下降
    trades = ([{"net_return": -0.02, "mfe": 0.05, "mae": -0.04,
                "false_entry": True}] * 10 +
              [{"net_return": -0.02, "mfe": 0.02, "mae": -0.03,
                "false_entry": True}] * 10)
    c = detect_loss_cluster(trades, window=10, hit_rate_threshold=0.5,
                            mfe_decline_threshold=0.8)
    assert c.cluster_triggered is True


def test_regime_recorded():
    t = _trades([-0.02, -0.03, -0.01, -0.04])
    c = detect_loss_cluster(t, regime="Bear")
    assert c.regime == "Bear"
