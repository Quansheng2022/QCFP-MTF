# coding: utf-8
"""Dead Authority Removal（QCFP-MTF 2.8：40 号代码退役执行）

模块 RETIRED 后不能只是 FEATURE_SET 标记 retired，而应：
    - 删除 Production import
    - 删除默认配置
    - 删除运行入口
    - 删除 Report 展示
    - 只保留历史 Replay 所需 frozen artifact

退役必须减少系统可执行路径数量，否则复杂度没有真正下降。
"""


def dead_authority_audit(module_name, retired=True,
                         production_imports=None, default_config=None,
                         entry_points=None, report_display=None,
                         frozen_artifact=None) -> dict:
    """退役审计：确认 RETIRED 模块不再存在于生产可执行路径。"""
    violations = []
    if not retired:
        violations.append("NOT_RETIRED")
    for imp in (production_imports or []):
        if imp:
            violations.append(f"PRODUCTION_IMPORT:{imp}")
    for cfg in (default_config or []):
        if cfg:
            violations.append(f"DEFAULT_CONFIG:{cfg}")
    for ep in (entry_points or []):
        if ep:
            violations.append(f"ENTRY_POINT:{ep}")
    for disp in (report_display or []):
        if disp:
            violations.append(f"REPORT_DISPLAY:{disp}")
    return {
        "module": module_name,
        "retired": bool(retired),
        "violations": violations,
        "clean_retirement": not violations,
        "frozen_artifact_preserved": bool(frozen_artifact),
        "note": "退役必须删除生产 import/配置/入口/展示，"
                "只保留历史 Replay 所需 frozen artifact",
    }


def dead_authority_dependency_check(module, production_dependencies) -> dict:
    """新 40 号：RETIRED 模块必须在 Production dependency graph 中
    真正消失（而不是只在旁边加一条新路径）。"""
    import re as _re
    def _tokens(name):
        s = _re.sub(r"(?<=[a-z])(?=[A-Z])", "_", str(name))
        return {t for t in _re.split(r"[\W_]+", s.lower()) if t}
    deps = list(production_dependencies or [])
    tokens = _tokens(module)
    still = [d for d in deps
             if tokens and tokens <= _tokens(d)]
    return {
        "module": module,
        "production_dependencies": deps,
        "still_in_graph": still,
        "verdict": "REMOVED_FROM_GRAPH" if not still
        else "STILL_IN_GRAPH",
        "removed": not still,
        "rule": "RETIRED 后 Production dependency graph 必须真正消失，"
                "只保留 historical replay artifact / migration support",
    }


def executable_path_reduction(removed_imports, removed_entries,
                              total_paths_before) -> dict:
    """可执行路径减少验证：退役必须减少路径数量。"""
    removed = len(removed_imports) + len(removed_entries)
    after = max(0, total_paths_before - removed)
    return {"paths_before": total_paths_before,
            "paths_removed": removed,
            "paths_after": after,
            "complexity_reduced": removed > 0}
