# coding: utf-8
"""Ablation Matrix 测试（28 号）"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[4]
CORE_DIR = PROJECT_ROOT / "Core"
if str(CORE_DIR) not in sys.path:
    sys.path.insert(0, str(CORE_DIR))

from QCFP_MTF.ablation.matrix import ablation_matrix, incremental_check, \
    matrix_to_md


def _variants():
    return {
        "Full": {"returns": [0.02, -0.01, 0.03, 0.01, -0.005, 0.02],
                 "turnover": 1.0, "mfe_capture": 0.7, "mae": -0.03,
                 "capital_utilization": 0.4},
        "No Permission": {"returns": [0.05, -0.08, 0.07, -0.06, 0.02,
                                      -0.04],
                          "turnover": 2.0, "mfe_capture": 0.9,
                          "mae": -0.10, "capital_utilization": 0.9},
        "No Wave": {"returns": [0.01, 0.0, 0.01, -0.01, 0.0, 0.01],
                    "turnover": 0.5, "mfe_capture": 0.3, "mae": -0.01,
                    "capital_utilization": 0.2},
        "No Risk": {"returns": [0.03, -0.05, 0.04, -0.04, 0.01, -0.03],
                    "turnover": 1.5, "mfe_capture": 0.8, "mae": -0.07,
                    "capital_utilization": 0.7},
    }


def test_ablation_matrix():
    m = ablation_matrix(_variants())
    assert m["actual"] == "Full"
    assert set(m["rows"]) == {"Full", "No Permission", "No Wave", "No Risk"}
    assert "No Permission" in m["deltas"]
    # Permission 关闭 → MDD 更差 → Risk Alpha / Loss Avoidance > 0
    assert m["deltas"]["No Permission"]["loss_avoidance_alpha"] > 0


def test_incremental_check():
    m = ablation_matrix(_variants())
    inc = incremental_check(m, pair=("No Permission", "No Risk"))
    assert inc["assessable"] is False or "loss_avoidance" in inc


def test_matrix_to_md():
    md = matrix_to_md(ablation_matrix(_variants()))
    assert "Ablation Matrix" in md
    assert "Return Alpha" in md
