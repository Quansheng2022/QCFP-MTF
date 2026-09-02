# coding: utf-8
"""Decision Explainability Graph（QCFP-MTF 2.8）

把一次 DecisionSnapshot 转成有向解释图：
    Feature → Institutional → Permission → Setup → Risk → FSM → Sizing →
    Final；每条边带 rule / input / threshold / output / reason / version
    （2.8/38 号：补 Threshold 与 Version，回答"为什么不是 8% 而是 4%"）。
"""


def build_explainability_graph(snap) -> dict:
    c = snap.context
    edges = [
        {"source": "Feature State", "target": "Institutional State",
         "rule": "C/F/P→state", "input": "C/F/P",
         "output": snap.institutional_state,
         "threshold": "persistence≥2 & pressure≥1",
         "version": snap.rule_version,
         "reason": ";".join(c.get("trace", {}).get("institutional", ()) or ())},
        {"source": "Institutional State", "target": "Permission",
         "rule": "permission_matrix", "input": snap.institutional_state,
         "output": snap.institutional_permission, "reason": "permission",
         "threshold": "state→BLOCK/WATCH/TEST/ALLOW/STRONG_ALLOW",
         "version": snap.rule_version},
        {"source": "Permission", "target": "Setup",
         "rule": "setup_gate", "input": snap.institutional_permission,
         "output": snap.setup_type or "NONE", "reason": "setup",
         "threshold": "permission≥TEST + W/D 触发",
         "version": snap.rule_version},
        {"source": "Setup", "target": "Risk Gate",
         "rule": "risk_gate", "input": snap.setup_type or "NONE",
         "output": snap.exit_event_kind, "reason": snap.exit_event_reason or "",
         "threshold": "DES≥7 / Extreme / Stop",
         "version": snap.rule_version},
        {"source": "Risk Gate", "target": "FSM",
         "rule": "fsm_transition", "input": snap.exit_event_kind,
         "output": f"{snap.prev_fsm_state}→{snap.next_fsm_state}",
         "reason": snap.primary_reason or "",
         "threshold": "permission_fsm_matrix",
         "version": snap.rule_version},
        {"source": "FSM", "target": "Sizing",
         "rule": "position_sizing", "input": snap.next_fsm_state,
         "output": f"raw={snap.raw_target_position:.4f}",
         "reason": "sizing", "threshold": "additive ladder",
         "version": snap.rule_version},
        {"source": "Sizing", "target": "Final Position",
         "rule": "governance_proof", "input": f"raw={snap.raw_target_position:.4f}",
         "output": f"final={snap.target_position:.4f}",
         "reason": f"budget={snap.participation_mode}(cap {snap.participation_cap:.4f}) "
                   f"constraint={snap.permission_constraint_applied}",
         "threshold": "permission/portfolio/data_quality/regime caps",
         "version": snap.rule_version},
    ]
    return {"nodes": ["Feature State", "Institutional State", "Permission",
                      "Setup", "Risk Gate", "FSM", "Sizing",
                      "Final Position"],
            "edges": edges}


def graph_to_md(g: dict) -> str:
    lines = ["```text"]
    for e in g["edges"]:
        lines.append(
            f"{e['source']} --[{e['rule']} | threshold={e.get('threshold', '-')}"
            f" | {e['reason'] or e['input']}]--> {e['target']}  "
            f"({e['output']}) [v={e.get('version', '-')}]")
    lines.append("```")
    return "\n".join(lines)


def provenance_graph(snap, constraint_trace=None) -> dict:
    """决策血缘图（21 号）：从"可审计记录"升级到"可解释决策链"。

    每个节点记录：value / timestamp / source / version / evidence /
    dependency / decision_effect（BUY 5% → 展开整个决策树）。
    """
    get = snap.get if isinstance(snap, dict) else \
        (lambda k: getattr(snap, k, None))
    ctx = (get("context") or {}) if isinstance(get("context"), dict) else {}
    trace = constraint_trace or ctx.get("constraint_trace") or {}
    reductions = trace.get("reductions") or {}
    nodes = [
        {"node": "Institutional State", "value": get("institutional_state"),
         "timestamp": get("decision_date"), "source": "institutional",
         "version": get("rule_version"),
         "evidence": "C/F/P → state", "dependency": [],
         "decision_effect": f"→ Permission {get('institutional_permission')}"},
        {"node": "Permission", "value": get("institutional_permission"),
         "timestamp": get("decision_date"), "source": "permission_gate",
         "version": get("rule_version"), "evidence": "权限上限",
         "dependency": ["Institutional State"],
         "decision_effect": "cap 约束"},
        {"node": "Regime", "value": ctx.get("market_regime"),
         "timestamp": get("decision_date"), "source": "market.regime",
         "version": get("rule_version"), "evidence": "市场状态",
         "dependency": [], "decision_effect": "风险/阈值修饰"},
        {"node": "Wave", "value": get("setup_type"),
         "timestamp": get("decision_date"), "source": "wave",
         "version": get("rule_version"), "evidence": "机会识别",
         "dependency": ["Regime"], "decision_effect": "机会意图"},
        {"node": "FSM", "value": f"{get('prev_fsm_state')}→"
                                f"{get('next_fsm_state')}",
         "timestamp": get("decision_date"), "source": "retail_fsm",
         "version": get("rule_version"), "evidence": "持仓状态",
         "dependency": ["Permission", "Wave"],
         "decision_effect": "状态转移"},
        {"node": "Risk", "value": get("exit_event_kind"),
         "timestamp": get("decision_date"), "source": "hard_exit",
         "version": get("rule_version"), "evidence": "退出事件",
         "dependency": ["FSM"], "decision_effect": "风险边界"},
        {"node": "Portfolio", "value": ctx.get("participation"),
         "timestamp": get("decision_date"), "source": "portfolio",
         "version": get("rule_version"), "evidence": "组合约束",
         "dependency": ["Risk"], "decision_effect":
             f"reductions={reductions}"},
        {"node": "Execution", "value": ctx.get("execution_assumption"),
         "timestamp": get("decision_date"), "source": "execution",
         "version": get("rule_version"), "evidence": "可执行性",
         "dependency": ["Portfolio"], "decision_effect": "容量/成本"},
        {"node": "Final Target", "value": get("target_position"),
         "timestamp": get("decision_date"), "source": "governance",
         "version": get("rule_version"), "evidence": "Governance Proof",
         "dependency": ["Execution", "Portfolio"],
         "decision_effect": f"final={get('target_position')}"},
    ]
    return {"decision_id": get("decision_id"), "nodes": nodes,
            "edges": [(n["node"], dep) for n in nodes for dep in
                      n["dependency"]]}
