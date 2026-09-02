# coding: utf-8
"""Release Identity / Version Lock 测试（35 号）"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[4]
CORE_DIR = PROJECT_ROOT / "Core"
if str(CORE_DIR) not in sys.path:
    sys.path.insert(0, str(CORE_DIR))

from QCFP_MTF.decision.release_identity import (ReleaseLockError,
                                                ReleaseRegistry,
                                                build_release_identity)


def test_release_id_deterministic():
    a = build_release_identity("M2.5", "R2.5", config_version="C1",
                               schema_version="S1")
    b = build_release_identity("M2.5", "R2.5", config_version="C1",
                               schema_version="S1")
    assert a.release_id() == b.release_id()
    assert len(a.release_id()) == 16


def test_release_lock_rejects_mismatch():
    reg = ReleaseRegistry()
    approved = build_release_identity("M2.5", "R2.5", config_version="C1")
    reg.approve(approved)
    reg.validate_release_lock(approved)
    bad = build_release_identity("M2.5", "R2.4", config_version="C1")
    try:
        reg.validate_release_lock(bad)
        raise AssertionError("should raise ReleaseLockError")
    except ReleaseLockError:
        pass


def test_release_identity_fields():
    ident = build_release_identity("M", "R", config_version="C",
                                   feature_manifest="FM",
                                   data_snapshot="DS",
                                   execution_version="E")
    d = ident.as_dict()
    assert d["feature_manifest"] == "FM"
    assert d["data_snapshot"] == "DS"
    assert d["execution_version"] == "E"
    assert "release_id" in d
