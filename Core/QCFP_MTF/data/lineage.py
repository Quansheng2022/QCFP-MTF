# coding: utf-8
"""Data Lineage（QCFP-MTF 2.8：31 号全链路数据血缘）

把"可审计"从决策审计扩展到数据审计：任意最终决策都能回答
"这个数字从哪里来、什么时候可获得、经过什么处理"：

    Decision → Feature → Indicator → Transformation → Raw Data →
    Data Source → Available Time

每个关键字段记录：
    data_source_id / snapshot_id / available_at / transform_version /
    quality_status / lineage_hash

lineage_hash = sha256(源→变换→特征→决策 全链指纹)，可用来校验
"同一决策的输入数据血缘是否可重建"。
"""

import hashlib
import json
from dataclasses import asdict, dataclass, field


@dataclass(frozen=True)
class LineageNode:
    kind: str                 # raw / transformation / indicator / feature
    name: str
    data_source_id: str = ""
    snapshot_id: str = ""
    available_at: str = ""
    transform_version: str = ""
    quality_status: str = ""
    source_timestamp: str = ""       # 2.8（42 号）：源数据时间戳
    transformation_id: str = ""      # 2.8（42 号）：变换 ID
    parent_names: tuple = field(default_factory=tuple)

    def as_dict(self) -> dict:
        d = asdict(self)
        d["parent_names"] = list(self.parent_names)
        return d


@dataclass(frozen=True)
class DataLineage:
    decision_id: str
    stock_code: str
    decision_date: str
    nodes: tuple
    lineage_hash: str

    def as_dict(self) -> dict:
        d = asdict(self)
        d["nodes"] = [n.as_dict() for n in self.nodes]
        return d

    def to_chain(self) -> list:
        """按 raw→transformation→indicator→feature 顺序输出可读链。"""
        order = {"raw": 0, "transformation": 1, "indicator": 2, "feature": 3}
        return sorted(self.nodes, key=lambda n: order.get(n.kind, 9))


def lineage_hash(nodes) -> str:
    raw = json.dumps(
        [{"kind": n.kind, "name": n.name, "source": n.data_source_id,
          "snapshot": n.snapshot_id, "available_at": n.available_at,
          "transform": n.transform_version, "quality": n.quality_status,
          "parents": list(n.parent_names)} for n in nodes],
        sort_keys=True, ensure_ascii=False, default=str)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]


def feature_lineage(feature_name, chain: list) -> dict:
    """单个特征的全链路血缘（42 号）：
        feature → transformation → intermediate → raw → source → available_at
    chain：[(kind, name, source_id, source_version, source_timestamp,
             available_at, transform_id, transform_version)]
    """
    nodes = []
    for kind, name, src, src_ver, ts, avail, tid, tver in chain:
        nodes.append(LineageNode(
            kind=kind, name=name, data_source_id=src,
            transform_version=tver or "",
            available_at=avail, source_timestamp=ts,
            transformation_id=tid or "",
            quality_status="PIT_CHK"))
    return {
        "feature": feature_name,
        "nodes": [n.as_dict() for n in nodes],
        "lineage_hash": lineage_hash(nodes),
        "source_id": chain[0][2] if chain else "",
        "source_version": chain[0][3] if chain else "",
        "available_at": chain[0][5] if chain else "",
    }


def build_lineage(decision_id, stock_code, decision_date, raw_sources,
                  transforms=None, indicators=None, features=None) -> DataLineage:
    """组装血缘链。

    raw_sources：[(table, data_source_id, snapshot_id, available_at,
                   quality_status)]
    transforms / indicators / features：[(name, transform_version,
                                          parent_names)]
    """
    nodes = []
    for table, src, snap, avail, quality in raw_sources:
        nodes.append(LineageNode("raw", table, data_source_id=src,
                                 snapshot_id=snap, available_at=avail,
                                 quality_status=quality))
    for name, ver, parents in (transforms or []):
        nodes.append(LineageNode("transformation", name,
                                 transform_version=ver,
                                 parent_names=tuple(parents)))
    for name, ver, parents in (indicators or []):
        nodes.append(LineageNode("indicator", name, transform_version=ver,
                                 parent_names=tuple(parents)))
    for name, ver, parents in (features or []):
        nodes.append(LineageNode("feature", name, transform_version=ver,
                                 parent_names=tuple(parents)))
    return DataLineage(
        decision_id=decision_id, stock_code=stock_code,
        decision_date=decision_date, nodes=tuple(nodes),
        lineage_hash=lineage_hash(nodes))


def lineage_to_md(lineage: DataLineage) -> str:
    lines = [
        f"# Data Lineage　{lineage.stock_code}　{lineage.decision_date}",
        "",
        f"**Decision：`{lineage.decision_id}`**　lineage_hash="
        f"`{lineage.lineage_hash}`",
        "",
        "| 层级 | 名称 | 数据源 | 快照 | 可用时间 | 变换版本 | 质量 |",
        "| --- | --- | --- | --- | --- | --- | --- |",
    ]
    for n in lineage.to_chain():
        lines.append(
            f"| {n.kind} | {n.name} | {n.data_source_id or '-'} | "
            f"{n.snapshot_id or '-'} | {n.available_at or '-'} | "
            f"{n.transform_version or '-'} | {n.quality_status or '-'} |")
    return "\n".join(lines)
