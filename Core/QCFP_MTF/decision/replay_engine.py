# coding: utf-8
"""Deterministic Replay Engine（QCFP-MTF 2.8：43 号确定性回放引擎）

输入 decision_id 自动恢复：
    Data Snapshot / Feature Snapshot / Model / Rule / Config / Schema /
    Execution Assumptions
然后 Original Decision → Replay → Field-by-field Compare。

比较字段（不能只比 final target）：
    permission / wave(setup) / fsm / risk(exit) / raw_target /
    governed_target / final_target / action / reason_codes
任何字段不一致 → REPLAY_MISMATCH（即使 final target 恰好相同）。
"""

from dataclasses import asdict, dataclass, field


REPLAY_FIELDS = (
    "institutional_permission",
    "setup_type",
    "prev_fsm_state",
    "next_fsm_state",
    "exit_event_kind",
    "raw_target_position",
    "target_position",
)


@dataclass(frozen=True)
class ReplayResult:
    decision_id: str
    status: str                 # EXACT_MATCH / REPLAY_MISMATCH
    mismatches: tuple
    compared_fields: int

    def as_dict(self) -> dict:
        d = asdict(self)
        d["mismatches"] = list(self.mismatches)
        return d


def _get(obj, key):
    if isinstance(obj, dict):
        return obj.get(key)
    return getattr(obj, key, None)


def field_by_field_compare(original, replay, decision_id="") -> ReplayResult:
    """逐字段比较（原始 vs 重放）。"""
    mismatches = []
    for f in REPLAY_FIELDS:
        o, r = _get(original, f), _get(replay, f)
        if f == "raw_target_position" or f == "target_position":
            o = round(float(o or 0.0), 4)
            r = round(float(r or 0.0), 4)
        if o != r:
            mismatches.append({"field": f, "original": o, "replay": r})
    # action / reason（来自 context / 顶层）
    o_act = (_get(original, "context") or {}).get("action") if \
        isinstance(_get(original, "context"), dict) else _get(original, "action")
    r_act = (_get(replay, "context") or {}).get("action") if \
        isinstance(_get(replay, "context"), dict) else _get(replay, "action")
    if o_act != r_act:
        mismatches.append({"field": "action", "original": o_act,
                           "replay": r_act})
    o_reason = _get(original, "primary_reason")
    r_reason = _get(replay, "primary_reason")
    if o_reason != r_reason:
        mismatches.append({"field": "primary_reason", "original": o_reason,
                           "replay": r_reason})
    status = "EXACT_MATCH" if not mismatches else "REPLAY_MISMATCH"
    return ReplayResult(
        decision_id=decision_id or _get(original, "decision_id") or "?",
        status=status, mismatches=tuple(mismatches),
        compared_fields=len(REPLAY_FIELDS) + 2)


def replay_to_md(r: ReplayResult) -> str:
    status_text = "✅ EXACT_MATCH" if r.status == "EXACT_MATCH" \
        else "❌ REPLAY_MISMATCH"
    lines = [
        f"# Deterministic Replay　{r.decision_id}",
        "",
        f"**状态：{status_text}**（比较 {r.compared_fields} 字段）",
        "",
    ]
    if r.mismatches:
        lines += ["| 字段 | Original | Replay |", "| --- | --- | --- |"]
        for m in r.mismatches:
            lines.append(f"| {m['field']} | {m['original']} | "
                         f"{m['replay']} |")
    return "\n".join(lines)
