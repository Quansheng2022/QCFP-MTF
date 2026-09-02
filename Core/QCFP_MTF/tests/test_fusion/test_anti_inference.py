# coding: utf-8
"""Anti-Inference 禁止推断过滤测试"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[4]
CORE_DIR = PROJECT_ROOT / "Core"
if str(CORE_DIR) not in sys.path:
    sys.path.insert(0, str(CORE_DIR))

from QCFP_MTF.fusion.anti_inference import RULES, filter_conclusions, scan_conclusions


def test_scan_detects_forbidden():
    text = "换手率下降，机构锁仓迹象明显"
    hits = scan_conclusions(text)
    assert any("机构锁仓" in h["forbidden"] for h in hits)


def test_scan_clean_text():
    assert scan_conclusions("季度机构增持，价格站上VWAP，市场活跃") == []


def test_warn_mode_keeps_text():
    text = "价涨量增，机构建仓"
    new_text, hits = filter_conclusions(text, mode="warn")
    assert "机构建仓" in new_text  # 保留原文
    assert "Anti-Inference" in new_text
    assert hits


def test_replace_mode():
    text = "价格跌破VWAP，趋势反转"
    new_text, hits = filter_conclusions(text, mode="replace")
    assert "趋势反转" not in new_text
    assert "短期平均持仓者亏损" in new_text


def test_all_rules_present():
    assert len(RULES) == 13  # 规格书 2.3 禁止推断表共 13 条


def test_rule_ids_unique():
    ids = [r["id"] for r in RULES]
    assert len(ids) == len(set(ids)) == 13
    assert all(i.startswith("RULE-") for i in ids)


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print(f"PASS {name}")
    print("test_anti_inference 全部通过 ✅")
