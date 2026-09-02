# coding: utf-8
"""Anti-Inference 禁止推断过滤器（规格书 2.3，14 条）

模式：
- warn（默认）：命中禁止表述时追加警告，保留原文；
- replace：把禁止表述替换为允许表述。
"""

import json
from pathlib import Path
from typing import List, Tuple

RULES = [
    {"id": "RULE-001", "trigger": "换手率下降", "forbidden": ["机构锁仓", "主力吸筹"],
     "allowed": "市场筹码交换速度下降"},
    {"id": "RULE-002", "trigger": "成交量下降", "forbidden": ["主力高度控盘", "抛压耗尽"],
     "allowed": "市场活跃度降低"},
    {"id": "RULE-003", "trigger": "价格上涨", "forbidden": ["机构买入", "主力拉升"],
     "allowed": "定价改善，买方占优"},
    {"id": "RULE-004", "trigger": "价涨量增", "forbidden": ["机构建仓", "主力控盘"],
     "allowed": "趋势扩张，有增量资金参与"},
    {"id": "RULE-005", "trigger": "价涨量缩", "forbidden": ["机构锁仓上涨", "主力高度控盘"],
     "allowed": "上涨动能减弱，或浮筹减少"},
    {"id": "RULE-006", "trigger": "高换手滞涨", "forbidden": ["主力派发", "出货确认"],
     "allowed": "多空分歧加大"},
    {"id": "RULE-007", "trigger": "低换手上涨", "forbidden": ["机构锁仓", "主力控盘"],
     "allowed": "筹码交换效率高，浮筹较少"},
    {"id": "RULE-008", "trigger": "季度机构持股上升", "forbidden": ["未来股价一定上涨", "机构看多"],
     "allowed": "机构投资者在该季度增持"},
    {"id": "RULE-009", "trigger": "季度股东户数下降", "forbidden": ["一定是机构在收集", "主力吸筹"],
     "allowed": "户均持股上升，筹码呈集中趋势"},
    {"id": "RULE-010", "trigger": "价格跌破VWAP", "forbidden": ["趋势反转", "主力出货"],
     "allowed": "短期平均持仓者亏损"},
    {"id": "RULE-011", "trigger": "价格站上VWAP", "forbidden": ["趋势启动", "主力入场"],
     "allowed": "短期平均持仓者盈利"},
    {"id": "RULE-012", "trigger": "CBI低位", "forbidden": ["筹码分散", "主力离场"],
     "allowed": "市场行为活跃，换手积极"},
    {"id": "RULE-013", "trigger": "CBI高位", "forbidden": ["机构高度锁仓", "无风险"],
     "allowed": "市场行为稳定，换手较低"},
]


def scan_conclusions(text: str) -> List[dict]:
    """扫描文本，返回命中的禁止推断列表"""
    hits = []
    for rule in RULES:
        found = [f for f in rule["forbidden"] if f in (text or "")]
        if found:
            hits.append({"id": rule.get("id"), "trigger": rule["trigger"], "forbidden": found,
                         "allowed": rule["allowed"]})
    return hits


def filter_conclusions(text: str, mode: str = "warn") -> Tuple[str, List[dict]]:
    """按模式过滤结论文本，返回 (新文本, 命中列表)"""
    hits = scan_conclusions(text)
    if not hits:
        return text, []
    new_text = text
    warnings = []
    for hit in hits:
        if mode == "replace":
            for f in hit["forbidden"]:
                new_text = new_text.replace(f, hit["allowed"])
            warnings.append(f"{hit['trigger']}：禁止表述已替换为「{hit['allowed']}」")
        else:  # warn
            warnings.append(
                f"{hit['trigger']}：命中禁止表述 {'/'.join(hit['forbidden'])}，"
                f"应降级为「{hit['allowed']}」")
    if warnings:
        new_text = f"{new_text}\n【Anti-Inference {'替换' if mode == 'replace' else '警告'}】" + "；".join(warnings)
    return new_text, hits


def load_rules_json(path=None) -> list:
    """从 JSON 加载规则（扩展用）；不存在时返回内置规则"""
    if path and Path(path).exists():
        return json.loads(Path(path).read_text(encoding="utf-8"))
    return RULES
