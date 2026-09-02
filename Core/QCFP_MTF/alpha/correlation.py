# coding: utf-8
"""Alpha Correlation Monitor（QCFP-MTF 2.8：82 号 Alpha 相关性监控）

Wave Score / Momentum / Trend / Breakout 看似四个模块，
可能高度相关 → 同一风险下注 4 次。

监控：Signal / Position / P&L / Drawdown / Regime 相关性
输出：Effective Alpha Count（有效独立信号数）。
"""

import numpy as np


def _corr_matrix(series_map) -> np.ndarray:
    keys = list(series_map)
    n = len(keys)
    if n == 0:
        return np.zeros((0, 0))
    m = np.column_stack([np.asarray(series_map[k], float) for k in keys])
    if m.shape[0] < 2:
        return np.eye(n)
    # 去均值后归一化相关
    std = m.std(axis=0)
    std[std == 0] = 1.0
    z = (m - m.mean(axis=0)) / std
    return np.corrcoef(z, rowvar=False)


def effective_alpha_count(series_map, threshold=0.7) -> dict:
    """有效 Alpha 数：相关矩阵特征值法（或贪婪聚类）。

    用特征值分解：Effective Count = (Σλ)² / Σλ²（参与度指数）。
    """
    keys = list(series_map)
    C = _corr_matrix(series_map)
    if C.size == 0:
        return {"n_signals": 0, "effective_count": 0.0}
    eig = np.linalg.eigvalsh(C)
    eig = np.clip(eig, 0, None)
    if eig.sum() <= 0:
        effective = 0.0
    else:
        effective = (eig.sum() ** 2) / (eig ** 2).sum()
    # 高相关信号对
    high_pairs = []
    for i in range(len(keys)):
        for j in range(i + 1, len(keys)):
            if abs(C[i, j]) >= float(threshold):
                high_pairs.append((keys[i], keys[j],
                                   round(float(C[i, j]), 4)))
    return {"n_signals": len(keys),
            "effective_count": round(float(effective), 4),
            "high_correlation_pairs": high_pairs,
            "duplicate_risk": bool(high_pairs)}


def alpha_correlation_report(series_map, threshold=0.7) -> dict:
    """Alpha 相关性汇总（Signal/Position/P&L 维度通用）。"""
    result = effective_alpha_count(series_map, threshold)
    return {
        **result,
        "interpretation": (
            f"{result['n_signals']} 个信号 → 有效独立信号 "
            f"{result['effective_count']:.1f}"
            if result["n_signals"] else "无信号"),
    }
