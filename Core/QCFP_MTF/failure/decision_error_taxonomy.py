# coding: utf-8
"""Decision Error Taxonomy（QCFP-MTF 2.8：76 号决策错误分类法）

统一记录系统"错在哪里"，不只看 P&L 亏损：
    DATA_ERROR / PIT_ERROR / PERMISSION_ERROR / WAVE_TIMING_ERROR /
    SIZING_ERROR / EXIT_ERROR / EXECUTION_ERROR / GOVERNANCE_ERROR /
    HUMAN_OVERRIDE_ERROR

验收标准：重大错误必须能归入稳定 taxonomy；
无法归类说明架构责任边界仍不清楚。
"""


DECISION_ERROR_TAXONOMY = (
    "DATA_ERROR", "PIT_ERROR", "PERMISSION_ERROR", "WAVE_TIMING_ERROR",
    "SIZING_ERROR", "EXIT_ERROR", "EXECUTION_ERROR", "GOVERNANCE_ERROR",
    "HUMAN_OVERRIDE_ERROR",
)

KEYWORD_MAP = {
    "DATA_ERROR": ("数据缺失", "data missing", "数据错误", "stale"),
    "PIT_ERROR": ("pit", "未来", "future", "超前", "lookahead",
                  "available"),
    "PERMISSION_ERROR": ("permission", "权限", "越权", "block"),
    "WAVE_TIMING_ERROR": ("wave", "波段", "时机", "timing", "过早",
                          "过晚"),
    "SIZING_ERROR": ("sizing", "仓位", "size", "sizing"),
    "EXIT_ERROR": ("exit", "退出", "止损", "stop"),
    "EXECUTION_ERROR": ("execution", "成交", "执行", "滑点", "slippage"),
    "GOVERNANCE_ERROR": ("governance", "治理", "ledger", "台账",
                         "约束"),
    "HUMAN_OVERRIDE_ERROR": ("override", "人工", "human", "手动"),
}


def classify_error(error_record: dict) -> dict:
    """error_record：{"message": str} 或 {"layer_hint": str}。

    按最长匹配关键词归类（最具体优先），避免"止损过晚"被
    WAVE_TIMING 的"过晚"抢先而误判为波段时机错误。
    """
    hint = str(error_record.get("layer_hint")
               or error_record.get("message") or "").lower()
    best_category, best_len = None, 0
    for category, keywords in KEYWORD_MAP.items():
        for kw in keywords:
            if kw.lower() in hint and len(kw) > best_len:
                best_category, best_len = category, len(kw)
    if best_category:
        return {"category": best_category, "classified": True,
                "message": error_record.get("message", "")}
    return {"category": "UNCLASSIFIED", "classified": False,
            "message": error_record.get("message", ""),
            "note": "无法归类说明架构责任边界仍不清楚"}


def error_taxonomy_report(errors) -> dict:
    counts = {k: 0 for k in DECISION_ERROR_TAXONOMY}
    unclassified = []
    for e in errors or []:
        r = classify_error(e)
        if r["classified"]:
            counts[r["category"]] += 1
        else:
            unclassified.append(e.get("message", ""))
    total = len(errors or [])
    return {"counts": counts, "total": total,
            "unclassified_count": len(unclassified),
            "unclassified_messages": unclassified,
            "taxonomy_stable": not unclassified}


ROOT_CAUSE_MAP = {
    "DATA_ERROR": ("数据管道缺失/陈旧", "data_pipeline"),
    "PIT_ERROR": ("未来数据/披露日映射错误", "pit_contract"),
    "PERMISSION_ERROR": ("权限判定错误", "permission_policy"),
    "WAVE_TIMING_ERROR": ("波段时机误判", "wave_stage"),
    "SIZING_ERROR": ("仓位计算错误", "position_sizing"),
    "EXIT_ERROR": ("退出过迟/过早", "exit_quality"),
    "EXECUTION_ERROR": ("成交/滑点假设失效", "execution_model"),
    "GOVERNANCE_ERROR": ("治理约束执行错误", "governance"),
    "HUMAN_OVERRIDE_ERROR": ("人工干预失误", "human_override"),
}


def trade_postmortem(trade: dict, message: str = "") -> dict:
    """新 76 号：Outcome → Error Classification → Root Cause →
    Corrective Layer（而不是 Loss → 调全部参数）。"""
    classification = classify_error({"message": message
                                     or str(trade.get("error") or "")})
    category = classification["category"]
    if category in ROOT_CAUSE_MAP:
        root_cause, corrective_layer = ROOT_CAUSE_MAP[category]
    else:
        root_cause, corrective_layer = "无法归因", "架构责任边界不清"
    return {
        "trade_id": trade.get("trade_id"),
        "outcome": trade.get("outcome"),
        "error_classification": category,
        "root_cause": root_cause,
        "corrective_layer": corrective_layer,
        "classified": classification["classified"],
        "rule": "盈利但 PIT 污染仍属 PIT_ERROR——不能因赚钱就认为系统正确",
    }
