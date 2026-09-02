# coding: utf-8
"""Feature Registry 测试（12 号）"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[4]
CORE_DIR = PROJECT_ROOT / "Core"
if str(CORE_DIR) not in sys.path:
    sys.path.insert(0, str(CORE_DIR))

from QCFP_MTF.data.feature_registry import FeatureMeta, FeatureRegistry


def _meta():
    return FeatureMeta(
        feature_id="WAVE_QUALITY_SCORE", feature_name="Wave 质量分",
        definition="多因子 Wave 质量", source="weekly_kline",
        source_table="hk_hist_weekly_kline", source_column="close",
        calculation="EMA+Volume+Turnover", frequency="weekly",
        available_at="T+1", lookback="60D", pit_grade="A",
        transform_version="FEATURE-2.3", owner="wave_team",
        status="production")


def test_feature_registry():
    reg = FeatureRegistry()
    reg.register(_meta())
    f = reg.get("WAVE_QUALITY_SCORE")
    assert f.source == "weekly_kline"
    assert f.pit_grade == "A"
    assert f.transform_version == "FEATURE-2.3"
    assert reg.by_status("production") == ["WAVE_QUALITY_SCORE"]
    assert reg.pit_grade_summary() == {"A": 1}


def test_feature_registry_report():
    reg = FeatureRegistry()
    reg.register(_meta())
    r = reg.registry_report()
    assert r["n_features"] == 1
    assert "WAVE_QUALITY_SCORE" in r["features"]
