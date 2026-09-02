# coding: utf-8
"""Wave Stage × Action 矩阵测试（12 号规格表落地验证）"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[4]
CORE_DIR = PROJECT_ROOT / "Core"
if str(CORE_DIR) not in sys.path:
    sys.path.insert(0, str(CORE_DIR))

from QCFP_MTF.wave.canonical import STAGE_ACTION_MATRIX, wave_stage_gate


def test_stage_action_matrix_matches_spec():
    """规格表：Discovery 禁建/禁加；Confirming TEST/禁加；
    Active 全允许；Mature 限建/禁加；Exhausting 禁建禁加优先减；
    Invalid 全禁 EXIT。"""
    assert STAGE_ACTION_MATRIX["DISCOVERY"]["entry"] is False
    assert STAGE_ACTION_MATRIX["DISCOVERY"]["add"] is False
    assert STAGE_ACTION_MATRIX["CONFIRMING"]["entry"] is True
    assert STAGE_ACTION_MATRIX["CONFIRMING"]["max_entry_scale"] == 0.5
    assert STAGE_ACTION_MATRIX["CONFIRMING"]["add"] is False
    assert STAGE_ACTION_MATRIX["ACTIVE"]["entry"] is True
    assert STAGE_ACTION_MATRIX["ACTIVE"]["add"] is True
    assert STAGE_ACTION_MATRIX["MATURE"]["max_entry_scale"] == 0.5
    assert STAGE_ACTION_MATRIX["MATURE"]["add"] is False
    assert STAGE_ACTION_MATRIX["EXHAUSTING"]["entry"] is False
    assert STAGE_ACTION_MATRIX["EXHAUSTING"]["add"] is False
    assert STAGE_ACTION_MATRIX["EXHAUSTING"]["reduce"] is True
    assert STAGE_ACTION_MATRIX["INVALID"]["entry"] is False
    assert STAGE_ACTION_MATRIX["INVALID"]["add"] is False
    assert STAGE_ACTION_MATRIX["INVALID"]["hold"] is False
    assert STAGE_ACTION_MATRIX["INVALID"]["reduce"] is True


def test_stage_gate_api():
    assert wave_stage_gate("DISCOVERY", "ENTRY")["allowed"] is False
    assert wave_stage_gate("CONFIRMING", "ENTRY")["max_entry_scale"] == 0.5
    assert wave_stage_gate("ACTIVE", "ADD")["allowed"] is True
    assert wave_stage_gate("INVALID", "EXIT")["allowed"] is True
