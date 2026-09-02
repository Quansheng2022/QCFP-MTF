# coding: utf-8
"""Trade Quality Score（QCFP-MTF 2.5：机会质量，牛散实战核心）

"允许交易" ≠ "值得交易"：
    Permission  限制上限（能不能做）
    TQS         决定在允许范围内值不值得做（不改变 Permission）

评分（0–100）：
    Setup 25 + Permission 支持 20 + 趋势 15 + 催化剂 15 + 风险 15 + 市场 10
波段：<20 Noise / 20–40 Weak / 40–60 Tradable / 60–80 High / ≥80 A+

引擎在 target>0 且 TQS < min_tradable 时把 target 压为 0（reason=TRADE_QUALITY_LOW）。
"""

SETUP_SCORE = {"BREAKOUT": 25, "PULLBACK": 22, "RECOVERY": 20,
               "ACCUMULATION": 16, "NONE": 0, None: 0}
PERMISSION_SCORE = {"STRONG_ALLOW": 20, "ALLOW": 16, "TEST": 10,
                    "WATCH": 4, "BLOCK": 0}
MARKET_SCORE = {"risk_on": 10, "neutral": 6, "risk_off": 2}


def _band(score: float) -> str:
    if score >= 80:
        return "A+"
    if score >= 60:
        return "High"
    if score >= 40:
        return "Tradable"
    if score >= 20:
        return "Weak"
    return "Noise"


def evaluate_trade_quality(setup_type=None, permission=None,
                           market_context=None, c_state=None, f_state=None,
                           p_state=None, q_trend_score=None,
                           q_position_52w=None, cbi_state=None,
                           catalyst_score=None, risk_level=None,
                           des_score=0) -> tuple:
    """返回 (score 0-100, band)"""
    s = float(SETUP_SCORE.get(setup_type, 0))
    s += float(PERMISSION_SCORE.get(permission, 0))
    s += float(MARKET_SCORE.get(market_context, 4))
    # 趋势质量（15）：Trend Score>60 且 52W 位置<0.6 → 15；否则按位置给分
    trend = float(q_trend_score or 0)
    pos52 = float(q_position_52w or 0)
    if trend >= 60 and pos52 < 0.6:
        s += 15
    elif trend >= 50:
        s += 10
    elif pos52 < 0.15:
        s += 8                      # 极低位本身有反弹价值
    else:
        s += 4
    # 催化剂（15）：CQS 中性偏强 +；F↑ 持续加分
    cqs = float(catalyst_score or 0)
    if cqs >= 2:
        s += 15
    elif cqs >= 1:
        s += 10
    elif cqs == 0:
        s += 5
    if f_state == "F↑":
        s += 3
    if cbi_state == "CBI_STABLE":
        s += 3
    # 风险（15）：Low/Medium 高分；DES 惩罚
    risk = risk_level or "Medium"
    s += {"Low": 15, "Medium": 10, "High": 4, "Extreme": 0}.get(risk, 6)
    des = float(des_score or 0)
    s -= min(8.0, des * 2)
    score = max(0.0, min(100.0, s))
    return round(score, 2), _band(score)
