# coding: utf-8
"""Incremental Alpha Test 测试（83 号）"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[4]
CORE_DIR = PROJECT_ROOT / "Core"
if str(CORE_DIR) not in sys.path:
    sys.path.insert(0, str(CORE_DIR))

from QCFP_MTF.ablation.incremental import causal_attribution, \
    incremental_alpha


def _metrics(return_=0.10, sharpe=1.0, capture=0.5, mdd=-0.08,
             turnover=1.0, cost=0.01, tail=-0.05):
    return {"return": return_, "sharpe": sharpe, "mfe_capture": capture,
            "mdd": mdd, "turnover": turnover, "cost": cost,
            "tail_risk": tail}


def test_incremental_alpha_positive():
    base = _metrics(return_=0.10, sharpe=1.0)
    new = _metrics(return_=0.15, sharpe=1.3, capture=0.6, mdd=-0.06,
                   turnover=1.1, cost=0.011, tail=-0.04)
    r = incremental_alpha(base, new, "wave_v4")
    assert r["verdict"] == "INCREMENTAL_ALPHA"
    assert r["recommendation"] == "KEEP"
    assert r["net_alpha"] > 0


def test_incremental_alpha_detrimental():
    base = _metrics(return_=0.10)
    new = _metrics(return_=0.08, sharpe=0.6, mdd=-0.15, turnover=2.5,
                   cost=0.03, tail=-0.12)
    r = incremental_alpha(base, new, "noise_module")
    assert r["recommendation"] == "DELETE"


def test_causal_attribution_84():
    # Observed 20%，Incremental 15% → 模块因果（75%）
    r = causal_attribution(0.20, 0.15, regime_effect=0.05)
    assert r["conclusion"] == "MODULE_CAUSAL"
    assert r["attributable_share"] == 0.75
    # Observed 20%，Incremental 2% → 环境驱动
    r2 = causal_attribution(0.20, 0.02, regime_effect=0.15)
    assert r2["conclusion"] == "ENVIRONMENT_DRIVEN"
