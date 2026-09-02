# coding: utf-8
"""Failure Mode Database（QCFP-MTF 2.8：48 号失败分类引擎）

每次交易/错失波段结束后自动归类失败模式：
    F01 Permission 判断错误 / F02 Wave False Positive / F03 Wave Miss /
    F04 Entry Too Early / F05 Entry Too Late / F06 Risk Exit Too Late /
    F07 Premature Exit / F08 Re-entry Whipsaw / F09 Liquidity Failure /
    F10 Data/PIT Failure / F11 Governance Violation / F12 Model Drift
    F13 Wrong Regime / F14 Oversizing / F15 Execution Failure
聚合：Failure Rate / Cost / Frequency / by Regime / by Module。

2.8（48 号）强化：统一失败分类 → 频率 / 亏损贡献 / Regime 分布 /
修正动作（corrective action），形成真正的"错误驱动优化系统"。
"""

from collections import Counter


FAILURE_MODES = {
    "F01": "PERMISSION_WRONG", "F02": "WAVE_FALSE_POSITIVE",
    "F03": "WAVE_MISS", "F04": "ENTRY_TOO_EARLY", "F05": "ENTRY_TOO_LATE",
    "F06": "RISK_EXIT_TOO_LATE", "F07": "PREMATURE_EXIT",
    "F08": "REENTRY_WHIPSAW", "F09": "LIQUIDITY_FAILURE",
    "F10": "DATA_PIT_FAILURE", "F11": "GOVERNANCE_VIOLATION",
    "F12": "MODEL_DRIFT",
    "F13": "WRONG_REGIME", "F14": "OVERSIZING", "F15": "EXECUTION_FAILURE",
}

CORRECTIVE_ACTIONS = {
    "F01": "重新校准 Permission 阈值或披露日映射",
    "F02": "收紧 Wave 触发宽度/增加确认",
    "F03": "检查波段时间窗与回看长度",
    "F04": "提高 Entry Quality 门槛（等确认）",
    "F05": "缩短决策延迟/T+1 成交假设复核",
    "F06": "收紧止损/风险退出阈值",
    "F07": "放宽移动止损缓冲/增加趋势存活权",
    "F08": "加强 Re-entry/Cooldown 治理",
    "F09": "生成 DELEVERAGE_PLAN，控制单笔规模",
    "F10": "修复数据管道/PIT 披露日历",
    "F11": "审查 finalize_target 唯一仓位链",
    "F12": "触发 Drift 监控，进入 Research Review",
    "F13": "引入 Regime Transition 提前降风险",
    "F14": "启用 Dynamic Risk Budget + 单股硬上限",
    "F15": "执行仿真器接入成本/滑点/成交率",
}

MISS_TO_CODE = {
    "PERMISSION_BLOCK": "F01", "PERMISSION_WATCH": "F01",
    "SETUP_ABSENT": "F03", "RISK": "F06", "COOLDOWN": "F08",
}


def classify_failure(trade: dict) -> list:
    """每笔交易结束后自动归类（返回失败码列表；无失败 → NONE）"""
    codes = []
    net = trade.get("net_return")
    if net is not None and net < 0:
        if trade.get("mae") is not None and trade["mae"] < -0.10:
            codes.append("F06" if trade.get("exit_late") else "F02")
        else:
            codes.append("F02")
    if trade.get("entry_late"):
        codes.append("F05")
    if trade.get("exit_early"):
        codes.append("F07")
    if trade.get("whipsaw"):
        codes.append("F08")
    if trade.get("wrong_regime"):
        codes.append("F13")
    if trade.get("oversized"):
        codes.append("F14")
    if trade.get("execution_failure"):
        codes.append("F15")
    return list(dict.fromkeys(codes)) or ["NONE"]


def classify_miss(miss_reason: str) -> str:
    return MISS_TO_CODE.get(miss_reason, "F03")


class FailureModeDB:
    def __init__(self):
        self.records = []

    def record(self, failure_code, stock="", date="", regime="Sideway",
               module="", cost=None):
        for c in (failure_code if isinstance(failure_code, list)
                  else [failure_code]):
            self.records.append({"code": c, "stock": stock, "date": date,
                                 "regime": regime, "module": module,
                                 "cost": cost})

    def summary(self) -> dict:
        n = len(self.records)
        by_code = Counter(r["code"] for r in self.records)
        by_regime = Counter(r["regime"] for r in self.records)
        by_module = Counter(r["module"] for r in self.records
                            if r["module"])
        costs = [r["cost"] for r in self.records if r["cost"] is not None]
        return {
            "n_failures": n,
            "failure_rate": round(n / max(1, n), 4),
            "by_code": dict(by_code),
            "by_regime": dict(by_regime),
            "by_module": dict(by_module),
            "mean_cost": round(sum(costs) / len(costs), 4) if costs else None,
        }

    def taxonomy_summary(self) -> dict:
        """48 号：频率 / 亏损贡献 / Regime 分布 / 修正动作。"""
        total_cost = sum(r["cost"] for r in self.records
                         if r["cost"] is not None and r["cost"] < 0)
        by_code = Counter(r["code"] for r in self.records)
        by_regime = Counter(r["regime"] for r in self.records)
        cost_by_code = {}
        for r in self.records:
            if r["cost"] is None:
                continue
            cost_by_code[r["code"]] = cost_by_code.get(
                r["code"], 0.0) + float(r["cost"])
        breakdown = {}
        for code, cnt in sorted(by_code.items(), key=lambda x: -x[1]):
            cost = cost_by_code.get(code, 0.0)
            breakdown[code] = {
                "name": FAILURE_MODES.get(code, code),
                "frequency": cnt,
                "loss_contribution": round(cost, 4),
                "loss_share": round(cost / total_cost, 4)
                if total_cost else 0.0,
                "regime_distribution": dict(Counter(
                    r["regime"] for r in self.records if r["code"] == code)),
                "corrective_action": CORRECTIVE_ACTIONS.get(code, ""),
            }
        return {
            "n_failures": len(self.records),
            "total_loss": round(total_cost, 4),
            "by_code": breakdown,
            "by_regime": dict(by_regime),
        }
