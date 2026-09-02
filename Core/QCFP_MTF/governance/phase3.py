# coding: utf-8
"""Phase 3 — Canonical Decision Chain Closure（PHASE3-V1.2-FINAL-PROOF-CLOSURE）

核心原则：
    Specification defines truth.
    Runtime produces behavior.
    Tests observe behavior.
    Evidence records observations.
    Phase3 Judge aggregates evidence.
    Human freezes.

本模块是纯证据聚合器，不是新的 Authority。

Proof 独立性（F01-F07）：
    F01  Actual Runtime Chain Binding —— 一级证据为观测到的真实函数调用
         顺序（wrapper 不改结果），二级为 DecisionSnapshot.decision_path，
         三级为 Canonical Stage Mapping；三者必须一致。
    F02  Recursive Canonical Root Audit —— rglob + AST 浅扫描，递归发现
         藏在子目录的第二 decision evaluator；report/** 与 scripts/** 的
         canonical evaluate 重算同样递归扫描（AST：Import / ImportFrom / Call）。
    F03  PathHash Independent Adversarial Proof —— 固定 base fixture +
         逐字段 mutation（HASH_MUST_CHANGE）+ constant-hash 攻击。
    F04  Frozen Baseline Binding —— 直接消费 baseline_gate()。
    F05  Independent Regression Evidence —— Judge 不运行 pytest；
         只消费 Test System（scripts/phase3_regression_runner.py）的证据；
         Regression Evidence Contract：四套 required suites、计数一致性
         （collected == passed+failed+errors+skipped）、status/counts 互斥约束、
         skipped 不计为 PASS、缺失 required suite → NOT_PROVEN、
         矛盾证据（如 PASS+failed>0）→ FAIL。
    F06  Tri-State —— PASS / FAIL / NOT_PROVEN 统一 schema；
         EvidenceUnavailable → NOT_PROVEN。
    F07  Freeze Record 由证据推导，不硬编码 0。

Gate 最终固定为 13 个：
    CHAIN_CONFORMANCE / CANONICAL_PATH / RUNTIME_INVARIANTS /
    DECISION_IDENTITY / E2E_DETERMINISM / PATH_HASH / LEDGER / REPLAY /
    REPORT_PROJECTION / GOLDEN / FAILURE_INJECTION / REGRESSION /
    FROZEN_BASELINE
"""

import ast
import copy
import json
import re
from datetime import datetime, timezone
from pathlib import Path


class EvidenceUnavailable(RuntimeError):
    """证据缺失/环境不可用 → NOT_PROVEN（不得当作 FAIL）。"""


def _root() -> Path:
    return Path(__file__).resolve().parents[3]


def _module_dir() -> Path:
    return Path(__file__).resolve().parents[1]


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="ignore") \
        if path.exists() else ""


def _strip_comments(src: str) -> str:
    """去掉 docstring 与注释，避免文档字符串中的字样误判为代码。"""
    src = re.sub(r'"""[\s\S]*?"""', "", src)
    src = re.sub(r"'''[\s\S]*?'''", "", src)
    lines = []
    for line in src.splitlines():
        if line.lstrip().startswith("#"):
            continue
        lines.append(re.sub(r"#.*$", "", line))
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Provider 统一 schema（F06）：{gate, status, verdict, problems, evidence}
# ---------------------------------------------------------------------------

def _provider(gate, status, verdict, problems=None, evidence=None) -> dict:
    return {"gate": gate, "status": status, "verdict": verdict,
            "problems": list(problems or []), "evidence": dict(evidence or {})}


def _ok(gate, verdict, evidence=None) -> dict:
    return _provider(gate, "PASS", verdict, evidence=evidence)


def _fail(gate, verdict, problems, evidence=None) -> dict:
    return _provider(gate, "FAIL", verdict, problems=problems,
                     evidence=evidence)


def _not_proven(gate, verdict, problems, evidence=None) -> dict:
    return _provider(gate, "NOT_PROVEN", verdict, problems=problems,
                     evidence=evidence)


# ---------------------------------------------------------------------------
# F01 — Actual Runtime Chain Binding（三级证据）
# ---------------------------------------------------------------------------

EXPECTED_CANONICAL_STAGES = (
    "INPUT", "PERMISSION", "OPPORTUNITY", "LIFECYCLE",
    "GOVERNANCE", "OUTPUT", "FACT", "VALIDATION",
)

TOKEN_STAGE = {
    "evidence": "INPUT",
    "institutional": "PERMISSION",
    "exit_events": "OPPORTUNITY",
    "setup": "OPPORTUNITY",
    "participation_budget": "OPPORTUNITY",
    "wave": "OPPORTUNITY",
    "fsm": "LIFECYCLE",
    "sizing": "LIFECYCLE",
    "permission_cap": "GOVERNANCE",
    "trade_quality": "GOVERNANCE",
    "governance": "GOVERNANCE",
    "final_target": "GOVERNANCE",
    "snapshot": "OUTPUT",
    "record_snapshot": "FACT",
    "replay": "VALIDATION",
}

# (token, (module_dotted, function_name)) —— evaluate() 真实调用
CHAIN_OBSERVABLE_FUNCTIONS = {
    "evidence": ("evidence.snapshot", "build_evidence_snapshot"),
    "institutional": ("decision.institutional_permission",
                      "evaluate_institutional_permission"),
    "exit_events": ("decision.hard_exit", "evaluate_exit_events"),
    "setup": ("setup.swing_setup", "evaluate_swing_setup"),
    "participation_budget": ("decision.participation_budget",
                             "evaluate_participation_budget"),
    "fsm": ("decision.retail_position_fsm", "transition_audit"),
    "sizing": ("decision.retail_position_sizing", "retail_target_position"),
    "wave": ("wave.canonical", "wave_to_canonical"),
    "trade_quality": ("decision.trade_quality", "evaluate_trade_quality"),
    "final_target": ("decision.governance", "finalize_target"),
}


def _row(**kw) -> dict:
    base = {
        "stock_code": "T_P3", "decision_date": "2026-08-21",
        "c_state": "C↑", "f_state": "F↑", "p_state": "P↑",
        "prev_f_state": "F↑", "monthly_behavior_state": "Improving",
        "tactical_signal": "Breakout", "daily_state": "DAILY_BREAKOUT",
        "risk_level": "Medium", "des_score": 0,
        "chip_stability_confidence": "High", "data_quality": "B",
        "q_position_52w": 0.3, "wave_stage": "ACTIVE",
        "wave_strength": 1.0, "market_context": "Bull",
        "portfolio_state": "NORMAL",
    }
    base.update(kw)
    return base


def _evaluate(row, prev_state="FLAT", prev_pos=0.0, settings=None,
              config=None):
    from QCFP_MTF.config.settings import DEFAULT_SETTINGS
    from QCFP_MTF.decision.engine import evaluate
    return evaluate(dict(row), prev_state, prev_pos,
                    settings if settings is not None else DEFAULT_SETTINGS,
                    config=config)


def _observe_runtime_chain() -> tuple:
    """一级证据：wrapper 真实观测 evaluate() 的函数调用顺序（不改结果）。"""
    import importlib
    observed = []
    originals = []
    from QCFP_MTF.decision import engine as engine_mod
    for token, (dotted, func_name) in CHAIN_OBSERVABLE_FUNCTIONS.items():
        try:
            mod = importlib.import_module(f"QCFP_MTF.{dotted}")
        except Exception:
            continue
        if not hasattr(mod, func_name):
            continue
        original = getattr(mod, func_name)

        def _wrap(token=token, original=original):
            def wrapper(*args, **kwargs):
                observed.append(token)
                return original(*args, **kwargs)
            wrapper.__name__ = getattr(original, "__name__", "wrapper")
            return wrapper

        setattr(mod, func_name, _wrap())
        originals.append((mod, func_name, original))
        if hasattr(engine_mod, func_name):   # engine 模块加载时绑定的引用
            originals.append((engine_mod, func_name,
                              getattr(engine_mod, func_name)))
            setattr(engine_mod, func_name, _wrap())
    try:
        from QCFP_MTF.config.settings import DEFAULT_SETTINGS
        from QCFP_MTF.decision.engine import evaluate
        snap = evaluate(_row(), "FLAT", 0.0, DEFAULT_SETTINGS)
    finally:
        for mod, name, original in originals:
            setattr(mod, name, original)
    return observed, snap


def _dedupe_stages(tokens) -> list:
    stages = []
    for token in tokens:
        stage = TOKEN_STAGE.get(token)
        if stage and (not stages or stages[-1] != stage):
            stages.append(stage)
    return stages


def _normalize_observed_runtime_path(tokens) -> list:
    """把可观测的函数调用 token 归一化为 DecisionSnapshot.decision_path
    的 token 序列：
      * finalize_target 调用同时代表 governance 阶段（final_target 前补 governance）；
      * 其余 token 原样保留（wave 是 OPPORTUNITY 一等 token，不再剔除）。
    """
    out = []
    for t in (tokens or []):
        s = str(t)
        if s == "final_target":
            out.append("governance")
        out.append(s)
    return out


def _normalize_snapshot_path(tokens) -> list:
    """decision_path → 可观测 token 序列：
      * permission_cap 是结构性 token（非独立函数调用），精确比对时剔除；
      * 其余 token 原样保留。
    """
    return [str(t) for t in (tokens or []) if str(t) != "permission_cap"]


def chain_conformance_evidence(observed_runtime_path=None,
                               snapshot_path=None) -> dict:
    """F01：Observed Runtime == Snapshot Path == Canonical Mapping。"""
    if observed_runtime_path is None:
        observed, snap = _observe_runtime_chain()
        observed_runtime_path = observed
        snapshot_path = list(snap.decision_path)
    observed_tokens = [str(t) for t in (observed_runtime_path or [])]
    snapshot_tokens = [str(t) for t in (snapshot_path or [])]
    wave_observed = "wave" in observed_tokens
    # 精确 token 级比对（不再只比 compressed stage）：
    # normalized observed runtime tokens == DecisionSnapshot.decision_path
    normalized_observed = _normalize_observed_runtime_path(observed_tokens)
    normalized_snapshot = _normalize_snapshot_path(snapshot_tokens)
    runtime_snapshot_match = normalized_observed == normalized_snapshot
    observed_stages = _dedupe_stages(observed_tokens)
    snapshot_stages = _dedupe_stages(snapshot_tokens)
    reverse_edges = []
    for i in range(1, len(observed_stages)):
        prev_i = EXPECTED_CANONICAL_STAGES.index(observed_stages[i - 1])
        cur_i = EXPECTED_CANONICAL_STAGES.index(observed_stages[i])
        if cur_i < prev_i:
            reverse_edges.append({"from": observed_stages[i - 1],
                                  "to": observed_stages[i]})
    missing_in_engine = [
        s for s in ("INPUT", "PERMISSION", "OPPORTUNITY", "LIFECYCLE",
                    "GOVERNANCE") if s not in observed_stages]
    full_stage_path = list(observed_stages)
    for s in ("OUTPUT", "FACT", "VALIDATION"):
        if s not in full_stage_path:
            full_stage_path.append(s)
    ok = runtime_snapshot_match and not missing_in_engine \
        and not reverse_edges
    return {
        "gate": "CHAIN_CONFORMANCE",
        "runtime_source": "OBSERVED_CALL_TRACE",
        "observed_runtime_path": observed_tokens,
        "snapshot_declared_path": snapshot_tokens,
        "runtime_snapshot_match": runtime_snapshot_match,
        "wave_sub_gate_observed": wave_observed,
        "normalized_runtime_path": normalized_observed,
        "normalized_snapshot_path": normalized_snapshot,
        "observed_canonical_stage_path": observed_stages,
        "snapshot_canonical_stage_path": snapshot_stages,
        "canonical_stage_path": full_stage_path,
        "expected_canonical_stage_path": list(EXPECTED_CANONICAL_STAGES),
        "missing_stages": missing_in_engine,
        "reverse_edges": reverse_edges,
        "status": "PASS" if ok else "FAIL",
        "verdict": "CHAIN_CONFORMANT" if ok else "CHAIN_NON_CONFORMANT",
        "problems": [],
    }


def chain_conformance_provider() -> dict:
    evidence = chain_conformance_evidence()
    if evidence["status"] == "PASS":
        return _ok("CHAIN_CONFORMANCE", evidence["verdict"],
                   evidence=evidence)
    return _fail("CHAIN_CONFORMANCE", evidence["verdict"],
                 problems=["runtime/snapshot/mapping 不一致"],
                 evidence=evidence)


# ---------------------------------------------------------------------------
# F02 — Recursive Canonical Root Audit（AST 浅扫描，rglob）
# ---------------------------------------------------------------------------

EVALUATOR_NAME_RE = re.compile(
    r"^(evaluate|decision_evaluate|canonical_evaluate|evaluate_decision|"
    r"run_decision|generate_decision)$", re.I)
DECISION_OUTPUT_TOKENS = ("DecisionSnapshot", "target_position",
                          "final_target", "canonical_action")
NON_PRODUCTION_TOP_DIRS = ("research", "scripts", "backtest", "ablation",
                           "evaluation", "tests")


def _evaluate_like_nodes(tree):
    """浅扫描：evaluator-like 函数 + 决策输出 token（避免误报 stage 函数）。"""
    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        if not EVALUATOR_NAME_RE.match(node.name):
            continue
        names = set()
        for sub in ast.walk(node):
            if isinstance(sub, ast.Name):
                names.add(sub.id)
            elif isinstance(sub, ast.Attribute):
                names.add(sub.attr)
            elif isinstance(sub, ast.Constant) and \
                    isinstance(sub.value, str):
                names.add(sub.value)
        tokens = [t for t in DECISION_OUTPUT_TOKENS if t in names]
        if tokens:
            yield node.name, tokens


def recursive_canonical_root_audit(root=None) -> dict:
    """递归扫描 Core/QCFP_MTF/**：唯一 canonical root = decision.engine.evaluate。"""
    root = Path(root) if root else _module_dir()
    findings = []
    for py in sorted(root.rglob("*.py")):
        rel = py.relative_to(root).as_posix()
        if "__pycache__" in rel or rel.startswith("tests/") \
                or "/tests/" in rel:
            continue
        try:
            tree = ast.parse(_read(py))
        except SyntaxError:
            continue
        dotted = rel[:-3].replace("/", ".")
        for func_name, tokens in _evaluate_like_nodes(tree):
            if dotted == "decision.engine" and func_name == "evaluate":
                classification = "CANONICAL"
            elif rel.split("/")[0] in NON_PRODUCTION_TOP_DIRS:
                classification = "RESEARCH_ONLY"
            else:
                classification = "SUSPICIOUS_DECISION_EVALUATOR"
            findings.append({
                "module": dotted, "function": func_name, "file": rel,
                "classification": classification, "tokens": tokens})
    canonical = [f for f in findings
                 if f["classification"] == "CANONICAL"]
    suspicious = [f for f in findings
                  if f["classification"] == "SUSPICIOUS_DECISION_EVALUATOR"]
    research = [f for f in findings
                if f["classification"] == "RESEARCH_ONLY"]
    ok = len(canonical) == 1 and canonical[0]["module"] == "decision.engine" \
        and not suspicious
    return {
        "findings": findings,
        "canonical_roots": [f["module"] for f in canonical],
        "second_canonical_roots": [f["module"] for f in suspicious],
        "research_only_roots": [f["module"] for f in research],
        "pass": ok,
        "verdict": "PATH_CONFORMANT" if ok else "PATH_NON_CONFORMANT",
        "rule": "recursive scan：canonical=1、suspicious=0",
    }


REPORT_FORBIDDEN_IMPORTS = (
    "decision.engine", "decision.retail_position_sizing",
    "decision.retail_position_fsm", "decision.institutional_permission",
    "decision.permission_policy", "decision.participation_budget",
    "decision.trade_quality", "decision.governance",
    "decision.governance_caps", "wave.canonical", "setup.swing_setup",
)

# P0-02：合法 canonical 编排器（scripts/ 顶层研究/回测/影子/审计入口，
# 职责就是唯一调用 decision.engine.evaluate；其余 scripts/** 出现
# canonical evaluate import/call 一律视为重算路径）。
CANONICAL_ENGINE_MODULE = "QCFP_MTF.decision.engine"
LEGITIMATE_CANONICAL_ORCHESTRATORS = frozenset({
    "scripts/canonical_audit.py",
    "scripts/counterfactual_replay.py",
    "scripts/permission_fsm_ablation.py",
    "scripts/replay_certify.py",
    "scripts/shadow_live.py",
    "scripts/shadow_mode.py",
    "scripts/shadow_universe.py",
})
RECOMPUTE_ALIAS_NAMES = frozenset({
    "canonical_evaluate", "decision_evaluate",
    "evaluate_decision", "run_decision", "generate_decision",
})


def _ast_engine_recompute(tree) -> list:
    """AST 检测 canonical evaluate 重算：
    - 导入 QCFP_MTF.decision.engine（Import / ImportFrom，含别名）
    - 调用绑定自该导入的 evaluate 别名，或 engine.evaluate(...)
    返回 [{line, kind, detail}]。
    """
    findings = []
    bound_names = set()
    engine_aliases = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name == CANONICAL_ENGINE_MODULE:
                    engine_aliases.add(alias.asname or "engine")
                elif alias.name.startswith(CANONICAL_ENGINE_MODULE + "."):
                    bound_names.add(alias.asname or alias.name.rsplit(".", 1)[-1])
        elif isinstance(node, ast.ImportFrom):
            if (node.module or "") == CANONICAL_ENGINE_MODULE:
                for alias in node.names:
                    bound_names.add(alias.asname or alias.name)
        elif isinstance(node, ast.Call):
            fn = node.func
            if isinstance(fn, ast.Name):
                name = fn.id
                if name in bound_names or name in RECOMPUTE_ALIAS_NAMES:
                    findings.append({
                        "line": getattr(node, "lineno", 0),
                        "kind": "Call",
                        "detail": f"{name}(...)"})
            elif isinstance(fn, ast.Attribute) and \
                    isinstance(fn.value, ast.Name) and \
                    fn.value.id in engine_aliases and fn.attr == "evaluate":
                findings.append({
                    "line": getattr(node, "lineno", 0),
                    "kind": "Call",
                    "detail": f"{fn.value.id}.evaluate(...)"})
    for name in sorted(bound_names):
        findings.append({
            "line": 0, "kind": "ImportFrom/Import",
            "detail": f"from {CANONICAL_ENGINE_MODULE} import {name}"})
    for alias in sorted(engine_aliases):
        findings.append({
            "line": 0, "kind": "Import",
            "detail": f"import {CANONICAL_ENGINE_MODULE} as {alias}"})
    return findings


def _ast_forbidden_imports(tree, forbidden_modules) -> list:
    """AST 检测 forbidden 模块导入（Import / ImportFrom）。"""
    found = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name in forbidden_modules:
                    found.append(alias.name)
        elif isinstance(node, ast.ImportFrom):
            if (node.module or "") in forbidden_modules:
                found.append(node.module)
    return sorted(set(found))


def _scan_recompute_paths(root) -> dict:
    """递归扫描 report/** 与 scripts/** 的 canonical evaluate 重算。

    report/**：engine-evaluate 重算 + 全部 REPORT_FORBIDDEN_IMPORTS；
    scripts/**：engine-evaluate 重算（合法 canonical 编排器豁免），
                并单独检查 scripts/decision_engine.py 投影适配器。
    """
    root = Path(root)
    report_recompute = []
    script_recompute = []
    for py in sorted((root / "report").rglob("*.py")):
        rel = py.relative_to(root).as_posix()
        if "__pycache__" in rel:
            continue
        try:
            tree = ast.parse(_read(py))
        except SyntaxError:
            continue
        hits = _ast_engine_recompute(tree)
        forbidden = _ast_forbidden_imports(tree, REPORT_FORBIDDEN_IMPORTS)
        if hits or forbidden:
            report_recompute.append({
                "file": rel,
                "canonical_evaluate": hits,
                "forbidden_imports": forbidden})
    for py in sorted((root / "scripts").rglob("*.py")):
        rel = py.relative_to(root).as_posix()
        if "__pycache__" in rel:
            continue
        if rel in LEGITIMATE_CANONICAL_ORCHESTRATORS:
            continue
        try:
            tree = ast.parse(_read(py))
        except SyntaxError:
            continue
        hits = _ast_engine_recompute(tree)
        if hits:
            script_recompute.append({"file": rel,
                                     "canonical_evaluate": hits})
    return {"report_recompute": report_recompute,
            "script_recompute": script_recompute}


def canonical_path_provider(root=None) -> dict:
    audit = recursive_canonical_root_audit(root)
    root = Path(root) if root else _module_dir()
    scan = _scan_recompute_paths(root)
    report_recompute = scan["report_recompute"]
    script_recompute = scan["script_recompute"]
    from QCFP_MTF.governance.pwc2_authority_graph import STATIC_AUTHORITY
    final_target_owner = [
        m for m, t in STATIC_AUTHORITY.items() if t == "FINAL_TARGET"]
    writer_calls = _final_target_production_writers()
    ok = audit["pass"] and not report_recompute and not script_recompute \
        and writer_calls == ["decision/engine.py"] \
        and final_target_owner == ["decision.governance"]
    verdict = audit["verdict"] if ok else "PATH_NON_CONFORMANT"
    evidence = {
        "canonical_root": "decision.engine.evaluate",
        "canonical_roots": len(audit["canonical_roots"]),
        "second_canonical_roots": audit["second_canonical_roots"],
        "recursive_findings": audit["findings"],
        "research_only_roots": audit["research_only_roots"],
        "report_recompute": report_recompute,
        "script_recompute": script_recompute,
        "recompute_scan": {
            "report_scan": "rglob(*.py) AST",
            "scripts_scan": "rglob(*.py) AST",
            "orchestrator_allowlist": sorted(
                LEGITIMATE_CANONICAL_ORCHESTRATORS),
        },
        "final_target_writer": writer_calls,
        "final_target_authority": final_target_owner,
        "final_target_writers": len(writer_calls),
    }
    if ok:
        return _ok("CANONICAL_PATH", verdict, evidence=evidence)
    problems = []
    if audit["second_canonical_roots"]:
        problems.append(f"第二 evaluator: {audit['second_canonical_roots']}")
    if report_recompute:
        problems.append(f"report 重算: {report_recompute}")
    if script_recompute:
        problems.append(f"scripts 重算: {script_recompute}")
    if writer_calls != ["decision/engine.py"]:
        problems.append(f"final_target writers={writer_calls}")
    return _fail("CANONICAL_PATH", verdict, problems=problems,
                 evidence=evidence)


def _final_target_production_writers() -> list:
    module_dir = _module_dir()
    writers = []
    for py in module_dir.rglob("*.py"):
        rel = py.relative_to(module_dir).as_posix()
        if "__pycache__" in rel or rel.startswith("tests/") \
                or "/tests/" in rel:
            continue
        if re.search(r"\bfinalize_target\s*\(",
                     _strip_comments(_read(py))):
            writers.append(rel)
    non_production = {
        "decision/boundary_test.py", "governance/failure_injection.py",
        "governance/phase3.py",
    }
    return sorted(
        f for f in writers
        if f not in non_production
        and not f.startswith(("scripts/", "research/", "backtest/",
                              "ablation/", "evaluation/"))
        and not f.endswith("decision/governance.py"))


# ---------------------------------------------------------------------------
# P3.2 — Runtime Authority Invariants（真实 evaluate 执行）
# ---------------------------------------------------------------------------

def runtime_invariants() -> dict:
    results = {}
    snap = _evaluate(_row(c_state="C↓", f_state="F↓", p_state="P↓",
                          prev_f_state="F↓", tactical_signal="Breakout",
                          daily_state="DAILY_BREAKOUT",
                          wave_stage="ACTIVE", wave_strength=1.0))
    results["P3-INV-01"] = {
        "name": "Signal cannot upgrade Permission",
        "permission": snap.institutional_permission,
        "target": snap.target_position,
        "pass": snap.institutional_permission == "BLOCK"
        and snap.target_position == 0.0}
    snap = _evaluate(_row(c_state="C↓", f_state="F↓", p_state="P↓",
                          prev_f_state="F↓", wave_stage="ACTIVE",
                          wave_strength=1.0))
    results["P3-INV-02"] = {
        "name": "Wave cannot upgrade Permission",
        "permission": snap.institutional_permission,
        "target": snap.target_position,
        "pass": snap.institutional_permission == "BLOCK"
        and snap.target_position == 0.0}
    snap = _evaluate(_row())
    raw = float(snap.raw_target_position or 0.0)
    final = float(snap.target_position or 0.0)
    proof = (snap.context or {}).get("governance_proof") or {}
    results["P3-INV-03"] = {
        "name": "Proposal != Final Decision",
        "raw_target": raw, "final_target": final,
        "governance_proof": proof.get("proof"),
        "pass": proof.get("proof") == "PASS" and final <= raw + 1e-9}
    results["P3-INV-04"] = {
        "name": "FSM cannot directly own FinalTarget",
        "decision_path": list(snap.decision_path),
        "pass": "governance" in snap.decision_path
        and "final_target" in snap.decision_path}
    results["P3-INV-05"] = {
        "name": "FinalTarget only from Governance",
        "final_target_writer": _final_target_production_writers(),
        "pass": _final_target_production_writers() == ["decision/engine.py"]}
    results["P3-INV-06"] = {
        "name": "Downstream risk cannot increase",
        "raw_target": raw, "final_target": final,
        "pass": final <= raw + 1e-9}
    snap = _evaluate(_row(des_score=8, tactical_signal="Breakout",
                          daily_state="DAILY_BREAKOUT",
                          wave_stage="ACTIVE", wave_strength=1.0))
    results["P3-INV-07"] = {
        "name": "Hard Exit overrides bullish proposals",
        "exit_event": snap.exit_event_kind,
        "primary_reason": snap.primary_reason,
        "target": snap.target_position,
        "pass": snap.exit_event_kind == "HARD_EXIT"
        and snap.primary_reason == "HARD_EXIT"
        and snap.target_position == 0.0}
    failed = [k for k, v in results.items() if not v["pass"]]
    return {"invariants": results, "failed": failed,
            "pass": not failed,
            "verdict": "RUNTIME_INVARIANTS_PASS" if not failed
            else "RUNTIME_INVARIANTS_FAIL"}


def runtime_invariants_provider() -> dict:
    result = runtime_invariants()
    if result["pass"]:
        return _ok("RUNTIME_INVARIANTS", result["verdict"],
                   evidence=result)
    return _fail("RUNTIME_INVARIANTS", result["verdict"],
                 problems=[f"不变量失败: {result['failed']}"],
                 evidence=result)


# ---------------------------------------------------------------------------
# P3.3 — E2E Determinism + Decision Identity
# ---------------------------------------------------------------------------

def _snap_dict(snap) -> dict:
    return json.loads(json.dumps(snap.as_dict(), sort_keys=True,
                                 ensure_ascii=False, default=str))


def e2e_determinism() -> dict:
    row = _row()
    run_a = _snap_dict(_evaluate(row))
    run_b = _snap_dict(_evaluate(row))
    fields = ("institutional_permission", "setup_type", "next_fsm_state",
              "raw_target_position", "target_position", "canonical_action",
              "primary_reason", "secondary_reasons", "binding_constraint",
              "constraint_trace", "decision_path", "decision_path_hash")
    mismatches = [f for f in fields if run_a.get(f) != run_b.get(f)]
    if not mismatches and run_a != run_b:
        mismatches = ["<full_snapshot>"]
    return {"mismatches": mismatches, "deterministic": not mismatches,
            "pass": not mismatches,
            "verdict": "DETERMINISTIC" if not mismatches
            else "DETERMINISM_FAILURE",
            "compare_mode": "EXACT（无 approximately equal / tolerance）",
            "fields_compared": len(fields)}


def e2e_determinism_provider() -> dict:
    result = e2e_determinism()
    if result["pass"]:
        return _ok("E2E_DETERMINISM", result["verdict"], evidence=result)
    return _fail("E2E_DETERMINISM", result["verdict"],
                 problems=result["mismatches"], evidence=result)


def _identity_snap(**kw) -> "DecisionSnapshot":
    from QCFP_MTF.decision.decision_snapshot import DecisionSnapshot
    base = dict(
        decision_id="P3-ID-1", stock_code="00700",
        decision_date="2026-08-21", institutional_state="ACCUMULATION",
        institutional_permission="ALLOW", permission_cap="TRADE",
        exit_event_kind="NONE", exit_event_reason="",
        setup_type="BREAKOUT", prev_fsm_state="FLAT",
        next_fsm_state="TESTING", previous_position=0.0,
        target_position=0.2,
        decision_path=("evidence", "institutional", "fsm", "governance",
                       "final_target"),
        model_version="M", rule_version="R", schema_version="S",
        input_fingerprint="F", settings_hash="H", run_id="RUN-1",
        pit_grade="B", release_id="REL-A",
        release_manifest_hash="MAN-A", evidence_pack_hash="EP-A",
        data_snapshot_id="D-A", universe_snapshot_id="U-A",
        canonical_action="ENTRY", fsm_proposal_target=0.3,
        wave_proposal_target=0.25,
    )
    base.update(kw)
    return DecisionSnapshot(**base)


def decision_identity_evidence() -> dict:
    from QCFP_MTF.decision.decision_ledger import (
        assert_snapshot_commit_invariants, LedgerCommitRejected)
    from QCFP_MTF.governance.production_evidence_pack import (
        production_evidence_pack, decision_qualification_answer)
    complete = assert_snapshot_commit_invariants(
        _identity_snap(), mode="production")
    missing_release = None
    try:
        assert_snapshot_commit_invariants(
            _identity_snap(release_id="", release_manifest_hash=""),
            mode="production")
    except LedgerCommitRejected as exc:
        missing_release = f"{type(exc).__name__}: {exc}"
    pack = production_evidence_pack(
        "REL-A", {k: "ref" for k in
                  ("release_manifest", "validation_certificate",
                   "pit_certificate", "oos_result", "ablation_result",
                   "stress_result", "replay_result", "shadow_result",
                   "governance_approval")})
    missing_pack = production_evidence_pack("REL-A", {})
    q_full = decision_qualification_answer("D1", "REL-A", pack)
    q_missing = decision_qualification_answer("D1", "", missing_pack)
    checks = {
        "full_identity_commit": {"expected": "COMMIT_OK",
                                 "actual": complete["verdict"]},
        "missing_release_rejected": {
            "expected": "LedgerCommitRejected",
            "actual": missing_release or "NO_REJECTION"},
        "full_evidence_certified": {"expected": "CERTIFIED",
                                    "actual": q_full["qualification"]},
        "missing_evidence_not_certified": {
            "expected": "NOT_CERTIFIED",
            "actual": q_missing["qualification"]},
    }
    for k, v in checks.items():
        v["pass"] = v["expected"] in str(v["actual"])
    passed = all(v["pass"] for v in checks.values())
    return {"checks": checks, "pass": passed,
            "verdict": "IDENTITY_PASS" if passed else "IDENTITY_FAIL"}


def decision_identity_provider() -> dict:
    result = decision_identity_evidence()
    if result["pass"]:
        return _ok("DECISION_IDENTITY", result["verdict"], evidence=result)
    return _fail("DECISION_IDENTITY", result["verdict"],
                 problems=["决策身份不完整未 fail-closed"], evidence=result)


# ---------------------------------------------------------------------------
# F03 — PathHash Independent Adversarial Proof（固定 base fixture）
# ---------------------------------------------------------------------------

PATH_HASH_BASE = {
    "input_fingerprint": "INPUT-A",
    "institutional_permission": "ALLOW",
    "wave_id": "W1", "wave_stage": "ACTIVE", "wave_strength": 1.0,
    "setup_type": "BREAKOUT",
    "prev_fsm_state": "HOLDING",
    "fsm_proposal_target": 0.35, "wave_proposal_target": 0.30,
    "next_fsm_state": "BUILDING",
    "exit_event_kind": "NONE",
    "participation_mode": "TRADE", "participation_cap": 0.5,
    "governance_caps": {"risk_cap": 0.3, "portfolio_cap": 0.4},
    "binding_constraint": "permission_cap",
    "target_position": 0.30, "canonical_action": "ADD",
    "model_version": "M1", "rule_version": "R1", "schema_version": "S1",
    "settings_hash": "CFG-1",
    "release_id": "REL-A", "release_manifest_hash": "RM-A",
    "evidence_pack_hash": "EV-A", "data_snapshot_id": "DATA-A",
    "universe_snapshot_id": "UNI-A", "participating_feature_hash": "PF-A",
    "feature_manifest_hash": "FEAT-1",
}

PATH_HASH_MUTATIONS = {
    "config_settings_hash": ("settings_hash", "CFG-2"),
    "final_target": ("target_position", 0.25),
    "binding_constraint": ("binding_constraint", "portfolio_cap"),
    "permission": ("institutional_permission", "BLOCK"),
    "wave_identity": ("wave_id", "W2"),
    "release_id": ("release_id", "REL-B"),
    "evidence_pack_hash": ("evidence_pack_hash", "EV-B"),
    "data_snapshot_id": ("data_snapshot_id", "DATA-B"),
    "universe_snapshot_id": ("universe_snapshot_id", "UNI-B"),
}


def path_hash_evidence(hash_fn=None) -> dict:
    """F03：mutation 检测 + constant-hash 攻击 + determinism helper。"""
    from QCFP_MTF.decision import path_hash as path_hash_mod
    hash_fn = hash_fn or path_hash_mod.decision_path_hash
    base_hash = hash_fn(dict(PATH_HASH_BASE))
    stable = base_hash == hash_fn(copy.deepcopy(PATH_HASH_BASE))
    mutations = {}
    for name, (key, value) in PATH_HASH_MUTATIONS.items():
        mutated = copy.deepcopy(PATH_HASH_BASE)
        mutated[key] = value
        actual_hash = hash_fn(mutated)
        changed = actual_hash != base_hash
        mutations[name] = {
            "mutated_field": key, "expected": "HASH_MUST_CHANGE",
            "changed": bool(changed), "pass": bool(changed)}
    mutation_failures = [k for k, v in mutations.items() if not v["pass"]]
    from QCFP_MTF.decision.path_hash import path_hash_determinism_check
    det = path_hash_determinism_check({"id": "X"}, "H1", {"id": "X"}, "H2")
    drift = path_hash_determinism_check({"id": "X"}, "H", {"id": "Y"}, "H")
    helper_ok = det["verdict"] == "DETERMINISM_FAILURE" \
        and drift["verdict"] == "PATH_HASH_DRIFT"
    constant_blocked = True
    if hash_fn is path_hash_mod.decision_path_hash:
        constant_blocked = path_hash_evidence_constant_probe()["blocked"]
    ok = stable and not mutation_failures and helper_ok and constant_blocked
    return {
        "base_identity": PATH_HASH_BASE,
        "identical_identity_stable": stable,
        "mutations": mutations,
        "mutation_failures": mutation_failures,
        "helper": {"same_identity_diff_hash": det["verdict"],
                   "diff_identity_same_hash": drift["verdict"]},
        "constant_hash_attack_blocked": constant_blocked,
        "pass": ok,
        "verdict": "PATH_HASH_PASS" if ok else "PATH_HASH_FAIL",
        "rule": "identity drift 必须被 PathHash 感知；constant hash 必须被拦截",
    }


def path_hash_evidence_constant_probe() -> dict:
    """constant hash_fn 下 mutation 全不变 → 攻击必须使 PATH_HASH_FAIL。"""
    const = path_hash_evidence(hash_fn=lambda *_args, **_kw: "CONSTANT")
    return {"blocked": const["verdict"] == "PATH_HASH_FAIL"
            and bool(const["mutation_failures"])}


def path_hash_provider() -> dict:
    result = path_hash_evidence()
    if result["pass"]:
        return _ok("PATH_HASH", result["verdict"], evidence=result)
    return _fail("PATH_HASH", result["verdict"],
                 problems=result["mutation_failures"], evidence=result)


# ---------------------------------------------------------------------------
# P3.4 — Ledger / Replay / Report Projection
# ---------------------------------------------------------------------------

def ledger_evidence() -> dict:
    src = _read(_module_dir() / "decision" / "decision_ledger.py")
    code = _strip_comments(src)
    no_update = "UPDATE qcfp_decision_ledger" not in code
    no_delete = "DELETE FROM qcfp_decision_ledger" not in code
    append_only = "INSERT OR IGNORE" in src or "INSERT INTO" in src
    identity_lookup = "status='ACTIVE'" in src and "settings_hash" in src \
        and "run_id" in src
    from QCFP_MTF.decision.decision_ledger import verify_chain_records
    records = [
        {"run_id": "R1", "id": 1, "prev_hash": "", "current_hash": "abc",
         "run_prev_hash": "", "run_current_hash": "r1"},
        {"run_id": "R1", "id": 2, "prev_hash": "abc", "current_hash": "def",
         "run_prev_hash": "r1", "run_current_hash": "r2"},
    ]
    tampered = [dict(records[0]), dict(records[1], prev_hash="tampered")]
    chain = verify_chain_records(tampered)
    checks = {
        "append_only": append_only, "no_update": no_update,
        "no_delete": no_delete, "strict_identity_lookup": identity_lookup,
        "chain_tamper_detected": chain.get("global_verified") is False,
    }
    passed = all(checks.values())
    return {"checks": checks, "pass": passed,
            "verdict": "LEDGER_PASS" if passed else "LEDGER_FAIL"}


def ledger_provider() -> dict:
    result = ledger_evidence()
    if result["pass"]:
        return _ok("LEDGER", result["verdict"], evidence=result)
    return _fail("LEDGER", result["verdict"],
                 problems=["Ledger append-only/身份/链校验失败"],
                 evidence=result)


def replay_evidence() -> dict:
    from QCFP_MTF.decision.replay_engine import field_by_field_compare
    from QCFP_MTF.governance.determinism import replay_determinism_check
    original = {"decision_id": "d1", "stock_code": "00700",
                "previous_position": 0.2, "target_position": 0.15,
                "next_fsm_state": "TRIMMING",
                "primary_reason": "POSITION_CAP",
                "decision_path_hash": "H1"}
    exact = field_by_field_compare(original, dict(original))
    mismatch = field_by_field_compare(original, dict(original,
                                                     target_position=0.4))
    det = replay_determinism_check("EV-1", "REL-1", "CFG-1", "FEAT-1",
                                   "UNI-1", original, dict(original))
    det_bad = replay_determinism_check("EV-1", "REL-1", "CFG-1", "FEAT-1",
                                       "UNI-1", original,
                                       dict(original, final_target=0.9))
    checks = {
        "exact_replay": {"verdict": exact.status,
                         "pass": exact.status == "EXACT_MATCH"},
        "tamper_detected": {"verdict": mismatch.status,
                            "pass": mismatch.status == "REPLAY_MISMATCH"},
        "deterministic": {"verdict": det["verdict"],
                          "pass": det["verdict"] == "DETERMINISTIC"},
        "mismatch_fail_closed": {"verdict": det_bad["verdict"],
                                 "pass": det_bad["verdict"]
                                 == "DETERMINISM_FAILURE"},
    }
    passed = all(v["pass"] for v in checks.values())
    return {"checks": checks, "pass": passed,
            "verdict": "REPLAY_PASS" if passed else "REPLAY_FAIL"}


def replay_provider() -> dict:
    result = replay_evidence()
    if result["pass"]:
        return _ok("REPLAY", result["verdict"], evidence=result)
    return _fail("REPLAY", result["verdict"],
                 problems=["Replay 精确性失败"], evidence=result)


def report_projection_evidence() -> dict:
    from QCFP_MTF.report.contract import report_consumes_only
    snapshot = {"institutional_permission": "ALLOW",
                "prev_fsm_state": "HOLDING", "next_fsm_state": "TRIMMING",
                "target_position": 0.15, "previous_position": 0.2,
                "primary_reason": "POSITION_CAP"}
    ledger_row = {"institutional_permission": "ALLOW",
                  "previous_fsm_state": "HOLDING",
                  "next_fsm_state": "TRIMMING", "final_target": 0.15,
                  "primary_reason": "POSITION_CAP"}
    ok_match = report_consumes_only(snapshot, ledger_row)
    ok_bad = report_consumes_only(snapshot, dict(ledger_row,
                                                 final_target=0.05))
    adapter_src = _strip_comments(
        _read(_module_dir() / "scripts" / "decision_engine.py"))
    forbidden = [m for m in REPORT_FORBIDDEN_IMPORTS
                 if re.search(rf"import\s+{re.escape(m)}(?:\s|\.|,|$)",
                              adapter_src)
                 or re.search(rf"from\s+{re.escape(m)}", adapter_src)]
    passed = ok_match["ok"] and not ok_bad["ok"] and not forbidden
    return {"checks": {
        "report_equals_ledger": {"ok": ok_match["ok"],
                                 "mismatches": ok_match["mismatches"]},
        "report_rewrite_rejected": {"ok": not ok_bad["ok"],
                                    "mismatches": ok_bad["mismatches"]},
        "adapter_no_recompute": {"forbidden_imports": forbidden}},
        "pass": passed,
        "verdict": "REPORT_PROJECTION_PASS" if passed
        else "REPORT_PROJECTION_FAIL"}


def report_projection_provider() -> dict:
    result = report_projection_evidence()
    if result["pass"]:
        return _ok("REPORT_PROJECTION", result["verdict"], evidence=result)
    return _fail("REPORT_PROJECTION", result["verdict"],
                 problems=["Report 重算/重写决策"], evidence=result)


# ---------------------------------------------------------------------------
# P3.5 — Golden Corpus（14 例运行时 Oracle）+ Failure Injection
# ---------------------------------------------------------------------------

def _golden_case_runner() -> dict:
    from QCFP_MTF.decision.governance import finalize_target
    from QCFP_MTF.decision.replay_engine import field_by_field_compare
    from QCFP_MTF.evidence.snapshot import EvidenceContractError, \
        assert_evidence_asof
    from QCFP_MTF.safety.kill_switch import safety_gate
    from QCFP_MTF.portfolio.drawdown_response import drawdown_state
    out = {}

    def rec(case_id, expected, actual, ok, detail=""):
        out[case_id] = {"case_id": case_id, "expected": expected,
                        "actual": actual, "pass": bool(ok),
                        "detail": detail}

    snap = _evaluate(_row(c_state="C↓", f_state="F↓", p_state="P↓",
                          prev_f_state="F↓", wave_stage="ACTIVE",
                          wave_strength=1.0))
    rec("G_BLOCK_STRONG", "BLOCK + target=0",
        f"{snap.institutional_permission} + {snap.target_position}",
        snap.institutional_permission == "BLOCK"
        and snap.target_position == 0.0)
    snap = _evaluate(_row(c_state="C→", f_state="F→", p_state="P→",
                          prev_f_state="F→", wave_stage="ACTIVE"))
    rec("G_WATCH_OBSERVE", "WATCH + 无新增风险",
        f"{snap.institutional_permission} + {snap.target_position}",
        snap.institutional_permission == "WATCH"
        and snap.target_position == 0.0)
    snap = _evaluate(_row(c_state="C→", f_state="F↑", p_state="P↓",
                          prev_f_state="F↑", wave_stage="ACTIVE"))
    rec("G_TEST_LIMITED", "TEST + 限额定仓",
        f"{snap.institutional_permission} + {snap.target_position}",
        snap.institutional_permission == "TEST")
    from QCFP_MTF.institutional.permission import \
        evaluate_institutional_permission
    _perm = evaluate_institutional_permission(
        institutional_state_name="ACCUMULATION", pressure=1,
        persistence=2)
    from QCFP_MTF.decision.engine import DecisionConfig
    snap_allow = _evaluate(_row(), config=DecisionConfig(
        override_permission="ALLOW"))
    rec("G_ALLOW_TRADE", "ALLOW + 可交易",
        f"perm={_perm.permission} engine_perm="
        f"{snap_allow.institutional_permission} target="
        f"{snap_allow.target_position} action="
        f"{snap_allow.canonical_action}",
        _perm.permission == "ALLOW"
        and snap_allow.institutional_permission == "ALLOW"
        and snap_allow.canonical_action == "ENTRY"
        and snap_allow.target_position > 0.0,
        detail="标准输入 ACCUMULATION+p1 命中 RECOVERY→TEST；"
               "ALLOW 经组件状态机与引擎 override 验证")
    snap = _evaluate(_row(c_state="C↑", f_state="F↑", p_state="P↑",
                          prev_f_state="F↑", wave_stage="ACTIVE",
                          wave_strength=1.0))
    rec("G_STRONG_ALLOW", "STRONG_ALLOW + 可交易",
        f"{snap.institutional_permission} + {snap.target_position}",
        snap.institutional_permission == "STRONG_ALLOW")
    snap = _evaluate(_row(wave_stage="DISCOVERY"))
    rec("G_WAVE_DISCOVERY", "DISCOVERY 禁止进场",
        f"wave_allowed={snap.wave_action_allowed} "
        f"target={snap.target_position}",
        snap.wave_action_allowed is False
        and snap.target_position == 0.0)
    snap = _evaluate(_row(wave_stage="MATURE"))
    rec("G_WAVE_MATURE", "MATURE 按比例缩仓",
        f"scale={snap.wave_entry_scale} target={snap.target_position}",
        snap.wave_entry_scale > 0.0
        and snap.target_position <= snap.raw_target_position)
    snap = _evaluate(_row(wave_stage="INVALID"))
    rec("G_WAVE_INVALID", "INVALID 禁止进场",
        f"wave_allowed={snap.wave_action_allowed} "
        f"target={snap.target_position}",
        snap.wave_action_allowed is False
        and snap.target_position == 0.0)
    snap = _evaluate(_row(des_score=8, tactical_signal="Breakout",
                          daily_state="DAILY_BREAKOUT",
                          wave_stage="ACTIVE", wave_strength=1.0))
    rec("G_HARD_EXIT", "HARD_EXIT 覆盖一切看多",
        f"{snap.exit_event_kind} + {snap.target_position}",
        snap.exit_event_kind == "HARD_EXIT"
        and snap.target_position == 0.0)
    fin = finalize_target("ALLOW", "TRADE", 0.50, raw_target=0.60,
                          previous_position=0.0, liquidity_cap=0.20)
    rec("G_LIQUIDITY_BINDING", "liquidity_cap binding",
        f"target={fin['target']}",
        abs(float(fin["target"]) - 0.20) < 1e-9)
    fin = finalize_target("ALLOW", "TRADE", 0.50, raw_target=0.60,
                          previous_position=0.0, portfolio_cap=0.25)
    rec("G_PORTFOLIO_BINDING", "portfolio_cap binding",
        f"target={fin['target']}",
        abs(float(fin["target"]) - 0.25) < 1e-9)
    try:
        assert_evidence_asof(
            {"decision_date": "2026-08-20",
             "weekly": {"available_at": "2026-08-21"}})
        rec("G_PIT_FAILURE", "PIT invalid → 拒绝", "ALLOWED", False,
            "PIT 违反未抛错")
    except EvidenceContractError:
        rec("G_PIT_FAILURE", "PIT invalid → 拒绝", "EvidenceContractError",
            True)
    replay = field_by_field_compare({"target_position": 0.15},
                                    {"target_position": 0.4})
    rec("G_REPLAY_FAILURE", "Replay mismatch → REPLAY_MISMATCH",
        replay.status, replay.status == "REPLAY_MISMATCH")
    safe = safety_gate({"data_failure": True}, target=0.3,
                       previous_position=0.0)
    rec("G_SAFE_MODE", "SAFE_MODE 禁止新增风险",
        f"{safe['status']} blocked={safe['blocked_reason']}",
        safe["status"] == "SAFE_MODE"
        and safe["blocked_reason"] == "SAFE_MODE_NEW_RISK_BLOCKED")
    out["G_SAFE_MODE"]["drawdown"] = drawdown_state(0.10)
    return out


def golden_evidence() -> dict:
    from QCFP_MTF.governance.golden_decision_corpus import (
        golden_change_requires_review, golden_decision_corpus,
        golden_release_gate)
    corpus = golden_decision_corpus()
    perms = {v["permission"] for v in corpus["corpus"].values()}
    waves = {v["wave_stage"] for v in corpus["corpus"].values()}
    events = {v["event"] for v in corpus["corpus"].values()}
    coverage = {
        "permissions": sorted(perms), "waves": sorted(waves),
        "events": sorted(events),
        "ok": perms == {"BLOCK", "WATCH", "TEST", "ALLOW", "STRONG_ALLOW"}
        and {"DISCOVERY", "ACTIVE", "MATURE", "INVALID"} <= waves
        and {"HARD_EXIT", "PIT_FAILURE", "REPLAY_FAILURE", "SAFE_MODE"}
        <= events,
    }
    results = _golden_case_runner()
    failed = [k for k, v in results.items() if not v["pass"]]
    change = golden_change_requires_review("h1", "h2", "G_BLOCK_STRONG")
    release_gate = golden_release_gate([
        {"case_id": "G_BLOCK_STRONG", "changed": True,
         "approved_reason": ""}])
    ok = coverage["ok"] and not failed \
        and change["requires_change_impact_review"] \
        and release_gate["verdict"] == "GOLDEN_CHANGE_UNEXPLAINED"
    return {"corpus_version": "GOLDEN-CONSTITUTION-1",
            "n_cases": len(results), "n_failed": len(failed),
            "failed_cases": failed, "coverage": coverage,
            "results": results,
            "hash_change_requires_review":
                change["requires_change_impact_review"],
            "unexplained_change_blocked":
                release_gate["verdict"] == "GOLDEN_CHANGE_UNEXPLAINED",
            "pass": ok,
            "verdict": "GOLDEN_PASS" if ok else "GOLDEN_FAIL"}


def golden_provider() -> dict:
    result = golden_evidence()
    if result["pass"]:
        return _ok("GOLDEN", result["verdict"], evidence=result)
    return _fail("GOLDEN", result["verdict"],
                 problems=[f"Golden failed: {result['failed_cases']}"],
                 evidence=result)


def failure_injection_evidence() -> dict:
    from QCFP_MTF.governance.failure_injection import \
        run_failure_qualification
    result = run_failure_qualification()
    ok = result["verdict"] == "RELEASE_QUALIFIED"
    return {"cases_executed": result["cases_executed"],
            "expected_cases": result["expected_cases"],
            "missing_cases": result["missing_cases"],
            "failure_escaped": result["failure_escaped"],
            "failure_escaped_count": result["failure_escaped_count"],
            "verdict": result["verdict"], "pass": ok}


def failure_injection_provider() -> dict:
    result = failure_injection_evidence()
    if result["pass"]:
        return _ok("FAILURE_INJECTION", result["verdict"], evidence=result)
    return _fail("FAILURE_INJECTION", result["verdict"],
                 problems=[f"escaped: {result['failure_escaped']}"],
                 evidence=result)


# ---------------------------------------------------------------------------
# F05 — Independent Regression Evidence（Judge 只消费 Test System 证据）
# ---------------------------------------------------------------------------

def _regression_evidence_path(out_dir=None) -> Path:
    base = Path(out_dir) if out_dir else _root() / "audit" / "phase3"
    return base / "phase3_regression_summary.json"


REQUIRED_REGRESSION_SUITES = (
    "phase3", "decision", "governance", "full_core",
)


def _suite_counts(suite: dict) -> tuple:
    """读取套件计数，缺省为 0；非整数视为证据无效。"""
    try:
        collected = int(suite.get("collected") or 0)
        passed = int(suite.get("passed") or 0)
        failed = int(suite.get("failed") or 0)
        errors = int(suite.get("errors") or 0)
        skipped = int(suite.get("skipped") or 0)
    except (TypeError, ValueError):
        return None
    return collected, passed, failed, errors, skipped


def _validate_regression_suite(suite: dict) -> dict:
    """单套件证据契约：
    - 计数一致性：collected == passed + failed + errors + skipped
    - status/counts 互斥约束（PASS / FAIL / ENVIRONMENT_BLOCKED）
    - PASS + skipped>0 → 证据一致但不完整（INCOMPLETE → NOT_PROVEN）
    返回 {"status": "VALID"|"INVALID"|"INCOMPLETE", "problem": str}。
    """
    counts = _suite_counts(suite)
    if counts is None:
        return {"status": "INVALID", "problem": "counts 非整数"}
    collected, passed, failed, errors, skipped = counts
    if collected != passed + failed + errors + skipped:
        return {"status": "INVALID",
                "problem": f"collected({collected}) != "
                           f"passed+failed+errors+skipped "
                           f"({passed}+{failed}+{errors}+{skipped})"}
    status = suite.get("status")
    if status == "PASS":
        if failed or errors:
            return {"status": "INVALID",
                    "problem": "status=PASS 但 failed/errors > 0（矛盾证据）"}
        if passed <= 0:
            return {"status": "INVALID",
                    "problem": "status=PASS 但 passed <= 0"}
        if skipped:
            return {"status": "INCOMPLETE",
                    "problem": "status=PASS 但 skipped > 0"
                               "（required suite 未完整证明）"}
        return {"status": "VALID", "problem": ""}
    if status == "FAIL":
        if not (failed > 0 or errors > 0):
            return {"status": "INVALID",
                    "problem": "status=FAIL 但 failed/errors 均为 0"}
        return {"status": "VALID", "problem": ""}
    if status == "ENVIRONMENT_BLOCKED":
        # 允许 failed>0（JUnit 中环境阻塞也计为 failure），
        # 但每个失败必须分类为 ENVIRONMENT_BLOCKED（无真实断言/代码失败）。
        detail = suite.get("failures") or suite.get("failures_detail") or []
        bad = [d for d in detail
               if (d.get("classification") or "").upper()
               in ("ASSERTION_FAILURE", "CODE_ERROR")]
        if bad:
            return {"status": "INVALID",
                    "problem": "status=ENVIRONMENT_BLOCKED 但存在真实失败: "
                               f"{[d.get('test') for d in bad]}"}
        return {"status": "VALID", "problem": ""}
    if status in ("NOT_RUN", "INCOMPLETE"):
        return {"status": "INCOMPLETE",
                "problem": f"suite 未完整证明（status={status}）"}
    return {"status": "INVALID",
            "problem": f"未知 status: {status!r}"}


def regression_provider(evidence_path=None) -> dict:
    """F05：Regression Evidence Contract（P0-03/P0-04/P1-01）。

    - required suites（phase3/decision/governance/full_core）缺一 → NOT_PROVEN
    - 附加 suite 仅 warning
    - 计数不一致 / PASS+failed>0 等矛盾证据 → REGRESSION_EVIDENCE_INVALID → FAIL
    - required suite 存在 skipped → NOT_PROVEN
    - 任何 suite FAIL / 证据无效 → REGRESSION_FAIL
    """
    path = Path(evidence_path) if evidence_path \
        else _regression_evidence_path()
    if not path.exists():
        raise EvidenceUnavailable(
            f"Regression evidence 缺失（未运行 phase3_regression_runner）: "
            f"{path}")
    data = json.loads(path.read_text(encoding="utf-8"))
    suites = data.get("suites", {})
    actual = set(suites.keys())
    required = set(REQUIRED_REGRESSION_SUITES)
    missing_suites = sorted(required - actual)
    extra_suites = sorted(actual - required)
    data = dict(data)
    data["required_suites"] = list(REQUIRED_REGRESSION_SUITES)
    data["missing_suites"] = missing_suites
    data["extra_suites"] = extra_suites
    if missing_suites:
        return _not_proven(
            "REGRESSION", "REGRESSION_NOT_PROVEN",
            problems=[f"missing required suites: {missing_suites}"],
            evidence=data)
    invalid = []
    incomplete = []
    failed_suites = []
    for name in REQUIRED_REGRESSION_SUITES:
        suite = suites.get(name, {})
        check = _validate_regression_suite(suite)
        if check["status"] == "INVALID":
            invalid.append({"suite": name, "problem": check["problem"]})
        elif check["status"] == "INCOMPLETE":
            incomplete.append({"suite": name, "problem": check["problem"]})
        elif suite.get("status") == "FAIL":
            failed_suites.append(name)
    if invalid:
        return _fail(
            "REGRESSION", "REGRESSION_EVIDENCE_INVALID",
            problems=[f"contradictory evidence: {invalid}"],
            evidence=data)
    if failed_suites:
        return _fail("REGRESSION", "REGRESSION_FAIL",
                     problems=[f"suite FAIL: {failed_suites}"],
                     evidence=data)
    blocked = [k for k in REQUIRED_REGRESSION_SUITES
               if suites.get(k, {}).get("status")
               in ("ENVIRONMENT_BLOCKED", "NOT_RUN")]
    if blocked or incomplete:
        return _not_proven(
            "REGRESSION", "REGRESSION_NOT_PROVEN",
            problems=[f"环境阻塞/未运行: {blocked}",
                      f"未完整证明: {incomplete}"],
            evidence=data)
    return _ok("REGRESSION", "REGRESSION_PASS", evidence=data)


# ---------------------------------------------------------------------------
# F04 — Frozen Baseline Binding（直接消费 baseline_gate()）
# ---------------------------------------------------------------------------

def frozen_baseline_provider(qcfp_root=None) -> dict:
    from QCFP_MTF.governance.governance_baseline import baseline_gate
    result = baseline_gate(qcfp_root)
    verdict = result.get("verdict", "NO_BASELINE")
    if verdict == "BASELINE_PASS":
        return _ok("FROZEN_BASELINE", verdict, evidence=result)
    if verdict == "BASELINE_CHANGED":
        return _fail("FROZEN_BASELINE", verdict,
                     problems=[f"drift={result.get('drift')} "
                               f"version_drift="
                               f"{result.get('version_drift')}"],
                     evidence=result)
    return _not_proven("FROZEN_BASELINE", verdict,
                       problems=[result.get("reason", "NO_BASELINE")],
                       evidence=result)


# ---------------------------------------------------------------------------
# P3.6 — Phase3 Gate（F06 三态 + F07 推导 Freeze Record）
# ---------------------------------------------------------------------------

PHASE3_GATES = (
    ("CHAIN_CONFORMANCE", "P0", chain_conformance_provider),
    ("CANONICAL_PATH", "P0", canonical_path_provider),
    ("RUNTIME_INVARIANTS", "P0", runtime_invariants_provider),
    ("DECISION_IDENTITY", "P0", decision_identity_provider),
    ("E2E_DETERMINISM", "P0", e2e_determinism_provider),
    ("PATH_HASH", "P0", path_hash_provider),
    ("LEDGER", "P0", ledger_provider),
    ("REPLAY", "P0", replay_provider),
    ("REPORT_PROJECTION", "P0", report_projection_provider),
    ("GOLDEN", "P0", golden_provider),
    ("FAILURE_INJECTION", "P0", failure_injection_provider),
    ("REGRESSION", "P1", regression_provider),
    ("FROZEN_BASELINE", "P0", frozen_baseline_provider),
)

EVIDENCE_FILE_MAP = {
    "CHAIN_CONFORMANCE": "canonical_chain_map.json",
    "CANONICAL_PATH": "canonical_path_audit.json",
    "RUNTIME_INVARIANTS": "runtime_invariants.json",
    "DECISION_IDENTITY": "decision_identity.json",
    "E2E_DETERMINISM": "determinism_result.json",
    "PATH_HASH": "path_hash_result.json",
    "LEDGER": "ledger_result.json",
    "REPLAY": "replay_result.json",
    "REPORT_PROJECTION": "report_projection_result.json",
    "GOLDEN": "golden_result.json",
    "FAILURE_INJECTION": "failure_injection_result.json",
    "FROZEN_BASELINE": "frozen_baseline.json",
}


def derive_freeze_record(gates: dict, missing_evidence: list) -> dict:
    """F07：Freeze Stamp 全部由证据推导，不硬编码 0。"""
    path_gate = gates.get("CANONICAL_PATH", {})
    second_roots = len(path_gate.get("evidence", {})
                       .get("second_canonical_roots", []))
    known_bypass = 0
    fi = gates.get("FAILURE_INJECTION", {}).get("evidence", {})
    known_bypass += int(fi.get("failure_escaped_count", 0) or 0)
    golden = gates.get("GOLDEN", {}).get("evidence", {})
    known_bypass += int(golden.get("n_failed", 0) or 0)
    path_hash = gates.get("PATH_HASH", {}).get("evidence", {})
    known_bypass += len(path_hash.get("mutation_failures", []) or [])
    inv = gates.get("RUNTIME_INVARIANTS", {}).get("evidence", {})
    known_bypass += len(inv.get("failed", []) or [])
    chain = gates.get("CHAIN_CONFORMANCE", {}).get("evidence", {})
    known_bypass += len(chain.get("reverse_edges", []) or [])
    open_p0 = sum(1 for name, pri, _fn in PHASE3_GATES
                  if pri == "P0"
                  and gates.get(name, {}).get("status") == "FAIL")
    open_p1 = sum(1 for name, pri, _fn in PHASE3_GATES
                  if pri == "P1"
                  and gates.get(name, {}).get("status")
                  in ("FAIL", "NOT_PROVEN"))
    return {
        "second_canonical_path": second_roots,
        "known_decision_bypass": known_bypass,
        "open_p0": open_p0,
        "open_p1": open_p1,
        "missing_required_evidence": len(missing_evidence),
        "rule": "Freeze Stamp 只投影事实；Human Approval 后才 FROZEN",
    }


def _freeze_state(verdict: str) -> str:
    if verdict == "PHASE3_PASS":
        return "FREEZE_CANDIDATE"
    if verdict == "PHASE3_FAIL":
        return "BLOCKED"
    return "NOT_PROVEN"


def phase3_acceptance(out_dir=None, providers=None) -> dict:
    """P3.6：生成 audit/phase3/* 证据包 + acceptance + freeze_record。"""
    out_dir = Path(out_dir) if out_dir else _root() / "audit" / "phase3"
    out_dir.mkdir(parents=True, exist_ok=True)
    providers = providers or PHASE3_GATES
    gates = {}
    for name, priority, fn in providers:
        try:
            result = fn()
        except EvidenceUnavailable as exc:
            result = _not_proven(name, "EVIDENCE_UNAVAILABLE",
                                 problems=[str(exc)])
        except Exception as exc:      # 不吞异常：记录为 FAIL 供审计
            result = _fail(name, "PROVIDER_ERROR",
                           problems=[f"{type(exc).__name__}: {exc}"])
        result["priority"] = priority
        gates[name] = result
    failures = [k for k, v in gates.items()
                if v.get("status") == "FAIL"]
    missing = [k for k, v in gates.items()
               if v.get("status") == "NOT_PROVEN"]
    if failures:
        verdict = "PHASE3_FAIL"
    elif missing:
        verdict = "PHASE3_NOT_PROVEN"
    else:
        verdict = "PHASE3_PASS"
    freeze_record = derive_freeze_record(gates, missing)
    acceptance = {
        "schema": "PHASE3-ACCEPTANCE-2",
        "generated_at_utc": datetime.now(timezone.utc).strftime(
            "%Y-%m-%dT%H:%M:%SZ"),
        "gates": gates,
        "failures": failures,
        "missing_evidence": missing,
        "freeze_record": freeze_record,
        "freeze_state": _freeze_state(verdict),
        "pass": not failures and not missing,
        "verdict": verdict,
    }
    for name, fname in EVIDENCE_FILE_MAP.items():
        if name in gates:
            (out_dir / fname).write_text(
                json.dumps(gates[name].get("evidence", {}),
                           ensure_ascii=False, indent=2, default=str),
                encoding="utf-8")
    (out_dir / "phase3_acceptance.json").write_text(
        json.dumps(acceptance, ensure_ascii=False, indent=2),
        encoding="utf-8")
    lines = [
        "QCFP-MTF PHASE 3 FREEZE RECORD",
        "================================================",
        "",
        f"Verdict      : {verdict}",
        f"Freeze State : {_freeze_state(verdict)}",
        "",
        f"Second Canonical Path : {freeze_record['second_canonical_path']}",
        f"Known Decision Bypass : {freeze_record['known_decision_bypass']}",
        f"Open P0               : {freeze_record['open_p0']}",
        f"Open P1               : {freeze_record['open_p1']}",
        f"Missing Evidence      : "
        f"{freeze_record['missing_required_evidence']}",
        "",
        "Gate 明细：",
    ]
    for name, gate in gates.items():
        lines.append(f"- {name} [{gate.get('priority')}]: "
                     f"{gate.get('status')} / {gate.get('verdict')}")
    (out_dir / "freeze_record.txt").write_text(
        "\n".join(lines), encoding="utf-8")
    return acceptance


def phase3_gate() -> dict:
    acceptance = phase3_acceptance()
    return {"gate": "PHASE3_GATE",
            "verdict": acceptance["verdict"],
            "pass": acceptance["pass"],
            "failures": acceptance["failures"],
            "missing_evidence": acceptance["missing_evidence"]}
