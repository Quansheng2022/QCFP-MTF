# coding: utf-8
"""Architecture Conformance CI 测试（49 号：可执行架构规则）"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[4]
CORE_DIR = PROJECT_ROOT / "Core"
if str(CORE_DIR) not in sys.path:
    sys.path.insert(0, str(CORE_DIR))

from QCFP_MTF.governance.architecture_conformance import \
    ARCHITECTURE_RULES, architecture_conformance


def _all_ok():
    return {spec["check"]: True
            for spec in ARCHITECTURE_RULES.values()}


def test_all_conformant_passes_ci():
    r = architecture_conformance(_all_ok())
    assert r["conformant"] is True
    assert r["ci_verdict"] == "PASS"
    assert r["failures"] == []
    assert len(r["results"]) == len(ARCHITECTURE_RULES)


def test_one_violation_fails_ci():
    checks = _all_ok()
    checks["report_sizing"] = (False, "report 直接 import sizing")
    r = architecture_conformance(checks)
    assert r["conformant"] is False
    assert r["ci_verdict"] == "FAIL"
    assert "report_no_sizing_import" in r["failures"]
    assert r["results"]["report_no_sizing_import"]["detail"] \
        == "report 直接 import sizing"


def test_legacy_default_violation():
    checks = _all_ok()
    checks["legacy_default"] = False
    r = architecture_conformance(checks)
    assert "legacy_not_canonical_default" in r["failures"]
