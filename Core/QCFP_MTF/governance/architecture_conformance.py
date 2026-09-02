# coding: utf-8
"""Architecture Conformance Check（QCFP-MTF 2.8：49 号可执行架构规则）

CI 自动检查核心架构边界（违反直接 CI FAIL）：
    Production 不能 import future-aware 模块
    Report 不能 import sizing 引擎
    Legacy 不能是 canonical 默认
    Execution 不能消费 TradeProposal
    只有 Governance 能创建 CanonicalDecision
    只有 ACTIVE feature 进入 ProductionManifest
"""


ARCHITECTURE_RULES = {
    "production_no_future_import": {
        "rule": "Production package 禁止 import WaveOutcomeLabel",
        "check": "future_import"},
    "report_no_sizing_import": {
        "rule": "Report 禁止 import position sizing",
        "check": "report_sizing"},
    "legacy_not_canonical_default": {
        "rule": "Legacy 不能是 canonical 默认",
        "check": "legacy_default"},
    "execution_no_proposal": {
        "rule": "Execution 不能消费 TradeProposal",
        "check": "proposal_consumption"},
    "governance_only_decision": {
        "rule": "只有 Governance 能创建 CanonicalDecision",
        "check": "decision_creation"},
    "active_only_in_manifest": {
        "rule": "只有 ACTIVE feature 进入 ProductionManifest",
        "check": "active_manifest"},
}


def architecture_conformance(checks: dict) -> dict:
    """checks：{rule_check: (ok, detail)} 或 {rule_check: bool}。"""
    results = {}
    failures = []
    for rule_name, spec in ARCHITECTURE_RULES.items():
        v = checks.get(spec["check"])
        if isinstance(v, tuple):
            ok, detail = v
        else:
            ok, detail = bool(v), ""
        results[rule_name] = {"ok": ok, "detail": detail,
                              "rule": spec["rule"]}
        if not ok:
            failures.append(rule_name)
    return {"results": results, "failures": failures,
            "conformant": not failures,
            "ci_verdict": "PASS" if not failures else "FAIL"}


# 新 20 号：禁止的架构边界（违反直接 CI FAIL，不等人工审查）
FORBIDDEN_IMPORT_EDGES = (
    ("report", "position_sizing"),          # Report 禁止算仓位
    ("production", "WaveOutcomeLabel"),     # Production 禁 future label
    ("research", "legacy_target"),          # Formal Research 禁 legacy target
    ("execution", "uncertified_decision"),  # Execution 禁未认证决策
)


def architecture_conformance_gate(import_edges,
                                  forbidden_edges=None) -> dict:
    """新 20 号：CI 硬规则——任何越界 import/引用直接 FAIL。"""
    forbidden = forbidden_edges or FORBIDDEN_IMPORT_EDGES
    violations = []
    for edge in import_edges or []:
        normalized = (str(edge[0]).lower(), str(edge[1]).lower())
        for fb in forbidden:
            if normalized == (str(fb[0]).lower(), str(fb[1]).lower()):
                violations.append({"edge": list(edge),
                                   "rule": list(fb)})
    return {"violations": violations,
            "ci_verdict": "PASS" if not violations else "FAIL",
            "blocked": bool(violations),
            "rule": "违反架构边界直接 CI FAIL，"
                    "而不是等人工代码审查发现"}
