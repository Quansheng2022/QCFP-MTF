# coding: utf-8
"""Simplification Release Gate（QCFP-MTF 2.8：50 号简化发布门）

收尾/证明/减法：任何"简化发布"必须同时证明三件事，缺一不可：
    1) 复杂度真实下降：执行路径↓ / 生产模块↓ / 决策关键 LOC↓ / 重复规则↓
    2) 覆盖不下降：Canonical 覆盖 / Replay 覆盖 / 不变量覆盖
    3) 绩效不显著变差：OOS / Ablation / Replay 三证（只允许减法，
       不允许在简化发布中夹带新 Alpha）

判定：
    APPROVED  复杂度下降 + 覆盖不降 + 三证通过
    REVIEW    复杂度下降但三证有疑问（需要 Research Review，禁止自动放行）
    REJECTED  复杂度没有真实下降（不是简化发布）或覆盖下降

Release 后的删除必须减少可执行路径数量，否则不算简化。
"""


METRIC_KEYS = (
    "execution_paths",          # 可执行路径数量（↓ 才算减法）
    "production_modules",       # Production 模块数量（↓ 或持平）
    "decision_loc",             # 决策关键代码行数（↓ 或持平）
    "duplicate_rules",          # 重复规则数量（↓ 或持平）
    "canonical_coverage",       # Canonical 覆盖率（不得下降）
    "replay_coverage",          # Replay 覆盖率（不得下降）
    "invariant_coverage",       # 不变量覆盖率（不得下降）
)


def simplification_metrics(before: dict, after: dict) -> dict:
    """对比简化前后的复杂度/覆盖指标，输出绝对值与相对变化。"""
    deltas = {}
    for key in METRIC_KEYS:
        b = before.get(key)
        a = after.get(key)
        if b is None or a is None:
            deltas[key] = None
        elif float(b) == 0:
            deltas[key] = None
        else:
            deltas[key] = round((float(a) - float(b)) / float(b), 4)
    complexity_down = all(
        deltas[k] is not None and deltas[k] < 0
        for k in ("execution_paths", "production_modules",
                  "decision_loc", "duplicate_rules"))
    coverage_not_down = all(
        deltas[k] is not None and deltas[k] >= 0
        for k in ("canonical_coverage", "replay_coverage",
                  "invariant_coverage"))
    return {
        "before": {k: before.get(k) for k in METRIC_KEYS},
        "after": {k: after.get(k) for k in METRIC_KEYS},
        "deltas": deltas,
        "complexity_down": complexity_down,
        "coverage_not_down": coverage_not_down,
        "summary": {
            "execution_paths_delta": deltas["execution_paths"],
            "production_modules_delta": deltas["production_modules"],
            "decision_loc_delta": deltas["decision_loc"],
            "duplicate_rules_delta": deltas["duplicate_rules"],
            "canonical_coverage_delta": deltas["canonical_coverage"],
            "replay_coverage_delta": deltas["replay_coverage"],
            "invariant_coverage_delta": deltas["invariant_coverage"],
        },
    }


def simplification_release_check(metrics: dict,
                                 validation: dict) -> dict:
    """简化发布门：复杂度 + 覆盖 + OOS/Ablation/Replay 三证。"""
    oos_before = float(validation.get("oos_sharpe_before") or 0.0)
    oos_after = float(validation.get("oos_sharpe_after") or 0.0)
    ablation_delta = float(validation.get("ablation_delta") or 0.0)
    replay_match = float(validation.get("replay_match_ratio") or 0.0)
    # 只允许减法：OOS 夏普不得显著变差（默认容忍 -0.10）
    oos_tolerance = float(validation.get("oos_tolerance") or 0.10)
    oos_ok = oos_after >= oos_before - oos_tolerance
    # 简化不得让被保留模块的边际效用显著变负
    ablation_ok = ablation_delta >= -0.02
    # Replay 一致性必须保持（≥95% 决策逐字段一致）
    replay_ok = replay_match >= 0.95

    checks = {
        "complexity_down": metrics.get("complexity_down", False),
        "coverage_not_down": metrics.get("coverage_not_down", False),
        "oos_not_worse": oos_ok,
        "ablation_not_negative": ablation_ok,
        "replay_preserved": replay_ok,
    }
    failures = [name for name, ok in checks.items() if not ok]
    if failures:
        return {
            "verdict": "REVIEW",
            "checks": checks,
            "failures": failures,
            "reason": "简化证据不足，需 Research Review 后才可进入 "
                      "Candidate/Shadow",
            "auto_approve_forbidden": True,
        }
    return {
        "verdict": "APPROVED",
        "checks": checks,
        "failures": [],
        "reason": "复杂度下降 + 覆盖不降 + OOS/Ablation/Replay 三证通过",
        "auto_approve_forbidden": False,
    }


def release_verdict(check: dict) -> str:
    """兼容判定：无 metrics 数据的空发布 → REJECTED（不空转）。"""
    if not check:
        return "REJECTED"
    if check.get("verdict") == "APPROVED":
        return "APPROVED"
    failures = check.get("failures") or []
    if "complexity_down" in failures or "coverage_not_down" in failures:
        return "REJECTED"
    return "REVIEW"


def simplification_ledger_entry(release_id, before, after,
                                validation, note="") -> dict:
    """简化发布留痕：一次减法必须可审计、可回放。"""
    metrics = simplification_metrics(before, after)
    check = simplification_release_check(metrics, validation)
    return {
        "release_id": release_id,
        "metrics": metrics["summary"],
        "validation": {
            "oos_sharpe_before": validation.get("oos_sharpe_before"),
            "oos_sharpe_after": validation.get("oos_sharpe_after"),
            "ablation_delta": validation.get("ablation_delta"),
            "replay_match_ratio": validation.get("replay_match_ratio"),
        },
        "verdict": release_verdict(check),
        "note": note,
        "ledger_immutable": True,
    }
