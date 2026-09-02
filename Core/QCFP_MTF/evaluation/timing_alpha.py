# coding: utf-8
"""Entry / Exit Alpha + Timing Alpha（QCFP-MTF 2.8：P1-9）

    Entry Alpha = Actual Entry vs Optimal Entry
    Exit Alpha  = Actual Exit vs MFE Peak
    Timing Alpha = Entry Alpha + Exit Alpha

并建立 MFE/MAE 学习闭环（结果反馈研究，不直接改生产）。
"""


def entry_alpha(actual_entry_price, optimal_entry_price) -> dict:
    """入场 Alpha：实际入场 vs 最优入场（正 = 实际更差）。"""
    a = float(actual_entry_price or 0.0)
    o = float(optimal_entry_price or 0.0)
    if o <= 0:
        return {"entry_alpha": None, "reason": "NO_OPTIMAL_REFERENCE"}
    alpha = (a - o) / o
    return {"entry_alpha": round(alpha, 4),
            "actual_entry": round(a, 4),
            "optimal_entry": round(o, 4),
            "grade": "OPTIMAL" if alpha <= 0.005
            else "LATE" if alpha <= 0.05 else "VERY_LATE"}


def exit_alpha(actual_exit_price, mfe_peak_price) -> dict:
    """退出 Alpha：实际退出 vs MFE 峰值（正 = 退出过早损失）。"""
    a = float(actual_exit_price or 0.0)
    m = float(mfe_peak_price or 0.0)
    if m <= 0:
        return {"exit_alpha": None, "reason": "NO_MFE_PEAK"}
    alpha = (m - a) / m
    return {"exit_alpha": round(alpha, 4),
            "actual_exit": round(a, 4),
            "mfe_peak": round(m, 4),
            "capture": round(a / m, 4) if m > 0 else None,
            "grade": "EXCELLENT" if alpha <= 0.05
            else "GOOD" if alpha <= 0.20 else "EARLY_EXIT"}


def timing_alpha(entry_alpha, exit_alpha) -> dict:
    """Timing Alpha = Entry + Exit（越低越好，负值=超越基准）。"""
    ea = float(entry_alpha if entry_alpha is not None else 0.0)
    xa = float(exit_alpha if exit_alpha is not None else 0.0)
    total = ea + xa
    return {"timing_alpha": round(total, 4),
            "entry_alpha": round(ea, 4),
            "exit_alpha": round(xa, 4),
            "quality": "EXCELLENT" if total <= 0.05
            else "GOOD" if total <= 0.15 else "POOR"}
