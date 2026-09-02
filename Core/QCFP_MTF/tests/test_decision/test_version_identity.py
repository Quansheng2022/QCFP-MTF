# coding: utf-8
"""VersionIdentity 测试（16 号）"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[4]
CORE_DIR = PROJECT_ROOT / "Core"
if str(CORE_DIR) not in sys.path:
    sys.path.insert(0, str(CORE_DIR))

from QCFP_MTF.decision.versions import (MODEL_VERSION,
                                        version_identity)


def test_version_identity_fields():
    vi = version_identity()
    d = vi.as_dict()
    for k in ("model_version", "decision_schema_version",
              "governance_rule_version", "engine_version",
              "commit_hash", "config_hash", "feature_manifest_hash"):
        assert k in d
    assert d["model_version"] == MODEL_VERSION
    assert len(d["feature_manifest_hash"]) == 16


def test_version_identity_singleton():
    assert version_identity() is version_identity()
