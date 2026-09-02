# coding: utf-8
"""Causal Evidence Level 测试（43 号）"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[4]
CORE_DIR = PROJECT_ROOT / "Core"
if str(CORE_DIR) not in sys.path:
    sys.path.insert(0, str(CORE_DIR))

from QCFP_MTF.research.causal_evidence import EVIDENCE_LEVELS, \
    causal_evidence_level


def test_evidence_levels():
    assert causal_evidence_level()["level"] == "L0_observation"
    assert causal_evidence_level(oos_consistent=True)[
        "level"] == "L2_conditional"
    assert causal_evidence_level(oos_consistent=True,
                                 ablation_ok=True)["level"] == "L3_robust_oos"
    assert causal_evidence_level(oos_consistent=True, ablation_ok=True,
                                 counterfactual_ok=True,
                                 matched_sample_ok=True)[
        "level"] == "L4_quasi_causal"
    assert causal_evidence_level(oos_consistent=True, ablation_ok=True,
                                 counterfactual_ok=True,
                                 matched_sample_ok=True,
                                 mechanism_supported=True)[
        "level"] == "L5_causal_supported"


def test_wording():
    r = causal_evidence_level(oos_consistent=True, ablation_ok=True)
    assert "条件相关" in r["recommended_wording"]
    assert EVIDENCE_LEVELS[0] == "L0_observation"
