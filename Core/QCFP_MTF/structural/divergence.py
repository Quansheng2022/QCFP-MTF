# coding: utf-8
"""三维背离检测：CPD（筹码-价格）/ FPD（资金-价格）/ CFD（筹码-资金）

判定：两因子 Z-Score 差超过阈值且方向符号相反 → 顶/底背离；
任一因子缺失 → 该对背离输出空串。
"""

import numpy as np
import pandas as pd


def _pair_signal(x: pd.Series, y: pd.Series,
                 label_x: str, label_y: str,
                 threshold: float) -> pd.Series:
    out = pd.Series("", index=x.index, dtype=object)
    xz = x.astype(float)
    yz = y.astype(float)
    diff = (xz - yz).abs()
    over = diff > threshold
    conflict = xz * yz < 0
    m = over & conflict
    out[(m) & (xz > 0) & (yz < 0)] = f"{label_x}顶背离"
    out[(m) & (xz < 0) & (yz > 0)] = f"{label_x}底背离"
    return out


def compute_divergence(c_z: pd.Series, f_z: pd.Series, p_z: pd.Series,
                       threshold: float = 1.0) -> pd.DataFrame:
    """计算 CPD/FPD/CFD

    Args:
        c_z: 筹码 Z-Score 序列（index 与结果一致）
        f_z: 资金 Z-Score 序列（缺失为 NaN）
        p_z: 价格 Z-Score 序列
        threshold: 背离 Z-Score 差阈值（默认 1.0）
    Returns:
        DataFrame: cpd / fpd / cfd（标签或空串）+ 布尔列
    """
    df = pd.DataFrame({
        "cpd": _pair_signal(c_z, p_z, "筹码", "价格", threshold),
        "fpd": _pair_signal(f_z, p_z, "资金", "价格", threshold),
        "cfd": _pair_signal(c_z, f_z, "筹码", "资金", threshold),
    }, index=c_z.index)
    for col in ("cpd", "fpd", "cfd"):
        df[col + "_flag"] = df[col].ne("").astype(int)
    return df
