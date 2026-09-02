# coding: utf-8
"""Decision Threshold Sensitivity Map（QCFP-MTF 2.8：63 号阈值敏感性地图）

对真正重要的阈值只测试附近的小范围扰动（默认 ±5%、±10%），
观察决策与表现是否突然断崖。

验收标准：好的 Production 规则应存在合理稳定区间；
如果 0.69 表现很好、0.70 就崩溃，应优先认为存在过拟合风险，
而不是精确锁死 0.69。
"""


THRESHOLD_KEYS = ("permission_threshold", "wave_confirmation",
                  "position_cap", "liquidity_cap", "stop_distance")

# 新 63 号：只检查真正 Decision-Critical 阈值（防止自己变成大型参数研究系统）
DECISION_CRITICAL_THRESHOLDS = (
    "permission_threshold", "wave_trigger_threshold",
    "wave_invalidation_threshold", "risk_budget",
    "liquidity_participation_limit", "position_cap", "stop_distance",
)


def default_probes(base: float, pct: float = 0.05) -> dict:
    """生成 ±pct 与 ±2×pct 的探测点（默认 ±5%、±10%）。"""
    b = float(base)
    return {round(b * (1 - 2 * pct), 4): None,
            round(b * (1 - pct), 4): None,
            round(b, 4): None,
            round(b * (1 + pct), 4): None,
            round(b * (1 + 2 * pct), 4): None}


def threshold_sensitivity_map(probes: dict,
                              cliff_delta: float = 0.20) -> dict:
    """probes：{threshold: {point: metric}}；
    相邻探测点之间 metric 突变超过 cliff_delta → CLIFF。"""
    result = {}
    for threshold, points in (probes or {}).items():
        if not points:
            result[threshold] = {"status": "NO_DATA", "points": {}}
            continue
        sorted_points = sorted((float(k), float(v))
                               for k, v in points.items()
                               if v is not None)
        deltas, cliff_at = [], None
        for i in range(1, len(sorted_points)):
            prev_p, prev_m = sorted_points[i - 1]
            cur_p, cur_m = sorted_points[i]
            d = round(cur_m - prev_m, 4)
            deltas.append({"from": prev_p, "to": cur_p,
                           "metric_delta": d})
            if abs(d) > cliff_delta and cliff_at is None:
                cliff_at = cur_p
        result[threshold] = {
            "status": "CLIFF" if cliff_at is not None else "STABLE",
            "points": {k: v for k, v in points.items()},
            "adjacent_deltas": deltas,
            "cliff_at": cliff_at,
        }
    return {"thresholds": result,
            "rule": "0.69 表现好、0.70 崩溃 → 过拟合风险而非精确锁死"}


def threshold_stability_verdict(map_result: dict) -> dict:
    cliffs = [t for t, r in (map_result.get("thresholds") or {}).items()
              if r.get("status") == "CLIFF"]
    if cliffs:
        return {"verdict": "OVERFIT_RISK",
                "cliff_thresholds": cliffs,
                "guidance": "阈值附近存在断崖，优先怀疑过拟合，"
                            "不精确锁死临界值"}
    return {"verdict": "STABLE_INTERVAL",
            "cliff_thresholds": [],
            "guidance": "阈值附近存在合理稳定区间"}


def critical_threshold_review(map_result: dict) -> dict:
    """新 63 号：发现敏感区 → REVIEW，而不是自动寻找最佳阈值 →
    Production（否则又回到过拟合）。"""
    verdict = threshold_stability_verdict(map_result)
    return {
        "verdict": "REVIEW" if verdict["verdict"] == "OVERFIT_RISK"
        else "STABLE",
        "cliff_thresholds": verdict["cliff_thresholds"],
        "guidance": "好规则应该有平台，不应该只在一个小数点上成立；"
                    "发现敏感区 → REVIEW，禁止自动寻优",
        "auto_optimize_forbidden": True,
    }
