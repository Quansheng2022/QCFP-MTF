# coding: utf-8
"""催化剂质量评分（CQS）

用现有季/月频因子区分"脉冲式行情（叙事/政策噪音）"与"反转行情（基本面/盈利质量改善）"：
- 资金持续性（F）：F↑ 且上一季度也 F↑ → +2；仅当季 F↑ → +1
- 趋势质量（P）：q_trend_score>60 且 q_position_52w<0.6 → +1；score<40 且 52w>0.5 → -1
- 筹码稳定（CBI）：CBI_STABLE / LOCKED_CANDIDATE → +1；CBI_TURBULENT → -1

总分范围 -3 ~ +3。
"""


def calc_catalyst_quality(f_state, prev_f_state, q_trend_score,
                          q_position_52w, cbi_state) -> int:
    score = 0
    # 1. 资金持续性（权重 +2）
    if f_state == "F↑":
        score += 2 if prev_f_state == "F↑" else 1
    # 2. 趋势质量（权重 +1；对困境反转股避免因 Trend Score 未达标而过度压制）
    try:
        trend = float(q_trend_score)
        pos = float(q_position_52w)
        if trend > 60 and pos < 0.6:
            score += 1
        elif trend < 40 and pos > 0.5:
            score -= 1
    except (TypeError, ValueError):
        pass
    # 3. CBI 稳定性（权重 +1）
    if cbi_state in ("CBI_STABLE", "CBI_LOCKED_CANDIDATE"):
        score += 1
    elif cbi_state == "CBI_TURBULENT":
        score -= 1
    return max(-3, min(3, score))


def catalyst_type(score) -> str:
    if score >= 2:
        return "高质量反转"
    if score >= 0:
        return "中性偏强"
    return "纯脉冲/噪音"


def observation_position(score, settings) -> float:
    """方案 B 观察仓：按 CQS 动态映射（5% / 20% / 35%）"""
    cfg = settings.get("decision", {}).get("catalyst_quality", {})
    if score >= 2:
        return float(cfg.get("position_high", 0.35))
    if score >= 0:
        return float(cfg.get("position_mid", 0.20))
    return float(cfg.get("position_low", 0.05))


def time_stop_weeks(score, settings):
    """观察仓时间止损（周）：高质量反转/中性偏强不限（改用移动止损），纯脉冲 2 周"""
    cfg = settings.get("decision", {}).get("catalyst_quality", {})
    if score >= 2:
        return cfg.get("time_stop_high")
    if score >= 0:
        val = cfg.get("time_stop_mid", 4)
        return None if val is None else int(val)
    val = cfg.get("time_stop_low", 2)
    return None if val is None else int(val)
