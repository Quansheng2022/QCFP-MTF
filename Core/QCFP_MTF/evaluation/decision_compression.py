# coding: utf-8
"""Decision Compression Test（QCFP-MTF 2.8：85 号决策压缩测试）

研究能否用更少的状态和 action 表达几乎相同的实战决策：
    Full action taxonomy vs Compressed taxonomy
比较 OOS / Turnover / Decision flip / 用户理解 / Risk。

验收标准：两个状态在真实决策中几乎没有独立行为意义 → 合并。
"""


COMPRESSION_METRICS = ("oos_sharpe", "turnover", "decision_flip_rate",
                       "user_understanding", "max_drawdown")


def decision_compression_test(full: dict, compressed: dict,
                              tolerances=None) -> dict:
    """full/compressed：{action_count, oos_sharpe, turnover,
    decision_flip_rate, user_understanding, max_drawdown}"""
    tol = tolerances or {"oos_sharpe": 0.10, "max_drawdown": 0.02,
                         "turnover": 0.0, "decision_flip_rate": 0.0,
                         "user_understanding": 0.0}
    worse, better = [], []
    # 越高越好：oos_sharpe, user_understanding
    for metric in ("oos_sharpe", "user_understanding"):
        cur = float(full.get(metric) or 0.0)
        new = float(compressed.get(metric) or 0.0)
        if new < cur - tol.get(metric, 0.0):
            worse.append(metric)
        elif new > cur:
            better.append(metric)
    # 越低越好：turnover, decision_flip_rate, max_drawdown
    for metric in ("turnover", "decision_flip_rate", "max_drawdown"):
        cur = float(full.get(metric) or 0.0)
        new = float(compressed.get(metric) or 0.0)
        if new > cur + tol.get(metric, 0.0):
            worse.append(metric)
        elif new < cur:
            better.append(metric)
    action_reduced = int(compressed.get("action_count")
                         or len(compressed.get("actions") or [])
                         or 0) < int(full.get("action_count")
                                     or len(full.get("actions") or [])
                                     or 0)
    if not worse and action_reduced:
        verdict = "MERGE_RECOMMENDED"
        reason = "状态/动作减少且 OOS/Risk 不恶化 → 合并"
    elif worse:
        verdict = "KEEP_FULL"
        reason = f"压缩后 {worse} 恶化 → 保留完整 taxonomy"
    else:
        verdict = "REVIEW"
        reason = "动作数未减少或证据不充分 → 复核"
    return {"worse_metrics": worse, "better_metrics": better,
            "action_reduced": action_reduced,
            "verdict": verdict, "reason": reason,
            "rule": "无独立行为意义的两个状态 → 合并"}


RECOMMENDED_COMPRESSED_TAXONOMY = ("NO_TRADE", "ENTRY", "HOLD",
                                   "REDUCE", "EXIT")


def recommended_compressed_taxonomy(full_actions) -> dict:
    """新 85 号：推荐压成更少的真正可行动类别。"""
    full = list(full_actions or [])
    compressed = list(RECOMMENDED_COMPRESSED_TAXONOMY)
    return {
        "full_actions": full,
        "full_count": len(full),
        "compressed_actions": compressed,
        "compressed_count": len(compressed),
        "reduction": len(full) - len(compressed),
        "rule": "减少认知复杂度，不是用 smoothing 掩盖真实治理边界",
    }


def compression_adoption(compression_result: dict) -> dict:
    """新 85 号：压缩后若风险/Wave Capture 基本不变且 Flip Rate 更低、
    解释更容易 → 采用更少 taxonomy。"""
    worse = compression_result.get("worse_metrics") or []
    better = compression_result.get("better_metrics") or []
    flip_down = "decision_flip_rate" in better
    risk_same = not any(m in ("max_drawdown", "oos_sharpe")
                        for m in worse)
    if not worse and compression_result.get("action_reduced") \
            and (flip_down or risk_same):
        return {"adopt": True,
                "verdict": "ADOPT_COMPRESSED",
                "reason": "风险与 Wave Capture 基本不变且 Flip 更低/"
                          "解释更容易 → 采用更少 taxonomy"}
    return {"adopt": False,
            "verdict": "KEEP_FULL",
            "reason": "压缩导致恶化或证据不足"}
