# coding: utf-8
"""Overfitting Firewall 测试（34 号）"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[4]
CORE_DIR = PROJECT_ROOT / "Core"
if str(CORE_DIR) not in sys.path:
    sys.path.insert(0, str(CORE_DIR))

from QCFP_MTF.research.overfitting_firewall import overfitting_firewall


def test_low_risk():
    r = overfitting_firewall(n_experiments=10, selection_rule="fixed",
                             holdout_locked=True)
    assert r["verdict"] == "LOW"
    assert r["firewall_blocked"] is False


def test_high_snooping():
    r = overfitting_firewall(n_experiments=500, n_parameter_searches=200,
                             selection_rule="best", holdout_locked=False)
    assert r["data_snooping_risk"] >= 0.6
    assert r["verdict"] == "HIGH_SNOOPING"
    assert r["firewall_blocked"] is True


def test_holdout_reduces_risk():
    a = overfitting_firewall(n_experiments=300, selection_rule="best")
    b = overfitting_firewall(n_experiments=300, selection_rule="best",
                             holdout_locked=True)
    assert b["data_snooping_risk"] < a["data_snooping_risk"]
