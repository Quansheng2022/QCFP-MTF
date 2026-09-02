# coding: utf-8
"""Daily Data Trust Report（数据健康检查报告优化）

把 check_data_quality + data_health_score + evidence_quality_contract +
PIT + Source Integrity + Transformation Health 串成一份统一主报告：
    Overall / Source Health / Source Integrity / PIT /
    Transformation Health / Evidence Quality / Decision Readiness /
    Critical Issues / Action

硬规则：
    - Source Version = UNKNOWN → 总体不能 NORMAL；
    - 关键监控缺失 → UNKNOWN → SAFE_MODE（没有数据 ≠ 默认正常）；
    - Decision Readiness 只有 YES / DEGRADED / NO / UNKNOWN 四态。
"""


SOURCE_INTEGRITY_CHECKS = ("schema", "source_version", "duplicate",
                           "timestamp", "price_continuity",
                           "corporate_action", "suspension",
                           "cross_source")


def source_integrity_check(checks: dict) -> dict:
    """Source Integrity：8 项 PASS/FAIL；Source Version=UNKNOWN →
    总体不能 NORMAL。"""
    results = {}
    for name in SOURCE_INTEGRITY_CHECKS:
        v = checks.get(name)
        results[name] = "PASS" if v is True else \
            "UNKNOWN" if v is None else "FAIL"
    unknown_version = results.get("source_version") == "UNKNOWN"
    failures = [k for k, s in results.items() if s == "FAIL"]
    unknowns = [k for k, s in results.items() if s == "UNKNOWN"]
    return {
        "results": results,
        "failures": failures,
        "unknowns": unknowns,
        "source_version_unknown": unknown_version,
        "overall": "PASS" if not failures and not unknowns
        else "FAIL" if failures else "UNKNOWN",
        "blocks_normal": bool(failures or unknown_version),
        "rule": "Source Version = UNKNOWN → 总体不能 NORMAL",
    }


def pit_health_section(pit: dict) -> dict:
    """PIT 专节：Integrity/Grade/Future Timestamp/AvailableDate Fail/
    Universe Snapshot/Disclosure Mode。"""
    future = int(pit.get("future_timestamp") or 0)
    avail_fail = int(pit.get("available_date_fail") or 0)
    integrity = 1.0 if (future == 0 and avail_fail == 0) else \
        max(0.0, 1.0 - (future + avail_fail) * 0.1)
    grade = pit.get("pit_grade")
    if grade is None:
        pit_grade = "UNKNOWN"
    elif grade in ("A", "B"):
        pit_grade = grade
    else:
        pit_grade = grade
    return {
        "pit_integrity": round(float(pit.get("pit_integrity")
                                     or integrity), 4),
        "pit_grade": pit_grade,
        "future_timestamp": future,
        "available_date_fail": avail_fail,
        # PWC-1（第 3 项）：缺失 → UNKNOWN，禁止 missing→PASS/REAL
        "universe_snapshot": pit.get("universe_snapshot")
        if pit.get("universe_snapshot") is not None else "UNKNOWN",
        "disclosure_mode": pit.get("disclosure_mode")
        if pit.get("disclosure_mode") is not None else "UNKNOWN",
        "pit_ok": future == 0 and avail_fail == 0
        and (pit_grade or "B") in ("A", "B"),
    }


def transformation_health(stages: list, nan_threshold: float = 0.05) -> dict:
    """Transformation Health：Stage Input/Output/NaN/Version/Status——
    原始数据好但中间步骤处理坏 → 必须被发现。"""
    rows = []
    failures = []
    stages = stages or []
    if not stages:
        return {"stages": [], "failures": [],
                "overall": "UNKNOWN",
                "rule": "没有 Transformation telemetry → UNKNOWN（≠PASS）"}
    for s in stages:
        inp = int(s.get("input") or 0)
        out = int(s.get("output") or 0)
        nan = float(s.get("nan") or 0.0)
        status = str(s.get("status") or "PASS").upper()
        if nan > nan_threshold or out < inp * 0.95 or status == "FAIL":
            status = "FAIL"
            failures.append(s.get("stage"))
        rows.append({"stage": s.get("stage"), "input": inp,
                     "output": out, "nan": round(nan, 4),
                     "version": s.get("version", ""),
                     "status": status})
    return {"stages": rows, "failures": failures,
            "overall": "PASS" if not failures else "FAIL",
            "rule": "中间 Transformation 把数据处理坏必须被发现"}


def trust_overall_status(dhs_status, source_integrity,
                         transformation, pit) -> str:
    """PWC-1（第 3 项）：Critical 证据缺失时总体不能 NORMAL。"""
    if source_integrity.get("overall") != "PASS" \
            or transformation.get("overall") != "PASS" \
            or pit.get("pit_grade") == "UNKNOWN":
        if dhs_status == "NORMAL":
            return "CAUTION"
        return dhs_status
    return dhs_status


def decision_readiness_v2(dhs_status, evidence_grade, pit_ok,
                          source_version_unknown=False) -> dict:
    """Decision Readiness 四态：YES / DEGRADED / NO / UNKNOWN。"""
    if evidence_grade == "UNKNOWN" or dhs_status is None:
        return {"readiness": "UNKNOWN", "new_risk_cap_scale": 0.0}
    if dhs_status == "BLOCK" or evidence_grade == "D" or not pit_ok \
            or source_version_unknown:
        return {"readiness": "NO", "new_risk_cap_scale": 0.0}
    if dhs_status == "DEGRADED" or evidence_grade == "C":
        return {"readiness": "DEGRADED", "new_risk_cap_scale": 0.0}
    if dhs_status == "CAUTION" or evidence_grade == "B":
        return {"readiness": "DEGRADED", "new_risk_cap_scale": 0.6}
    return {"readiness": "YES", "new_risk_cap_scale": 1.0}


def daily_data_trust_report_v2(assessment, dhs, evidence, pit,
                               source_integrity, transformation,
                               stamp, model_version="") -> dict:
    """统一 Daily Data Trust Report 主报告。"""
    grade_order = {"A": 0, "B": 1, "C": 2, "D": 3}
    worst = assessment["grade"].map(grade_order).max() \
        if len(assessment) else 3
    worst_grade = {0: "A", 1: "B", 2: "C", 3: "D"}[int(worst)]
    status = trust_overall_status(dhs["status"], source_integrity,
                                  transformation, pit)
    readiness = decision_readiness_v2(
        dhs["status"], evidence["grade"], pit["pit_ok"],
        source_integrity["source_version_unknown"])
    critical_issues = list(dhs.get("critical_failures") or [])
    critical_issues += source_integrity["failures"]
    critical_issues += transformation["failures"]
    action = "停止系统" if readiness["readiness"] == "NO" else \
        "降低新增风险" if readiness["readiness"] == "DEGRADED" else \
        "不需要停止系统"
    return {
        "report": "QCFP_MTF DAILY DATA TRUST REPORT",
        "date": stamp, "model_version": model_version,
        "overall": {"data_health_score": dhs["score"],
                    "status": status,
                    "evidence_grade": evidence["grade"],
                    "worst_source_grade": worst_grade,
                    "decision_readiness": readiness["readiness"],
                    "new_risk_cap_scale":
                        readiness["new_risk_cap_scale"],
                    "critical_failures": critical_issues},
        "source_health": assessment.to_dict(orient="records"),
        "source_integrity": source_integrity,
        "pit": pit,
        "transformation": transformation,
        "evidence": {"pit_valid": evidence.get("pit_valid"),
                     "grade": evidence["grade"],
                     "cap_scale": evidence["cap_scale"],
                     "new_risk_allowed": evidence["new_risk_allowed"],
                     "decision_allowed": evidence["decision_allowed"]},
        "decision_readiness": readiness,
        "action": action,
        "rule": "DATA READY FOR CANONICAL DECISION? "
                "YES / DEGRADED / NO / UNKNOWN",
    }


def trust_report_to_md(report: dict) -> str:
    """给人看的主报告（细节进 Appendix/JSON/CSV）。"""
    o = report["overall"]
    lines = [
        "# QCFP_MTF Daily Data Trust",
        "",
        f"Date: {report['date']}",
        "",
        f"Overall Data Health      {o['data_health_score']} / {o['status']}",
        f"Evidence Grade           {o['evidence_grade']}",
        f"Worst Source Grade       {o['worst_source_grade']}",
        f"Decision Readiness       {o['decision_readiness']}",
        f"New Risk Cap Scale       {o['new_risk_cap_scale']:.0%}",
        "",
        "## Source Health",
        "",
        "| data_type | rows | missing | anomalies | grade |",
        "| --- | ---: | ---: | ---: | --- |",
    ]
    for r in report["source_health"]:
        lines.append(f"| {r['data_type']} | {int(r['rows'])} | "
                     f"{r['core_missing_rate']:.1%} | {int(r['anomalies'])} "
                     f"| {r['grade']} |")
    lines += [
        "",
        "## Source Integrity",
        "",
        "| check | status |",
        "| --- | --- |",
    ]
    for k, v in report["source_integrity"]["results"].items():
        lines.append(f"| {k} | {v} |")
    lines += [
        "",
        "## PIT",
        "",
        f"PIT Integrity: {report['pit']['pit_integrity']} / "
        f"Grade {report['pit']['pit_grade']}",
        f"Future Timestamp: {report['pit']['future_timestamp']} / "
        f"AvailableDate Fail: {report['pit']['available_date_fail']}",
        "",
        "## Transformation Health",
        "",
        "| stage | input | output | nan | version | status |",
        "| --- | ---: | ---: | ---: | --- | --- |",
    ]
    for s in report["transformation"]["stages"]:
        lines.append(f"| {s['stage']} | {s['input']} | {s['output']} | "
                     f"{s['nan']:.1%} | {s['version']} | {s['status']} |")
    lines += [
        "",
        "## Decision",
        "",
        f"Decision Allowed: "
        f"{'YES' if report['evidence']['decision_allowed'] else 'NO'}",
        f"New Risk Allowed: "
        f"{'YES' if report['evidence']['new_risk_allowed'] else 'NO'}",
        "",
        "## Critical Issues",
        "",
    ]
    lines += [f"- {c}" for c in o["critical_failures"]] or ["- NONE"]
    lines += ["", f"## Action", "", f"- {report['action']}", ""]
    return "\n".join(lines)
