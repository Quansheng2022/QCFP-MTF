# coding: utf-8
"""Model/Data/Execution Joint Stress（QCFP-MTF 2.8：94 号联合退化压力）

最危险的是 Data↓ + Model↓ + Execution↓ 同时发生：
    Market Crash + Data Delay + Liquidity Collapse + Slippage↑ +
    Wave Confidence↓

输出：
    Worst Case Loss / Max Position / Exit Feasibility /
    Liquidity Requirement / Recovery Time
"""

from dataclasses import asdict, dataclass, field


@dataclass(frozen=True)
class JointStressResult:
    worst_case_loss: float
    max_position: float
    exit_feasible: bool
    liquidity_requirement: float
    recovery_weeks: int
    joint_severity: str      # LOW / MEDIUM / HIGH / CRITICAL
    reasons: tuple = field(default_factory=tuple)

    def as_dict(self) -> dict:
        d = asdict(self)
        d["reasons"] = list(self.reasons)
        return d


def joint_stress(position, weekly_vol, data_degraded=False,
                 model_degraded=False, execution_degraded=False,
                 slippage_multiplier=1.0, liquidity_collapse_pct=0.0,
                 recovery_weeks=8) -> JointStressResult:
    """联合退化压力。

    输入：
        position            当前仓位
        weekly_vol          周波动
        *_degraded          各维度退化标记
        slippage_multiplier 滑点倍数
        liquidity_collapse_pct 流动性崩塌（0-1）
        recovery_weeks      预估恢复周数
    """
    reasons = []
    n_fail = sum(bool(x) for x in (data_degraded, model_degraded,
                                   execution_degraded))
    vol = float(weekly_vol or 0.0)
    pos = float(position or 0.0)
    if n_fail == 0:
        severity = "LOW"
    elif n_fail == 1:
        severity = "MEDIUM"
    elif n_fail == 2:
        severity = "HIGH"
    else:
        severity = "CRITICAL"
    if data_degraded:
        reasons.append("DATA_DEGRADED")
    if model_degraded:
        reasons.append("MODEL_DEGRADED")
    if execution_degraded:
        reasons.append("EXECUTION_DEGRADED")
    # 最坏损失 = 仓位 × (波动×联合乘数 + 滑点溢价 + 流动性崩塌)
    joint_mult = 1.0 + 0.5 * n_fail
    worst = pos * (vol * joint_mult
                   + (float(slippage_multiplier or 1.0) - 1.0) * 0.02
                   + float(liquidity_collapse_pct or 0.0))
    # 退出可行性：流动性崩塌 + 执行退化 → 不可顺畅退出
    exit_feasible = not (execution_degraded
                         and float(liquidity_collapse_pct or 0.0) >= 0.3)
    liquidity_req = pos * (1.0 + float(liquidity_collapse_pct or 0.0))
    return JointStressResult(
        worst_case_loss=round(worst, 4),
        max_position=round(pos, 4),
        exit_feasible=exit_feasible,
        liquidity_requirement=round(liquidity_req, 4),
        recovery_weeks=int(recovery_weeks),
        joint_severity=severity,
        reasons=tuple(reasons))


JOINT_SCENARIOS = {
    "A_market_vol_liquidity": {
        "label": "市场-10% + VIX↑ + 流动性-30%",
        "market_shock": -0.10, "vol_mult": 1.5,
        "liquidity_collapse_pct": 0.30, "slippage_multiplier": 1.5,
        "permission_degrade": False, "wave_failure": False},
    "B_sector_permission_wave": {
        "label": "行业-20% + 权限↓ + Wave 破位",
        "market_shock": -0.20, "vol_mult": 1.3,
        "liquidity_collapse_pct": 0.15, "slippage_multiplier": 1.2,
        "permission_degrade": True, "wave_failure": True},
    "C_crash_collapse_correlation": {
        "label": "市场崩盘 + 流动性崩塌 + 滑点×2 + 相关性↑",
        "market_shock": -0.25, "vol_mult": 2.0,
        "liquidity_collapse_pct": 0.50, "slippage_multiplier": 2.0,
        "permission_degrade": True, "wave_failure": True},
}


def joint_scenario_engine(position, weekly_vol, capital,
                          scenarios=None) -> dict:
    """联合情景引擎（18 号）：三个联合情景 → 系统状态。"""
    scenarios = scenarios or JOINT_SCENARIOS
    results = {}
    for name, spec in scenarios.items():
        r = joint_stress(
            position, weekly_vol,
            data_degraded=spec.get("permission_degrade", False),
            model_degraded=spec.get("wave_failure", False),
            execution_degraded=spec.get("slippage_multiplier", 1.0) > 1.3,
            slippage_multiplier=spec.get("slippage_multiplier", 1.0),
            liquidity_collapse_pct=spec.get("liquidity_collapse_pct", 0.0))
        expected_loss = r.worst_case_loss
        max_loss = expected_loss * 1.5
        capital_remaining = max(0.0, float(capital) * (1 - max_loss))
        if r.joint_severity in ("CRITICAL",):
            state = "HALTED"
        elif r.joint_severity in ("HIGH",):
            state = "SAFE_MODE"
        else:
            state = "DEFENSIVE"
        results[name] = {
            "label": spec.get("label", name),
            "gross_exposure": round(float(position), 4),
            "net_exposure": round(float(position), 4),
            "expected_loss": round(expected_loss, 4),
            "max_loss": round(max_loss, 4),
            "exit_days": None,
            "liquidity_shortfall": round(
                max(0.0, r.liquidity_requirement - float(capital)), 4),
            "capital_remaining": round(capital_remaining, 4),
            "system_state": state,
            "exit_feasible": r.exit_feasible,
        }
    worst_state = "DEFENSIVE"
    for r in results.values():
        order = {"DEFENSIVE": 0, "SAFE_MODE": 1, "HALTED": 2}
        if order[r["system_state"]] > order[worst_state]:
            worst_state = r["system_state"]
    return {"scenarios": results, "worst_system_state": worst_state,
            "auto_degraded": worst_state != "DEFENSIVE"}
