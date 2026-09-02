# coding: utf-8
"""Report Information Budget（QCFP-MTF 2.8：69 号报告信息预算）

正式牛散报告只回答 6 个问题：
    能不能参与 / 当前机会阶段 / 建议仓位 / 为什么变化 /
    最大风险 / 什么条件下退出或失效
研究统计、Ablation、Shadow、Legacy comparator 放 Appendix。

验收标准：新增一个报告字段必须证明它会改变理解或行动，
否则不进入主报告（报告复杂度也需要预算）。
"""


REPORT_SIX_QUESTIONS = (
    "can_participate",          # 能不能参与
    "opportunity_stage",        # 当前机会阶段
    "suggested_position",       # 建议仓位
    "why_changed",              # 为什么变化
    "max_risk",                 # 最大风险
    "exit_or_invalidation",     # 什么条件下退出/失效
)

# 新 69 号：主报告就保持六块（Permission / Wave Stage / Final Target /
# Decision Delta / Binding Risk / Exit & Invalidation）
MAIN_REPORT_SECTIONS = (
    "permission",
    "wave_stage",
    "final_target",
    "decision_delta",
    "binding_risk",
    "exit_invalidation",
)


def report_information_budget(fields: dict) -> dict:
    """fields：{field: {"changes_understanding": bool,
                        "changes_action": bool}}"""
    main, appendix = [], []
    for name, meta in (fields or {}).items():
        changes = bool(meta.get("changes_understanding") or
                       meta.get("changes_action"))
        (main if changes else appendix).append(name)
    return {"main_report_fields": main,
            "appendix_fields": appendix,
            "budget_note": "新增字段必须改变理解或行动，否则进 Appendix"}


def main_report_completeness(answers: dict) -> dict:
    """6 问是否齐全。"""
    missing = [q for q in REPORT_SIX_QUESTIONS
               if answers.get(q) is None]
    return {"missing": missing,
            "complete": not missing,
            "six_questions": list(REPORT_SIX_QUESTIONS)}


def report_field_justification(field: str,
                               changes_understanding: bool,
                               changes_action: bool) -> dict:
    """新 69 号：新增主报告字段必须回答"是否会改变用户对当前交易决策
    的理解或行动"；不会 → APPENDIX。"""
    changes = bool(changes_understanding or changes_action)
    return {
        "field": field,
        "changes_understanding": bool(changes_understanding),
        "changes_action": bool(changes_action),
        "placement": "MAIN_REPORT" if changes else "APPENDIX",
        "rule": "报告复杂度也属于系统复杂度；不改变理解或行动 → APPENDIX",
    }


def main_report_sections() -> dict:
    """主报告六块定义。"""
    return {"sections": list(MAIN_REPORT_SECTIONS),
            "appendix_contains": (
                "IC", "HAC", "Ablation", "Shadow divergence",
                "Parameter sensitivity", "Feature contribution"),
            "rule": "主报告就保持六块，其余放 Appendix"}
