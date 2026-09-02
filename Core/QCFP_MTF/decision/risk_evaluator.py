# coding: utf-8
"""风险评估器：Low / Medium / High / Extreme

score = 基础分(按 MTF 状态) + 背离 + risk_off + 数据质量 + 低置信度
"""


def evaluate_risk(mtf_regime, alignment, market, data_quality, confidence, settings):
    cfg = settings.get("decision", {}).get("risk", {})
    base = int(cfg.get("base", {}).get(mtf_regime, 4))
    score = base
    reasons = [f"基础:{mtf_regime}({base})"]

    if alignment == "Divergence":
        score += int(cfg.get("add_divergence", 1))
        reasons.append("结构-行为背离+1")
    if market == "risk_off":
        score += int(cfg.get("add_risk_off", 1))
        reasons.append("市场risk_off+1")
    if data_quality == "C":
        score += int(cfg.get("add_dq_c", 1))
        reasons.append("数据质量C+1")
    elif data_quality == "D":
        score += int(cfg.get("add_dq_d", 2))
        reasons.append("数据质量D+2")
    if confidence == "Low":
        score += int(cfg.get("add_low_confidence", 1))
        reasons.append("置信度Low+1")

    if score <= 2:
        level = "Low"
    elif score == 3:
        level = "Medium"
    elif score == 4:
        level = "High"
    else:
        level = "Extreme"
    return level, score, reasons
