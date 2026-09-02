# coding: utf-8
"""Model Drift Monitor（QCFP-MTF 2.6：Shadow 漂移监控）

回测基线分布 vs 实时 Shadow 分布偏差超过阈值 → REGIME_DRIFT，
而不是继续认为模型"正常"。
"""


def distribution_drift(baseline: dict, live: dict,
                       threshold: float = 0.15) -> tuple:
    """各类别占比偏差；返回 (drift_flag, worst_delta, deltas)"""
    keys = set(baseline) | set(live)
    deltas = {}
    for k in keys:
        b = float(baseline.get(k, 0.0))
        l = float(live.get(k, 0.0))
        deltas[k] = round(abs(b - l), 4)
    worst = max(deltas.values()) if deltas else 0.0
    return worst > threshold, worst, deltas


DEFAULT_THRESHOLDS = {
    "distribution": 0.15, "wave_capture": 0.10, "false_entry": 0.05,
    "entry_delay": 2.0, "mfe": 0.03, "mae": 0.03, "avg_holding": 1.5,
}


def drift_report(baseline: dict, live: dict,
                 thresholds: dict = None) -> dict:
    """多维度漂移：permission/setup/fsm 分布 + wave/MAE/持有期等标量

    overall：无漂移 → NORMAL；1 项 → WARNING；≥2 项 → RESEARCH_REVIEW。
    """
    thr = {**DEFAULT_THRESHOLDS, **(thresholds or {})}
    metrics = {}
    for k, b in (baseline or {}).items():
        l = (live or {}).get(k)
        if l is None:
            continue
        t = thr.get(k, thr["distribution"])
        if isinstance(b, dict) and isinstance(l, dict):
            flag, worst, _ = distribution_drift(b, l, threshold=t)
            metrics[k] = {"flag": "DRIFT" if flag else "OK",
                          "worst": worst}
        else:
            try:
                delta = abs(float(l) - float(b))
            except (TypeError, ValueError):
                continue
            metrics[k] = {"flag": "DRIFT" if delta > t else "OK",
                          "delta": round(delta, 4)}
    drifted = [k for k, v in metrics.items() if v["flag"] == "DRIFT"]
    overall = "RESEARCH_REVIEW" if len(drifted) >= 2 else \
        "WARNING" if len(drifted) == 1 else "NORMAL"
    return {"overall": overall, "metrics": metrics, "drifted": drifted}
