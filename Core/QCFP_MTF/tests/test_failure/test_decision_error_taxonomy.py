# coding: utf-8
"""Decision Error Taxonomy 测试（76 号）"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[4]
CORE_DIR = PROJECT_ROOT / "Core"
if str(CORE_DIR) not in sys.path:
    sys.path.insert(0, str(CORE_DIR))

from QCFP_MTF.failure.decision_error_taxonomy import classify_error, \
    error_taxonomy_report


def test_classify_errors():
    assert classify_error({"message": "PIT 数据超前"})["category"] == \
        "PIT_ERROR"
    assert classify_error({"message": "permission 越权"})["category"] == \
        "PERMISSION_ERROR"
    assert classify_error({"message": "人工 override 干预"})[
        "category"] == "HUMAN_OVERRIDE_ERROR"
    assert classify_error({"message": "执行滑点超预期"})["category"] == \
        "EXECUTION_ERROR"


def test_unclassified_reported():
    r = classify_error({"message": "完全未知原因"})
    assert r["classified"] is False
    assert r["category"] == "UNCLASSIFIED"


def test_taxonomy_report():
    errors = [{"message": "PIT 超前"}, {"message": "sizing 过大"},
              {"message": "奇怪原因"}]
    r = error_taxonomy_report(errors)
    assert r["total"] == 3
    assert r["counts"]["PIT_ERROR"] == 1
    assert r["counts"]["SIZING_ERROR"] == 1
    assert r["unclassified_count"] == 1
    assert r["taxonomy_stable"] is False


def test_all_classified_stable():
    errors = [{"message": "数据缺失"}, {"message": "exit 止损过晚"}]
    r = error_taxonomy_report(errors)
    assert r["unclassified_count"] == 0
    assert r["taxonomy_stable"] is True
