# coding: utf-8
"""Alpha Source Registry 测试（81 号）"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[4]
CORE_DIR = PROJECT_ROOT / "Core"
if str(CORE_DIR) not in sys.path:
    sys.path.insert(0, str(CORE_DIR))

from QCFP_MTF.alpha.registry import AlphaRegistry, AlphaSource


def _src(aid, deps, status="active"):
    return AlphaSource(alpha_id=aid, source=f"src_{aid}",
                       hypothesis=f"h_{aid}",
                       feature_dependencies=tuple(deps),
                       production_status=status)


def test_registry_basic():
    reg = AlphaRegistry()
    reg.register(_src("WAVE", ["q_trend_score", "q_position_52w"]))
    reg.register(_src("MOM", ["q_position_52w", "m_volume_accel"]))
    assert reg.active_alpha_count() == 2
    assert reg.dependencies_of("WAVE") == {"q_trend_score",
                                           "q_position_52w"}


def test_shared_dependency_detected():
    reg = AlphaRegistry()
    reg.register(_src("WAVE", ["q_position_52w"]))
    reg.register(_src("MOM", ["q_position_52w"]))
    reg.register(_src("FSM", ["m_volume_accel"]))
    rep = reg.shared_dependency_report()
    assert rep["duplicate_risk_suspect"] is True
    assert "q_position_52w" in rep["shared_dependencies"]
    assert len(rep["shared_dependencies"]["q_position_52w"]) == 2
