# coding: utf-8
"""MTR Closure 静态扫描：旧决策权威关闭 + 正式研究 canonical-only"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[4]
CORE_DIR = PROJECT_ROOT / "Core"
if str(CORE_DIR) not in sys.path:
    sys.path.insert(0, str(CORE_DIR))

from QCFP_MTF.decision.decision_snapshot import DecisionSnapshot
from QCFP_MTF.scripts.decision_engine import project_display_fields


def test_decision_engine_is_projection_only():
    src = (Path(CORE_DIR) / "QCFP_MTF" / "scripts" /
           "decision_engine.py").read_text(encoding="utf-8")
    assert "generate_action" not in src
    assert "effective_position_cqs" not in src
    assert "apply_downside_risk" not in src
    # 不再出现第二次 Canonical 计算：禁止 evaluate() / DecisionConfig /
    # FLAT/0 强制状态。
    assert "canonical_evaluate" not in src
    assert "from QCFP_MTF.decision.engine" not in src
    assert "DecisionConfig" not in src
    assert "load_canonical_snapshot" in src
    assert "project_display_fields" in src
    assert "ledger" in src.lower()


def test_projection_preserves_ledger_decision():
    """Ledger 决策 → 投影后必须保持 final_target/final_action，
    不得重新 evaluate（构造 previous_position=0.20, FinalTarget=0.15）。"""
    snap = DecisionSnapshot(
        decision_id="d1", stock_code="00700", decision_date="2026-08-21",
        institutional_state="DISTRIBUTION",
        institutional_permission="ALLOW", permission_cap="TRADE",
        exit_event_kind="NONE", exit_event_reason="", setup_type="BREAKOUT",
        prev_fsm_state="HOLDING", next_fsm_state="TRIMMING",
        previous_position=0.20, target_position=0.15,
        decision_path=("evidence", "institutional", "fsm", "governance",
                       "final_target"),
        primary_reason="POSITION_CAP", run_id="RUN-1")
    p = project_display_fields(snap)
    assert p["final_target"] == 0.15
    assert p["final_action"] == "REDUCE"
    assert p["action_signal"] == "REDUCE"
    assert p["authority"] == "LEDGER_PROJECTION_ONLY"
    assert p["engine_source"] == "ledger"
    assert p["ledger_run_id"] == "RUN-1"


def test_projection_exit_preserved():
    snap = DecisionSnapshot(
        decision_id="d2", stock_code="01951", decision_date="2026-08-21",
        institutional_state="ACCUMULATION",
        institutional_permission="BLOCK", permission_cap="STAND",
        exit_event_kind="HARD_EXIT", exit_event_reason="stop",
        setup_type="NONE", prev_fsm_state="HOLDING",
        next_fsm_state="EXITING", previous_position=0.25,
        target_position=0.0)
    p = project_display_fields(snap)
    assert p["final_target"] == 0.0
    assert p["final_action"] == "EXIT"


def test_execution_ablation_canonical_only():
    src = (Path(CORE_DIR) / "QCFP_MTF" / "scripts" /
           "execution_ablation.py").read_text(encoding="utf-8")
    assert "build_signal_timeline" not in src
    assert '"--engine"' not in src
    assert "run_canonical_ablation" in src


def test_retired_module_not_importable_by_production():
    """Sprint D：RETIRED 模块不得再被 Production 代码 import。
    score_calculator 已物理删除；其余 RETIRED 权威不得有生产引用。"""
    retired = ("decision.score_calculator", "decision.action_generator",
               "decision.position_sizing", "decision.permission_gate")
    qcfp_root = Path(CORE_DIR) / "QCFP_MTF"
    from QCFP_MTF.governance.pwc2_authority_graph import \
        build_authority_graph
    graph = build_authority_graph(qcfp_root)
    nodes = graph["nodes"]
    for module in graph["reachable_modules"]:
        info = nodes[module]
        src = (qcfp_root / info.get("file", "")).read_text(
            encoding="utf-8", errors="ignore")
        for dotted in retired:
            assert f"QCFP_MTF.{dotted}" not in src, \
                f"{info.get('file')} 仍引用 {dotted}"


def test_score_calculator_file_absent():
    assert not (Path(CORE_DIR) / "QCFP_MTF" / "decision" /
                "score_calculator.py").exists()
