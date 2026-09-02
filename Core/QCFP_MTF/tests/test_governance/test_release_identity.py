# coding: utf-8
"""ReleaseManifest / ProductionBundle 测试（新 31 号）"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[4]
CORE_DIR = PROJECT_ROOT / "Core"
if str(CORE_DIR) not in sys.path:
    sys.path.insert(0, str(CORE_DIR))

from QCFP_MTF.governance.release_manifest import ReleaseManifest, \
    production_release_identity, release_required_check


def _manifest():
    return ReleaseManifest(
        release_id="REL-001", strategy_version="QCFP-MTF-2.5.0",
        engine_version="canonical-2.8", governance_version="GOV-2.5.0",
        config_hash="cfg1", feature_manifest_hash="fm1",
        code_commit="abc123", data_contract_version="1.0",
        decision_schema_version="DECISION-1.1")


def test_production_release_identity():
    ident = production_release_identity(_manifest())
    assert ident["release_id"] == "REL-001"
    assert ident["manifest_hash"]
    assert "ReleaseManifest" in ident["chain"]


def test_release_required_certified():
    r = release_required_check({"decision_id": "d1",
                                "release_id": "REL-001"})
    assert r["certification"] == "CERTIFIED"
    assert r["certified"] is True


def test_release_missing_not_certified():
    r = release_required_check({"decision_id": "d1"})
    assert r["certification"] == "NOT_CERTIFIED"
    assert r["certified"] is False


def test_release_in_context():
    r = release_required_check({"decision_id": "d1",
                                "context": {"release_id": "REL-002"}})
    assert r["certified"] is True
