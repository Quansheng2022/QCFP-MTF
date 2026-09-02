# coding: utf-8
"""Module Trim Execution（QCFP-MTF 2.8：20 号复杂度预算真正执行删除）

不再是只生成报告，而是真的执行：
    Ablation → Incremental Value → Complexity Cost →
    KEEP / REVIEW / DROP → Shadow Retirement → RETIRED

模块价值只看四类贡献：
    Alpha Improvement / Risk Reduction / Execution Improvement /
    Governance Necessity
四个都没有明显贡献 → 删除（不是"以后可能有用"）。
"""


def module_trim_execute(modules: dict, deletion_ledger=None) -> dict:
    """执行模块删除。

    modules：{name: {alpha_improvement, risk_reduction,
                    execution_improvement, governance_necessity,
                    complexity_cost}}
    返回 {kept, review, dropped} + 删除台账记录。
    """
    kept, review, dropped = [], [], []
    deletions = []
    for name, m in modules.items():
        value = (float(m.get("alpha_improvement") or 0.0)
                 + float(m.get("risk_reduction") or 0.0)
                 + float(m.get("execution_improvement") or 0.0)
                 + float(m.get("governance_necessity") or 0.0))
        cost = float(m.get("complexity_cost") or 0.0)
        contribution_type = _contribution_type(m)
        if value <= 0.01 and contribution_type == "none":
            dropped.append(name)
            deletions.append({"module": name, "action": "RETIRED",
                              "reason": "四类贡献均无 + 复杂度",
                              "value": round(value, 4),
                              "cost": round(cost, 4)})
        elif value <= 0.05 or cost > value:
            review.append(name)
        else:
            kept.append(name)
    if deletion_ledger is not None:
        deletion_ledger.extend(deletions)
    return {"kept": kept, "review": review, "dropped": dropped,
            "deletions": deletions}


def _contribution_type(m) -> str:
    contribs = {
        "alpha_improvement": float(m.get("alpha_improvement") or 0.0),
        "risk_reduction": float(m.get("risk_reduction") or 0.0),
        "execution_improvement": float(m.get("execution_improvement") or 0.0),
        "governance_necessity": float(m.get("governance_necessity") or 0.0),
    }
    best = max(contribs, key=contribs.get)
    return "none" if contribs[best] <= 0.01 else best


def quarterly_trim_report(deletion_ledger, period="2026-Q3") -> dict:
    """季度复盘：这一次除了增加了什么，实际删除了什么。"""
    return {"period": period,
            "deleted_modules": [d["module"] for d in deletion_ledger],
            "deletion_count": len(deletion_ledger),
            "deletions": deletion_ledger,
            "principle": "四类贡献均无 → 删除，而不是保留'以后可能有用'"}


def physical_retirement_gate(retired_modules, production_imports=None,
                             entry_points=None, report_display=None,
                             executable_paths_before=0,
                             executable_paths_after=0) -> dict:
    """新 18 号：RETIRED 必须物理删除，而不是只改状态标记。

    验收标准：RETIRED 必须让 executable path 数量下降——
    删除 Production import / 配置项 / 运行入口 / 报告展示，
    只保留历史 Replay artifact。
    """
    violations = []
    for mod in (production_imports or []):
        if mod:
            violations.append(f"PRODUCTION_IMPORT:{mod}")
    for ep in (entry_points or []):
        if ep:
            violations.append(f"ENTRY_POINT:{ep}")
    for disp in (report_display or []):
        if disp:
            violations.append(f"REPORT_DISPLAY:{disp}")
    paths_decreased = int(executable_paths_after or 0) < \
        int(executable_paths_before or 0)
    if not paths_decreased:
        violations.append("EXECUTABLE_PATHS_NOT_DECREASED")
    return {
        "retired_modules": list(retired_modules or []),
        "violations": violations,
        "executable_paths_before": int(executable_paths_before or 0),
        "executable_paths_after": int(executable_paths_after or 0),
        "paths_decreased": paths_decreased,
        "verdict": "RETIRED_CLEAN" if not violations
        else "RETIRE_INCOMPLETE",
        "rule": "RETIRED 必须减少可执行路径，只保留 Replay artifact",
    }
