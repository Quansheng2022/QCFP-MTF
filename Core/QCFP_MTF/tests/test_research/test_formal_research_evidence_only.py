# coding: utf-8
"""Formal Research Evidence-only 测试（Convergence 新 7 号）"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[4]
CORE_DIR = PROJECT_ROOT / "Core"
if str(CORE_DIR) not in sys.path:
    sys.path.insert(0, str(CORE_DIR))


def test_research_validation_uses_evidence_timeline():
    src = (Path(CORE_DIR) / "QCFP_MTF" / "scripts" /
           "research_validation.py").read_text(encoding="utf-8")
    assert "build_evidence_timeline" in src
    # Formal path 禁止 legacy target/action 生成器
    assert "from QCFP_MTF.decision.action_generator import" not in src
    assert "effective_position_cqs" not in src


def test_research_validation_no_own_validated_verdict():
    src = (Path(CORE_DIR) / "QCFP_MTF" / "scripts" /
           "research_validation.py").read_text(encoding="utf-8")
    assert "Research Validated ✅" not in src
    assert "certificate_display" in src
    assert "validation_certificate" in src
