# coding: utf-8
"""ReleaseManifest 测试（31 号）"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[4]
CORE_DIR = PROJECT_ROOT / "Core"
if str(CORE_DIR) not in sys.path:
    sys.path.insert(0, str(CORE_DIR))

from QCFP_MTF.governance.release_manifest import (ReleaseManifest,
                                                  ReleaseManifestRegistry)


def _manifest(config="cfg1", commit="abc", release="REL-1"):
    return ReleaseManifest(
        release_id=release, strategy_version="S1", engine_version="E1",
        governance_version="GOV-1", config_hash=config,
        feature_manifest_hash="FM1", code_commit=commit,
        data_contract_version="DC1", decision_schema_version="DS1")


def test_manifest_hash_deterministic():
    assert _manifest().manifest_hash() == _manifest().manifest_hash()
    assert len(_manifest().manifest_hash()) == 16


def test_config_drift_detected():
    reg = ReleaseManifestRegistry()
    reg.freeze(_manifest())
    # 相同代码不同 config → 不同 manifest hash
    drifted = _manifest(config="cfg2", commit="abc", release="REL-2")
    assert drifted.manifest_hash() != _manifest().manifest_hash()
    reg.freeze(drifted)
    assert reg.verify_production_identity(_manifest()) is True
    assert reg.verify_production_identity(drifted) is True


def test_implicit_version_conflict_rejected():
    reg = ReleaseManifestRegistry()
    reg.freeze(_manifest())
    # 相同 manifest hash 但不同 release_id → 隐性版本冲突
    same = _manifest(release="REL-WRONG")
    assert same.manifest_hash() == _manifest().manifest_hash()
    try:
        reg.freeze(same)
        raise AssertionError("should raise")
    except ValueError:
        pass
