# coding: utf-8
"""Exit Quality Engine（QCFP-MTF 2.8：退出质量与原因分类）

九类退出：
    PROFIT      盈利目标/利润保护（移动止损、盈利回撤）
    RISK        风险退出（止损、DES、波动失控）
    SIGNAL      信号退出（周/日线转弱、Setup 失效）
    WAVE        波段退出（Wave 进入 EXHAUSTING/INVALID，机会结束）
    TIME        时间退出（Time-in-Trade 超期）
    REGIME      环境退出（市场 Regime 转熊/高波动）
    LIQUIDITY   流动性退出（ADV 萎缩/价差扩大，仓位无法顺畅退出）
    GOVERNANCE  治理退出（Permission 降级、Portfolio 约束、合规）
    HARD        硬退出（Hard Exit，最高优先级）

每次退出必须回答"为什么退出"（kind + reason + trigger_detail），
并标记建议动作 REDUCE / EXIT（与 FSM 解耦：本模块只给建议）。
"""

from dataclasses import asdict, dataclass, field


EXIT_KINDS = ("PROFIT", "RISK", "SIGNAL", "WAVE", "TIME", "REGIME",
              "LIQUIDITY", "GOVERNANCE", "HARD", "NONE")


@dataclass(frozen=True)
class ExitQuality:
    kind: str                 # 七类之一 / NONE
    reason: str
    severity: int             # 1=提示, 2=减仓, 3=清仓
    suggested_action: str     # HOLD / REDUCE / EXIT
    score: float = 0.0        # 0-100（退出紧迫度）
    trigger_detail: str = ""
    reasons: tuple = field(default_factory=tuple)

    def as_dict(self) -> dict:
        d = asdict(self)
        d["reasons"] = list(self.reasons)
        return d


def _severity_action(kind, severity) -> str:
    if severity >= 3 or kind == "HARD":
        return "EXIT"
    if severity >= 2:
        return "REDUCE"
    return "HOLD"


def evaluate_exit_quality(
        profit_take_hit=False,
        trailing_stop_hit=False,
        stop_loss_hit=False,
        des_score=0,
        signal_weakened=False,
        wave_exhausted=False,
        time_exit=False,
        regime_bearish=False,
        regime_crisis=False,
        liquidity_low=False,
        permission_downgraded=False,
        portfolio_risk_off=False,
        hard_exit=False,
        max_severity_input=0) -> ExitQuality:
    """按优先级返回唯一退出质量判定（HARD > GOVERNANCE > REGIME >
    LIQUIDITY > TIME > WAVE > SIGNAL > RISK > PROFIT > NONE）。"""
    if hard_exit:
        return ExitQuality("HARD", "Hard Exit（致命风险，无条件清仓）",
                           3, "EXIT", 100.0,
                           trigger_detail="hard_exit=True")
    if portfolio_risk_off:
        return ExitQuality("GOVERNANCE", "组合风险开关触发（RISK_OFF）",
                           2, "REDUCE", 85.0,
                           trigger_detail="portfolio_risk_off=True")
    if permission_downgraded:
        return ExitQuality("GOVERNANCE", "机构权限降级（Permission 约束）",
                           2, "REDUCE", 80.0,
                           trigger_detail="permission_downgraded=True")
    if regime_crisis:
        return ExitQuality("REGIME", "Crisis 市场环境（禁新增风险）",
                           2, "REDUCE", 90.0,
                           trigger_detail="regime_crisis=True")
    if regime_bearish:
        return ExitQuality("REGIME", "Bear 市场环境（趋势存活权下降）",
                           1, "HOLD", 55.0,
                           trigger_detail="regime_bearish=True")
    if liquidity_low:
        return ExitQuality("LIQUIDITY", "流动性恶化（退出困难/冲击成本高）",
                           2, "REDUCE", 82.0,
                           trigger_detail="liquidity_low=True")
    if time_exit:
        return ExitQuality("TIME", "超过最大持有期且无扩张证据",
                           2, "REDUCE", 75.0,
                           trigger_detail="time_exit=True")
    if wave_exhausted:
        return ExitQuality("WAVE", "波段机会结束（EXHAUSTING/INVALID）",
                           2, "REDUCE", 73.0,
                           trigger_detail="wave_exhausted=True")
    if signal_weakened:
        return ExitQuality("SIGNAL", "波段信号转弱（Setup 失效）",
                           2, "REDUCE", 70.0,
                           trigger_detail="signal_weakened=True")
    if stop_loss_hit or des_score >= 8:
        return ExitQuality("RISK", "风险退出（止损/DES 触发）",
                           3, "EXIT", 95.0,
                           trigger_detail=f"stop_loss_hit={stop_loss_hit},"
                                          f"des_score={des_score}")
    if des_score >= 5:
        return ExitQuality("RISK", "风险预警（DES 偏高）",
                           2, "REDUCE", 65.0,
                           trigger_detail=f"des_score={des_score}")
    if trailing_stop_hit:
        return ExitQuality("PROFIT", "移动止损（利润保护）",
                           2, "REDUCE", 72.0,
                           trigger_detail="trailing_stop_hit=True")
    if profit_take_hit:
        return ExitQuality("PROFIT", "盈利目标达成",
                           2, "REDUCE", 68.0,
                           trigger_detail="profit_take_hit=True")
    sev = int(max_severity_input or 0)
    if sev >= 3:
        return ExitQuality("GOVERNANCE", "外部治理强制退出",
                           3, "EXIT", 98.0,
                           trigger_detail=f"max_severity_input={sev}")
    return ExitQuality("NONE", "", 0, "HOLD", 0.0)


EXIT_KIND_TO_TAXONOMY = {
    "HARD": "EXIT_HARD",
    "GOVERNANCE": "EXIT_SIGNAL",
    "REGIME": "EXIT_REGIME",
    "LIQUIDITY": "EXIT_RISK",
    "TIME": "EXIT_TIME",
    "WAVE": "EXIT_DECAY",
    "SIGNAL": "EXIT_SIGNAL",
    "RISK": "EXIT_RISK",
    "PROFIT": "EXIT_TRAILING",
    "NONE": "",
}


def exit_taxonomy(kind) -> str:
    """ExitQuality kind → EXIT_* 分类（75 号）。"""
    return EXIT_KIND_TO_TAXONOMY.get(kind, "")


def exit_efficiency(captured_return, available_mfe) -> dict:
    """退出效率（75 号）：
        Exit Efficiency = Captured MFE / Available MFE
    回答"不是只赚了多少，而是捕获了这次 Wave 的多少有效空间"。
    """
    captured = float(captured_return or 0.0)
    available = float(available_mfe or 0.0)
    if available <= 0:
        return {"efficiency": None, "captured": round(captured, 4),
                "available_mfe": 0.0, "grade": "N/A"}
    eff = captured / available
    grade = "EXCELLENT" if eff >= 0.8 else "GOOD" if eff >= 0.6 \
        else "FAIR" if eff >= 0.4 else "POOR"
    return {"efficiency": round(eff, 4),
            "captured": round(captured, 4),
            "available_mfe": round(available, 4),
            "grade": grade}
