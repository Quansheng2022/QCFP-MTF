# coding: utf-8
"""Trade Ledger（QCFP-MTF 2.6：逐笔波段交易，而非只输出 weekly PnL）

从逐周回测构建"每笔 Swing Trade"：
    entry/exit 日期与价格、初始/最大仓位、加/减仓次数、MFE/MAE、
    持有周数、毛/净收益、后验归因（entry 太晚？exit 太早/太晚？）
"""

import pandas as pd


def build_trade_ledger(bt: pd.DataFrame, weekly_kl: pd.DataFrame = None):
    """bt 为 run_backtest 输出（stock_code/week_end/position_start/pnl）"""
    w = None
    if weekly_kl is not None and not weekly_kl.empty:
        w = weekly_kl.copy()
        w["week_end"] = pd.to_datetime(w["date"]).dt.strftime("%Y-%m-%d")
        w = w.set_index(["stock_code", "week_end"])
    trades = []
    for code, g in bt.groupby("stock_code"):
        g = g.sort_values("week_end").reset_index(drop=True)
        pos = g["position_start"].astype(float)
        i, n = 0, len(g)
        while i < n:
            if pos.iloc[i] <= 0:
                i += 1
                continue
            entry_i, entry_date = i, g.loc[i, "week_end"]
            entry_pos = float(pos.iloc[i])
            entry_price = _price(w, code, entry_date, "close")
            max_pos, adds, reduces = entry_pos, 0, 0
            prev_pos = entry_pos
            mfe = mae = 0.0
            j = i
            while j < n and pos.iloc[j] > 0:
                p = float(pos.iloc[j])
                max_pos = max(max_pos, p)
                if j > i:
                    if p > prev_pos + 1e-9:
                        adds += 1
                    elif p < prev_pos - 1e-9:
                        reduces += 1
                hi = _price(w, code, g.loc[j, "week_end"], "high")
                lo = _price(w, code, g.loc[j, "week_end"], "low")
                if hi and entry_price:
                    mfe = max(mfe, hi / entry_price - 1)
                if lo and entry_price:
                    mae = min(mae, lo / entry_price - 1)
                prev_pos = p
                j += 1
            exit_i = j - 1
            exit_date = g.loc[exit_i, "week_end"]
            exit_price = _price(w, code, exit_date, "close")
            holding = max(0, exit_i - i)
            gross = (exit_price / entry_price - 1) if entry_price else None
            pnl_sum = float(g.loc[i:exit_i, "pnl"].sum())
            # 后验归因（用未来 4 周，Evaluation-only）
            fwd_4 = _price(w, code, exit_date, "close", offset=4)
            exit_early = bool(fwd_4 and exit_price and fwd_4 > exit_price * 1.05)
            exit_late = bool(fwd_4 and exit_price and fwd_4 < exit_price * 0.95)
            back4 = _price(w, code, entry_date, "close", offset=-4)
            entry_late = bool(back4 and entry_price and
                              entry_price > back4 * 1.05)
            trades.append({
                "trade_id": f"{code}_{entry_date}",
                "stock_code": code,
                "entry_date": entry_date, "exit_date": exit_date,
                "entry_price": entry_price, "exit_price": exit_price,
                "initial_position": round(entry_pos, 4),
                "max_position": round(max_pos, 4),
                "add_count": adds, "reduce_count": reduces,
                "gross_return": round(gross, 6) if gross is not None else None,
                "net_return": round(pnl_sum / max(entry_pos, 1e-9), 6),
                "mfe": round(mfe, 6), "mae": round(mae, 6),
                "holding_weeks": holding,
                "entry_late": entry_late, "exit_early": exit_early,
                "exit_late": exit_late,
            })
            i = j + 1
    if not trades:
        return pd.DataFrame(columns=[
            "trade_id", "stock_code", "entry_date", "exit_date",
            "entry_price", "exit_price", "initial_position", "max_position",
            "add_count", "reduce_count", "gross_return", "net_return",
            "mfe", "mae", "holding_weeks", "entry_late", "exit_early",
            "exit_late"])
    return pd.DataFrame(trades)


def _price(w, code, week_end, col, offset=0):
    if w is None:
        return None
    try:
        sub = w.loc[code]
    except KeyError:
        return None
    if week_end not in sub.index:
        return None
    pos = sub.index.get_loc(week_end)
    target = pos + offset
    if target < 0 or target >= len(sub):
        return None
    row = sub.iloc[target]
    v = row.get(col) if hasattr(row, "get") else None
    return float(v) if v is not None and v == v else None


def trade_ledger_summary(trades: pd.DataFrame) -> dict:
    if trades is None or trades.empty:
        return {"n_trades": 0}
    win = trades["net_return"].dropna()
    return {
        "n_trades": int(len(trades)),
        "win_rate": round(float((win > 0).mean()), 4) if len(win) else None,
        "avg_holding_weeks": round(float(trades["holding_weeks"].mean()), 2),
        "avg_mfe": round(float(trades["mfe"].mean()), 4),
        "avg_mae": round(float(trades["mae"].mean()), 4),
        "avg_add_count": round(float(trades["add_count"].mean()), 2),
        "avg_reduce_count": round(float(trades["reduce_count"].mean()), 2),
        "entry_late_rate": round(float(trades["entry_late"].mean()), 4),
        "exit_early_rate": round(float(trades["exit_early"].mean()), 4),
        "exit_late_rate": round(float(trades["exit_late"].mean()), 4),
    }
