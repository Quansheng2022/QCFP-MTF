# coding: utf-8
"""Decision Stability（QCFP-MTF 2.7：防止噪声导致决策跳变）

同一股票、相近时间、轻微数据变化，不应导致 Permission/FSM/Target/Exit 剧烈跳变。
扰动 Price/Feature/Data Quality/Parameter 后统计：
    Decision Flip Rate（Permission/FSM/Exit）
    Position Sensitivity（target 波动）
    Stability Score（0-100，越高越稳）
"""

import copy

import numpy as np

from .engine import evaluate


def _perturb(row, rng, eps_price=0.005, eps_feature=0.02, dq_shift=True):
    r = copy.deepcopy(row)
    if r.get("q_position_52w") is not None:
        r["q_position_52w"] = max(0.0, min(1.0, float(r["q_position_52w"])
                                           * (1 + rng.uniform(-eps_feature,
                                                              eps_feature))))
    if r.get("q_trend_score") is not None:
        r["q_trend_score"] = float(r["q_trend_score"]) + rng.uniform(-2, 2)
    if r.get("des_score") is not None:
        r["des_score"] = int(r["des_score"]) + rng.choice((-1, 0, 1))
    if dq_shift and rng.random() < 0.3:
        dq = r.get("data_quality") or "B"
        shift = {"A": "B", "B": "C", "C": "D"}.get(dq, "B")
        r["data_quality"] = shift
    return r


def stability_report(row, settings, n_perturbations=30, seed=11,
                     previous_state="FLAT", previous_position=0.0) -> dict:
    rng = np.random.default_rng(seed)
    base = evaluate(dict(row), previous_state, previous_position, settings)
    perm_flips = fsm_flips = exit_flips = 0
    targets = []
    for _ in range(n_perturbations):
        p = _perturb(row, rng)
        snap = evaluate(p, previous_state, previous_position, settings)
        if snap.institutional_permission != base.institutional_permission:
            perm_flips += 1
        if snap.next_fsm_state != base.next_fsm_state:
            fsm_flips += 1
        if (snap.exit_event_kind == "NONE") != (base.exit_event_kind == "NONE"):
            exit_flips += 1
        targets.append(snap.target_position)
    n = max(1, n_perturbations)
    perm_rate, fsm_rate, exit_rate = perm_flips / n, fsm_flips / n, exit_flips / n
    targets = np.array(targets, dtype=float)
    base_t = float(base.target_position)
    pos_sens = float(np.std(targets)) if base_t > 1e-9 else 0.0
    stability = round(100 * (1 - (perm_rate + fsm_rate + exit_rate) / 3), 2)
    return {
        "stability_score": stability,
        "permission_flip_rate": round(perm_rate, 4),
        "fsm_flip_rate": round(fsm_rate, 4),
        "exit_flip_rate": round(exit_rate, 4),
        "position_sensitivity": round(pos_sens, 6),
        "base_target": round(base_t, 4),
        "n_perturbations": n_perturbations,
    }


def decision_robustness(row, settings, n_perturbations=24, seed=7,
                        previous_state="FLAT", previous_position=0.0) -> dict:
    """决策鲁棒性评分（91 号）：
        六类扰动（Feature/Data/Parameter/Timing/Cost/Regime）→
        决策跳变率 → Robust / Fragile / Unstable

    用途：Fragile Decision → 自动降低仓位或进入 Watch。
    """
    rng = np.random.default_rng(seed)
    base = evaluate(dict(row), previous_state, previous_position, settings)
    flip_count = 0
    per_dim = {}
    dims = ("feature", "data", "parameter", "timing", "cost", "regime")
    for _ in range(n_perturbations):
        p = dict(row)
        dim = dims[_ % len(dims)]
        if dim == "feature":
            if p.get("q_position_52w") is not None:
                p["q_position_52w"] = max(0.0, min(
                    1.0, float(p["q_position_52w"]) *
                    (1 + rng.uniform(-0.02, 0.02))))
        elif dim == "data":
            dq = p.get("data_quality") or "B"
            p["data_quality"] = {"A": "B", "B": "C", "C": "D"}.get(dq, "B")
        elif dim == "parameter":
            p["wave_strength"] = max(
                0.0, min(1.0, float(p.get("wave_strength") or 0.5)
                         + rng.uniform(-0.05, 0.05)))
        elif dim == "timing":
            p["des_score"] = int(p.get("des_score") or 0) + \
                int(rng.choice((-1, 0, 1)))
        elif dim == "cost":
            p["execution_cost"] = float(p.get("execution_cost") or 0.005) \
                * rng.uniform(0.5, 2.0)
        elif dim == "regime":
            p["market_regime"] = rng.choice(
                ("Bull", "Sideway", "Bear", "HighVolatility"))
        snap = evaluate(p, previous_state, previous_position, settings)
        changed = (snap.institutional_permission != base.institutional_permission
                   or snap.next_fsm_state != base.next_fsm_state
                   or abs(float(snap.target_position)
                          - float(base.target_position)) > 0.01)
        if changed:
            flip_count += 1
            per_dim[dim] = per_dim.get(dim, 0) + 1
    flip_rate = flip_count / max(1, n_perturbations)
    if flip_rate <= 0.05:
        band = "ROBUST"
    elif flip_rate <= 0.20:
        band = "FRAGILE"
    else:
        band = "UNSTABLE"
    return {
        "robustness_score": round(100 * (1 - flip_rate), 2),
        "flip_rate": round(flip_rate, 4),
        "band": band,
        "flips_by_dimension": per_dim,
        "recommendation": "NORMAL_EXECUTION" if band == "ROBUST" else
        "REDUCE_OR_WATCH" if band == "FRAGILE" else "BLOCK_ENTRY",
    }
