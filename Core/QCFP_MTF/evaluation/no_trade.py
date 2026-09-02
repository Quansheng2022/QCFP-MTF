# coding: utf-8
"""No-Trade Quality Score（QCFP-MTF 2.8：96 号不交易质量评分）

QCFP_MTF 核心目标之一是"少做错误交易"，所以必须评价"不交易"的质量：
    Correct No-Trade（阻止后下跌） / False No-Trade（阻止后大涨） /
    Correct Trade / False Trade → Decision Confusion Matrix

No-Trade Score = 正确不交易质量 − 错误不交易代价。
"""


def no_trade_quality(decisions) -> dict:
    """decisions：[{traded: bool, net_return: 后续收益}]

    混淆矩阵：
        Correct Trade     traded + return>0
        False Trade       traded + return<=0
        Correct No-Trade  not traded + return<0（避免损失）
        False No-Trade    not traded + return>0（错过机会）
    """
    ct = ft = cn = fn = 0
    avoided_loss = 0.0
    missed_gain = 0.0
    for d in decisions:
        ret = float(d.get("net_return") or 0.0)
        if d.get("traded"):
            if ret > 0:
                ct += 1
            else:
                ft += 1
        else:
            if ret < 0:
                cn += 1
                avoided_loss += -ret
            else:
                fn += 1
                missed_gain += ret
    total = max(1, len(decisions))
    score = round(100 * ((ct + cn) / total) - 100 * (fn / total) * 0.5, 2)
    return {
        "confusion_matrix": {
            "correct_trade": ct, "false_trade": ft,
            "correct_no_trade": cn, "false_no_trade": fn},
        "no_trade_score": score,
        "avoided_loss": round(avoided_loss, 4),
        "missed_gain": round(missed_gain, 4),
        "no_trade_accuracy": round((cn + ct) / total, 4),
    }
