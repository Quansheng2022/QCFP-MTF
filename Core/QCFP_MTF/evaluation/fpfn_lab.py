# coding: utf-8
"""False Positive / False Negative Lab（QCFP-MTF 2.8：28 号错误实验室）

四象限：
    TP 预测BUY+实际WIN / FP 预测BUY+实际LOSS（假信号）/
    FN 预测NO+实际WIN（错过） / TN 预测NO+实际LOSS（避免）

重点：不能只追求"少亏钱"（压 FP）而忽视 FN（错过牛股）。
"""


def fpfn_analysis(decisions) -> dict:
    """decisions：[{predicted_buy: bool, actual_win: bool,
    net_return, miss_reason?, false_positive_reason?}]"""
    quadrant = {"TP": 0, "FP": 0, "FN": 0, "TN": 0}
    fp_reasons = {}
    fn_reasons = {}
    fp_cost = 0.0
    fn_cost = 0.0
    for d in decisions:
        pred = bool(d.get("predicted_buy"))
        win = bool(d.get("actual_win"))
        ret = float(d.get("net_return") or 0.0)
        if pred and win:
            quadrant["TP"] += 1
        elif pred and not win:
            quadrant["FP"] += 1
            fp_cost += abs(ret)
            r = d.get("false_positive_reason") or "UNKNOWN"
            fp_reasons[r] = fp_reasons.get(r, 0) + 1
        elif not pred and win:
            quadrant["FN"] += 1
            fn_cost += ret
            r = d.get("miss_reason") or "UNKNOWN"
            fn_reasons[r] = fn_reasons.get(r, 0) + 1
        else:
            quadrant["TN"] += 1
    total = max(1, len(decisions))
    tp, fp, fn, tn = (quadrant[k] for k in ("TP", "FP", "FN", "TN"))
    precision = tp / max(1, tp + fp)
    recall = tp / max(1, tp + fn)
    return {
        "quadrant": quadrant,
        "precision": round(precision, 4),
        "recall": round(recall, 4),
        "f1": round(2 * precision * recall / (precision + recall + 1e-9), 4),
        "fp_cost": round(fp_cost, 4),
        "fn_cost": round(fn_cost, 4),
        "fp_reasons": fp_reasons,
        "fn_reasons": fn_reasons,
        "balance_issue": bool(fn_cost > fp_cost * 2),
        "conclusion": "FP_DOMINANT" if fp_cost > fn_cost
        else "FN_DOMINANT" if fn_cost > fp_cost else "BALANCED",
    }
