# coding: utf-8
"""Duplicate Logic Detector（QCFP-MTF 2.8：73 号重复逻辑检测器）

自动发现"同义规则被写了两遍"：扫描生产代码中的相似条件
（如多处 `if permission == BLOCK`、多处自行计算 position cap、
多处重新映射 action）。

验收标准：决策关键逻辑如果在两个 production module 中独立实现，
CI 必须告警；长期目标是"逻辑复用，而不是语义复制"。
"""


def duplicate_logic_detector(pattern_matches: dict) -> dict:
    """pattern_matches：{pattern: [modules]}。"""
    duplicates = {}
    for pattern, modules in (pattern_matches or {}).items():
        unique = sorted(set(modules or []))
        if len(unique) > 1:
            duplicates[pattern] = unique
    return {
        "duplicates": duplicates,
        "duplicate_count": len(duplicates),
        "ci_verdict": "WARN" if duplicates else "PASS",
        "rule": "决策关键逻辑重复实现 → CI 告警；"
                "逻辑复用，而不是语义复制",
    }


def duplicate_scan(scan_items) -> dict:
    """scan_items：[{"pattern":..., "module":...}] → 按 pattern 聚合。"""
    grouped = {}
    for item in scan_items or []:
        pattern = item.get("pattern")
        module = item.get("module")
        if pattern:
            grouped.setdefault(pattern, []).append(module)
    return duplicate_logic_detector(grouped)


BUSINESS_RULE_PATTERNS = (
    "permission_mapping", "position_cap", "wave_stage_mapping",
    "risk_level_mapping", "action_mapping", "research_validated",
    "pit_valid", "final_target_calculation",
)


def duplicate_authority_release_gate(pattern_matches: dict) -> dict:
    """新 73 号：业务决策规则重复 → 阻止 Release（Duplicate Authority=0）。

    普通 helper 重复不是最严重问题；业务决策规则重复才必须阻止。
    """
    r = duplicate_logic_detector(pattern_matches)
    business_duplicates = {
        p: mods for p, mods in r["duplicates"].items()
        if p in BUSINESS_RULE_PATTERNS}
    blocked = bool(business_duplicates)
    return {
        "business_duplicates": business_duplicates,
        "duplicate_count": len(business_duplicates),
        "release_verdict": "RELEASE_BLOCKED" if blocked
        else "RELEASE_ALLOWED",
        "allowed": not blocked,
        "rule": "Production 中 Duplicate Authority = 0；"
                "业务决策规则重复必须阻止 Release",
    }
