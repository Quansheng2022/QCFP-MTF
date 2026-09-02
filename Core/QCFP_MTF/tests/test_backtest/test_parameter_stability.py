# coding: utf-8
"""Parameter Stability Surface 测试（27 号）"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[4]
CORE_DIR = PROJECT_ROOT / "Core"
if str(CORE_DIR) not in sys.path:
    sys.path.insert(0, str(CORE_DIR))

from QCFP_MTF.backtest.robustness import parameter_stability_surface


def test_stable_plateau():
    sweep = [{"param": p, "sharpe": s} for p, s in
             ((10, 1.0), (12, 1.1), (14, 1.15), (16, 1.18),
              (18, 1.16), (20, 1.12), (22, 1.05))]
    r = parameter_stability_surface(sweep)
    assert r["best_param"] == 16
    assert len(r["stable_region"]) >= 1
    assert r["verdict"] == "STABLE"


def test_peaky_suspect():
    sweep = [{"param": p, "sharpe": s} for p, s in
             ((14, 0.6), (15, 0.7), (16, 0.65), (17, 2.1),
              (18, 0.8), (19, 0.7), (20, 0.6))]
    r = parameter_stability_surface(sweep)
    assert r["best_param"] == 17
    assert r["verdict"] == "PEAKY"
