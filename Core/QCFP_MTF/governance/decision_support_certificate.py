# coding: utf-8
"""Decision Support Qualification Certificate（P1-8）

把证据累计固化成一个可审计的 Certificate：
    certificate_id / release_id / evidence_freeze_id /
    shadow_window / outcome_window / replay / violations /
    maturity / evidence_window_hash / runtime_evidence_chain_hash /
    oos_status / certificate_status

状态：
    QUALIFIED
    QUALIFIED_WITH_OOS_PENDING
    SUSPENDED
    EXPIRED
    NOT_QUALIFIED

OOS 处理（诚实）：默认 OOS 是硬门 → OOS != OOS_PASS 时 NOT_QUALIFIED；
allow_oos_pending=True 才签发 QUALIFIED_WITH_OOS_PENDING（明确区别于
完全证据闭合）。
"""

import hashlib
import json
from datetime import datetime
from pathlib import Path

from ..common.paths import get_report_root


def build_decision_support_certificate(*, release_id, evidence_freeze_id,
                                       shadow, outcome, replay, violations,
                                       evidence_window_hash="",
                                       runtime_evidence_chain_hash="",
                                       oos_status="OOS_NOT_COMPARABLE",
                                       maturity=None,
                                       allow_oos_pending=False,
                                       qualified=False) -> dict:
    """certificate 固化。qualified 来自 Promotion Gate 的
    DECISION_SUPPORT_QUALIFIED 状态判定。"""
    shadow_qualified = (shadow or {}).get("state") == "SHADOW_QUALIFIED"
    ds_state = (shadow or {}).get("state") or ""
    hard_ok = ds_state != "SUSPENDED"
    outcome_ok = int((outcome or {}).get("outcome_qualified_days") or 0) \
        >= int((outcome or {}).get("required_days") or 20)
    replay_ok = bool((replay or {}).get("ok"))
    violations_ok = not any(int(v or 0) > 0 for v in
                            (violations or {}).values())
    oos_ok = str(oos_status or "") == "OOS_PASS"
    base_ok = shadow_qualified and outcome_ok and replay_ok \
        and violations_ok and hard_ok
    if not base_ok:
        status = "SUSPENDED" if ds_state == "SUSPENDED" else "NOT_QUALIFIED"
    elif oos_ok:
        status = "QUALIFIED"
    elif allow_oos_pending:
        status = "QUALIFIED_WITH_OOS_PENDING"
    else:
        status = "NOT_QUALIFIED"
    cert = {
        "certificate_id": hashlib.sha256(
            f"{release_id}|{evidence_freeze_id}|"
            f"{datetime.now():%Y%m%d%H%M%S}".encode("utf-8")
        ).hexdigest()[:16],
        "schema": "DECISION-SUPPORT-CERTIFICATE-1",
        "release_id": release_id,
        "evidence_freeze_id": evidence_freeze_id,
        "qualification_date": datetime.now().strftime("%Y-%m-%d"),
        "shadow_window": {"state": ds_state,
                          "qualified_days":
                              (shadow or {}).get("qualified_days"),
                          "required_days":
                              (shadow or {}).get("required_days")},
        "outcome_window": {"qualified_days":
                           (outcome or {}).get("outcome_qualified_days"),
                           "required_days":
                               (outcome or {}).get("required_days")},
        "replay": {"state": (replay or {}).get("state"),
                   "window_exact_rate":
                       ((replay or {}).get("stats") or {}).get(
                           "window_exact_rate"),
                   "replay_gap_days":
                       ((replay or {}).get("stats") or {}).get(
                           "replay_gap_days")},
        "violations": violations or {},
        "maturity": maturity or {},
        "evidence_window_hash": evidence_window_hash,
        "runtime_evidence_chain_hash": runtime_evidence_chain_hash,
        "oos_status": oos_status,
        "certificate_status": status,
        "rule": "OOS 默认是硬门（OOS_PASS 才 QUALIFIED）；"
                "QUALIFIED_WITH_OOS_PENDING 仅显式 opt-in 且区别于"
                "完全证据闭合",
    }
    return cert


def write_certificate(cert: dict) -> Path:
    out_dir = get_report_root() / "audit" / "runtime_closure"
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / "decision_support_certificate.json"
    path.write_text(json.dumps(cert, ensure_ascii=False, indent=2),
                    encoding="utf-8")
    return path
