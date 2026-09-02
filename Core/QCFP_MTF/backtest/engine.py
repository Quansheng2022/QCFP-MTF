# coding: utf-8
"""向量化回测引擎

规则：
- 信号在下一周生效（position = target.shift(1)），杜绝同周偏差；
- 换仓成本在仓位变化周扣除（单边费率 × |Δ仓位|）；
- pnl = 仓位 × 周收益 - 换仓成本。
"""

import pandas as pd
import numpy as np

from .cost_model import directional_cost
from ..decision.stop_loss import stop_loss_buffer_pct
from ..config.settings import retail_settings


def _weekly_returns(weekly_df):
    df = weekly_df[["stock_code", "date", "close"]].copy()
    df["week_end"] = pd.to_datetime(df["date"], errors="coerce").dt.strftime("%Y-%m-%d")
    df = df.sort_values(["stock_code", "week_end"])
    df["weekly_return"] = df.groupby("stock_code")["close"].pct_change()
    df["prev_close"] = df.groupby("stock_code")["close"].shift(1)
    if "low" in weekly_df.columns:
        lows = weekly_df[["stock_code", "date", "low"]].copy()
        lows["week_end"] = pd.to_datetime(lows["date"], errors="coerce").dt.strftime("%Y-%m-%d")
        df = df.merge(lows[["stock_code", "week_end", "low"]],
                      on=["stock_code", "week_end"], how="left")
    else:
        df["low"] = None
    return df[["stock_code", "week_end", "weekly_return", "low", "close",
               "prev_close"]].reset_index(drop=True)


def _apply_entry_week_low_stop(out: pd.DataFrame, settings) -> pd.DataFrame:
    """Entry-Week-Low Stop（建仓周最低价止损，P0-4 更名）

    执行假设（P0 修复，方案 A）：**周线收盘确认**跌破建仓周最低价×(1-buffer)
    → 该周完整承受周收益（持仓至收盘）→ **次周离场**（不按周内止损价成交，
    不使用未来信息；隔夜跳空损益不纳入，属保守/中性口径）。
    直到周信号中断或新季度结构披露（新试多段）才允许重新入场。
    """
    cfg = settings.get("decision", {}).get("trailing_stop", {})
    if not cfg.get("enabled", True):
        return out
    if "is_override" not in out.columns or out["is_override"].eq(False).all():
        out["position_start"] = out["position"].astype(float)
        out["effective_return"] = out["weekly_return"]   # 缺失保持 NaN，不 fillna(0)
        return out
    base_buffer = stop_loss_buffer_pct(settings)
    ts = retail_settings(settings).get("trend_survival", {})
    ts_enabled = bool(ts.get("enabled", True))
    ts_buffer = float(ts.get("buffer_pct", 0.05))
    ts_min_state = str(ts.get("min_state", "HOLDING"))
    fsm_states = out["fsm_state"].to_numpy() \
        if "fsm_state" in out.columns else None
    out = out.sort_values(["stock_code", "week_end"]).reset_index(drop=True)
    orig_positions = out["position"].to_numpy(dtype=float).copy()
    positions = orig_positions.copy()
    pos_start = orig_positions.copy()
    is_ov = out["is_override"].to_numpy(dtype=bool)
    structs = out["structural_available_date"].to_numpy() \
        if "structural_available_date" in out.columns \
        else [None] * len(out)
    lows = out["low"].to_numpy()
    closes = out["close"].to_numpy()
    prev_closes = out["prev_close"].to_numpy()
    prev_struct, entry_low, stopped = None, None, False
    for i in range(len(out)):
        ov = bool(is_ov[i])
        struct = structs[i]
        if not ov or struct != prev_struct:
            prev_struct = struct
            entry_low, stopped = None, False
            if not ov:
                continue
        if stopped:
            positions[i] = 0.0
            pos_start[i] = 0.0        # 已退出：周初无暴露（不残留原 target 仓位）
            continue
        if entry_low is None:
            if positions[i] > 0:
                entry_low = lows[i]
            else:
                continue
        if entry_low is None or pd.isna(entry_low) or pd.isna(closes[i]):
            continue
        buf = ts_buffer if (ts_enabled and fsm_states is not None
                            and fsm_states[i] == ts_min_state) else base_buffer
        if closes[i] < float(entry_low) * (1.0 - buf):
            # 周收盘确认：本周完整收益照记（持仓至收盘），期末仓位归零，次周离场
            positions[i] = 0.0
            stopped = True
    out["position"] = positions
    out["position_start"] = pos_start
    out["effective_return"] = out["weekly_return"]      # 缺失保持 NaN，不 fillna(0)
    # 移动止损离场后重算换手与成本（含止损交易成本）
    out["delta"] = out.groupby("stock_code")["position"].diff().fillna(out["position"])
    out["turnover"] = out["delta"].abs()
    out["cost"] = directional_cost(out["delta"], settings)
    return out


def run_backtest(signals, weekly_df, settings, start=None, end=None):
    """把信号时间线转成逐周逐股的回测结果

    Args:
        signals: data_pipeline.build_signal_timeline 输出（每股票×每周）
        weekly_df: hk_hist_weekly_kline
        settings: QCFP 配置
    Returns:
        DataFrame: stock_code / week_end / action_signal / mtf_regime /
            market_regime / position / turnover / cost / weekly_return / pnl

    P0-1（Canonical-only）：target 必须携带 canonical provenance
    （列 canonical_target 或 target 来自 canonical_replay），
    否则拒绝——禁止 Evidence → target 旁路。
    """
    has_canonical = ("canonical_provenance" in signals.columns
                     or "canonical_target" in signals.columns)
    mode = (settings or {}).get("backtest", {}).get(
        "mode", "research_exploration")
    require_canonical = mode in ("research_validation", "production") \
        or (settings or {}).get("backtest", {}).get(
            "require_canonical_provenance", False)
    if not has_canonical:
        if require_canonical:
            raise ValueError(
                "P0-1 Canonical-only：正式模式拒绝无 canonical "
                "provenance 的 target（禁止 Evidence→target 旁路）。"
                "请经 canonical_replay → evaluate 生成 target。")
        import warnings
        warnings.warn(
            "P0-1 Canonical-only：研究模式使用非 canonical target，"
            "仅供 Shadow Comparator/对比，非正式结果来源")
    target = settings.get("backtest", {}).get("position_target", {})

    s = signals.copy()
    if "market_regime" not in s.columns and "market_context" in s.columns:
        s = s.rename(columns={"market_context": "market_regime"})
    if "canonical_target" in s.columns:
        s["target"] = s["canonical_target"].astype(float)
    elif "target" in s.columns:
        s["target"] = s["target"].astype(float)
    else:
        s["target"] = s["action_signal"].map(lambda a: float(target.get(a, 0.0)))
    # P0-C（新 8 号）：canonical-only 证据链没有 legacy action_signal
    if "action_signal" not in s.columns:
        s["action_signal"] = ""
    s = s.sort_values(["stock_code", "decision_date"])
    s["position"] = s.groupby("stock_code")["target"].shift(1).fillna(0.0)
    s["turnover"] = (s["position"] - s.groupby("stock_code")["position"].shift(1).fillna(0.0)).abs()
    s["delta"] = s["position"] - s.groupby("stock_code")["position"].shift(1).fillna(0.0)
    s["cost"] = directional_cost(s["delta"], settings)

    ret = _weekly_returns(weekly_df)
    out = s.merge(ret, left_on=["stock_code", "decision_date"],
                  right_on=["stock_code", "week_end"], how="inner")
    if start:
        out = out[out["week_end"] >= start]
    if end:
        out = out[out["week_end"] <= end]
    out = _apply_entry_week_low_stop(out, settings)
    # P0-3：缺失收益 ≠ 收益 0——持仓周若 return 缺失则 pnl 为 NaN（标记 return_missing），
    # 由组合层显式处理，绝不用 fillna(0) 把 NO_DATA 变成 ZERO_RETURN。
    out["return_missing"] = out["effective_return"].isna() & (out["position_start"] > 0)
    out["pnl"] = out["position_start"] * out["effective_return"] - out["cost"]
    cols = ["stock_code", "week_end", "action_signal", "mtf_regime",
            "market_regime", "structural_regime", "position", "position_start",
            "turnover", "cost", "weekly_return", "effective_return",
            "return_missing", "pnl"]
    return out[cols].reset_index(drop=True)


def portfolio_returns(results: pd.DataFrame) -> pd.DataFrame:
    """等权组合层：每只股票占用 1/N 资金

    组合周收益 = 个股周 pnl 的均值（pnl 已含仓位与成本）；
    组合换手 = 个股周换手的均值。
    P0-4 组合账本（explicit ledger）：周均暴露 / 现金占比 / 持仓数 /
    缺失收益数（return_missing 周不参与收益平均，也不当 0 处理）。
    """
    g = results.groupby("week_end").agg(
        portfolio_return=("pnl", "mean"),
        avg_turnover=("turnover", "mean"),
        n_stocks=("stock_code", "nunique"),
        avg_exposure=("position_start", "mean"),
        n_missing_return=("return_missing", "sum"),
    )
    g["cash_weight"] = (1.0 - g["avg_exposure"]).round(6)
    return g.reset_index()
