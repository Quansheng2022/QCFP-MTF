# coding: utf-8
"""Data Lineage 测试（31 号：全链路数据血缘）"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[4]
CORE_DIR = PROJECT_ROOT / "Core"
if str(CORE_DIR) not in sys.path:
    sys.path.insert(0, str(CORE_DIR))

from QCFP_MTF.data.lineage import (DataLineage, build_lineage,
                                   feature_lineage, lineage_hash,
                                   lineage_to_md)


def test_build_lineage_chain():
    lineage = build_lineage(
        "01951_2026-08-21", "01951", "2026-08-21",
        raw_sources=[("hk_hist_institutional_holdings", "hkex/ccass",
                      "snap1", "2026-06-30", "A")],
        transforms=[("qcfp_quarterly_structural", "p1_v48",
                     ("hk_hist_institutional_holdings",))],
        indicators=[("structural_regime", "v48",
                     ("qcfp_quarterly_structural",))],
        features=[("institutional_permission", "v48",
                   ("structural_regime",))])
    assert isinstance(lineage, DataLineage)
    assert len(lineage.nodes) == 4
    assert lineage.lineage_hash
    kinds = [n.kind for n in lineage.to_chain()]
    assert kinds == ["raw", "transformation", "indicator", "feature"]


def test_lineage_hash_deterministic():
    a = build_lineage("d1", "01951", "2026-08-21",
                      raw_sources=[("t", "s", "snap", "2026-06-30", "A")])
    b = build_lineage("d1", "01951", "2026-08-21",
                      raw_sources=[("t", "s", "snap", "2026-06-30", "A")])
    assert a.lineage_hash == b.lineage_hash
    assert lineage_hash(a.nodes) == a.lineage_hash


def test_lineage_to_md():
    lineage = build_lineage("d1", "01951", "2026-08-21",
                            raw_sources=[("t", "s", "snap", "d", "A")])
    md = lineage_to_md(lineage)
    assert "Data Lineage" in md
    assert "lineage_hash" in md


def test_feature_lineage_42():
    chain = [
        ("raw", "weekly_price", "vendor_x", "v3", "2026-08-21T00:00:00",
         "2026-08-21", "raw_load", "1.0"),
        ("transformation", "wave_features_v3", "vendor_x", "v3",
         "2026-08-21T00:00:00", "2026-08-21", "wave_feature_engine",
         "v48"),
        ("feature", "wave_opportunity", "vendor_x", "v3",
         "2026-08-21T00:00:00", "2026-08-21", "wave_opportunity_v2",
         "v1"),
    ]
    fl = feature_lineage("final_target", chain)
    assert fl["source_id"] == "vendor_x"
    assert fl["source_version"] == "v3"
    assert fl["available_at"] == "2026-08-21"
    assert len(fl["nodes"]) == 3
    assert fl["lineage_hash"]
