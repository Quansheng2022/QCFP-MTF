# coding: utf-8
"""Model Performance Decay / Retirement（QCFP-MTF 2.8：48 号模型衰减与退役）

模型上线后持续评估衰减指标：
    OOS Sharpe↓ / MFE↓ / MFE Capture↓ / MAE↑ / Calibration↓ /
    Turnover↑ / Cost Sensitivity↑ / Regime Dependence↑

退役阶梯：
    Experimental → Validated → Shadow → Production → Aging →
    Degraded → Retirement Candidate → Retired

持续恶化 → DEGRADED；严重 → HALTED（不等回撤严重才人工发现）。
"""


RETIREMENT_LADDER = (
    "EXPERIMENTAL", "VALIDATED", "SHADOW", "PRODUCTION", "AGING",
    "DEGRADED", "RETIREMENT_CANDIDATE", "RETIRED",
)


def model_decay_score(indicators: dict) -> dict:
    """衰减评分（0-100 健康度，越低越差）。

    indicators：{oos_sharpe_trend, mfe_trend, mfe_capture_trend, mae_trend,
                 calibration_trend, turnover_trend, cost_sensitivity,
                 regime_dependence}（均为 0-1+ 比例，1=正常/无恶化）。
    """
    s = 100.0
    decay = []
    if float(indicators.get("oos_sharpe_trend") or 1.0) < 0.8:
        s -= 15
        decay.append("OOS_SHARPE_DOWN")
    if float(indicators.get("mfe_trend") or 1.0) < 0.8:
        s -= 15
        decay.append("MFE_DOWN")
    if float(indicators.get("mfe_capture_trend") or 1.0) < 0.8:
        s -= 15
        decay.append("MFE_CAPTURE_DOWN")
    if float(indicators.get("mae_trend") or 1.0) > 1.2:
        s -= 15
        decay.append("MAE_UP")
    if float(indicators.get("calibration_trend") or 1.0) < 0.8:
        s -= 10
        decay.append("CALIBRATION_DOWN")
    if float(indicators.get("turnover_trend") or 1.0) > 1.5:
        s -= 10
        decay.append("TURNOVER_UP")
    if float(indicators.get("cost_sensitivity") or 1.0) > 1.5:
        s -= 10
        decay.append("COST_SENSITIVITY_UP")
    if float(indicators.get("regime_dependence") or 1.0) > 1.5:
        s -= 10
        decay.append("REGIME_DEPENDENCE_UP")
    s = max(0.0, s)
    if s >= 80:
        stage = "PRODUCTION"
    elif s >= 60:
        stage = "AGING"
    elif s >= 35:
        stage = "DEGRADED"
    else:
        stage = "RETIREMENT_CANDIDATE"
    return {"score": round(s, 1), "stage": stage, "decay_flags": decay,
            "retire": stage in ("RETIREMENT_CANDIDATE",)}


def advance_retirement_ladder(current, target) -> str:
    """退役阶梯推进（只进不退）。"""
    if current not in RETIREMENT_LADDER or target not in RETIREMENT_LADDER:
        raise ValueError(f"非法阶梯状态 {current}→{target}")
    if RETIREMENT_LADDER.index(target) < RETIREMENT_LADDER.index(current):
        raise ValueError(f"禁止回退退役阶梯 {current}→{target}")
    return target


def decay_to_md(decay: dict) -> str:
    lines = [
        "# Model Decay Report",
        "",
        f"**健康度：{decay['score']:.0f}**　Stage：{decay['stage']}",
        "",
    ]
    if decay["decay_flags"]:
        lines += ["## 衰减指标", ""]
        lines += [f"- {f}" for f in decay["decay_flags"]]
    lines += ["", f"退役建议：{'RETIRE' if decay['retire'] else '继续观察'}"]
    return "\n".join(lines)


def alpha_health(indicators: dict) -> dict:
    """Alpha Health Score（89 号，更早的预警）：
        90–100 HEALTHY / 75–90 WATCH / 60–75 WARNING / <60 DEGRADED

    指标：Signal Strength / Calibration / MFE / MFE Capture /
          Entry Edge / Exit Edge / Turnover / Cost / Regime Dependence
    WARNING → 增加验证频率（不是自动改参数）。
    """
    s = 100.0
    flags = []
    if float(indicators.get("signal_strength") or 1.0) < 0.8:
        s -= 12
        flags.append("SIGNAL_STRENGTH_DOWN")
    if float(indicators.get("calibration") or 1.0) < 0.8:
        s -= 12
        flags.append("CALIBRATION_DOWN")
    if float(indicators.get("mfe") or 1.0) < 0.8:
        s -= 12
        flags.append("MFE_DOWN")
    if float(indicators.get("mfe_capture") or 1.0) < 0.8:
        s -= 12
        flags.append("MFE_CAPTURE_DOWN")
    if float(indicators.get("entry_edge") or 1.0) < 0.8:
        s -= 8
        flags.append("ENTRY_EDGE_DOWN")
    if float(indicators.get("exit_edge") or 1.0) < 0.8:
        s -= 8
        flags.append("EXIT_EDGE_DOWN")
    if float(indicators.get("turnover") or 1.0) > 1.5:
        s -= 8
        flags.append("TURNOVER_UP")
    if float(indicators.get("cost") or 1.0) > 1.5:
        s -= 8
        flags.append("COST_UP")
    if float(indicators.get("regime_dependence") or 1.0) > 1.5:
        s -= 10
        flags.append("REGIME_DEPENDENCE_UP")
    s = max(0.0, s)
    if s >= 90:
        band = "HEALTHY"
    elif s >= 75:
        band = "WATCH"
    elif s >= 60:
        band = "WARNING"
    else:
        band = "DEGRADED"
    return {
        "score": round(s, 1), "band": band, "flags": flags,
        "action": "INCREASE_VALIDATION" if band in ("WARNING", "WATCH")
        else "CONTINUE" if band == "HEALTHY" else "REVIEW_AND_CONTAIN",
    }
