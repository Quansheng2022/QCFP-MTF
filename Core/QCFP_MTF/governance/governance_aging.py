# coding: utf-8
"""Governance Aging Review（QCFP-MTF 2.8：81 号治理老化审查）

防止规则"历史正确、现在失效"。每个 ACTIVE 核心规则保存：
    certified_at / last_revalidated_at / evidence_window /
    current_status / next_review_due

重点：Permission 风险削减价值、Wave Stage 区分度、
Liquidity 假设、Cost/Slippage 假设是否老化。

验收标准：不能因为"曾经通过认证"就永久 ACTIVE；
长期没有新证据支持的模块进入 REVALIDATE / REVIEW / RETIRE。
"""


AGING_STATUSES = ("ACTIVE", "REVALIDATE", "REVIEW", "RETIRE")


def _ym_to_months(ym: str) -> int:
    try:
        year, month = str(ym).split("-")
        return int(year) * 12 + (int(month) - 1)
    except (ValueError, AttributeError):
        return 0


def _add_months(ym: str, months: int) -> str:
    total = _ym_to_months(ym) + months
    return f"{total // 12:04d}-{total % 12 + 1:02d}"


def governance_aging_review(rules: dict, as_of="2026-08",
                            revalidate_after_months=12,
                            retire_after_months=24) -> dict:
    """rules：{rule: {"certified_at", "last_revalidated_at",
    "evidence_window", "current_status"}}"""
    results = {}
    for rule, attrs in (rules or {}).items():
        attrs = attrs or {}
        last = attrs.get("last_revalidated_at") \
            or attrs.get("certified_at") or as_of
        months = _ym_to_months(as_of) - _ym_to_months(last)
        if months >= retire_after_months:
            status = "RETIRE"
        elif months >= revalidate_after_months:
            status = "REVALIDATE"
        else:
            status = "ACTIVE"
        results[rule] = {
            "certified_at": attrs.get("certified_at"),
            "last_revalidated_at": last,
            "evidence_window": attrs.get("evidence_window"),
            "months_since_revalidation": months,
            "current_status": status,
            "next_review_due": _add_months(
                last, revalidate_after_months),
        }
    return {"results": results,
            "rule": "不能因曾经认证就永久 ACTIVE；"
                    "无新证据 → REVALIDATE/REVIEW/RETIRE"}


def aging_promotion_gate(rules: dict, as_of="2026-08") -> dict:
    """新 81 号：Aging 接到 Release/Promotion——
    到期意味着失去自动续证资格，必须重新拿
    PIT/OOS/Ablation/Stress Evidence。"""
    review = governance_aging_review(rules, as_of=as_of)
    lost_certification = [
        rule for rule, r in review["results"].items()
        if r["current_status"] in ("REVALIDATE", "RETIRE")]
    return {
        "lost_auto_certification": lost_certification,
        "release_verdict": "PROMOTION_BLOCKED" if lost_certification
        else "PROMOTION_OK",
        "allowed": not lost_certification,
        "rule": "2026 年已无人验证的规则不能因 2024 年通过一次测试 "
                "就继续永久 ACTIVE；到期必须重新取证",
    }
