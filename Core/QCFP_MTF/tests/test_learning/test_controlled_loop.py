# coding: utf-8
"""Controlled Learning Loop 测试（25 号：学习不污染生产）"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[4]
CORE_DIR = PROJECT_ROOT / "Core"
if str(CORE_DIR) not in sys.path:
    sys.path.insert(0, str(CORE_DIR))

from QCFP_MTF.learning.controlled_loop import (LearningProposal,
                                               ResearchSandbox,
                                               validate_proposal)


def _proposal(**kw):
    base = {"candidate_version": "v2.0", "hypothesis": "h",
            "ablation_ok": True, "oos_ok": True, "replay_ok": True,
            "stability_ok": True, "cost_stress_ok": True,
            "shadow_ok": True, "approved": True}
    base.update(kw)
    return LearningProposal(**base)


def test_proposal_gates_all_required():
    ok, failed = validate_proposal(_proposal())
    assert ok and not failed
    ok, failed = validate_proposal(_proposal(approved=False))
    assert not ok and "approved" in failed
    ok, failed = validate_proposal(_proposal(oos_ok=False))
    assert not ok and "oos_ok" in failed


def test_sandbox_write_read_separation():
    sb = ResearchSandbox()
    sb.write_outcome({"trade_id": "t1", "net_return": 0.1})
    assert len(sb.read_evidence()) == 1
    sb.create_candidate(_proposal())
    assert len(sb.candidates) == 1
    # 未过全部门 → 不晋升
    ok, failed = sb.promote(_proposal(approved=False))
    assert not ok


def test_sandbox_promote():
    sb = ResearchSandbox()
    ok, failed = sb.promote(_proposal())
    assert ok and not failed
