# coding: utf-8
"""PIT Universe Registry（QCFP-MTF 2.8：P0-5 时点股票池注册表）

回答"2024-03-31 当时系统究竟知道哪些股票"：
    universe_id / effective_from / effective_to / stock_code /
    inclusion_status / source / available_at / period_end / snapshot_hash

PIT Integrity Score：PIT-A=100 / PIT-B=90 / PIT-C=仅探索。
"""

import hashlib
import json
from dataclasses import asdict, dataclass, field


@dataclass(frozen=True)
class PitUniverseEntry:
    universe_id: str
    stock_code: str
    effective_from: str
    effective_to: str = ""
    inclusion_status: str = "included"
    source: str = ""
    available_at: str = ""
    period_end: str = ""

    def as_dict(self) -> dict:
        return asdict(self)


def snapshot_hash(entries) -> str:
    raw = json.dumps([asdict(e) for e in entries], sort_keys=True,
                     ensure_ascii=False, default=str)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]


class PitUniverseRegistry:
    def __init__(self):
        self.entries = []

    def register(self, entry: PitUniverseEntry) -> None:
        self.entries.append(entry)

    def stocks_known_at(self, date) -> list:
        """date 时点已知的股票（effective_from ≤ date < effective_to）。"""
        return sorted({e.stock_code for e in self.entries
                       if e.effective_from <= date
                       and (not e.effective_to or e.effective_to > date)})

    def summary(self) -> dict:
        return {"n_entries": len(self.entries),
                "n_unique_stocks": len({e.stock_code
                                        for e in self.entries}),
                "snapshot_hash": snapshot_hash(self.entries)}


def pit_integrity_score(grade="C") -> dict:
    """PIT Integrity Score：A=100 / B=90 / C=仅探索（不可正式验证）。"""
    if grade == "A":
        score, valid_for_research = 100.0, True
    elif grade == "B":
        score, valid_for_research = 90.0, True
    elif grade == "C":
        score, valid_for_research = None, False
    else:
        score, valid_for_research = 0.0, False
    return {"grade": grade, "integrity_score": score,
            "research_valid": valid_for_research}
