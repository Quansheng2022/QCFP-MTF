# coding: utf-8
"""回测运行状态门（P1 · Run Status / Data Quality Gate）

防止"带着错误继续生成看似正常的结果"：
    PASS / PASS_WITH_WARNING / FAILED
    - PIT disclosure = ESTIMATED → WARNING（真实披露日覆盖表缺失）
    - PIT universe 缺失：production → FAILED；research → WARNING
"""

from ..common.asof import load_disclosure_overrides


def disclosure_mode(settings) -> str:
    """PIT 披露模式：REAL（有覆盖表）/ ESTIMATED（period_end+45 天）"""
    overrides = load_disclosure_overrides()
    if not overrides:
        return "ESTIMATED"
    return "REAL"


def run_status(settings, universe_empty: bool,
               universe_incomplete_stocks: list = None) -> dict:
    mode = disclosure_mode(settings)
    pit_grade = "A" if mode == "REAL" else "C"   # PIT-A 真实披露 / PIT-C 固定滞后估算
    checks = [f"PIT disclosure = {mode} (PIT-{pit_grade})"]
    status = "PASS"
    if mode != "REAL":
        status = "PASS_WITH_WARNING"
        checks.append("披露日为推算值（period_end + lag），非真实披露日历（PIT-C）")
    bt_mode = settings.get("backtest", {}).get("mode", "research_exploration")
    # P0：PIT 硬门——research_validation 只允许 PIT-A/B；PIT-C 只能 exploration
    if bt_mode == "research_validation" and pit_grade not in ("A", "B"):
        return {"status": "FAILED",
                "checks": checks + [f"PIT-{pit_grade} 不允许 research_validation（需 PIT-A/B）"]}
    if universe_empty:
        # 三档 PIT Universe：exploration→WARN；research_validation/production→FAILED
        if bt_mode in ("research_validation", "production"):
            return {"status": "FAILED",
                    "checks": checks + [
                        f"PIT universe 缺失 → ERROR（{bt_mode} 模式禁止产出绩效）"]}
        status = "PASS_WITH_WARNING"
        checks.append("PIT universe 缺失（research_exploration 模式，存在幸存者偏差风险）")
    else:
        incomplete = [str(c) for c in (universe_incomplete_stocks or [])]
        if incomplete:
            # 2.3：记录不完整 = PIT_INVALID，不得退化为 valid forever
            if bt_mode in ("research_validation", "production"):
                return {"status": "FAILED",
                        "checks": checks + [
                            f"PIT universe 记录不完整 {len(incomplete)} 只"
                            f"（如 {','.join(incomplete[:5])}）→ PIT_INVALID，"
                            f"{bt_mode} 模式禁止产出绩效"]}
            status = "PASS_WITH_WARNING"
            checks.append(
                f"PIT universe 记录不完整 {len(incomplete)} 只（研究模式，"
                f"strict 过滤已剔除；exploration 仍按 valid-forever 处理）")
    return {"status": status, "checks": checks, "pit_grade": pit_grade,
            "pit_disclosure_mode": mode}


def cost_metrics(bt) -> dict:
    """成本语义：毛换手 / 交易成本 / 成本占换手比 / 平均仓位 / 平均单笔换仓"""
    annual_turnover = float(bt["turnover"].mean() * 52) if len(bt) else 0.0
    annual_cost = float(bt["cost"].mean() * 52) if len(bt) else 0.0
    trades = bt[bt["turnover"] > 1e-12]
    return {
        "annual_gross_turnover": round(annual_turnover, 4),
        "annual_transaction_cost": round(annual_cost, 6),
        "cost_per_turnover": round(annual_cost / annual_turnover, 6)
        if annual_turnover > 0 else None,
        "avg_position": round(float(bt["position"].mean()), 4) if len(bt) else None,
        "avg_trade_size": round(float(trades["turnover"].mean()), 4)
        if len(trades) else None,
    }
