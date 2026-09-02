# coding: utf-8
"""Wave Quality Matrix（QCFP-MTF 2.8：27 号双向错误框架）

不只研究"抓到多少牛股"，还研究两类错误：
    False Positive（认为有机会但实际失败）
    False Negative / Missed（后验强 Wave 但未参与）

指标：Wave Recall / Precision / Capture Ratio / False Entry Rate /
      Missed Wave Rate
"""


def wave_quality_matrix(realized_waves, predicted_positive,
                        captured_wave_ids, miss_reasons=None) -> dict:
    """realized_waves：[{wave_id}]（后验确认的强 Wave）
    predicted_positive：{wave_id}（系统预测有 Wave）
    captured_wave_ids：{wave_id}（实际参与的）"""
    realized = {w["wave_id"] for w in realized_waves}
    predicted = set(predicted_positive or ())
    captured = set(captured_wave_ids or ())
    tp = len(realized & captured)
    fp = len(predicted - realized)
    fn = len(realized - captured)
    tn = 0
    precision = tp / max(1, tp + fp)
    recall = tp / max(1, tp + fn)
    missed = realized - captured
    return {
        "quadrant": {"TP": tp, "FP": fp, "FN": fn, "TN": tn},
        "wave_precision": round(precision, 4),
        "wave_recall": round(recall, 4),
        "capture_ratio": round(tp / max(1, len(realized)), 4),
        "false_entry_rate": round(fp / max(1, tp + fp), 4),
        "missed_wave_rate": round(fn / max(1, len(realized)), 4),
        "missed_waves": sorted(missed),
        "miss_reasons": dict(miss_reasons or {}),
    }
