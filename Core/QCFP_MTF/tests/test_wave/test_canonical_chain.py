# coding: utf-8
"""Wave → Canonical Proposal Chain 测试（P0-8 号）"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[4]
CORE_DIR = PROJECT_ROOT / "Core"
if str(CORE_DIR) not in sys.path:
    sys.path.insert(0, str(CORE_DIR))

from QCFP_MTF.wave.canonical import wave_to_canonical


def test_active_full_entry():
    r = wave_to_canonical("ACTIVE", "ALLOW", 0.05, proposed_action="ENTRY")
    assert r["allowed"] is True
    assert r["proposed_target"] == 0.05


def test_discovey_blocked():
    r = wave_to_canonical("DISCOVERY", "ALLOW", 0.05,
                          proposed_action="ENTRY")
    assert r["allowed"] is False
    assert "WAVE_STAGE" in r["blocked_reason"]


def test_mature_scaled():
    r = wave_to_canonical("MATURE", "ALLOW", 0.10,
                          proposed_action="ENTRY")
    assert r["allowed"] is True
    assert r["max_entry_scale"] == 0.5
    assert r["proposed_target"] == 0.05


def test_permission_blocks():
    r = wave_to_canonical("ACTIVE", "BLOCK", 0.05,
                          proposed_action="ENTRY")
    assert r["allowed"] is False
    assert "PERMISSION_BLOCK" in r["blocked_reason"]
