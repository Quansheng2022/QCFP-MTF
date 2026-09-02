# coding: utf-8
"""证据等级标注：A/A-/B/C/D（规格书 2.1）

- A   ：事实/直接数据，可单独支撑结构性结论
- A-  ：高可信派生事实，需交叉验证
- B   ：行为代理，仅用于阶段修正
- C   ：短周期交易信号，仅用于 Timing
- D   ：模型推断/组合结果，仅供决策参考
"""

import pandas as pd

EVIDENCE_MAP = {
    # A 级：季度真实筹码 / 资金 / 价格事实
    "inst_ownership_pct_chg": "A",
    "holder_quantity_chg_pct": "A",
    "inst_participation_chg": "A",
    "q_inst_flow_raw": "A",
    # A- 级：高可信派生事实
    "q_inst_flow_z": "A-",
    "q_ifa_zscore": "A-",
    "q_return": "A-",
    "q_trend_score": "A-",
    "q_position_52w": "A-",
    # B 级：月线行为代理
    "m_turnover_zscore": "B",
    "m_turnover_pctl": "B",
    "m_turnover_ma_ratio": "B",
    "m_volume_ma_ratio": "B",
    "m_volume_accel": "B",
    "m_vwap_deviation": "B",
    "m_vp_regime": "B",
    "turnover_liquidity_regime": "B",
    "monthly_behavior_state": "B",
    # C 级：周线战术信号
    "w_turnover_deviation": "C",
    "w_turnover_spike": "C",
    "w_volume_breakout": "C",
    "w_vwap_deviation": "C",
    "w_ma_slope": "C",
    "w_breakout": "C",
    "w_breakdown": "C",
    "tactical_signal": "C",
    # D 级：模型推断 / 组合结果
    "cbi_score": "D",
    "cost_position": "D",
    "chip_stability_confidence": "D",
    "structural_regime": "D",
    "mtf_regime": "D",
    "qcfp_score": "D",
    "action_signal": "D",
    "risk_level": "D",
}

# 由代理/派生逻辑得到的因子：A -> A- 降级
DERIVED_FACTORS = {
    "q_inst_flow_raw",      # 来自 IDR/FBI 派生，非原始机构资金拆分
    "q_inst_flow_z",
    "q_ifa_zscore",
}


def get_evidence_level(factor: str, source: str = "direct") -> str:
    """返回因子证据等级；派生因子自动 A -> A-"""
    level = EVIDENCE_MAP.get(factor, "D")
    if level == "A" and source == "derived" and factor in DERIVED_FACTORS:
        return "A-"
    return level


def annotate(factors, source_map=None) -> pd.DataFrame:
    """批量标注：factors 为因子名列表，返回 DataFrame

    Args:
        factors: 因子名列表
        source_map: {因子名: 'direct'|'derived'}，缺省视为 direct
    """
    source_map = source_map or {}
    rows = []
    for f in factors:
        src = source_map.get(f, "direct")
        rows.append({
            "factor": f,
            "evidence_level": get_evidence_level(f, src),
            "source": src,
            "meaning": _MEANING.get(f, ""),
        })
    return pd.DataFrame(rows)


_MEANING = {
    "inst_ownership_pct_chg": "机构持股比例变化（季度）",
    "holder_quantity_chg_pct": "股东户数变化（季度）",
    "inst_participation_chg": "机构数量变化（季度）",
    "q_inst_flow_raw": "季度机构资金净流入",
    "q_inst_flow_z": "季度机构资金净流入 Z-Score",
    "q_ifa_zscore": "机构资金优势 Z-Score",
    "q_return": "季度收益率",
    "q_trend_score": "季度趋势评分",
    "q_position_52w": "52 周价格位置",
    "cbi_score": "筹码行为指数（代理）",
    "cost_position": "多周期成本位置",
    "chip_stability_confidence": "筹码稳定置信度",
    "structural_regime": "季度结构状态",
    "mtf_regime": "多周期综合状态",
    "qcfp_score": "QCFP 综合评分",
    "tactical_signal": "周线战术信号",
}
