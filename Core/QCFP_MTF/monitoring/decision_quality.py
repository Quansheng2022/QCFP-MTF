# coding: utf-8
"""Decision Quality Monitoring（QCFP-MTF 2.8：47 号决策质量监控）

生产后不只监控 P&L，而是逐模块监控质量：
    Permission Quality：BLOCK 避免的损失 / ALLOW 成功率
    Wave Quality：Hit Rate / MFE / MAE / MFE Capture
    Entry Quality：Optimal / Late / Early 占比
    Exit Quality：Exit Early / Late 占比、Exit Capture
    FSM Quality：合法 / 异常 Transition、状态停留

回答"哪个模块正在创造价值，哪个模块正在退化"。
"""

from collections import Counter


def decision_quality_report(trades) -> dict:
    """trades：逐笔交易 [{net_return, mfe, mae, permission, setup_type,
    entry_timing, exit_timing, fsm_transitions, ...}]"""
    n = len(trades)
    if n == 0:
        return {"n": 0}
    # Permission Quality
    allow_trades = [t for t in trades if t.get("permission") in
                    ("ALLOW", "STRONG_ALLOW")]
    allow_wins = [t for t in allow_trades
                  if float(t.get("net_return") or 0.0) > 0]
    blocked_avoided = [t for t in trades if t.get("blocked") is True
                       and float(t.get("net_return") or 0.0) < 0]
    # Wave Quality
    wave_wins = [t for t in trades if float(t.get("net_return") or 0.0) > 0]
    mfe = [float(t.get("mfe") or 0.0) for t in trades]
    mae = [float(t.get("mae") or 0.0) for t in trades]
    captures = [float(t.get("mfe_capture") or 0.0) for t in trades
                if t.get("mfe_capture") is not None]
    # Entry / Exit Timing
    entry_timing = Counter(t.get("entry_timing", "unknown")
                           for t in trades)
    exit_timing = Counter(t.get("exit_timing", "unknown") for t in trades)
    # FSM Quality
    abnormal_transitions = sum(1 for t in trades
                               if t.get("abnormal_transition"))
    return {
        "n": n,
        "permission_quality": {
            "allow_win_rate": round(len(allow_wins) / len(allow_trades), 4)
            if allow_trades else None,
            "blocked_losses_avoided": round(
                -sum(float(t.get("net_return") or 0.0)
                     for t in blocked_avoided), 4),
        },
        "wave_quality": {
            "hit_rate": round(len(wave_wins) / n, 4),
            "mean_mfe": round(sum(mfe) / len(mfe), 4) if mfe else None,
            "mean_mae": round(sum(mae) / len(mae), 4) if mae else None,
            "mean_mfe_capture": round(sum(captures) / len(captures), 4)
            if captures else None,
        },
        "entry_quality": dict(entry_timing),
        "exit_quality": dict(exit_timing),
        "fsm_quality": {
            "abnormal_transitions": abnormal_transitions,
            "abnormal_rate": round(abnormal_transitions / n, 4),
        },
    }
