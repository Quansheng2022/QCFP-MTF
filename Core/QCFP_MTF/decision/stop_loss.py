# coding: utf-8
"""止损策略单一来源（StopLossPolicy）

P0-3：规格 / 代码 / 报告必须读取同一个 Policy，禁止报告自行解释止损规则。
Backtest（engine._apply_trailing_stop）、DSS/All-in-One（stop_loss_trigger）
统一从 `decision.stop_loss_policy` 读取。
"""


def get_stop_loss_policy(settings: dict) -> dict:
    """返回止损策略：type=entry_week_low（默认）/ quarterly_vwap；buffer_pct 等参数"""
    pol = dict(settings.get("decision", {}).get("stop_loss_policy", {}))
    if not pol.get("type"):
        # 兼容旧配置：trailing_stop.buffer_pct
        buf = settings.get("decision", {}).get("trailing_stop", {}).get("buffer_pct", 0.02)
        pol = {"type": "entry_week_low", "buffer_pct": float(buf)}
    if pol.get("type") == "entry_week_low":
        pol.setdefault("buffer_pct", 0.02)
    if pol.get("type") == "quarterly_vwap":
        pol.setdefault("threshold", 0.95)
        pol.setdefault("require_volume_confirmation", True)
    return pol


def stop_loss_display(policy: dict) -> str:
    """报告展示文本（与回测执行一致）"""
    t = policy.get("type")
    if t == "entry_week_low":
        return (f"移动止损：收盘跌破建仓周最低价×(1-"
                f"{float(policy.get('buffer_pct', 0.02)):.0%})"
                "（周线收盘确认 → 次周离场；不做盘中触发）")
    if t == "quarterly_vwap":
        return (f"周线放量跌破季VWAP×{float(policy.get('threshold', 0.95)):.2f}"
                + ("（需放量确认）" if policy.get("require_volume_confirmation") else ""))
    return str(policy.get("display") or t or "—")


def stop_loss_buffer_pct(settings: dict) -> float:
    """回测引擎读取的缓冲（与报告展示同源）"""
    return float(get_stop_loss_policy(settings).get("buffer_pct", 0.02))
