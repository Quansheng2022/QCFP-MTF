# coding: utf-8
"""Paired Ablation 修复 + 统一指标测试（新 9 号）"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[4]
CORE_DIR = PROJECT_ROOT / "Core"
if str(CORE_DIR) not in sys.path:
    sys.path.insert(0, str(CORE_DIR))

from QCFP_MTF.ablation.portfolio_counterfactual import variant_metrics
from QCFP_MTF.ablation.statistical import paired_ablation


def test_paired_ablation_non_multiple_block_size():
    """n 不是 block_size 整数倍时不再 reshape 报错。"""
    base = [0.01, 0.02, 0.0, 0.01, 0.02, 0.01, 0.0, 0.01, 0.02, 0.01]
    treat = [0.06, 0.07, 0.05, 0.06, 0.08, 0.06, 0.05, 0.07, 0.08, 0.06]
    r = paired_ablation(base, treat, n_perm=100, seed=7, block_size=4)
    assert r["n"] == 10
    assert r["mean_delta"] > 0


def test_paired_ablation_null_distribution_valid():
    """相同序列 → 无增量 → DROP（sign-flip null 正确）。"""
    base = [0.02, 0.01, 0.03, 0.02, 0.01, 0.03] * 2
    r = paired_ablation(base, base, n_perm=200, seed=42, block_size=4)
    assert r["verdict"] == "DROP"
    assert r["mean_delta"] == 0.0


def test_variant_metrics_compounded_cagr():
    m = variant_metrics([0.02, -0.02, 0.02])
    total = (1.02 * 0.98 * 1.02) - 1
    assert abs(m["total_return"] - round(total, 4)) < 1e-4
    expected_ann = (1 + total) ** (52 / 3) - 1
    assert abs(m["annualized_return"] - round(expected_ann, 4)) < 1e-3
