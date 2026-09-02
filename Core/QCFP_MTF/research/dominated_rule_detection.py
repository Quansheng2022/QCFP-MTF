# coding: utf-8
"""Dominated Rule Detection（QCFP-MTF 2.8：84 号被支配规则检测）

寻找"永远被另一个规则覆盖的规则"。统计：
    Rule triggered / Rule binding / Rule independently changed decision /
    Rule prevented violation
分为：ESSENTIAL / USEFUL / REDUNDANT / DOMINATED。

验收标准：长期 trigger>0、binding=0、independent impact=0 的
非治理必要规则进入 RETIRE REVIEW。
"""


def dominated_rule_detection(stats: dict) -> dict:
    """stats：{rule: {"triggered", "binding", "independently_changed",
    "prevented_violation"}}"""
    results = {}
    for rule, s in (stats or {}).items():
        s = s or {}
        triggered = int(s.get("triggered") or 0)
        binding = int(s.get("binding") or 0)
        independent = int(s.get("independently_changed") or 0)
        prevented = int(s.get("prevented_violation") or 0)
        if binding > 0 or prevented > 0:
            cls, retire = "ESSENTIAL", False
        elif independent > 0:
            cls, retire = "USEFUL", False
        elif triggered > 0:
            cls, retire = "DOMINATED", True
        else:
            cls, retire = "REDUNDANT", True
        results[rule] = {
            "triggered": triggered, "binding": binding,
            "independently_changed": independent,
            "prevented_violation": prevented,
            "classification": cls,
            "retire_review": retire,
        }
    return {"results": results,
            "retire_candidates": [r for r, v in results.items()
                                  if v["retire_review"]],
            "rule": "trigger>0 且 binding=0 且独立影响=0 "
                    "→ RETIRE REVIEW"}


def dominated_to_removal(detection: dict) -> dict:
    """新 84 号：REDUNDANT/DOMINATED 真正进入第 83 项删除测试。"""
    removal_candidates = [
        rule for rule, v in (detection.get("results") or {}).items()
        if v.get("classification") in ("REDUNDANT", "DOMINATED")]
    return {
        "removal_candidates": removal_candidates,
        "feeds_rule_removal_test": True,
        "rule": "REDUNDANT/DOMINATED 必须进入删除测试，"
                "而不是只输出分类报告",
    }
