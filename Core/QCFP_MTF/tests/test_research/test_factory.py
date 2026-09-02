# coding: utf-8
"""Research Experiment Factory 测试（19 号）"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[4]
CORE_DIR = PROJECT_ROOT / "Core"
if str(CORE_DIR) not in sys.path:
    sys.path.insert(0, str(CORE_DIR))

from QCFP_MTF.ablation.statistical import ExperimentRegistry
from QCFP_MTF.research.factory import ExperimentSpec, \
    ResearchExperimentFactory


def test_factory_create_and_report():
    reg = ExperimentRegistry()
    f = ResearchExperimentFactory(registry=reg)
    spec = ExperimentSpec(
        experiment_id="EXP-F1", hypothesis="Wave 阈值 0.75 更好",
        dataset="HK 2020-2026", pit_grade="B", baseline="thr_0.70",
        treatment="thr_0.75", parameter_space={"threshold": [0.7, 0.75]},
        cost_model="BASE", execution_model="T+1")
    f.create(spec)
    f.record_metrics("EXP-F1", {"sharpe": 1.3, "return": 0.10})
    f.record_artifact("EXP-F1", "oos", "Report/oos.json")
    f.finalize("EXP-F1")
    r = f.report("EXP-F1")
    assert r["status"] == "completed"
    assert r["metrics"]["sharpe"] == 1.3
    assert r["artifacts"]["oos"] == "Report/oos.json"
    # 注册表同步
    assert reg.get("EXP-F1") is not None
    assert reg.get("EXP-F1")["hypothesis"] == "Wave 阈值 0.75 更好"


def test_factory_duplicate_rejected():
    f = ResearchExperimentFactory()
    spec = ExperimentSpec(experiment_id="EXP-F2", hypothesis="h")
    f.create(spec)
    try:
        f.create(spec)
        raise AssertionError("should raise")
    except ValueError:
        pass
