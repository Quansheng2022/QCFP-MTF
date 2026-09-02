# coding: utf-8
"""Chip Stability Confidence（筹码稳定置信度）

公式（权重可配置）：60% × Quarterly_Chip_Score + 40% × CBI_Normalized
Quarterly_Chip_Score 复用 hk_quarterly_chip_analysis.chip_structure_score（0~100）
强制规则：c_state=C↓ → 一律 Low（低流动性/关注度下降，禁锁仓结论）
"""


def compute_chip_confidence(chip_score, cbi_score, c_state, settings):
    """返回 (confidence_score, level)；任一输入缺失返回 (None, None)"""
    if chip_score is None or cbi_score is None:
        return None, None
    cfg = settings.get("fusion", {}).get("chip_confidence", {})
    w_q = float(cfg.get("quarterly_chip_weight", 0.60))
    w_cbi = float(cfg.get("cbi_weight", 0.40))
    high_thr = float(cfg.get("high_threshold", 70))
    med_thr = float(cfg.get("medium_threshold", 50))

    # 权重归一化：W_chip + W_cbi = 1（校准不同权重组合时保证绝对尺度一致）
    total_w = w_q + w_cbi
    if total_w <= 0:
        return None, None
    w_q, w_cbi = w_q / total_w, w_cbi / total_w

    score = w_q * float(chip_score) + w_cbi * float(cbi_score)
    if score >= high_thr:
        level = "High"
    elif score >= med_thr:
        level = "Medium"
    else:
        level = "Low"
    # 强制规则：季度筹码走弱 → Low
    if c_state == "C↓":
        level = "Low"
    return round(score, 4), level
