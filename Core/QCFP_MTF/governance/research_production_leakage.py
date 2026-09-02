# coding: utf-8
"""Research-to-Production Leakage Test（QCFP-MTF 2.8：88 号泄漏测试）

任何 Research-only 对象都不能进入 Production decision graph：
    WaveOutcomeLabel / future MFE / future MAE / research rank /
    ablation result / shadow-only alpha / diagnostic score
都应标记 RESEARCH_ONLY，并通过 CI 检查 Production import graph。

验收标准：Production dependency graph 中
Research-only node count = 0（PIT 防泄漏的最终工程化版本）。
"""


RESEARCH_ONLY_OBJECTS = ("WaveOutcomeLabel", "future_mfe", "future_mae",
                         "research_rank", "ablation_result",
                         "shadow_alpha", "diagnostic_score")


def research_production_leakage(dependency_nodes: dict) -> dict:
    """dependency_nodes：{node: {"research_only": bool,
    "in_production_graph": bool}}"""
    leaked = []
    for node, attrs in (dependency_nodes or {}).items():
        attrs = attrs or {}
        if attrs.get("research_only") \
                and attrs.get("in_production_graph"):
            leaked.append(node)
    return {
        "leaked_nodes": leaked,
        "leakage_count": len(leaked),
        "production_research_only_node_count": len(leaked),
        "ci_verdict": "PASS" if not leaked else "FAIL",
        "target": "Production dependency graph 中 "
                  "Research-only node count = 0",
        "rule": "Research-only 对象不得进入 Production decision graph",
    }


def research_only_nodes_reachable(dependencies: dict) -> list:
    """新 88 号：从 Production 出发可达的 Research-only 节点。"""
    reachable = []
    for node, attrs in (dependencies or {}).items():
        attrs = attrs or {}
        if attrs.get("reachable_from_production") \
                and attrs.get("research_only"):
            reachable.append(node)
    return reachable


def leakage_ci_zero_tolerance(dependencies: dict) -> dict:
    """新 88 号：Research/Production 隔离是 CI 零容忍硬规则——
    只要一个 Research-only 节点从 Production 可达 → CI FAIL。"""
    leaked = research_only_nodes_reachable(dependencies)
    return {
        "leaked_nodes": leaked,
        "research_only_nodes_reachable_from_production": len(leaked),
        "ci_verdict": "FAIL" if leaked else "PASS",
        "zero_tolerance": True,
        "rule": "Research-only nodes reachable from Production = 0",
    }


def tag_research_only(node: str) -> dict:
    return {"node": node, "research_only": True,
            "production_allowed": False}
