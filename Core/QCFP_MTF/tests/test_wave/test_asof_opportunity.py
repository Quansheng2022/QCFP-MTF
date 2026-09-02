# coding: utf-8
"""AsOfWaveOpportunity / WaveOutcomeLabel 隔离测试（P0-9 号）"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[4]
CORE_DIR = PROJECT_ROOT / "Core"
if str(CORE_DIR) not in sys.path:
    sys.path.insert(0, str(CORE_DIR))

from QCFP_MTF.governance.feature_gate import FeatureGateError
from QCFP_MTF.wave.asof_opportunity import (AsOfWaveOpportunity,
                                            assert_no_outcome_fields)
from QCFP_MTF.wave.outcome_label import WaveOutcomeLabel


def test_asof_opportunity_no_future_fields():
    op = AsOfWaveOpportunity(
        wave_id="W1", stock_code="01951", as_of_date="2024-02-01",
        stage="ACTIVE", strength=0.8, entry_zone_low=9.0,
        entry_zone_high=9.5, invalidation=8.0,
        expected_mfe_band=(0.15, 0.30), expected_mae_band=(-0.08, -0.04),
        expiry="2024-03-01")
    d = op.as_dict()
    for f in ("realized_mfe", "peak_date", "end_date", "capture_ratio"):
        assert f not in d


def test_outcome_fields_blocked():
    try:
        assert_no_outcome_fields({"wave_id": "W1", "realized_mfe": 0.2})
        raise AssertionError("should raise")
    except FeatureGateError:
        pass
    assert_no_outcome_fields({"wave_id": "W1", "strength": 0.8})


def test_outcome_label_future_aware():
    label = WaveOutcomeLabel(wave_id="W1", stock_code="01951",
                             start_date="2024-01-01", peak_date="2024-06-01",
                             realized_mfe=0.25, capture_ratio=0.6)
    assert label.future_aware is True
    assert label.capture_ratio == 0.6
