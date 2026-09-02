# coding: utf-8
"""Report Information Budget 测试（69 号）"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[4]
CORE_DIR = PROJECT_ROOT / "Core"
if str(CORE_DIR) not in sys.path:
    sys.path.insert(0, str(CORE_DIR))

from QCFP_MTF.report.information_budget import REPORT_SIX_QUESTIONS, \
    main_report_completeness, report_information_budget


def test_field_budget_main_vs_appendix():
    r = report_information_budget({
        "suggested_position": {"changes_understanding": True,
                               "changes_action": True},
        "appendix_sharpe_table": {"changes_understanding": False,
                                  "changes_action": False},
    })
    assert "suggested_position" in r["main_report_fields"]
    assert "appendix_sharpe_table" in r["appendix_fields"]


def test_field_changes_action_only_goes_main():
    r = report_information_budget({
        "exit_condition": {"changes_understanding": False,
                           "changes_action": True}})
    assert "exit_condition" in r["main_report_fields"]


def test_six_questions_complete():
    answers = {q: "value" for q in REPORT_SIX_QUESTIONS}
    r = main_report_completeness(answers)
    assert r["complete"] is True
    assert r["missing"] == []


def test_six_questions_missing():
    answers = {q: "value" for q in REPORT_SIX_QUESTIONS[:4]}
    r = main_report_completeness(answers)
    assert r["complete"] is False
    assert "max_risk" in r["missing"]
    assert "exit_or_invalidation" in r["missing"]
