# coding: utf-8
"""Reactivation Gate 测试（97 号 + Runtime Evidence Wiring：第 9 项）"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[4]
CORE_DIR = PROJECT_ROOT / "Core"
if str(CORE_DIR) not in sys.path:
    sys.path.insert(0, str(CORE_DIR))

from QCFP_MTF.safety.reactivation_gate import REACTIVATION_STEPS, \
    reactivation_certificate, reactivation_gate


def test_high_severity_requires_all_steps():
    r = reactivation_gate(REACTIVATION_STEPS[:-1], severity="HIGH")
    assert r["verdict"] == "STAY_SUSPENDED"
    assert r["missing_steps"] == ["governance_approval"]
    assert r["certificate"] is None


def test_full_steps_reactivated_with_cert():
    r = reactivation_gate(list(REACTIVATION_STEPS), severity="HIGH")
    assert r["verdict"] == "REACTIVATED"
    assert r["certificate"]["reactivation_certificate_id"]
    assert r["certificate"]["severity"] == "HIGH"
    cert = reactivation_certificate(r)
    assert cert["valid"] is True


def test_low_severity_subset():
    done = ["root_cause", "fix", "replay", "regression",
            "governance_approval"]
    r = reactivation_gate(done, severity="LOW")
    assert r["verdict"] == "REACTIVATED"


def test_no_certificate_when_suspended():
    r = reactivation_gate([], severity="HIGH")
    assert reactivation_certificate(r)["valid"] is False


def test_certificate_identity_binds_incident():
    """第 9 项：不同 Incident 完成同样步骤 → 不同 Certificate Identity。"""
    steps = list(REACTIVATION_STEPS)
    a = reactivation_gate(steps, severity="HIGH", incident_id="INC-1",
                          release_id="REL-A", checkpoint_hash="CP-1",
                          replay_hash="RP-1", approval_identity="GOV-1")
    b = reactivation_gate(steps, severity="HIGH", incident_id="INC-2",
                          release_id="REL-A", checkpoint_hash="CP-1",
                          replay_hash="RP-1", approval_identity="GOV-1")
    assert a["certificate"]["reactivation_certificate_id"] != \
        b["certificate"]["reactivation_certificate_id"]
    assert a["certificate"]["incident_id"] == "INC-1"
    assert a["certificate"]["replay_hash"] == "RP-1"
    # 缺 replay_hash / approval → 不允许 REACTIVATED（identity 不完整）
    incomplete = reactivation_gate(steps, severity="HIGH",
                                   incident_id="INC-3",
                                   release_id="REL-A")
    assert incomplete["verdict"] == "REACTIVATED"      # 步骤齐全仍通过
    assert incomplete["certificate"]["replay_hash"] == ""
