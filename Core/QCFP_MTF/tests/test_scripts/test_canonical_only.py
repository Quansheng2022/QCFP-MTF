# coding: utf-8
"""Canonical-only 门测试（P0-1 号）"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[4]
CORE_DIR = PROJECT_ROOT / "Core"
if str(CORE_DIR) not in sys.path:
    sys.path.insert(0, str(CORE_DIR))

from QCFP_MTF.scripts.backtest_runner import canonical_only_gate


def test_canonical_default_allowed():
    ok, mode = canonical_only_gate("canonical")
    assert ok is True
    assert mode == "canonical"
    ok, mode = canonical_only_gate(None)      # 缺省 → canonical
    assert ok is True and mode == "canonical"


def test_legacy_requires_shadow_comparator():
    ok, reason = canonical_only_gate("legacy", shadow_comparator=False)
    assert ok is False
    assert reason == "legacy_requires_shadow_comparator"
    ok, mode = canonical_only_gate("legacy", shadow_comparator=True)
    assert ok is True
    assert mode == "legacy_shadow_comparator"


def test_unknown_engine_rejected():
    ok, reason = canonical_only_gate("mystery")
    assert ok is False
    assert reason.startswith("unknown_engine")
