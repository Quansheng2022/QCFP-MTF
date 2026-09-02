# coding: utf-8
"""Replay Certification 测试（20 号：指纹链一致性）"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[4]
CORE_DIR = PROJECT_ROOT / "Core"
if str(CORE_DIR) not in sys.path:
    sys.path.insert(0, str(CORE_DIR))

from QCFP_MTF.decision.decision_snapshot import DecisionSnapshot
from QCFP_MTF.decision.replay_cert import (ReplayCert, certify_and_safety,
                                           certify_replay,
                                           ledger_fingerprint)


def _snap(decision_id="01951_2024-02-01", target=0.02):
    return DecisionSnapshot(
        decision_id=decision_id, stock_code="01951",
        decision_date="2024-02-01",
        institutional_state="ACCUMULATION",
        institutional_permission="ALLOW",
        permission_cap="TRADE", exit_event_kind="NONE",
        exit_event_reason="", setup_type="BREAKOUT",
        prev_fsm_state="FLAT", next_fsm_state="TESTING",
        previous_position=0.0, target_position=target,
        participation_mode="EXPLORE", participation_cap=0.10)


def test_certify_verified():
    live = _snap()
    cert = certify_replay("01951_2024-02-01", live, live)
    assert cert.status == "VERIFIED"
    assert len(cert.chain) == 2
    # 未提供 input_fields 时 input_hash 为空（输入指纹需显式字段集）
    assert cert.input_hash == ""
    assert cert.decision_hash


def test_certify_mismatch():
    live = _snap()
    replay = _snap(target=0.10)
    cert = certify_replay("01951_2024-02-01", live, replay)
    assert cert.status == "REPLAY_MISMATCH"
    assert "LIVE_VS_REPLAY_MISMATCH" in cert.reasons


def test_certify_with_ledger():
    live = _snap()
    ledger = {"decision_id": "01951_2024-02-01",
              "stock_code": "01951", "decision_date": "2024-02-01",
              "final_target": 0.02, "institutional_permission": "ALLOW",
              "next_fsm_state": "TESTING", "previous_position": 0.0,
              "raw_target": 0.02, "primary_reason": "NONE",
              "model_version": "", "rule_version": "",
              "schema_version": "", "settings_hash": "",
              "input_fingerprint": "", "feature_manifest_hash": "",
              "participation_mode": "EXPLORE", "participation_cap": 0.10,
              "previous_fsm_state": "FLAT"}
    # ledger 指纹基于字段子集；构造与快照身份一致的 ledger 需要完整字段，
    # 此处只验证 API 契约（指纹函数可调用 + chain 包含 ledger 段）。
    fp = ledger_fingerprint(ledger)
    assert fp
    cert = certify_replay("01951_2024-02-01", live, live,
                          ledger_row=ledger)
    assert len(cert.chain) == 3
    assert cert.ledger_hash == fp


def test_certificate_mismatch_flag():
    live = _snap()
    cert = certify_replay("01951_2024-02-01", live, live,
                          certificate={"wrong": True})
    assert cert.status == "REPLAY_MISMATCH"
    assert "REPLAY_VS_CERTIFICATE_MISMATCH" in cert.reasons


def test_replay_cert_type():
    live = _snap()
    cert = certify_replay("01951_2024-02-01", live, live)
    assert isinstance(cert, ReplayCert)
    assert cert.as_dict()["status"] == "VERIFIED"


def test_certify_and_safety_mismatch_halts():
    live = _snap()
    replay = _snap(target=0.10)
    cert = certify_replay("01951_2024-02-01", live, replay)
    assert cert.status == "REPLAY_MISMATCH"
    r = certify_and_safety(cert)
    assert r["safety_status"] == "HALTED"
    assert "replay_failure" in r["triggered"]


def test_certify_and_safety_verified_keeps_state():
    live = _snap()
    cert = certify_replay("01951_2024-02-01", live, live)
    r = certify_and_safety(cert, checks={"risk_breach": True})
    assert r["safety_status"] == "WARNING"   # 不因 VERIFIED 触发 HALTED
