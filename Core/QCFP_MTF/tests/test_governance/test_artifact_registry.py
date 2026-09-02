# coding: utf-8
"""Release / Artifact Registry 测试（P1-6 号）"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[4]
CORE_DIR = PROJECT_ROOT / "Core"
if str(CORE_DIR) not in sys.path:
    sys.path.insert(0, str(CORE_DIR))

from QCFP_MTF.governance.artifact_registry import ArtifactRegistry, \
    ReleaseArtifact


def _artifact():
    return ReleaseArtifact(
        release_id="REL-001", git_commit="abc123", code_hash="ch1",
        model_version="M2.5", rule_version="R2.5", config_hash="cfg1",
        schema_version="S1", feature_manifest="fm1",
        data_snapshot_id="ds1", execution_version="e1",
        test_manifest="tm1", oos_artifact="oos1",
        ablation_artifact="abl1", replay_artifact="rep1",
        certification_artifact="cert1")


def test_release_hash_deterministic():
    assert _artifact().release_hash() == _artifact().release_hash()
    assert len(_artifact().release_hash()) == 16


def test_artifact_registry():
    reg = ArtifactRegistry()
    reg.register(_artifact())
    assert reg.verify_release_hash("REL-001")["verified"] is True
    assert reg.verify_release_hash("NOPE")["verified"] is False


def test_release_artifact_fields():
    d = _artifact().as_dict()
    assert d["git_commit"] == "abc123"
    assert d["certification_artifact"] == "cert1"
    assert "release_hash" in d
