# coding: utf-8
"""Version / Rule Change Impact Analysis（QCFP-MTF 2.8：37 号版本变更影响）

新版本上线前不只看 New Return > Old Return，而是在同一批数据上比较：
    Decision / Permission / Wave(Setup) / FSM / Position / Exit /
    P&L / Risk 差异 + Decision Flip Rate

输出"哪些字段导致了翻转"，让版本升级变成可解释、可审查的工程过程。
"""

from dataclasses import asdict, dataclass, field


COMPARE_FIELDS = (
    ("institutional_permission", "permission"),
    ("setup_type", "wave"),
    ("exit_event_kind", "exit"),
    ("prev_fsm_state", "fsm"),
    ("next_fsm_state", "fsm"),
    ("target_position", "position"),
    ("primary_reason", "reason"),
)


@dataclass(frozen=True)
class VersionImpact:
    old_version: str
    new_version: str
    n_decisions: int
    flip_rate: float
    flips: tuple
    field_flip_counts: dict
    pnl_diff: float
    risk_diff: float

    def as_dict(self) -> dict:
        d = asdict(self)
        d["flips"] = list(self.flips)
        return d


def _get(obj, key):
    if isinstance(obj, dict):
        return obj.get(key)
    return getattr(obj, key, None)


def version_impact(old_snapshots, new_snapshots, old_version="old",
                   new_version="new", pnl_map=None, risk_map=None) \
        -> VersionImpact:
    """同批决策旧/新版本对比。snapshots 为 {decision_id: snap/dict}。"""
    ids = sorted(set(old_snapshots) & set(new_snapshots))
    flips = []
    field_counts = {k: 0 for _, k in COMPARE_FIELDS}
    for did in ids:
        o, n = old_snapshots[did], new_snapshots[did]
        flipped_fields = []
        for field, bucket in COMPARE_FIELDS:
            ov, nv = _get(o, field), _get(n, field)
            if field == "target_position":
                ov = round(float(ov or 0.0), 4)
                nv = round(float(nv or 0.0), 4)
            if ov != nv:
                flipped_fields.append(field)
                field_counts[bucket] += 1
        if flipped_fields:
            flips.append({"decision_id": did,
                          "flipped_fields": flipped_fields,
                          "old_target": _get(o, "target_position"),
                          "new_target": _get(n, "target_position")})
    n = len(ids)
    pnl_diff = 0.0
    if pnl_map:
        for did in ids:
            o_ret, n_ret = pnl_map.get(did, (None, None))
            if o_ret is not None and n_ret is not None:
                pnl_diff += float(n_ret) - float(o_ret)
    risk_diff = 0.0
    if risk_map:
        for did in ids:
            o_r, n_r = risk_map.get(did, (None, None))
            if o_r is not None and n_r is not None:
                risk_diff += float(n_r) - float(o_r)
    return VersionImpact(
        old_version=old_version, new_version=new_version,
        n_decisions=n,
        flip_rate=round(len(flips) / n, 4) if n else 0.0,
        flips=tuple(flips),
        field_flip_counts=field_counts,
        pnl_diff=round(pnl_diff, 6),
        risk_diff=round(risk_diff, 6))


def impact_to_md(impact: VersionImpact) -> str:
    lines = [
        f"# Version Impact Analysis　{impact.old_version} → "
        f"{impact.new_version}",
        "",
        f"**决策数：{impact.n_decisions}**　**翻转率："
        f"{impact.flip_rate:.1%}**",
        "",
        "## 按维度翻转次数",
        "",
        "| 维度 | 翻转次数 |", "| --- | --- |",
    ]
    for bucket, cnt in sorted(impact.field_flip_counts.items(),
                              key=lambda x: -x[1]):
        lines.append(f"| {bucket} | {cnt} |")
    lines += ["", "## P&L / 风险差异", "",
              f"- P&L 差异（New−Old）：{impact.pnl_diff:+.2%}",
              f"- 风险差异（New−Old）：{impact.risk_diff:+.2%}", ""]
    if impact.flips:
        lines += ["## 翻转明细（前 20）", "", "| decision_id | 翻转字段 |",
                  "| --- | --- |"]
        for f in list(impact.flips)[:20]:
            lines.append(f"| {f['decision_id']} | "
                         f"{', '.join(f['flipped_fields'])} |")
        lines += [""]
    return "\n".join(lines)


# Release 3（新 23 号）：Change Severity 分级
CHANGE_SEVERITY = {
    0: "NO_DECISION_CHANGE",
    1: "REASON_EXPLANATION_CHANGE",
    2: "WAVE_FSM_STATE_CHANGE",
    3: "FINAL_TARGET_ACTION_CHANGE",
    4: "PERMISSION_HARDEXIT_CERTIFICATION_CHANGE",
}


def change_severity(flip_fields: list) -> int:
    """按受影响字段判定严重级别。"""
    fields = set(flip_fields or [])
    if fields & {"institutional_permission", "exit_event_kind"}:
        return 4
    if "target_position" in fields:
        return 3
    if fields & {"setup_type", "next_fsm_state", "prev_fsm_state"}:
        return 2
    if fields & {"primary_reason"}:
        return 1
    return 0


def version_impact_release_gate(impact: dict) -> dict:
    """新 23 号：Decision-critical change 必须产生 Version Impact Report；
    Permission/HardExit/FinalTarget 大面积 Flip → FULL 验证。"""
    flips = impact.get("flips") or []
    field_counts = impact.get("field_flip_counts") or {}
    n = int(impact.get("n_decisions") or 0)
    high_risk = (
        field_counts.get("permission", 0) > 0
        or field_counts.get("exit", 0) > 0
        or (n and field_counts.get("position", 0) / max(n, 1) > 0.15))
    severity = max((change_severity(f.get("flipped_fields"))
                    for f in flips), default=0)
    return {
        "flip_rate": impact.get("flip_rate"),
        "severity": severity,
        "severity_label": CHANGE_SEVERITY.get(severity),
        "high_risk_flips": high_risk,
        "validation_required": "FULL_OOS_ABLATION_STRESS_SHADOW_HUMAN"
        if high_risk else "STANDARD",
        "version_impact_report_required": True,
        "verdict": "REVIEW_REQUIRED" if high_risk else "OK",
        "rule": "所有 Production-critical commit 必须 Change Impact Report",
    }
