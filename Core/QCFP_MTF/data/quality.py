# coding: utf-8
"""数据质量检测：按规格书输出 A/B/C/D 标签 + 硬门禁（29 号）

联合规则：任一关键维度为 D 则整体判定为"数据不足，不产生决策信号"。

2.8（29 号）：data_quality_gate —— PASS / DEGRADED / BLOCK 三级硬门：
    BLOCK → 不允许产生 Trade Decision（数据异常 → 决策降级或停止，
    而不是给出一个"看起来正常"的信号）。
"""

from typing import Dict, Iterable, List, Optional

import pandas as pd

GRADES = ("A", "B", "C", "D")

# 各数据类型的核心字段（缺失即影响决策）与辅助字段
REQUIRED_COLS: Dict[str, List[str]] = {
    "daily_kline": ["close", "volume", "turnover_rate"],
    "weekly_kline": ["close", "volume", "turnover_rate"],
    "monthly_kline": ["close", "volume", "turnover_rate"],
    "quarterly_kline": ["close", "volume", "turnover_rate"],
    "daily_moneyflow": ["capital_trend", "extra_large", "large", "medium", "small"],
    "weekly_moneyflow": ["capital_trend", "extra_large", "large", "medium", "small"],
    "monthly_moneyflow": ["capital_trend", "extra_large", "large", "medium", "small"],
    "quarterly_moneyflow": ["capital_trend", "extra_large", "large", "medium", "small"],
    "idx_hist": ["date", "HSI"],
    "institutional_holdings": ["period_text", "institution_quantity", "holder_quantity", "holder_pct"],
}

AUX_COLS: Dict[str, List[str]] = {
    "daily_kline": ["open", "high", "low", "amount", "amplitude", "change_percent"],
    "weekly_kline": ["open", "high", "low", "amount", "amplitude", "change_percent"],
    "monthly_kline": ["open", "high", "low", "amount", "amplitude", "change_percent"],
    "quarterly_kline": ["open", "high", "low", "amount", "amplitude", "change_percent"],
    "daily_moneyflow": ["price_chgpct", "capital_in_super", "capital_in_big",
                        "capital_in_mid", "capital_in_small",
                        "capital_out_super", "capital_out_big",
                        "capital_out_mid", "capital_out_small"],
    "weekly_moneyflow": ["price_chgpct"],
    "monthly_moneyflow": ["price_chgpct"],
    "quarterly_moneyflow": ["price_chgpct"],
    "idx_hist": ["HSCEI", "HSTECH", "VHSI", "SouthboundFlow"],
    "institutional_holdings": ["quarter_end_price", "update_time", "data_source"],
}


def _missing_rate(series: pd.Series) -> float:
    if len(series) == 0:
        return 1.0
    return float(series.isna().mean())


# 换手率字段语义（Convergence / Data Health 优化）：
#   日线 = 单日换手率；周/月/季 = 周期累计换手率（>100 合法）
TURNOVER_SEMANTICS = {
    "D": "daily_rate",
    "W": "period_cumulative",
    "M": "period_cumulative",
    "Q": "period_cumulative",
}


def validate_bar(row, timeframe) -> dict:
    """Data Health 4 级分类（PASS/INFO/CLEAN/ERROR）：
        停牌 volume<=0 且 amount<=0        → CLEAN/DROP
        volume<=0 但 amount>0              → ERROR/REVIEW
        前复权 OHLC<=0                     → CLEAN/DROP（分析域不适用）
        负换手率                            → ERROR/REVIEW
        周/月/季累计换手率 >=100%           → INFO/KEEP（合法市场极端）
    """
    if timeframe not in ("D", "W", "M", "Q"):
        raise ValueError(f"invalid timeframe {timeframe}")
    volume = row.get("volume")
    amount = row.get("amount")
    if volume is not None and float(volume) <= 0:
        if amount is None or float(amount) <= 0:
            return {"status": "CLEAN", "action": "DROP",
                    "reason": "NO_TRADING_OR_SUSPENSION"}
        return {"status": "ERROR", "action": "REVIEW",
                "reason": "VOLUME_AMOUNT_INCONSISTENCY"}
    prices = [row.get(k) for k in ("open", "high", "low", "close")]
    if any(p is not None and float(p) <= 0 for p in prices):
        return {"status": "CLEAN", "action": "DROP",
                "reason": "FQ_NON_POSITIVE_PRICE"}
    tr = row.get("turnover_rate")
    if tr is not None and float(tr) < 0:
        return {"status": "ERROR", "action": "REVIEW",
                "reason": "NEGATIVE_TURNOVER"}
    if tr is not None and float(tr) >= 100 \
            and timeframe in ("W", "M", "Q"):
        return {"status": "INFO", "action": "KEEP",
                "reason": "HIGH_CUMULATIVE_TURNOVER"}
    return {"status": "PASS", "action": "KEEP"}


def _timeframe_from_type(data_type: str) -> str:
    mapping = {"daily_kline": "D", "weekly_kline": "W",
               "monthly_kline": "M", "quarterly_kline": "Q"}
    return mapping.get(data_type, "D")


def _anomaly_breakdown(df: pd.DataFrame, checks: List[str],
                       timeframe="D") -> dict:
    """分层异常计数：errors（真正数据错误）计入 grade 失败；
    clean（可清洗记录）与 info（合法市场极端）只报告、不降级。"""
    errors, clean, info = {}, {}, {}
    if "negative_price" in checks and "close" in df.columns:
        fq = int((df["close"] <= 0).sum())
        if fq:
            clean["前复权非正价格"] = fq
    if "non_positive_volume" in checks and "volume" in df.columns:
        if "amount" in df.columns:
            susp = int(((df["volume"] <= 0)
                        & (df["amount"].fillna(0) <= 0)).sum())
            inc = int(((df["volume"] <= 0) & (df["amount"] > 0)).sum())
        else:
            susp = int((df["volume"] <= 0).sum())
            inc = 0
        if susp:
            clean["停牌/无交易"] = susp
        if inc:
            errors["量额矛盾"] = inc
    if "turnover_out_of_range" in checks and "turnover_rate" in df.columns:
        neg = int((df["turnover_rate"] < 0).sum())
        if neg:
            errors["负换手率"] = neg
        if timeframe in ("W", "M", "Q"):
            high = int((df["turnover_rate"] >= 100).sum())
            if high:
                info["周期高换手"] = high
    return {"errors": errors, "clean": clean, "info": info}


def assess_table(data_type: str,
                 df: pd.DataFrame,
                 settings: dict) -> pd.DataFrame:
    """对单个数据源表做按股票分组的质量评估

    Returns DataFrame: stock_code, data_type, rows, first_date, last_date,
        core_missing_rate, anomalies, grade, reasons
    """
    dq = settings.get("data_quality", {})
    b_thr = float(dq.get("missing_threshold_b", 0.05))
    c_thr = float(dq.get("missing_threshold_c", 0.20))
    checks = list(dq.get("anomaly_checks", []))
    req = REQUIRED_COLS.get(data_type, [])

    if data_type == "idx_hist":
        groups = [("IDX", df)]
    elif df.empty or "stock_code" not in df.columns:
        groups = [("UNKNOWN", df)]
    else:
        groups = list(df.groupby("stock_code", dropna=False))

    out = []
    for name, g in groups:
        code = str(name) if name is not None else "UNKNOWN"
        rows = len(g)
        reasons = []

        if rows == 0:
            out.append(_row(code, data_type, 0, None, None, 1.0, 0, "D", ["无数据"]))
            continue

        # 核心字段缺失率（整列缺失视为 100%）
        present = [c for c in req if c in g.columns]
        absent = [c for c in req if c not in g.columns]
        core_missing = 0.0
        if present:
            core_missing = float(pd.Series([_missing_rate(g[c]) for c in present]).mean())
        core_missing += len(absent) / max(len(req), 1)
        if absent:
            reasons.append(f"缺核心列: {','.join(absent)}")

        # 辅助字段缺失（仅影响 B/A 判定）
        aux_missing = 0.0
        aux_present = [c for c in AUX_COLS.get(data_type, []) if c in g.columns]
        if aux_present:
            aux_missing = float(pd.Series([_missing_rate(g[c]) for c in aux_present]).mean())

        timeframe = _timeframe_from_type(data_type)
        classification = _anomaly_breakdown(g, checks, timeframe)
        anomaly_breakdown = classification["errors"]
        anomalies = sum(anomaly_breakdown.values())
        if anomalies > 0:
            detail = "；".join(f"{k} {v}" for k, v in anomaly_breakdown.items())
            reasons.append(f"异常值 {anomalies} 条（{detail}）")
        if classification["clean"]:
            clean_detail = "；".join(
                f"{k} {v}" for k, v in classification["clean"].items())
            reasons.append(f"可清洗 {sum(classification['clean'].values())}"
                           f" 条（{clean_detail}）")
        if classification["info"]:
            info_detail = "；".join(
                f"{k} {v}" for k, v in classification["info"].items())
            reasons.append(f"合法市场极端 {sum(classification['info'].values())}"
                           f" 条（{info_detail}）")

        if core_missing > c_thr or rows == 0:
            grade = "D"
            reasons.append(f"核心缺失率 {core_missing:.1%} > {c_thr:.0%}")
        elif core_missing > b_thr or anomalies > 0:
            grade = "C"
            reasons.append(f"核心缺失率 {core_missing:.1%} 或异常")
        elif core_missing > 0 or aux_missing > b_thr:
            grade = "B"
            reasons.append(f"轻微缺失（核心 {core_missing:.1%} / 辅助 {aux_missing:.1%}）")
        else:
            grade = "A"

        # 首末日期
        first = last = None
        if "date" in g.columns:
            dts = pd.to_datetime(g["date"], errors="coerce").dropna()
            if len(dts):
                first, last = dts.min().strftime("%Y-%m-%d"), dts.max().strftime("%Y-%m-%d")
        elif "period_text" in g.columns:
            pts = g["period_text"].dropna()
            if len(pts):
                first, last = pts.min(), pts.max()

        out.append(_row(code, data_type, rows, first, last,
                        core_missing, anomalies, grade, reasons))
    return pd.DataFrame(out, columns=[
        "stock_code", "data_type", "rows", "first_date", "last_date",
        "core_missing_rate", "anomalies", "grade", "reasons",
    ])


def _row(stock_code, data_type, rows, first, last, core_missing, anomalies, grade, reasons):
    return {
        "stock_code": stock_code,
        "data_type": data_type,
        "rows": rows,
        "first_date": first,
        "last_date": last,
        "core_missing_rate": round(float(core_missing), 6),
        "anomalies": int(anomalies),
        "grade": grade,
        "reasons": "；".join(reasons) if reasons else "",
    }


def assess_catalog(catalog: Dict[str, pd.DataFrame],
                   settings: dict,
                   data_types: Optional[Iterable[str]] = None) -> pd.DataFrame:
    """评估整个目录，返回合并的质量评估表"""
    types = list(data_types) if data_types else list(catalog.keys())
    frames = []
    for t in types:
        if t not in catalog:
            continue
        df = catalog[t]
        frames.append(assess_table(t, df, settings))
    if not frames:
        return pd.DataFrame()
    return pd.concat(frames, ignore_index=True)


def worst_grade_by_stock(assessment: pd.DataFrame) -> pd.DataFrame:
    """每只股票的最差质量等级（跨数据源）"""
    if assessment.empty:
        return pd.DataFrame(columns=["stock_code", "worst_grade", "worst_types", "rows"])
    grade_order = {"A": 0, "B": 1, "C": 2, "D": 3}
    sub = assessment.copy()
    sub["_rank"] = sub["grade"].map(grade_order).fillna(3)
    idx = sub.groupby("stock_code")["_rank"].idxmax()
    result = sub.loc[idx, ["stock_code", "grade", "data_type", "reasons"]].rename(
        columns={"grade": "worst_grade", "data_type": "worst_types"}
    )
    counts = sub.groupby("stock_code").size().rename("rows")
    result = result.join(counts, on="stock_code")
    return result.reset_index(drop=True)


def load_latest_quality_labels(db_path=None) -> pd.DataFrame:
    """读取 qcfp_data_quality_audit 中最新审计日期的质量标签

    Returns DataFrame: stock_code, data_type, grade
    """
    from ..common.db import connect
    conn = connect(db_path)
    try:
        df = pd.read_sql_query(
            """SELECT DISTINCT q.stock_code, q.data_type, q.grade
               FROM qcfp_data_quality_audit q
               JOIN (SELECT stock_code, data_type, MAX(update_time) AS mt
                     FROM qcfp_data_quality_audit GROUP BY stock_code, data_type) m
                 ON q.stock_code = m.stock_code AND q.data_type = m.data_type
                AND q.update_time = m.mt
               ORDER BY q.stock_code, q.data_type""",
            conn,
        )
    finally:
        conn.close()
    return df


QUALITY_GATE_CHECKS = (
    "missingness", "duplicate", "timestamp", "available_date",
    "price_continuity", "corporate_action", "volume_anomaly",
    "suspension", "outlier", "schema", "source_version",
)

# PWC-1（第 2 项）：Critical Checks——缺失/None → UNKNOWN（≠PASS）
CRITICAL_QUALITY_CHECKS = {
    "available_date", "price_continuity", "suspension",
    "schema", "source_version",
}


class DataQualityGateError(ValueError):
    pass


def data_quality_gate(checks: dict) -> dict:
    """数据质量硬门禁（29 号 / PWC-1 第 2 项：绝对 Fail-Closed）。

    checks：{检查名: True(异常)/False(明确正常)/None·缺失(UNKNOWN)}。
    状态模型 PASS / DEGRADED / BLOCK / UNKNOWN：
        critical FAIL (True)            → BLOCK
        critical UNKNOWN (None/缺失)     → UNKNOWN（≠PASS）
        non-critical anomaly            → DEGRADED
        全部明确 PASS                    → PASS
    """
    blocked = [k for k in CRITICAL_QUALITY_CHECKS
               if checks.get(k) is True]
    unknown = [k for k in CRITICAL_QUALITY_CHECKS
               if k not in checks or checks.get(k) is None]
    degraded = [k for k in QUALITY_GATE_CHECKS
                if k not in CRITICAL_QUALITY_CHECKS
                and checks.get(k) is True]
    if blocked:
        status = "BLOCK"
    elif unknown:
        status = "UNKNOWN"
    elif degraded:
        status = "DEGRADED"
    else:
        status = "PASS"
    return {"status": status, "blocked_checks": blocked,
            "degraded_checks": degraded, "unknown_checks": unknown,
            "triggered": blocked + degraded}


def assert_data_quality_gate(checks: dict) -> str:
    """硬门：BLOCK → DataQualityGateError（Decision Abort）；
    UNKNOWN → SAFE_MODE（no-new-risk / non-certifiable，不是市场清仓）。"""
    g = data_quality_gate(checks)
    if g["status"] == "BLOCK":
        raise DataQualityGateError(
            f"DataQualityGate: BLOCK（{g['blocked_checks']}），"
            f"不允许产生 Trade Decision")
    return g["status"]


def data_health_score(completeness=1.0, accuracy=1.0, timeliness=1.0,
                      consistency=1.0, pit_integrity=1.0,
                      outlier_rate=0.0, duplicate_rate=0.0,
                      source_reliability=1.0,
                      critical_failures=None) -> dict:
    """Data Health Score（11 号）：
        8 维健康度（各 0-1）→ DHS 0-100
        DHS ≥ 95 NORMAL / 90–95 CAUTION / 80–90 DEGRADED / <80 BLOCK

    硬规则：关键字段失败 → 直接 BLOCK（不平均分稀释）。
    """
    critical = critical_failures or []
    if critical:
        return {"score": round(
            min(79.0, 100.0 * min(completeness, accuracy,
                                  timeliness, consistency,
                                  pit_integrity, source_reliability)), 1),
            "status": "BLOCK",
            "critical_failures": critical,
            "dimensions": {"completeness": round(float(completeness), 3),
                           "accuracy": round(float(accuracy), 3),
                           "timeliness": round(float(timeliness), 3),
                           "consistency": round(float(consistency), 3),
                           "pit_integrity": round(float(pit_integrity), 3),
                           "outlier_rate": round(float(outlier_rate), 4),
                           "duplicate_rate": round(float(duplicate_rate), 4),
                           "source_reliability":
                               round(float(source_reliability), 3)},
            "hard_blocked": True}
    outlier_penalty = max(0.0, 1.0 - float(outlier_rate or 0.0) * 10)
    dup_penalty = max(0.0, 1.0 - float(duplicate_rate or 0.0) * 20)
    score = 100.0 * (
        float(completeness) * 0.20 + float(accuracy) * 0.20
        + float(timeliness) * 0.15 + float(consistency) * 0.10
        + float(pit_integrity) * 0.15 + outlier_penalty * 0.05
        + dup_penalty * 0.05 + float(source_reliability) * 0.10)
    score = max(0.0, min(100.0, score))
    if score >= 95:
        status = "NORMAL"
    elif score >= 90:
        status = "CAUTION"
    elif score >= 80:
        status = "DEGRADED"
    else:
        status = "BLOCK"
    return {"score": round(score, 1), "status": status,
            "critical_failures": [],
            "dimensions": {"completeness": round(float(completeness), 3),
                           "accuracy": round(float(accuracy), 3),
                           "timeliness": round(float(timeliness), 3),
                           "consistency": round(float(consistency), 3),
                           "pit_integrity": round(float(pit_integrity), 3),
                           "outlier_rate": round(float(outlier_rate), 4),
                           "duplicate_rate": round(float(duplicate_rate), 4),
                           "source_reliability":
                               round(float(source_reliability), 3)},
            "hard_blocked": False}


def evidence_quality_contract(pit_valid=None, coverage=None,
                              staleness_hours=None, missing_rate=None,
                              source_consistent=None,
                              corporate_action_status="OK") -> dict:
    """Evidence Quality Contract（22 号）：
        七维 → QUALITY_GRADE A/B/C/D/UNKNOWN → Governance Cap 缩放。

    A=正常参与 / B=降低仓位上限 / C=禁止新增风险 /
    D=不生成正式交易决策 / UNKNOWN=Fail Closed。
    """
    unknown = [k for k, v in {
        "pit_valid": pit_valid, "coverage": coverage,
        "staleness": staleness_hours, "missing_rate": missing_rate,
        "source_consistent": source_consistent}.items()
        if v is None]
    if unknown:
        return {"grade": "UNKNOWN", "cap_scale": 0.0,
                "unknown_fields": unknown,
                "new_risk_allowed": False,
                "decision_allowed": False}
    bad = []
    if not pit_valid:
        bad.append("PIT_INVALID")
    if corporate_action_status != "OK":
        bad.append("CORPORATE_ACTION_ISSUE")
    if not source_consistent:
        bad.append("SOURCE_INCONSISTENT")
    if bad:
        return {"grade": "D", "cap_scale": 0.0,
                "unknown_fields": [], "reasons": bad,
                "new_risk_allowed": False, "decision_allowed": False}
    if float(missing_rate or 0.0) > 0.20 \
            or float(staleness_hours or 0.0) > 48 \
            or float(coverage or 0.0) < 0.7:
        return {"grade": "C", "cap_scale": 0.0,
                "unknown_fields": [], "reasons": ["CRITICAL_DEGRADATION"],
                "new_risk_allowed": False, "decision_allowed": True}
    if float(missing_rate or 0.0) > 0.10 \
            or float(staleness_hours or 0.0) > 24 \
            or float(coverage or 0.0) < 0.85:
        return {"grade": "B", "cap_scale": 0.6,
                "unknown_fields": [], "reasons": ["DEGRADED"],
                "new_risk_allowed": True, "decision_allowed": True}
    return {"grade": "A", "cap_scale": 1.0, "unknown_fields": [],
            "reasons": [], "new_risk_allowed": True,
            "decision_allowed": True}
