# coding: utf-8
"""DeterminismContract Replay Identity 测试（新 43 号）"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[4]
CORE_DIR = PROJECT_ROOT / "Core"
if str(CORE_DIR) not in sys.path:
    sys.path.insert(0, str(CORE_DIR))

from QCFP_MTF.governance.determinism import determinism_identity, \
    replay_determinism_check


def test_research_identity_requires_seed():
    r = determinism_identity(seed=42, numpy_version="2.0",
                             sampling_method="block_bootstrap",
                             block_size=4, n_permutations=1000)
    assert r["random_seed"] == 42
    assert r["determinism_version"] == "DET-1.0"
    assert r["research_seed_required"] is False


def test_production_random_forbidden():
    r = determinism_identity(seed=None)
    assert r["production_random_forbidden"] is False
    assert r["research_seed_required"] is True


def test_replay_deterministic():
    identity = ("ev1", "REL-1", "cfg1", "fm1", "uni1")
    a = {"decision_id": "d1", "decision_path_hash": "H",
         "final_target": 0.2, "reason_codes": ["WAVE"]}
    r = replay_determinism_check(*identity, a, dict(a))
    assert r["deterministic"] is True
    assert r["verdict"] == "DETERMINISTIC"


def test_replay_determinism_failure():
    identity = ("ev1", "REL-1", "cfg1", "fm1", "uni1")
    a = {"decision_id": "d1", "decision_path_hash": "H",
         "final_target": 0.2, "reason_codes": ["WAVE"]}
    b = dict(a, final_target=0.3)
    r = replay_determinism_check(*identity, a, b)
    assert r["verdict"] == "DETERMINISM_FAILURE"
    assert "final_target" in r["mismatches"]
