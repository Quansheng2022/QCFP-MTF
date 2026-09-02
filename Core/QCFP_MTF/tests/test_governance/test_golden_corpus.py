# coding: utf-8
"""Golden Decision Corpus 测试（新 42 号）"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[4]
CORE_DIR = PROJECT_ROOT / "Core"
if str(CORE_DIR) not in sys.path:
    sys.path.insert(0, str(CORE_DIR))

from QCFP_MTF.governance.golden_decision_corpus import GOLDEN_CORPUS, \
    golden_change_requires_review, golden_decision_corpus, golden_case_hash


def test_corpus_coverage():
    c = golden_decision_corpus()
    perms = {v["permission"] for v in c["corpus"].values()}
    assert perms == {"BLOCK", "WATCH", "TEST", "ALLOW", "STRONG_ALLOW"}
    waves = {v["wave_stage"] for v in c["corpus"].values()}
    assert {"DISCOVERY", "ACTIVE", "MATURE", "INVALID"} <= waves
    events = {v["event"] for v in c["corpus"].values()}
    assert {"HARD_EXIT", "PIT_FAILURE", "SAFE_MODE"} <= events
    assert c["n_cases"] == len(GOLDEN_CORPUS)


def test_case_hash_deterministic():
    case = {"case_id": "G_BLOCK_STRONG", "permission": "BLOCK"}
    assert golden_case_hash(case) == golden_case_hash(case)


def test_change_requires_review():
    r = golden_change_requires_review("hash1", "hash2", "G_BLOCK_STRONG")
    assert r["changed"] is True
    assert r["requires_change_impact_review"] is True
    r2 = golden_change_requires_review("hash1", "hash1", "G_BLOCK_STRONG")
    assert r2["requires_change_impact_review"] is False
