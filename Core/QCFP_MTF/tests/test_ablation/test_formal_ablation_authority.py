# coding: utf-8
"""Formal Ablation Authority 测试（Convergence 新 9A 号）"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[4]
CORE_DIR = PROJECT_ROOT / "Core"
if str(CORE_DIR) not in sys.path:
    sys.path.insert(0, str(CORE_DIR))

from QCFP_MTF.ablation.statistical import formal_ablation_authority


def test_single_formal_authority():
    r = formal_ablation_authority()
    assert r["authority"] == "PAIRED_TIME_SERIES_ABLATION"
    assert r["formal_authority_count"] == 1
    assert r["legacy_certifiable"] is False
    assert r["legacy_permutation"] == "RESEARCH_ARCHIVE"
