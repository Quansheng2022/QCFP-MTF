# coding: utf-8
"""Action 生成器（单向门控）

输出 BUY/ADD/HOLD/REDUCE/EXIT/WAIT：
- 季度结构空头族（DECLINE/DISTRIBUTION）禁止 BUY/ADD；
- 季度结构多头族（BULLISH/ACCUMULATION）禁止 EXIT；
- risk=Extreme 禁止 BUY/ADD（强制 WAIT）；
- DATA_INSUFFICIENT / 结构未定 → WAIT。
"""

BULLISH_FAMILY = {"STRUCTURAL_BULLISH", "STRUCTURAL_ACCUMULATION"}
BEARISH_FAMILY = {"STRUCTURAL_DECLINE", "STRUCTURAL_DISTRIBUTION"}


def generate_action(mtf_regime, structural_regime, risk_level, settings):
    mapping = settings.get("decision", {}).get("action_mapping", {})
    action = mapping.get(mtf_regime, "WAIT")

    if mtf_regime == "DATA_INSUFFICIENT" \
            or structural_regime in (None, "STATE_UNDETERMINED"):
        return "WAIT"
    if structural_regime in BEARISH_FAMILY and action in ("BUY", "ADD"):
        return "WAIT"
    if structural_regime in BULLISH_FAMILY and action == "EXIT":
        return "REDUCE"
    if risk_level == "Extreme" and action in ("BUY", "ADD"):
        return "WAIT"
    return action
