# coding: utf-8
"""Wave Capture Evaluation（QCFP-MTF 2.3：波段捕获指标）

散户波段系统最重要的验收指标不是 Sharpe，而是：
    大波段捕获率 / 进入延迟 / MFE / MAE / 峰值捕获 / 错误试仓率

术语：
    capture_ratio = 策略波段收益 / 买入持有波段收益
    entry_delay   = 波段开始到首次建仓的周数
    MFE / MAE     = 波段窗口内策略权益的最大有利/不利波动
"""

import numpy as np
import pandas as pd

DEFAULT_WINDOW = 26


def find_waves(weekly_df: pd.DataFrame, min_gain: float = 0.5,
               window: int = DEFAULT_WINDOW) -> pd.DataFrame:
    """识别 26 周窗口内涨幅 >= min_gain 的波段（每只股票独立）"""
    waves = []
    for code, g in weekly_df.groupby("stock_code"):
        g = g.sort_values("date").reset_index(drop=True)
        if "week_end" not in g.columns:
            g["week_end"] = pd.to_datetime(g["date"]).dt.strftime("%Y-%m-%d")
        closes = g["close"].to_numpy(dtype=float)
        week_ends = g["week_end"].astype(str).tolist()
        for i in range(len(g)):
            j = min(i + window, len(g))
            if j - i < 4 or closes[i] <= 0:
                continue
            peak_idx = i + int(np.argmax(closes[i:j]))
            gain = closes[peak_idx] / closes[i] - 1.0
            if gain >= min_gain:
                waves.append({
                    "stock_code": code,
                    "start_date": week_ends[i],
                    "peak_date": week_ends[peak_idx],
                    "end_date": week_ends[j - 1],
                    "start_price": float(closes[i]),
                    "peak_price": float(closes[peak_idx]),
                    "gain": float(gain),
                })
    if not waves:
        return pd.DataFrame(columns=[
            "stock_code", "start_date", "peak_date", "end_date",
            "start_price", "peak_price", "gain"])
    return pd.DataFrame(waves)


def wave_capture_metrics(bt: pd.DataFrame, waves: pd.DataFrame) -> pd.DataFrame:
    """对每个波段计算策略捕获指标（bt 为 run_backtest 输出）"""
    if waves is None or waves.empty:
        return waves.copy()
    bt = bt.copy()
    bt["week_end"] = pd.to_datetime(bt["week_end"]).dt.strftime("%Y-%m-%d")
    rows = []
    for w in waves.to_dict("records"):
        mask = ((bt["stock_code"] == w["stock_code"])
                & (bt["week_end"] >= w["start_date"])
                & (bt["week_end"] <= w["end_date"]))
        seg = bt.loc[mask].sort_values("week_end")
        base = dict(w)
        if seg.empty or (seg["position_start"] > 0).sum() == 0:
            base.update({
                "strategy_return": None, "capture_ratio": None,
                "entry_delay_weeks": None, "peak_capture": None,
                "mfe": None, "mae": None, "participated": False,
                "wave_status": "MISSED",
            })
            rows.append(base)
            continue
        # 2.5：NO_DATA ≠ ZERO_RETURN——持仓周 return 缺失 → 数据不完整，捕获 NA
        missing = seg["return_missing"].fillna(False) \
            if "return_missing" in seg.columns \
            else pd.Series(False, index=seg.index)
        if bool(missing.any()):
            base.update({
                "strategy_return": None, "capture_ratio": None,
                "entry_delay_weeks": None, "peak_capture": None,
                "mfe": None, "mae": None, "participated": True,
                "wave_status": "DATA_INCOMPLETE",
            })
            rows.append(base)
            continue
        equity = (1 + seg["pnl"].fillna(0)).cumprod()
        strat_ret = float(equity.iloc[-1] - 1)
        capture = strat_ret / w["gain"] if w["gain"] > 0 else None
        peak_capture = float(equity.max() - 1) / w["gain"] \
            if w["gain"] > 0 else None
        drawdown = equity / equity.cummax() - 1.0
        first_entry = seg.loc[seg["position_start"] > 0, "week_end"].iloc[0]
        entry_delay = max(0, int(
            (pd.to_datetime(first_entry)
             - pd.to_datetime(w["start_date"])).days // 7))
        base.update({
            "strategy_return": round(strat_ret, 6),
            "capture_ratio": round(capture, 4) if capture is not None else None,
            "entry_delay_weeks": entry_delay,
            "peak_capture": round(peak_capture, 4)
            if peak_capture is not None else None,
            "mfe": round(float(equity.max() - 1), 6),
            "mae": round(float(drawdown.min()), 6),
            "participated": True,
            "wave_status": "OK",
        })
        rows.append(base)
    return pd.DataFrame(rows)


def wave_capture_summary(metrics: pd.DataFrame) -> dict:
    """全波段汇总：捕获率 / 进入延迟 / MFE / MAE / 错失率"""
    if metrics is None or metrics.empty:
        return {"n_waves": 0}
    part = metrics[metrics["participated"]]
    n = int(len(metrics))
    return {
        "n_waves": n,
        "participated": int(len(part)),
        "missed_wave_rate": round(1 - len(part) / n, 4) if n else None,
        "capture_ratio_mean": round(float(part["capture_ratio"].mean()), 4)
        if len(part) else None,
        "entry_delay_mean_weeks": round(
            float(part["entry_delay_weeks"].mean()), 2) if len(part) else None,
        "mfe_mean": round(float(part["mfe"].mean()), 4) if len(part) else None,
        "mae_mean": round(float(part["mae"].mean()), 4) if len(part) else None,
        "gain_mean": round(float(metrics["gain"].mean()), 4) if n else None,
    }


def false_entry_rate(bt: pd.DataFrame, waves: pd.DataFrame) -> float:
    """错误试仓率：波段窗口之外的建仓周 / 全部建仓周"""
    if waves is None or waves.empty:
        return None
    bt = bt.copy()
    bt["week_end"] = pd.to_datetime(bt["week_end"]).dt.strftime("%Y-%m-%d")
    entries = bt[bt["position_start"] > 0].copy()
    if entries.empty:
        return None
    inside = pd.Series(False, index=entries.index)
    for w in waves.to_dict("records"):
        inside |= ((entries["stock_code"] == w["stock_code"])
                   & (entries["week_end"] >= w["start_date"])
                   & (entries["week_end"] <= w["end_date"]))
    return round(float((~inside).sum() / len(entries)), 4)
