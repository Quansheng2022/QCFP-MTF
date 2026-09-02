# coding: utf-8
"""Research Experiment Registry 测试（39 号）"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[4]
CORE_DIR = PROJECT_ROOT / "Core"
if str(CORE_DIR) not in sys.path:
    sys.path.insert(0, str(CORE_DIR))

from QCFP_MTF.ablation.statistical import ExperimentRegistry, \
    statistical_validation


def test_register_research_full():
    reg = ExperimentRegistry()
    r = statistical_validation([0.0] * 10, [0.05] * 10, n_perm=100)
    reg.register_research(
        "EXP-00231", "Permission 降低错误交易", "Wave Only",
        "Wave+Permission", "HK 2020-2026", pit_grade="B",
        oos_window="2023-2026", statistical_test="permutation",
        selection_rule="best_ci", result=r)
    e = reg.get("EXP-00231")
    assert e is not None
    assert e["hypothesis"] == "Permission 降低错误交易"
    assert e["pit_grade"] == "B"
    assert e["oos_window"] == "2023-2026"
    rep = reg.report()
    assert rep["experiment_count"] == 1
    assert rep["research_records"][0]["experiment_id"] == "EXP-00231"


def test_assert_registered_enforcement():
    reg = ExperimentRegistry()
    try:
        reg.assert_registered("EXP-NOPE")
        raise AssertionError("should raise")
    except ValueError as exc:
        assert "UnregisteredExperiment" in str(exc)
    reg.register_research("EXP-OK", "h", "b", "t", "d")
    reg.assert_registered("EXP-OK")   # 不抛错


def test_existing_register_compat():
    reg = ExperimentRegistry()
    reg.register("e1", "v2", "best_ci", "oos_2024")
    assert reg.count() == 1


def test_register_research_full_36():
    reg = ExperimentRegistry()
    reg.register_research(
        "EXP-0036", "假设", "b", "t", "ds", pit_grade="B",
        pit_specification="disclosure_lag_45d", feature_version="v48",
        parameter_space={"lookback": [10, 20]}, train_period="2020-2023",
        validation_period="2023-2024", oos_window="2025-2026",
        cost_model="BASE", execution_model="T+1",
        ablation_definition="Full-NoPermission", promotion_status="research")
    e = reg.get("EXP-0036")
    assert e["pit_specification"] == "disclosure_lag_45d"
    assert e["parameter_space"] == {"lookback": [10, 20]}
    assert e["train_period"] == "2020-2023"
    assert e["execution_model"] == "T+1"
    assert e["promotion_status"] == "research"


def test_holdout_lock_37():
    reg = ExperimentRegistry()
    reg.register_research("EXP-0037", "h", "b", "t", "ds")
    r = reg.holdout_lock("EXP-0037", "2025-2026", used_in_selection=True)
    assert r["ok"] is False
    r2 = reg.holdout_lock("EXP-0037", "2026-2027", used_in_selection=False)
    assert r2["ok"] is True
    assert reg.get("EXP-0037")["oos_window"] == "2026-2027"
    assert reg.get("EXP-0037")["holdout_locked"] is True
