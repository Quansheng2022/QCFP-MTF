# coding: utf-8
"""Report Information Budget 六块主报告测试（新 69 号）"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[4]
CORE_DIR = PROJECT_ROOT / "Core"
if str(CORE_DIR) not in sys.path:
    sys.path.insert(0, str(CORE_DIR))

from QCFP_MTF.report.information_budget import MAIN_REPORT_SECTIONS, \
    main_report_sections, report_field_justification


def test_main_report_six_blocks():
    assert MAIN_REPORT_SECTIONS == (
        "permission", "wave_stage", "final_target", "decision_delta",
        "binding_risk", "exit_invalidation")
    s = main_report_sections()
    assert "Ablation" in s["appendix_contains"]


def test_field_changes_action_main():
    r = report_field_justification("exit_condition",
                                   changes_understanding=False,
                                   changes_action=True)
    assert r["placement"] == "MAIN_REPORT"


def test_field_no_change_appendix():
    r = report_field_justification("ic_stat",
                                   changes_understanding=False,
                                   changes_action=False)
    assert r["placement"] == "APPENDIX"
