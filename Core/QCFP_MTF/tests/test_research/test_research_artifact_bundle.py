# coding: utf-8
"""Research Artifact Bundle 测试（55 号：研究制品包）"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[4]
CORE_DIR = PROJECT_ROOT / "Core"
if str(CORE_DIR) not in sys.path:
    sys.path.insert(0, str(CORE_DIR))

from QCFP_MTF.research.research_artifact_bundle import \
    freeze_research_bundle, verify_reproducible


def _bundle():
    return {
        "experiment_id": "EXP-001",
        "hypothesis": "Permission Gate 降低坏暴露",
        "code_commit": "abc123",
        "config": {"permission_cap": 0.2},
        "dataset_snapshot": "ds-2026Q2",
        "universe_snapshot": "uni-2026Q2",
        "random_seed": 42,
        "metric_contract": {"sharpe": ">=0", "mdd": ">-0.3"},
        "results": {"sharpe": 0.71, "mdd": -0.12},
        "plots": ["p1.png"],
        "validation_status": None,
    }


def test_freeze_generates_unique_id():
    f = freeze_research_bundle(_bundle())
    assert f["research_artifact_id"]
    assert f["frozen"] is True
    assert f["validation_status"] == "UNVERIFIED"


def test_freeze_deterministic_id():
    f1 = freeze_research_bundle(_bundle())
    f2 = freeze_research_bundle(_bundle())
    assert f1["research_artifact_id"] == f2["research_artifact_id"]


def test_verify_reproducible():
    f = freeze_research_bundle(_bundle())
    ok = verify_reproducible(f, {"sharpe": 0.71, "mdd": -0.12})
    assert ok["validation_status"] == "VERIFIED"
    bad = verify_reproducible(f, {"sharpe": 0.40})
    assert bad["validation_status"] == "UNVERIFIED"
    assert bad["reproducible"] is False
