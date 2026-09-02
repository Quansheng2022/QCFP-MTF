# coding: utf-8
"""Negative Result Registry（QCFP-MTF 2.8：56 号负结果登记）

正式记录"哪些东西被证明没用"，防止复杂度重新长回来：
    Hypothesis / Experiment / OOS result / Ablation result /
    Failure reason / Retired version

验收标准：未来若有人重新引入类似逻辑，系统能发现
"这个想法以前已经验证失败过"。
"""

import hashlib
import json
import re


def normalize_hypothesis(hypothesis: str) -> str:
    text = re.sub(r"[\W_]+", " ", str(hypothesis).strip().lower())
    return re.sub(r"\s+", " ", text).strip()


class NegativeResultRegistry:
    def __init__(self):
        self._records = {}

    def record(self, entry: dict) -> dict:
        key = normalize_hypothesis(entry.get("hypothesis") or "")
        raw = json.dumps(entry, sort_keys=True, ensure_ascii=False,
                         default=str)
        record_id = hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]
        self._records[key] = {"record_id": record_id, **entry}
        return {"record_id": record_id, "registered": True, "key": key}

    def find_prior_failure(self, hypothesis: str) -> dict:
        key = normalize_hypothesis(hypothesis)
        record = self._records.get(key)
        if record:
            return {"match": "EXACT", "found": True, "record": record}
        tokens = set(key.split())
        hits = []
        for k, r in self._records.items():
            overlap = tokens & set(k.split())
            if len(overlap) >= 2:
                hits.append({"key": k, "overlap": sorted(overlap),
                             "retired_version": r.get("retired_version"),
                             "failure_reason": r.get("failure_reason")})
        return {"match": "FUZZY" if hits else "NONE",
                "found": bool(hits), "candidates": hits}

    def check_reintroduction(self, hypothesis: str) -> dict:
        prior = self.find_prior_failure(hypothesis)
        if prior["found"]:
            return {"verdict": "REJECT_REINTRODUCTION",
                    "reason": "该假设此前已验证失败（见 "
                              "Negative Result Registry）",
                    "prior": prior}
        return {"verdict": "NO_PRIOR_FAILURE",
                "reason": "无已知负结果"}


def feature_proposal_gate(hypothesis: str, registry,
                          justification: str = "") -> dict:
    """新 56 号：新研究立项前首先查询 Negative Result Registry；
    被删除模块换名字重新进入必须解释为什么过去失败现在可能不再适用。"""
    prior = registry.find_prior_failure(hypothesis)
    if not prior["found"]:
        return {"verdict": "PROPOSAL_ALLOWED",
                "prior_failure": None,
                "allowed": True}
    if not justification.strip():
        return {"verdict": "BLOCKED_NO_JUSTIFICATION",
                "prior_failure": prior,
                "allowed": False,
                "reason": "此前已验证失败且未解释为何现在可能不再适用"}
    return {"verdict": "PROPOSAL_ALLOWED_WITH_JUSTIFICATION",
            "prior_failure": prior,
            "allowed": True,
            "justification": justification}
