# coding: utf-8
"""MFE / MAE Benchmark（QCFP-MTF 2.8：63 号收益风险基准体系）

按 Wave Type × Entry Type × Market Regime × Holding Period 建立历史基准：
    MFE 中位数 / MAE 中位数 / 最佳持仓期

当前交易可回答："这次 Wave 的实际表现是否明显偏离历史同类机会？"
并为 Entry / Exit / Sizing 提供统一基准（Expected MFE/MAE/Holding）。
"""


def _median(values):
    vals = sorted(float(v) for v in values)
    if not vals:
        return None
    n = len(vals)
    mid = n // 2
    if n % 2:
        return round(vals[mid], 4)
    return round((vals[mid - 1] + vals[mid]) / 2, 4)


def mfe_mae_benchmark(trades, keys=("wave_type", "entry_type",
                                    "market_regime")) -> dict:
    """按维度分层建立 MFE/MAE/持仓期基准。"""
    layers = {}
    for t in trades:
        group_key = tuple(str(t.get(k) or "unknown") for k in keys)
        layers.setdefault(group_key, []).append(t)
    out = {}
    for group_key, group in layers.items():
        mfe = [float(t.get("mfe") or 0.0) for t in group]
        mae = [float(t.get("mae") or 0.0) for t in group]
        holding = [float(t.get("holding_days") or t.get("holding_weeks")
                         or 0.0) for t in group]
        # 最佳持仓期：收益最高分组的持仓中位数
        best_holding = None
        if len(group) >= 3:
            by_holding = {}
            for t in group:
                h = float(t.get("holding_days") or 0.0)
                bucket = int(h // 7) * 7
                by_holding.setdefault(bucket, []).append(
                    float(t.get("net_return") or 0.0))
            best_bucket = max(by_holding, key=lambda b:
                              sum(by_holding[b]) / len(by_holding[b]))
            best_holding = int(best_bucket)
        out["|".join(group_key)] = {
            "n": len(group),
            "mfe_median": _median(mfe),
            "mae_median": _median(mae),
            "holding_median": _median(holding),
            "best_holding_period": best_holding,
        }
    return out


def benchmark_deviation(trade, benchmarks, keys=("wave_type", "entry_type",
                                                 "market_regime")) -> dict:
    """当前交易 vs 同类历史基准的偏离。"""
    group_key = "|".join(str(trade.get(k) or "unknown") for k in keys)
    b = benchmarks.get(group_key)
    if not b or not b["n"]:
        return {"group": group_key, "n": 0, "deviation": None}
    mfe = float(trade.get("mfe") or 0.0)
    mae = float(trade.get("mae") or 0.0)
    dev = {
        "mfe_deviation": round(
            mfe - (b["mfe_median"] or 0.0), 4),
        "mae_deviation": round(
            mae - (b["mae_median"] or 0.0), 4),
    }
    return {"group": group_key, "n": b["n"], "benchmark": b,
            "deviation": dev,
            "outlier": abs(dev["mfe_deviation"]) > 0.05
            or abs(dev["mae_deviation"]) > 0.03}
