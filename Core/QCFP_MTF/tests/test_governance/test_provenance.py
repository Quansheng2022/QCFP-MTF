# coding: utf-8
"""Research-to-Production Provenance 测试（90 号）"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[4]
CORE_DIR = PROJECT_ROOT / "Core"
if str(CORE_DIR) not in sys.path:
    sys.path.insert(0, str(CORE_DIR))

from QCFP_MTF.governance.provenance import (ProvenanceError,
                                            ResearchProvenance,
                                            assert_provenance_complete,
                                            provenance_to_md)


def _provenance():
    return ResearchProvenance(
        production_version="QCFP-MTF-2.5.0",
        release_id="REL-001",
        certification="CERTIFIED",
        oos_result={"sharpe": 1.2},
        ablation_result={"wave_alpha": 0.03},
        experiment_id="EXP-0090",
        hypothesis="Wave v4 提供独立增量",
        dataset="HK 2020-2026",
        pit_snapshot="ds_20260821",
        feature_version="v48",
        code_commit="abc123",
        configuration={"threshold": 0.6},
        approved_by="GOVERNANCE_GATE_2026-08-27")


def test_provenance_chain_complete():
    p = _provenance()
    assert_provenance_complete(p)
    assert len(p.chain()) == 13
    assert p.chain()[0] == ("production_version", "QCFP-MTF-2.5.0")


def test_provenance_missing_raises():
    p = ResearchProvenance(production_version="V", release_id="")
    try:
        assert_provenance_complete(p)
        raise AssertionError("should raise")
    except ProvenanceError:
        pass


def test_provenance_to_md():
    md = provenance_to_md(_provenance())
    assert "Research-to-Production Provenance" in md
    assert "REL-001" in md
