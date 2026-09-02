# coding: utf-8
"""Benchmark Ladder（QCFP-MTF 2.8：52 号最小基准阶梯）

防止复杂系统只和自己比较。永久保留极简基线并固定比较结构：
    Simple Baseline（Cash / Buy-and-Hold / Simple Trend）
        → Core Model（Wave-only）
        → Governed Model（Permission + Wave）
        → Full Production（Full Canonical）

验收标准：任何新增复杂度都必须证明相对更简单层级的增量，
而不是只证明"它自身赚钱"。
"""


LADDER_RUNGS = (
    ("SIMPLE_BASELINE", ("Cash", "BuyAndHold", "SimpleTrend")),
    ("CORE_MODEL", ("WaveOnly",)),
    ("GOVERNED_MODEL", ("PermissionWave",)),
    ("FULL_PRODUCTION", ("FullCanonical",)),
)

# 新 28 号：固定 B0–B6 永久基线（防复杂系统只和自己比较）
BENCHMARK_BASELINES = (
    ("B0_CASH", "Cash"),
    ("B1_BUY_HOLD", "Buy & Hold"),
    ("B2_SIMPLE_TREND", "Simple Trend"),
    ("B3_WAVE_ONLY", "Wave Only"),
    ("B4_PERMISSION_WAVE", "Permission + Wave"),
    ("B5_PERMISSION_WAVE_FSM_RISK", "Permission + Wave + FSM/Risk"),
    ("B6_FULL_CANONICAL", "Full Canonical"),
)


def _rung_value(m: dict) -> dict:
    return {
        "sharpe": round(float(m.get("sharpe") or 0.0), 4),
        "mdd": round(float(m.get("mdd") or 0.0), 4),
        "ret": round(float(m.get("ret") or m.get("return") or 0.0), 4),
    }


def benchmark_ladder(rung_metrics: dict,
                     min_mdd_delta: float = 0.02) -> dict:
    """rung_metrics：{rung: metrics}；每级必须证明相对上一级的增量。

    缺档即视为阶梯不完整（增量链条断裂 → 不得宣称已证明）。
    """
    steps, prev = [], None
    for rung, _strategies in LADDER_RUNGS:
        m = rung_metrics.get(rung)
        if not m:
            steps.append({"rung": rung, "available": False})
            prev = None
            continue
        val = _rung_value(m)
        step = {"rung": rung, "available": True, "metrics": val}
        if prev is not None:
            sharpe_delta = round(val["sharpe"] - prev["sharpe"], 4)
            mdd_delta = round(val["mdd"] - prev["mdd"], 4)
            mdd_improved = mdd_delta >= min_mdd_delta
            step["increment"] = {"sharpe_delta": sharpe_delta,
                                 "mdd_delta": mdd_delta,
                                 "mdd_improved": mdd_improved}
            step["incremental_value_proven"] = (
                sharpe_delta > 0.05 or mdd_improved)
        else:
            step["increment"] = None
            step["incremental_value_proven"] = True
        steps.append(step)
        prev = val
    available = [s for s in steps if s.get("available")]
    all_proven = len(available) == len(LADDER_RUNGS) and all(
        s.get("incremental_value_proven", False) for s in available)
    return {
        "ladder": steps,
        "all_increments_proven": all_proven,
        "rule": "新增复杂度必须证明相对更简单层级的增量",
    }


def benchmark_simple_vs_full(candidate: dict, simple: dict,
                             min_sharpe_delta: float = 0.05,
                             min_mdd_delta: float = 0.02) -> dict:
    """Full Production vs Simple Baseline 的净增量（防自我比较）。"""
    c, s = _rung_value(candidate), _rung_value(simple)
    sharpe_delta = round(c["sharpe"] - s["sharpe"], 4)
    mdd_delta = round(c["mdd"] - s["mdd"], 4)
    mdd_improved = mdd_delta >= min_mdd_delta
    incremental = sharpe_delta > min_sharpe_delta or mdd_improved
    return {
        "candidate": c,
        "simple_baseline": s,
        "sharpe_delta": sharpe_delta,
        "mdd_delta": mdd_delta,
        "mdd_improved": mdd_improved,
        "incremental_value": incremental,
        "conclusion": "有净增量" if incremental else "无净增量",
    }


def benchmark_ladder_baselines(metrics: dict) -> dict:
    """新 28 号：B0–B6 固定基线对照。"""
    rows = {}
    for key, label in BENCHMARK_BASELINES:
        rows[key] = {"label": label, "metrics": metrics.get(key)}
    return {"baselines": rows,
            "rule": "系统最危险的对手不是另一个复杂模型，"
                    "而是一个简单模型"}


def core_vs_full(core_metrics: dict, full_metrics: dict,
                 core_modules: int = 9,
                 full_modules: int = 25) -> dict:
    """新 28 号：Core vs Full——复杂增量必须证明稳定增量，否则 Core 赢。"""
    core_s = float(core_metrics.get("sharpe") or 0.0)
    full_s = float(full_metrics.get("sharpe") or 0.0)
    full_complexity = full_modules >= core_modules * 2
    incremental = full_s >= core_s + 0.05
    if not incremental and full_complexity:
        verdict = "CORE_PREFERRED"
        reason = "Full 复杂度翻倍但 Sharpe 无稳定增量 → Core 更优"
    elif incremental:
        verdict = "FULL_JUSTIFIED"
        reason = "Full 相对 Core 有稳定增量"
    else:
        verdict = "CORE_PREFERRED"
        reason = "两者接近 → 默认保留更简单的 Core"
    return {"core_sharpe": round(core_s, 4),
            "full_sharpe": round(full_s, 4),
            "sharpe_delta": round(full_s - core_s, 4),
            "core_modules": core_modules,
            "full_modules": full_modules,
            "full_complexity_double": full_complexity,
            "verdict": verdict,
            "reason": reason}


def oos_benchmark_table(metrics: dict) -> dict:
    """Release 3（新 28 号）：正式 OOS 报告固定输出 B2–B6 对照表。"""
    required_models = ("B2_SIMPLE_TREND", "B3_WAVE_ONLY",
                       "B4_PERMISSION_WAVE", "B5_PERMISSION_WAVE_FSM_RISK",
                       "B6_FULL_CANONICAL")
    missing = [m for m in required_models if not metrics.get(m)]
    return {"models": required_models,
            "missing": missing,
            "complete": not missing,
            "metrics": {m: metrics.get(m) for m in required_models},
            "rule": "每个大版本必须回答 Full 比 Permission+Wave 多提供什么"}


def benchmark_missing_gate(table: dict) -> dict:
    """Benchmark Ladder missing → Promotion BLOCKED。"""
    if table.get("missing"):
        return {"verdict": "PROMOTION_BLOCKED",
                "missing_models": table["missing"],
                "allowed": False,
                "rule": "Benchmark Ladder missing → Promotion BLOCKED"}
    return {"verdict": "BENCHMARK_COMPLETE", "allowed": True}


def promotion_requires_ladder(ladder_result: dict,
                              required_baselines=None) -> dict:
    """新 52 号：没有 Benchmark Ladder 结果，不允许 Production Promotion。

    Full Canonical 必须证明相对 Permission+Wave 与 WaveOnly 有稳定增量。
    """
    required = required_baselines or (
        "B4_PERMISSION_WAVE", "B3_WAVE_ONLY")
    baselines = (ladder_result or {}).get("baselines") or {}
    missing = [b for b in required
               if not baselines.get(b) or
               not baselines[b].get("metrics")]
    if missing:
        return {"verdict": "PROMOTION_BLOCKED",
                "missing_baselines": missing,
                "allowed": False,
                "rule": "没有 Benchmark Ladder 结果，不允许 Promotion"}
    return {"verdict": "LADDER_PRESENT",
            "missing_baselines": [],
            "allowed": True,
            "rule": "Full 必须证明相对 Permission+Wave 与 WaveOnly 的稳定增量"}
