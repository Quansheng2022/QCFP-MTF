# coding: utf-8
"""Confidence Calibration（QCFP-MTF 2.8：61 号置信度校准）

Confidence = 0.8 是否真的意味着 ~80% 成功概率？
    Predicted Confidence → Historical Outcome → Calibration Curve

监控：
    Calibration Error / Brier Score / Reliability Curve /
    Confidence Bucket Win Rate / Confidence × MFE / × MAE

输出：
    Raw Confidence → Calibration → Calibrated Confidence
约束：校准参数必须来自 OOS/独立验证，不能直接用当前生产结果偷偷修改。
"""

import math


def _brier_score(predictions, outcomes) -> float:
    """Brier Score = mean((p - y)²)，越低越好。"""
    if not predictions:
        return None
    return round(sum((float(p) - float(y)) ** 2
                     for p, y in zip(predictions, outcomes))
                 / len(predictions), 4)


def calibration_curve(records, buckets=((0.0, 0.55), (0.55, 0.70),
                                       (0.70, 0.85), (0.85, 1.01))) -> dict:
    """records：[{confidence, outcome(0/1)}] → 分桶实际成功率。"""
    curve = {}
    for lo, hi in buckets:
        group = [r for r in records
                 if lo <= float(r.get("confidence") or 0.0) < hi]
        if not group:
            continue
        wins = sum(1 for r in group if float(r.get("outcome") or 0.0) > 0)
        curve[f"{lo:.2f}-{hi:.2f}"] = {
            "n": len(group),
            "actual_win_rate": round(wins / len(group), 4),
            "midpoint": round((lo + hi) / 2, 4),
            "calibration_error": round(
                wins / len(group) - (lo + hi) / 2, 4),
        }
    return curve


def calibrate_confidence(records, oos_validated=True) -> dict:
    """校准报告 + 校准参数（仅当 oos_validated=True 时才更新校准映射）。"""
    preds = [float(r.get("confidence") or 0.0) for r in records]
    outs = [float(r.get("outcome") or 0.0) for r in records]
    brier = _brier_score(preds, outs)
    curve = calibration_curve(records)
    errs = [abs(c["calibration_error"]) for c in curve.values()]
    cal_error = round(sum(errs) / len(errs), 4) if errs else None
    # 校准映射：bucket midpoint → actual win rate（OOS 验证后才可用）
    mapping = {c["midpoint"]: c["actual_win_rate"] for c in curve.values()} \
        if oos_validated else {}
    return {
        "n": len(records),
        "brier_score": brier,
        "calibration_error": cal_error,
        "reliability_curve": curve,
        "overconfident": bool(cal_error is not None and cal_error < -0.05),
        "calibration_mapping": mapping,
        "oos_validated": oos_validated,
        "calibrated": bool(oos_validated and mapping),
    }


def apply_calibration(raw_confidence, calibration_mapping) -> float:
    """Raw Confidence → Calibrated Confidence（就近桶映射）。"""
    raw = float(raw_confidence or 0.0)
    if not calibration_mapping:
        return round(raw, 4)
    best = min(calibration_mapping, key=lambda m: abs(m - raw))
    return round(float(calibration_mapping[best]), 4)


def log_loss(predictions, outcomes, eps=1e-9) -> float:
    """Log Loss：-mean(y·log(p) + (1-y)·log(1-p))，越低越好。"""
    if not predictions:
        return None
    total = 0.0
    for p, y in zip(predictions, outcomes):
        p = max(eps, min(1 - eps, float(p)))
        y = float(y)
        total += y * math.log(p) + (1 - y) * math.log(1 - p)
    return round(-total / len(predictions), 4)


def expected_calibration_error(records, n_bins=10) -> dict:
    """Expected Calibration Error：|实际胜率 − 预测概率| 加权平均。"""
    if not records:
        return {"ece": None, "n_bins": n_bins}
    confs = [float(r.get("confidence") or 0.0) for r in records]
    outcomes = [float(r.get("outcome") or 0.0) for r in records]
    lo, hi = 0.0, 1.0
    bin_w = (hi - lo) / n_bins
    ece = 0.0
    for i in range(n_bins):
        b_lo, b_hi = lo + i * bin_w, lo + (i + 1) * bin_w
        group = [(c, o) for c, o in zip(confs, outcomes)
                 if b_lo <= c < b_hi]
        if not group:
            continue
        pred = sum(c for c, _ in group) / len(group)
        acc = sum(o for _, o in group) / len(group)
        ece += (len(group) / len(records)) * abs(acc - pred)
    return {"ece": round(ece, 4), "n_bins": n_bins}
