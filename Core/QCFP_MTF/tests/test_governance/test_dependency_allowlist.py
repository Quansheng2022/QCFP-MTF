# coding: utf-8
"""Production Dependency Allowlist 测试（新 49 号）"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[4]
CORE_DIR = PROJECT_ROOT / "Core"
if str(CORE_DIR) not in sys.path:
    sys.path.insert(0, str(CORE_DIR))

from QCFP_MTF.governance.production_dependency_allowlist import \
    dependency_allowlist_check


def test_allowed_dependencies_pass():
    r = dependency_allowlist_check([
        "data.asof", "decision.engine", "governance", "ledger",
        "safety.incident_protocol", "common.db"])
    assert r["allowed"] is True
    assert r["ci_verdict"] == "PASS"


def test_forbidden_prefixes_fail():
    r = dependency_allowlist_check([
        "decision.engine", "research.ablation", "legacy.score",
        "report.contract", "wave.outcome_label"])
    assert r["allowed"] is False
    assert r["ci_verdict"] == "FAIL"
    assert r["research_only_dependency_count"] == 1
    assert r["legacy_authority_dependency_count"] == 1


def test_unlisted_default_forbidden():
    r = dependency_allowlist_check(["some_new_module"])
    assert r["allowed"] is False
    assert r["violations"][0]["reason"] == "NOT_ALLOWLISTED"
