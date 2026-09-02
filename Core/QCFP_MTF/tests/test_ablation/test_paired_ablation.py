# coding: utf-8
"""Paired time-series Ablation 测试（P0-10 号）"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[4]
CORE_DIR = PROJECT_ROOT / "Core"
if str(CORE_DIR) not in sys.path:
    sys.path.insert(0, str(CORE_DIR))

from QCFP_MTF.ablation.statistical import paired_ablation


def test_paired_ablation_keep():
    base = [0.01, 0.02, 0.0, 0.01, 0.02, 0.01, 0.0, 0.01,
            0.02, 0.01, 0.0, 0.01]
    treat = [0.05, 0.06, 0.04, 0.05, 0.07, 0.05, 0.04, 0.06,
             0.07, 0.05, 0.04, 0.06]
    r = paired_ablation(base, treat, n_perm=500, seed=42)
    assert r["mean_delta"] > 0
    assert r["verdict"] in ("KEEP", "REVIEW")
    assert r["effect_size"] > 0
    assert r["n_permutations"] == 500


def test_paired_ablation_drop():
    base = [0.03, 0.02, 0.03, 0.02, 0.03, 0.02, 0.03, 0.02]
    treat = [0.031, 0.019, 0.030, 0.021, 0.029, 0.020, 0.031, 0.021]
    r = paired_ablation(base, treat, n_perm=200, seed=42)
    assert r["verdict"] == "DROP"
    assert r["contribution_type"] == "none"


def test_paired_ablation_regime_stratification():
    base = [0.01] * 8
    treat = [0.05] * 8
    regimes = ["Bull"] * 4 + ["Bear"] * 4
    r = paired_ablation(base, treat, regime_series=regimes, n_perm=200)
    assert "regime_breakdown" in r
    assert "Bull" in r["regime_breakdown"]
    assert "Bear" in r["regime_breakdown"]
