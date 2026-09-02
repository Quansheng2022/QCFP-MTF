# coding: utf-8
"""Signal Conflict Resolver 测试（56 号）"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[4]
CORE_DIR = PROJECT_ROOT / "Core"
if str(CORE_DIR) not in sys.path:
    sys.path.insert(0, str(CORE_DIR))

from QCFP_MTF.governance.conflict import CONFLICT_PRIORITY, resolve_conflict


def test_priority_order():
    # Governance > Hard Exit > Risk > Permission > Portfolio > Liquidity >
    # FSM > Wave > Entry
    assert CONFLICT_PRIORITY.index("GOVERNANCE_BLOCK") < \
        CONFLICT_PRIORITY.index("HARD_EXIT")
    assert CONFLICT_PRIORITY.index("INSTITUTIONAL_PERMISSION") == 3
    assert CONFLICT_PRIORITY.index("PORTFOLIO_BLOCK") < \
        CONFLICT_PRIORITY.index("LIQUIDITY_BLOCK")
    assert CONFLICT_PRIORITY.index("WAVE") > CONFLICT_PRIORITY.index("FSM")


def test_governance_wins_over_wave():
    r = resolve_conflict(governance_failed=True, wave_strength=0.9,
                         permission="ALLOW", fsm_next="TESTING")
    assert r["winning_rule"] == "GOVERNANCE_BLOCK"
    assert "WAVE" in r["suppressed"]


def test_wave_cannot_override_risk():
    r = resolve_conflict(risk_level="Extreme", wave_strength=0.9,
                         permission="ALLOW")
    assert r["winning_rule"] == "RISK_BLOCK"


def test_liquidity_beats_wave():
    r = resolve_conflict(liquidity_flag="LIQUIDITY_LOW", wave_strength=0.9,
                         permission="ALLOW")
    assert r["winning_rule"] == "LIQUIDITY_BLOCK"


def test_regime_block_22():
    r = resolve_conflict(market_regime="Crisis", wave_strength=0.9,
                         permission="ALLOW")
    assert r["winning_rule"] == "REGIME_BLOCK"
    # Regime 在 Liquidity 之上、FSM/Wave 之下层级
    assert CONFLICT_PRIORITY.index("REGIME_BLOCK") < \
        CONFLICT_PRIORITY.index("LIQUIDITY_BLOCK")
    assert CONFLICT_PRIORITY.index("REGIME_BLOCK") > \
        CONFLICT_PRIORITY.index("INSTITUTIONAL_PERMISSION")
