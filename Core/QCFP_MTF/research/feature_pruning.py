# coding: utf-8
"""Feature Pruning（QCFP-MTF 2.8：33 号特征淘汰机制）

系统不仅会加 Feature，还会主动删除低价值、冗余 Feature：
    Feature Value = Predictive Contribution + Incremental Alpha +
    Stability − Correlation Penalty − Data Cost − Complexity Cost −
    Failure Risk（× PIT Quality）

判定：KEEP / REVIEW / SHADOW / RETIRE
"""


def feature_pruning(features: dict) -> dict:
    """features：{feature_id: {predictive_contribution, incremental_alpha,
    stability, correlation, data_cost, complexity_cost, failure_risk,
    pit_quality}}"""
    out = {}
    for fid, f in features.items():
        value = (float(f.get("predictive_contribution") or 0.0)
                 + float(f.get("incremental_alpha") or 0.0)
                 + float(f.get("stability") or 0.0)
                 - float(f.get("correlation") or 0.0)
                 - float(f.get("data_cost") or 0.0)
                 - float(f.get("complexity_cost") or 0.0)
                 - float(f.get("failure_risk") or 0.0))
        value *= float(f.get("pit_quality") or 1.0)
        if value >= 0.6:
            verdict = "KEEP"
        elif value >= 0.3:
            verdict = "SHADOW"
        elif value >= 0.1:
            verdict = "REVIEW"
        else:
            verdict = "RETIRE"
        out[fid] = {"value": round(value, 4), "verdict": verdict}
    return {"features": out,
            "retire_candidates": [k for k, v in out.items()
                                  if v["verdict"] == "RETIRE"],
            "shadow_candidates": [k for k, v in out.items()
                                  if v["verdict"] == "SHADOW"]}
