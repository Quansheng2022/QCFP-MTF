# coding: utf-8
"""UniverseSnapshotContract（QCFP-MTF 2.8：34 号时点股票池快照契约）

每次回测/Replay 冻结当时真实可交易 universe（上市/退市/停牌/长期无成交），
不是今天的股票列表倒推历史（Survivorship Bias 控制）。

universe_snapshot_id 成为 EvidenceSnapshot/DataSnapshot 组成部分：
    运行 2022 年决策时，不能因今天已退市而自动排除当时存在的股票。
"""

import hashlib
import json


# 新 34 号：真实历史可投资状态
INVESTABILITY_STATES = ("eligible", "suspended", "special_event",
                        "zero_volume", "new_listing", "delisting_window",
                        "corporate_action_locked", "insufficient_history")


def universe_investability_state(entry: dict) -> str:
    """单个股票在决策日的可投资状态（唯一判定）。"""
    if entry.get("delisting_window"):
        return "delisting_window"
    if entry.get("corporate_action_locked"):
        return "corporate_action_locked"
    if entry.get("suspended"):
        return "suspended"
    if entry.get("zero_volume"):
        return "zero_volume"
    if entry.get("special_event"):
        return "special_event"
    if entry.get("new_listing"):
        return "new_listing"
    if entry.get("insufficient_history"):
        return "insufficient_history"
    return "eligible"


def universe_snapshot_contract(entries, decision_date) -> dict:
    """entries：[{stock_code, listed_date, delisted_date, suspended,
    active}]；decision_date：决策日。

    冻结当时 universe：
        listed_date ≤ decision_date < delisted_date（或未退市）
    校验：用今天的名单倒推 → survivorship 警告。
    """
    known_at_date = []
    for e in entries:
        code = e.get("stock_code")
        listed = str(e.get("listed_date") or "")[:10]
        delisted = str(e.get("delisted_date") or "")[:10] if \
            e.get("delisted_date") else ""
        in_universe = (not listed or listed <= decision_date) and \
            (not delisted or decision_date < delisted)
        if in_universe:
            entry = {
                "stock_code": code,
                "listed_date": listed,
                "delisted_date": delisted,
                "suspended": bool(e.get("suspended")),
                "active_today": bool(e.get("active")),
                # 新 22 号：可交易/板块/币种/每手/入池原因
                "tradable": bool(e.get("tradable", True)),
                "board": e.get("board", ""),
                "currency": e.get("currency", ""),
                "lot_size": e.get("lot_size"),
                "universe_reason": e.get("universe_reason", ""),
                "as_of_date": str(decision_date)[:10],
            }
            known_at_date.append(entry)
    # Survivorship 检查：今天退市但当时存在的股票不应被排除
    delisted_then = [e["stock_code"] for e in known_at_date
                     if e["delisted_date"] and not e["active_today"]]
    snapshot_id = hashlib.sha256(
        json.dumps({"date": decision_date,
                    "universe": sorted(e["stock_code"]
                                       for e in known_at_date)},
                   sort_keys=True, default=str).encode("utf-8")
    ).hexdigest()[:16]
    return {
        "decision_date": decision_date,
        "universe_snapshot_id": snapshot_id,
        "n_stocks": len(known_at_date),
        "stocks": sorted(e["stock_code"] for e in known_at_date),
        "investability": {
            e["stock_code"]: universe_investability_state(e)
            for e in known_at_date},
        "delisted_but_included": delisted_then,
        "survivorship_control": bool(delisted_then),
        "note": "运行历史决策时，当时存在的股票（含今日已退市）不得排除",
    }
