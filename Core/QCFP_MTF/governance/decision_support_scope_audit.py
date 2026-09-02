# coding: utf-8
"""Decision Support Scope Audit（P1-10：目标重新对齐式收敛）

把模块按决策支持目标分类：
    CORE_DECISION / CORE_EVIDENCE / SUPPORT / RESEARCH_ONLY /
    OPTIONAL_EXECUTION / RETIRED

DoD：
    * Production Decision-critical LOC 不增加（< 冻结 V9 baseline）
    * ACTIVE Feature 不增加（<= V9 baseline ACTIVE）
    * Broker/Small-Live 模块不在 Production Reachable 集合内
      （OPTIONAL_EXECUTION 从 Production 依赖图解绑）
"""

import json
from pathlib import Path

from ..common.paths import get_qcfp_dir, get_report_root
from .minimal_trusted_release import (
    FROZEN_PRODUCTION_MANIFEST, V9_PRODUCTION_BASELINE_MANIFEST,
    critical_loc_metrics)
from .pwc2_authority_graph import build_authority_graph


CLASS_RULES = (
    (("execution.broker_adapter", "execution.paper_pipeline",
      "execution.unknown_resolution", "execution.simulator",
      "execution.order_state_machine", "execution.execution_gate",
      "execution.deployment_cap", "execution.paper_pipeline",
      "safety.runtime_incident_qualification"),
     "OPTIONAL_EXECUTION"),
    (("ablation.", "evaluation.", "scripts.", "research.",
      "backtest.benchmarks", "backtest.cross_sectional",
      "backtest.robustness"),
     "RESEARCH_ONLY"),
    (("decision.engine", "decision.canonical_action",
      "decision.governance", "decision.institutional_permission",
      "decision.retail_fsm", "decision.retail_position_fsm",
      "decision.retail_position_sizing", "decision.permission_gate",
      "decision.permission_policy", "decision.hard_exit",
      "decision.fsm_authority", "decision.governance_caps",
      "decision.governance_proof", "decision.path_hash",
      "decision.stop_loss", "decision.time_in_trade",
      "decision.trade_quality", "decision.entry_quality",
      "decision.exit_quality", "decision.certified_decision",
      "wave.canonical", "wave.stage_gate", "market.regime"),
     "CORE_DECISION"),
    (("monitoring.runtime_evidence", "governance.runtime_promotion_gate",
      "decision.decision_ledger", "decision.replay_contract",
      "decision.replay_engine", "decision.decision_snapshot",
      "decision.versions", "research.decision_outcome",
      "research.research_outcome", "safety.decision_support_incident_"
      "qualification", "evidence.snapshot", "data.pit_registry",
      "data.information_set", "data.feature_contract",
      "data.asof_contract", "backtest.canonical_runs",
      "backtest.canonical", "backtest.performance",
      "backtest.data_pipeline", "backtest.lookahead_filter",
      "backtest.pit_universe", "execution.runtime_event_ledger"),
     "CORE_EVIDENCE"),
    (("common.", "config.", "governance.", "decision.",
      "backtest.", "wave.", "data.", "market.", "setup.", "portfolio.",
      "safety."),
     "SUPPORT"),
)


def classify(module: str) -> str:
    for prefixes, cls in CLASS_RULES:
        if any(module.startswith(p) for p in prefixes):
            return cls
    return "SUPPORT"


def audit_scope(qcfp_root=None) -> dict:
    qcfp_root = Path(qcfp_root or get_qcfp_dir())
    graph = build_authority_graph(qcfp_root)
    reachable = graph.get("reachable_modules") or []
    metrics = critical_loc_metrics(graph)
    classification = {m: classify(m) for m in reachable}
    by_class = {}
    for m, cls in classification.items():
        by_class.setdefault(cls, []).append(m)
    baseline_path = get_report_root() / "audit" / "mtr" / \
        "critical_loc_baseline.json"
    baseline_loc = None
    baseline_ok = None
    if baseline_path.exists():
        bl = json.loads(baseline_path.read_text(encoding="utf-8"))
        baseline_loc = int((bl.get("baseline") or {}).get(
            "decision_critical_loc") or 0)
        baseline_ok = metrics["decision_critical_loc"] < baseline_loc
    v9_active = sum(1 for i in V9_PRODUCTION_BASELINE_MANIFEST.values()
                    if i.get("state") == "ACTIVE")
    current_active = sum(1 for i in FROZEN_PRODUCTION_MANIFEST.values()
                         if i.get("state") == "ACTIVE")
    optional_in_production = [
        m for m in reachable if classification.get(m) == "OPTIONAL_EXECUTION"]
    return {
        "schema": "DECISION-SUPPORT-SCOPE-AUDIT-1",
        "generated_at": __import__("datetime").datetime.now().strftime(
            "%Y-%m-%d %H:%M:%S"),
        "classification": classification,
        "by_class": {k: sorted(v) for k, v in by_class.items()},
        "reachable_module_count": len(reachable),
        "decision_critical_loc": metrics["decision_critical_loc"],
        "baseline_decision_critical_loc": baseline_loc,
        "decision_critical_loc_down": baseline_ok,
        "active_features": {
            "v9_baseline": v9_active,
            "current": current_active,
            "not_increased": current_active <= v9_active,
        },
        "optional_execution_in_production": optional_in_production,
        "gates": {
            "decision_critical_loc_not_increased": bool(baseline_ok),
            "active_features_not_increased":
                current_active <= v9_active,
            "broker_unbound_from_production":
                not optional_in_production,
        },
        "rule": "Broker/Small-Live 从 Production 依赖图解绑；"
                "不增加 Decision-critical LOC 与 ACTIVE Feature",
    }


def write_audit(report: dict) -> Path:
    out_dir = get_report_root() / "audit" / "runtime_closure"
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / "decision_support_scope_audit.json"
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2),
                    encoding="utf-8")
    return path


def main(argv=None) -> int:
    report = audit_scope()
    path = write_audit(report)
    print(f"Scope Audit: decision_critical_loc={report['decision_critical_loc']} "
          f"down={report['decision_critical_loc_down']} "
          f"active={report['active_features']['current']} "
          f"optional_exec_in_prod={report['optional_execution_in_production']}")
    print(f"→ {path}")
    return 0 if all(report["gates"].values()) else 1


if __name__ == "__main__":
    import sys
    sys.exit(main())
