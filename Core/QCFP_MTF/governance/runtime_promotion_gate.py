# coding: utf-8
"""Runtime Promotion Gate（决策支持目标重新对齐：P0-1）

QCFP_MTF 是辅助决策支持系统，不负责向 Broker 下交易指令。
最终 Production 目标 = DECISION_SUPPORT_QUALIFIED，生命周期：

    RUNTIME_SCHEMA_READY
        ↓
    SHADOW_ACCUMULATING（20 个有效交易日连续合格）
        ↓
    SHADOW_QUALIFIED
        ↓
    OUTCOME_ACCUMULATING（Outcome 覆盖率/成熟度累计）
        ↓
    DECISION_SUPPORT_QUALIFIED
        ↓
    SUSPENDED（任一 hard reset）

不再把 BROKER_QUALIFIED / SMALL_LIVE_ELIGIBLE 作为产品正式目标；
没有任何"必须连接 Broker 才能成为正式决策支持版本"的条件。
60D observation window 作为非阻塞统计置信度补充。

本模块是极薄治理层：
    * 绝不重新计算 Decision / Permission / Target / Risk / Wave；
    * 只读取 Verified Runtime Evidence（来自 qcfp_runtime_evidence_daily
      或 build_runtime_evidence_from_ledger 的 artifact）；
    * 不接受 shadow_ok=True / operator_says_ok=True 这类自证输入。

状态：
    SHADOW_ACCUMULATING   （连续合格天数 < required_days，无 hard reset）
    SHADOW_QUALIFIED      （连续合格天数 >= required_days）
    SUSPENDED             （窗口内出现 hard reset 事件）

Hard reset（连续天数归零）：
    permission_violation / PIT violation / uncertified execution /
    critical replay mismatch / decision duplicate / canonical identity break

Operational interruption（休市 / 明确 maintenance / 计划停机）：
    该日 status=NOT_APPLICABLE → 不计入也不中断连续天数。
"""

import hashlib
import json


HARD_RESET_FIELDS = ("permission_violations", "pit_violations",
                     "uncertified_executions",
                     "critical_replay_mismatch")

# 兼容 SHADOW 旧 evidence 与决策支持新 evidence 的 READY verdict
READY_VERDICTS = ("EVIDENCE_READY", "DECISION_SUPPORT_EVIDENCE_READY")


def day_qualified(day: dict) -> tuple:
    """单日是否合格：
        verdict == EVIDENCE_READY
        coverage == 100%
        permission/pit/uncertified == 0
        replay 存在且 eligible==exact（100%）且 critical mismatch == 0
    返回 (ok, reasons)。无 replay 数据 → 不 qualify（Missing → NOT_PROVEN）。"""
    if not isinstance(day, dict):
        return False, ["NOT_DICT"]
    reasons = []
    if str(day.get("verdict") or "").upper() not in READY_VERDICTS:
        return False, [f"verdict={day.get('verdict')}"]
    try:
        coverage = float(day.get("coverage") or 0.0)
    except (TypeError, ValueError):
        coverage = 0.0
    if coverage < 1.0 - 1e-9:
        reasons.append("COVERAGE<100%")
    for f in ("permission_violations", "pit_violations",
              "uncertified_executions"):
        if int(day.get(f) or 0) > 0:
            reasons.append(f"{f}>0")
    eligible = day.get("replay_eligible")
    exact = day.get("replay_exact")
    if eligible is None or exact is None:
        reasons.append("REPLAY_MISSING")
    else:
        if int(eligible or 0) <= 0:
            reasons.append("REPLAY_NO_DECISIONS")
        if int(eligible or 0) != int(exact or 0):
            reasons.append("REPLAY_NOT_100%")
    if int(day.get("critical_replay_mismatch") or 0) > 0:
        reasons.append("CRITICAL_REPLAY_MISMATCH")
    if int(day.get("decision_duplicate_count") or 0) > 0:
        reasons.append("DECISION_DUPLICATE")
    if int(day.get("canonical_identity_break") or 0) > 0:
        reasons.append("CANONICAL_IDENTITY_BREAK")
    return (not reasons), reasons


def _hard_reset_hit(day: dict) -> list:
    return [f for f in HARD_RESET_FIELDS
            if int(day.get(f) or 0) > 0] \
        + [f for f in ("decision_duplicate_count",
                       "canonical_identity_break")
           if int(day.get(f) or 0) > 0]


def evaluate_shadow_qualification(evidence_window, required_days=20) -> dict:
    """从每日 evidence projection 计算 Shadow Qualification。

    evidence_window：按日期升序的 dict 列表（每元素为
    qcfp_runtime_evidence_daily 一行或 runtime evidence artifact 的
    evidence 投影）。NOT_APPLICABLE 日跳过（不中断）。"""
    rows = list(evidence_window or [])
    consecutive = 0
    qualified_days = 0
    blocking_reasons = []
    hard_reset_count = 0
    window_parts = []
    for day in rows:
        window_parts.append(
            f"{day.get('trade_date')}|{day.get('verdict')}|"
            f"{day.get('evidence_hash')}")
        if str(day.get("status") or "").upper() == "NOT_APPLICABLE":
            continue
        reset = _hard_reset_hit(day)
        if reset:
            consecutive = 0
            hard_reset_count += 1
            blocking_reasons.extend(
                f"{day.get('trade_date')}:{r}" for r in reset)
            continue
        ok, reasons = day_qualified(day)
        if ok:
            qualified_days += 1
            consecutive += 1
        else:
            consecutive = 0
            blocking_reasons.extend(
                f"{day.get('trade_date')}:{r}" for r in reasons[:3])
    window_hash = hashlib.sha256(
        "\n".join(window_parts).encode("utf-8")).hexdigest()[:16] \
        if window_parts else ""
    if hard_reset_count > 0:
        state = "SUSPENDED"
    elif consecutive >= required_days:
        state = "SHADOW_QUALIFIED"
    else:
        state = "SHADOW_ACCUMULATING"
    return {
        "state": state,
        "qualified_days": consecutive,
        "required_days": required_days,
        "remaining_days": max(0, required_days - consecutive),
        "blocking_reasons": blocking_reasons[:10],
        "evidence_window_hash": window_hash,
        "hard_reset_count": hard_reset_count,
        "rule": "只读 Verified Evidence；hard reset 归零连续天数；"
                "NOT_APPLICABLE 不中断；不接受自证输入",
    }


def evaluate_decision_support_qualification(evidence_window,
                                            shadow_days=20,
                                            outcome_days=20,
                                            outcome_min_coverage=0.8) -> dict:
    """决策支持资格：Shadow 20D 第一门 + Outcome 20D 第二门。

    evidence_window：每日 evidence projection（按日期升序）。
    60D observation（非阻塞）一并报告。"""
    rows = list(evidence_window or [])
    shadow = evaluate_shadow_qualification(rows,
                                           required_days=shadow_days)
    if shadow["state"] == "SUSPENDED":
        return {"state": "SUSPENDED",
                "shadow_state": "SUSPENDED",
                "outcome_state": "SUSPENDED",
                "qualified_days": shadow["qualified_days"],
                "shadow_days": shadow_days,
                "outcome_days": 0,
                "required_outcome_days": outcome_days,
                "remaining_outcome_days": outcome_days,
                "blocking_reasons": shadow["blocking_reasons"],
                "evidence_window_hash": shadow["evidence_window_hash"],
                "observation_60d": {"qualified_days_60": 0,
                                    "window_days": 0,
                                    "blocking": False},
                "rule": "SUSPENDED 时下游阶段不得 PASS"}
    outcome_days_ok = 0
    blocking = []
    for day in rows:
        if str(day.get("status") or "").upper() == "NOT_APPLICABLE":
            continue
        verdict = str(day.get("verdict") or "").upper()
        if verdict not in READY_VERDICTS:
            continue
        try:
            oc = float(day.get("outcome_coverage") or 0.0)
        except (TypeError, ValueError):
            oc = 0.0
        matured = (day.get("outcome_maturity_5d") or
                   day.get("outcome_maturity_20d") or
                   day.get("outcome_maturity_60d"))
        if matured is None:
            blocking.append(f"{day.get('trade_date')}:OUTCOME_MATURITY_MISSING")
            continue
        if oc >= outcome_min_coverage - 1e-9:
            outcome_days_ok += 1
        else:
            blocking.append(
                f"{day.get('trade_date')}:OUTCOME_COVERAGE<{outcome_min_coverage}")
    if outcome_days_ok >= outcome_days and shadow["state"] == "SHADOW_QUALIFIED":
        state = "DECISION_SUPPORT_QUALIFIED"
    elif outcome_days_ok < outcome_days and shadow["state"] == "SHADOW_QUALIFIED":
        state = "OUTCOME_ACCUMULATING"
    else:
        state = shadow["state"]
    obs_window = rows[-60:]
    obs_qualified = sum(1 for d in obs_window
                        if str(d.get("verdict") or "").upper()
                        in READY_VERDICTS
                        and str(d.get("status") or "").upper()
                        != "NOT_APPLICABLE")
    return {
        "state": state,
        "shadow_state": shadow["state"],
        "outcome_state": "OUTCOME_ACCUMULATING"
        if state == "OUTCOME_ACCUMULATING" else state,
        "qualified_days": shadow["qualified_days"],
        "shadow_days": shadow_days,
        "outcome_days": outcome_days_ok,
        "required_outcome_days": outcome_days,
        "remaining_outcome_days": max(0, outcome_days - outcome_days_ok),
        "blocking_reasons": (shadow["blocking_reasons"] + blocking)[:10],
        "evidence_window_hash": shadow["evidence_window_hash"],
        "observation_60d": {"qualified_days_60": obs_qualified,
                            "window_days": len(obs_window),
                            "blocking": False},
        "rule": "DECISION_SUPPORT_QUALIFIED = 20D Shadow + 20D Outcome "
                "覆盖；60D 仅观察不阻塞；Broker 不是必要条件",
    }
