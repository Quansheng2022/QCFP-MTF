# coding: utf-8
"""Report Snapshot/Ledger-only 测试（新 7 号）"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[4]
CORE_DIR = PROJECT_ROOT / "Core"
if str(CORE_DIR) not in sys.path:
    sys.path.insert(0, str(CORE_DIR))

from QCFP_MTF.config.settings import DEFAULT_SETTINGS
from QCFP_MTF.scripts.dss_report import display_action, position_advice, \
    trade_intent, trade_interpretation


def _override_row():
    return {"action_signal": "REDUCE",
            "align_method": "tactical_override",
            "is_override": True, "target": 0.2,
            "final_target": 0.2, "mtf_regime": "BULLISH_WARNING",
            "risk_level": "High"}


def test_canonical_action_not_rewritten():
    row = _override_row()
    assert trade_intent(row) == "REDUCE"
    assert display_action(row) == "REDUCE"
    assert "Tactical test condition" in trade_interpretation(row)


def test_position_advice_reads_fact_not_recompute():
    row = _override_row()
    assert position_advice(row, DEFAULT_SETTINGS) == \
        "20%（Canonical FinalTarget）"


def test_position_advice_legacy_marked():
    row = {"action_signal": "HOLD", "target": 0.3}
    assert position_advice(row, DEFAULT_SETTINGS).endswith(
        "（Legacy target，仅供对照）")


def test_plain_row_no_interpretation():
    row = {"action_signal": "HOLD", "align_method": "normal"}
    assert trade_interpretation(row) == ""
