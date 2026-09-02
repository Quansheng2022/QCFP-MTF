# coding: utf-8
"""Research Artifact Bundle Promotion 门测试（新 55 号）"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[4]
CORE_DIR = PROJECT_ROOT / "Core"
if str(CORE_DIR) not in sys.path:
    sys.path.insert(0, str(CORE_DIR))

from QCFP_MTF.research.research_artifact_bundle import \
    freeze_research_bundle, promotion_requires_artifact, \
    verify_reproducible


def _bundle():
    return {"experiment_id": "EXP-1", "hypothesis": "H",
            "results": {"sharpe": 0.7}, "validation_status": None}


def test_candidate_eligible_with_verified_artifact():
    frozen = freeze_research_bundle(_bundle())
    verified = verify_reproducible(frozen, {"sharpe": 0.7})
    experiment = dict(frozen)
    experiment["validation_status"] = verified["validation_status"]
    r = promotion_requires_artifact(experiment)
    assert r["verdict"] == "CANDIDATE_ELIGIBLE"


def test_missing_artifact_blocks_candidate():
    r = promotion_requires_artifact({"experiment_id": "EXP-1",
                                     "results": {"sharpe": 0.7}})
    assert r["verdict"] == "NOT_CANDIDATE_ELIGIBLE"
    assert "RESEARCH_ARTIFACT_ID" in r["missing"]


def test_unverified_blocks_candidate():
    frozen = freeze_research_bundle(_bundle())
    experiment = dict(frozen)
    experiment["validation_status"] = "UNVERIFIED"
    r = promotion_requires_artifact(experiment)
    assert r["verdict"] == "NOT_CANDIDATE_ELIGIBLE"
    assert "REPRODUCIBILITY_VERIFIED" in r["missing"]
