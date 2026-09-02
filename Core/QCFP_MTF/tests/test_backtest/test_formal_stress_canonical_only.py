# coding: utf-8
"""Formal Stress Canonical-Only 静态扫描（PWC-1 第 8 项）"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[4]
CORE_DIR = PROJECT_ROOT / "Core"
if str(CORE_DIR) not in sys.path:
    sys.path.insert(0, str(CORE_DIR))


def test_cost_stress_uses_canonical_api():
    src = (Path(CORE_DIR) / "QCFP_MTF" / "scripts" /
           "cost_stress_test.py").read_text(encoding="utf-8")
    assert "run_canonical_stress" in src
    assert "build_signal_timeline" not in src
    assert "run_backtest(" not in src
