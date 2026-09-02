# coding: utf-8
"""证据等级标注测试"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[3]
CORE_DIR = PROJECT_ROOT / "Core"
if str(CORE_DIR) not in sys.path:
    sys.path.insert(0, str(CORE_DIR))

from QCFP_MTF.data.evidence import annotate, get_evidence_level


def test_direct_a():
    assert get_evidence_level("inst_ownership_pct_chg") == "A"
    assert get_evidence_level("holder_quantity_chg_pct") == "A"


def test_derived_downgrade():
    assert get_evidence_level("q_inst_flow_raw", source="direct") == "A"
    assert get_evidence_level("q_inst_flow_raw", source="derived") == "A-"


def test_behavioral_b():
    assert get_evidence_level("m_turnover_zscore") == "B"
    assert get_evidence_level("m_vp_regime") == "B"


def test_tactical_c():
    assert get_evidence_level("tactical_signal") == "C"
    assert get_evidence_level("w_breakout") == "C"


def test_model_d():
    assert get_evidence_level("cbi_score") == "D"
    assert get_evidence_level("mtf_regime") == "D"


def test_annotate():
    df = annotate(["inst_ownership_pct_chg", "q_inst_flow_raw"],
                  source_map={"q_inst_flow_raw": "derived"})
    assert len(df) == 2
    assert df.iloc[1]["evidence_level"] == "A-"


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print(f"PASS {name}")
    print("test_evidence 全部通过 ✅")
