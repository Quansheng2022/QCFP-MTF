# coding: utf-8
"""Statistical Validation Layer 测试（29 号）"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[4]
CORE_DIR = PROJECT_ROOT / "Core"
if str(CORE_DIR) not in sys.path:
    sys.path.insert(0, str(CORE_DIR))

from QCFP_MTF.ablation.statistical import (ExperimentRegistry,
                                           statistical_validation,
                                           validation_to_md)


def test_statistical_validation_significant():
    base = [0.01, 0.02, 0.0, 0.01, 0.02, 0.0, 0.01, 0.02]
    treat = [0.06, 0.07, 0.05, 0.06, 0.08, 0.05, 0.07, 0.06]
    r = statistical_validation(base, treat, experiment_id="wave_test",
                               n_perm=200, seed=42)
    assert r.delta > 0
    assert r.sample_size == 8
    assert r.ci_low > 0 or r.ci_high < 0
    assert r.p_value < 0.05
    assert r.verdict == "SIGNIFICANT"


def test_statistical_validation_not_significant():
    base = [0.01, 0.02, 0.0, 0.01, 0.02, 0.0]
    treat = [0.011, 0.021, 0.001, 0.012, 0.019, 0.002]
    r = statistical_validation(base, treat, n_perm=200, seed=42)
    assert r.verdict != "SIGNIFICANT"


def test_multiple_testing_alpha_shrink():
    base = [0.01] * 10
    treat = [0.05] * 10
    r1 = statistical_validation(base, treat, n_experiments=1, n_perm=100)
    r20 = statistical_validation(base, treat, n_experiments=20, n_perm=100)
    assert r20.alpha_effective < r1.alpha_effective


def test_experiment_registry():
    reg = ExperimentRegistry()
    r = statistical_validation([0.0] * 10, [0.06] * 10, n_perm=100)
    reg.register("exp1", "v2", "best_ci", "oos_2024", r)
    rep = reg.report()
    assert rep["experiment_count"] == 1
    assert rep["candidate_count"] == 1
    assert reg.check_selection_bias()["risk"] == "LOW"


def test_registry_bias_warning():
    reg = ExperimentRegistry()
    for i in range(10):
        reg.register(f"e{i}", f"v{i}", "best", "oos")
    bias = reg.check_selection_bias()
    assert bias["risk"] in ("MEDIUM", "HIGH")


def test_validation_to_md():
    r = statistical_validation([0.0] * 10, [0.05] * 10, n_perm=100)
    md = validation_to_md(r)
    assert "Statistical Validation" in md
