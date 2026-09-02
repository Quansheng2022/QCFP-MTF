# coding: utf-8
"""Reason Code 标准化（QCFP-MTF 2.8：33 号原因码）

把"because wave looks good"类自由文本升级为机器可审计的原因码：
    WAVE_CONFIRM / WAVE_MATURE / ENTRY_OPTIMAL / ENTRY_LATE /
    PERMISSION_BLOCK / PERMISSION_TEST / RISK_LIMIT / PORTFOLIO_LIMIT /
    LIQUIDITY_LIMIT / TIME_STOP / HARD_EXIT / REGIME_BREAK /
    DATA_DEGRADED / GOVERNANCE_FAIL

Decision 结构：
    primary_reason      主因（单个标准码）
    secondary_reasons   次因列表
    constraint_reasons  约束轨迹原因码（32 号联动）

并提供聚合统计：过去 N 个月有多少交易因 ENTRY_LATE 被阻止。
"""

from collections import Counter


REASON_CODES = (
    "WAVE_CONFIRM", "WAVE_MATURE", "ENTRY_OPTIMAL", "ENTRY_LATE",
    "PERMISSION_BLOCK", "PERMISSION_TEST", "RISK_LIMIT",
    "PORTFOLIO_LIMIT", "LIQUIDITY_LIMIT", "TIME_STOP", "HARD_EXIT",
    "REGIME_BREAK", "DATA_DEGRADED", "GOVERNANCE_FAIL", "NONE",
)

REASON_DESCRIPTIONS = {
    "WAVE_CONFIRM": "波段已确认（CONFIRMING→ACTIVE）",
    "WAVE_MATURE": "波段进入成熟期，机会衰减",
    "ENTRY_OPTIMAL": "进场时机最佳（ACTIVE+回撤介入）",
    "ENTRY_LATE": "进场时机过晚（已实现大部分 MFE）",
    "PERMISSION_BLOCK": "机构权限 BLOCK，禁止交易",
    "PERMISSION_TEST": "机构权限 TEST，仅探索仓位",
    "RISK_LIMIT": "风险预算上限约束",
    "PORTFOLIO_LIMIT": "组合暴露上限约束",
    "LIQUIDITY_LIMIT": "流动性/容量上限约束",
    "TIME_STOP": "持仓时间止损",
    "HARD_EXIT": "硬退出（致命风险）",
    "REGIME_BREAK": "市场环境转坏（Regime 转换）",
    "DATA_DEGRADED": "数据质量降级",
    "GOVERNANCE_FAIL": "治理校验失败",
    "NONE": "无",
}


# 机器级约束原因码（17 号）：回答"谁提出仓位、谁降低仓位、
# 最终谁成为 binding constraint"
CONSTRAINT_REASON_CODES = {
    "PERMISSION_BLOCK_NEW_RISK": "权限 BLOCK 禁止新增风险",
    "WAVE_MATURE_NO_ADD": "Wave MATURE 禁止加仓",
    "WAVE_INVALID_NO_ENTRY": "Wave INVALID 禁止新入场",
    "PORTFOLIO_GROSS_CAP": "组合总暴露上限",
    "PORTFOLIO_SECTOR_CAP": "行业暴露上限",
    "PORTFOLIO_THEME_CAP": "主题暴露上限",
    "RISK_BUDGET_CAP": "风险预算上限",
    "LIQUIDITY_EXIT_LIMIT": "流动性退出上限",
    "EXECUTION_CAPACITY_LIMIT": "执行容量上限",
    "DRAWDOWN_SAFE_MODE": "回撤 SAFE_MODE",
    "DATA_QUALITY_BLOCK": "数据质量 BLOCK",
    "REGIME_CRISIS_BLOCK": "Crisis 环境禁新增",
    "HARD_EXIT_STOP": "硬退出止损",
}


def standard_constraint_reason(constraint_name) -> str:
    """约束名 → 标准机器原因码（报告不靠自然语言猜原因）。"""
    mapping = {
        "permission_cap": "PERMISSION_BLOCK_NEW_RISK",
        "budget_cap": "PORTFOLIO_GROSS_CAP",
        "risk_cap": "RISK_BUDGET_CAP",
        "portfolio_cap": "PORTFOLIO_GROSS_CAP",
        "sector_cap": "PORTFOLIO_SECTOR_CAP",
        "theme_cap": "PORTFOLIO_THEME_CAP",
        "liquidity_cap": "LIQUIDITY_EXIT_LIMIT",
        "execution_cap": "EXECUTION_CAPACITY_LIMIT",
        "drawdown_cap": "DRAWDOWN_SAFE_MODE",
        "data_quality": "DATA_QUALITY_BLOCK",
        "regime_cap": "REGIME_CRISIS_BLOCK",
        "hard_exit": "HARD_EXIT_STOP",
    }
    return mapping.get(str(constraint_name or "").lower(),
                       f"CONSTRAINT_{constraint_name}")


def normalize_reason(reason) -> str:
    """把既有原因文本映射为标准码（无法映射保留原样）。"""
    if reason in REASON_CODES:
        return reason
    r = str(reason or "").upper()
    mapping = [
        ("HARD_EXIT", "HARD_EXIT"),
        ("FORCED_DELEVERAGE", "RISK_LIMIT"),
        ("PERMISSION_BLOCK", "PERMISSION_BLOCK"),
        ("BLOCK", "PERMISSION_BLOCK"),
        ("POSITION_CAP", "PORTFOLIO_LIMIT"),
        ("TRADE_QUALITY_LOW", "ENTRY_LATE"),
        ("ENTRY_LATE", "ENTRY_LATE"),
        ("TIME", "TIME_STOP"),
        ("REGIME", "REGIME_BREAK"),
        ("DATA_QUALITY", "DATA_DEGRADED"),
        ("GOVERNANCE", "GOVERNANCE_FAIL"),
    ]
    for key, code in mapping:
        if key in r:
            return code
    return reason or "NONE"


def reason_code_stats(decisions, code="ENTRY_LATE") -> dict:
    """统计：N 笔决策中因某原因码触发/被阻止的数量。"""
    total = len(decisions)
    hit = 0
    for d in decisions:
        codes = [d.get("primary_reason")] + list(
            d.get("secondary_reasons") or []) + list(
            d.get("constraint_reasons") or [])
        if code in codes:
            hit += 1
    return {"code": code, "count": hit, "total": total,
            "rate": round(hit / total, 4) if total else 0.0}


def reason_code_summary(decisions) -> dict:
    """按原因码聚合统计（可研究的数据）。"""
    counter = Counter()
    for d in decisions:
        for c in [d.get("primary_reason")] + list(
                d.get("secondary_reasons") or []) + list(
                d.get("constraint_reasons") or []):
            if c:
                counter[normalize_reason(c)] += 1
    return dict(counter)
