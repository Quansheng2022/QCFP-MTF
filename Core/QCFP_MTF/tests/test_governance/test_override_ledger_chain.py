# coding: utf-8
"""Human Override 接 Execution + Ledger 测试（新 61 号）"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[4]
CORE_DIR = PROJECT_ROOT / "Core"
if str(CORE_DIR) not in sys.path:
    sys.path.insert(0, str(CORE_DIR))

from QCFP_MTF.governance.human_override import ALLOWED_OVERRIDE_TYPES, \
    override_ledger_chain, override_permission_boundary


def test_override_ledger_chain_event():
    r = override_ledger_chain(0.20, "OVERRIDE_REDUCE", 0.05,
                              "MANUAL_RISK", 0.05, "trader-a")
    assert r["diverged"] is True
    assert r["override_event_id"]
    assert r["ledger_integrity"] == "OK"


def test_divergence_without_event_integrity_fail():
    r = override_ledger_chain(0.20, "", 0.0, "", 0.05, "op")
    assert r["diverged"] is True
    assert r["ledger_integrity"] == "FAIL"


def test_boundary_blocks_risk_increase():
    r = override_permission_boundary("OVERRIDE_ADD", 0.4, 0.2)
    assert r["allowed"] is False
    r2 = override_permission_boundary("OVERRIDE_EXIT", 0.0, 0.2)
    assert r2["allowed"] is True


def test_override_types_whitelist():
    assert set(ALLOWED_OVERRIDE_TYPES) == {
        "OVERRIDE_SKIP", "OVERRIDE_REDUCE", "OVERRIDE_EXIT",
        "OVERRIDE_HALT"}
