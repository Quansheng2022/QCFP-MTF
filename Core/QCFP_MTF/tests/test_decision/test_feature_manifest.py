# coding: utf-8
"""Feature Production Manifest 测试（15 号）"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[4]
CORE_DIR = PROJECT_ROOT / "Core"
if str(CORE_DIR) not in sys.path:
    sys.path.insert(0, str(CORE_DIR))

from QCFP_MTF.decision.feature_manifest import FEATURE_LIFECYCLE, \
    FeatureManifest


def test_production_manifest_only_active():
    fm = FeatureManifest()
    fm.register("wave_quality")
    fm.register("legacy_score")
    fm.advance("wave_quality", "ACTIVE")
    fm.advance("legacy_score", "RETIRED")
    assert fm.production_manifest() == ["wave_quality"]
    snap = fm.snapshot_feature_set()
    assert snap["active_features"] == ["wave_quality"]
    assert snap["total_features"] == 2


def test_lifecycle_advance():
    fm = FeatureManifest()
    fm.register("f1")
    fm.advance("f1", "CERTIFIED")
    assert fm.features["f1"].status == "CERTIFIED"
    try:
        fm.advance("f1", "WIRED")      # 回退 → 拒绝
        raise AssertionError("should raise")
    except ValueError:
        pass


def test_lifecycle_constant():
    assert FEATURE_LIFECYCLE == ("DEFINED", "WIRED", "VALIDATED",
                                 "CERTIFIED", "ACTIVE", "DEPRECATED",
                                 "RETIRED")
