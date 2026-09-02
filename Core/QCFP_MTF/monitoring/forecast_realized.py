# coding: utf-8
"""Forecast-to-Realized Monitor（QCFP-MTF 2.8：模型预期 vs 实际发生）

比较 Expected MFE / MAE / Holding / Return 与 Realized，
输出 Forecast Bias / Calibration Error，识别"系统性高估波段空间"等问题。

2.8（24 号）：分层校准——除 Trade Quality 分档外，新增按
    Permission / Regime / Wave Stage 分层统计，定位"哪个环境下系统性高估"。
"""

import numpy as np


def _expected_from_quality(trade_quality, holding_hint=1.0):
    """预期代理：由进场时 Trade Quality 映射 MFE 期望（评价用）"""
    tq = float(trade_quality or 0.0)
    return {
        "expected_mfe": round(max(0.0, (tq - 30) / 100.0), 4),
        "expected_mae": round(-max(0.0, (60 - tq) / 200.0), 4),
        "expected_holding": max(1, int(round(holding_hint * 4))),
    }


def compare_trade(trade: dict, expected: dict) -> dict:
    """单笔：预期 vs 实际 → 误差"""
    return {
        "trade_id": trade.get("trade_id"),
        "expected_mfe": expected.get("expected_mfe"),
        "actual_mfe": trade.get("mfe"),
        "mfe_error": round(float(trade.get("mfe") or 0.0)
                           - float(expected.get("expected_mfe") or 0.0), 4),
        "expected_mae": expected.get("expected_mae"),
        "actual_mae": trade.get("mae"),
        "mae_error": round(float(trade.get("mae") or 0.0)
                           - float(expected.get("expected_mae") or 0.0), 4),
        "expected_holding": expected.get("expected_holding"),
        "actual_holding": trade.get("holding_weeks"),
        "holding_error": int(trade.get("holding_weeks") or 0) \
            - int(expected.get("expected_holding") or 0),
        "actual_return": trade.get("net_return"),
    }


def calibration_summary(comparisons: list) -> dict:
    """批量：平均/中位误差 + 系统性方向（bias）"""
    if not comparisons:
        return {"n": 0}
    mfe_err = [c["mfe_error"] for c in comparisons if c["mfe_error"] is not None]
    mae_err = [c["mae_error"] for c in comparisons if c["mae_error"] is not None]
    hold_err = [c["holding_error"] for c in comparisons
                if c["holding_error"] is not None]
    return {
        "n": len(comparisons),
        "mfe_mean_error": round(float(np.mean(mfe_err)), 4) if mfe_err else None,
        "mae_mean_error": round(float(np.mean(mae_err)), 4) if mae_err else None,
        "holding_mean_error": round(float(np.mean(hold_err)), 2)
        if hold_err else None,
        "mfe_systematic_overestimate": bool(
            mfe_err and np.mean(mfe_err) < -0.01),
        "mae_systematic_underestimate": bool(
            mae_err and np.mean(mae_err) > 0.01),
    }


def calibration_table(trades: list, tq_key="trade_quality") -> dict:
    """OOS 校准：按 Trade Quality 分档 → 实际 MFE/MAE/持有期分布（median/P75）"""
    bands = {"0-40": (0, 40), "40-60": (40, 60),
             "60-80": (60, 80), "80-100": (80, 100)}
    out = {}

    def _q(x, p):
        x = sorted(x)
        if not x:
            return None
        return x[min(len(x) - 1, int(p * len(x)))]

    for band, (lo, hi) in bands.items():
        g = [t for t in trades if lo <= float(t.get(tq_key) or 0.0) < hi]
        if not g:
            continue
        mfe = [float(t.get("mfe") or 0.0) for t in g]
        mae = [float(t.get("mae") or 0.0) for t in g]
        hold = [int(t.get("holding_weeks") or 0) for t in g]
        out[band] = {
            "n": len(g),
            "mfe_median": round(_q(mfe, 0.5), 4),
            "mfe_p75": round(_q(mfe, 0.75), 4),
            "mae_median": round(_q(mae, 0.5), 4),
            "holding_median": _q(hold, 0.5),
        }
    return out


def stratified_calibration(comparisons: list, layer_key="permission") -> dict:
    """按指定维度分层：permission / regime / wave_stage → 各层校准摘要。

    输入 comparisons 中每项应带 layer 字段（如 permission/regime/wave_stage），
    否则按 layer_key 从 trade 原字段取。
    """
    layers = {}
    for c in comparisons:
        layer = c.get(layer_key) or (c.get("trade") or {}).get(layer_key) \
            or "unknown"
        layers.setdefault(str(layer), []).append(c)
    out = {}
    for layer, items in sorted(layers.items()):
        out[layer] = calibration_summary(items)
    return out


def calibration_by_strata(comparisons: list, trade_field_key="trade") -> dict:
    """一键三层统计：permission / regime / wave_stage。
    comparisons 为 compare_trade 输出列表，trade 字段携带分层属性。"""
    def _with_layer(c, key):
        t = c.get(trade_field_key) or {}
        return {**c, key: t.get(key) or "unknown"}
    return {
        "permission": stratified_calibration(
            [_with_layer(c, "permission") for c in comparisons],
            layer_key="permission"),
        "regime": stratified_calibration(
            [_with_layer(c, "regime") for c in comparisons],
            layer_key="regime"),
        "wave_stage": stratified_calibration(
            [_with_layer(c, "wave_stage") for c in comparisons],
            layer_key="wave_stage"),
        "trade_quality": calibration_table(
            [c.get(trade_field_key) or {} for c in comparisons]),
    }
