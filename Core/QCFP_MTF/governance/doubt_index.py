# coding: utf-8
"""Model Doubt Index（QCFP-MTF 2.8：P1-10 模型怀疑指数）

把"什么时候应该怀疑自己"代码化：
    MDI = 综合 11 项指标（Data/Feature/PIT/Permission Drift、
    Wave Hit-rate↓、MFE↓、MAE↑、Calibration↑、OOS Decay、
    Slippage↑、Decision Flip↑）

    MDI 0-20 NORMAL / 20-40 CAUTION / 40-60 DEFENSIVE /
        60-80 SAFE_MODE / 80-100 HALTED

MDI ↑ → Risk Budget ↓ → Position Size ↓（不等严重亏损才处理）。
"""

from dataclasses import asdict, dataclass, field


@dataclass(frozen=True)
class DoubtIndex:
    score: float
    band: str
    risk_budget_scale: float
    triggered: tuple

    def as_dict(self) -> dict:
        d = asdict(self)
        d["triggered"] = list(self.triggered)
        return d


def model_doubt_index(indicators: dict) -> DoubtIndex:
    """11 项指标 → MDI（0-100，越高越怀疑）。

    indicators 均为 0-1 恶化度（0=健康，1=严重恶化）。
    """
    weights = {
        "data_drift": 10, "feature_drift": 10, "pit_degradation": 15,
        "permission_drift": 8, "wave_hit_decline": 12, "mfe_decline": 10,
        "mae_increase": 8, "calibration_error": 10, "oos_decay": 12,
        "slippage_increase": 5, "decision_flip": 10,
    }
    score = sum(float(indicators.get(k, 0.0) or 0.0) * w
                for k, w in weights.items())
    score = max(0.0, min(100.0, score))
    if score >= 80:
        band, scale = "HALTED", 0.0
    elif score >= 60:
        band, scale = "SAFE_MODE", 0.3
    elif score >= 40:
        band, scale = "DEFENSIVE", 0.5
    elif score >= 20:
        band, scale = "CAUTION", 0.7
    else:
        band, scale = "NORMAL", 1.0
    triggered = [k for k in weights if float(indicators.get(k, 0.0)
                                             or 0.0) >= 0.6]
    return DoubtIndex(score=round(score, 1), band=band,
                      risk_budget_scale=scale, triggered=tuple(triggered))


def doubt_adjusted_budget(mdi: DoubtIndex, risk_budget) -> dict:
    """MDI → 风险预算/仓位缩放。"""
    budget = float(risk_budget or 0.0) * mdi.risk_budget_scale
    return {"original_budget": round(float(risk_budget or 0.0), 4),
            "adjusted_budget": round(budget, 4),
            "scale": mdi.risk_budget_scale,
            "band": mdi.band}
