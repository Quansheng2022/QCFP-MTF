# coding: utf-8
"""InformationSet(t)（QCFP-MTF 2.8：6 号 PIT 架构化）

定义：在决策时间 t，系统实际可以知道的全部信息。
所有 Decision Feature 必须来自 InformationSet(t)——
不再依赖开发人员"记得不要用未来数据"，而是架构强制。

    InformationSet(t)
        ├── features       决策特征（全部 as-of）
        ├── available_at   各特征可获得时点
        ├── decision_time  t
        └── assert_pit_clean()  任一 available_at > t → 抛错
"""

from dataclasses import asdict, dataclass, field


class PITViolation(ValueError):
    pass


@dataclass(frozen=True)
class InformationSet:
    decision_time: str
    features: dict = field(default_factory=dict)
    available_at: dict = field(default_factory=dict)
    sources: dict = field(default_factory=dict)

    def as_dict(self) -> dict:
        return asdict(self)

    def assert_pit_clean(self) -> None:
        """PIT 硬断言：任何特征 available_at > decision_time → 抛错。"""
        for name, avail in self.available_at.items():
            if avail and avail > self.decision_time:
                raise PITViolation(
                    f"PIT: {name} available_at={avail} > "
                    f"decision_time={self.decision_time}")


def _feature_available_at(row, name):
    """从证据行推断特征可获得时点（优先 *_available_at，其次通用字段）。"""
    for key in (f"{name}_available_at", f"{name}_date",
                "available_at", "available_date",
                "structural_available_date", "data_available_date"):
        v = row.get(key)
        if v is None:
            continue
        s = str(v).strip().lower()
        # NaN/NaT/None → 该特征无可用时点（DATA_INSUFFICIENT 不算违规，
        # 与 lookahead_filter.validate_timeline 语义一致），绝不能把
        # "nan" 当字符串比较（"nan" > 任何日期 → 假 PIT 违规）。
        if s in ("", "nan", "nat", "none", "<nat>"):
            continue
        return str(v)[:10]
    return ""


def build_information_set(evidence: dict, decision_time: str) -> InformationSet:
    """从证据行构建 InformationSet(t)。

    features：过滤掉上下文/元数据键后的特征值；
    available_at：各特征的可获得时点（推断）；
    并执行 Feature Contract 层权限校验（非法未来特征 → FeatureGateError）。
    """
    from .feature_contract import validate_evidence_features
    present = {k: v for k, v in evidence.items() if v is not None}
    ok, errors = validate_evidence_features(present, layer="decision")
    if not ok:
        from ..governance.feature_gate import FeatureGateError
        raise FeatureGateError("; ".join(errors))
    meta_keys = {"decision_date", "stock_code", "run_id", "prev_f_state"}
    features = {k: v for k, v in present.items() if k not in meta_keys}
    available = {k: _feature_available_at(evidence, k)
                 for k in features}
    info = InformationSet(
        decision_time=str(decision_time)[:10], features=features,
        available_at=available)
    info.assert_pit_clean()
    return info
