# coding: utf-8
"""Feature Contract（QCFP-MTF 2.8：32 号特征契约）

给进入 Decision Layer 的每个 Feature 建立严格契约：
    name / type / source / available_at / PIT_required / allowed_layer /
    missing_policy / range / version / validation_rule

错误 Feature 进入 Decision → FeatureGateError → Decision Abort
（从"代码小心不使用未来数据"升级为"架构层禁止错误 Feature 穿透"）。
"""

import re
from dataclasses import asdict, dataclass

from ..governance.feature_gate import FeatureGateError, feature_allowed


@dataclass(frozen=True)
class FeatureContract:
    name: str
    type: str = "float"          # float / int / str / bool
    source: str = ""
    available_at: str = ""       # 该特征可获得的时点（字段名，如 available_date）
    pit_required: bool = True    # 决策层必须 PIT
    allowed_layer: str = "decision"   # structural / wave / decision / evaluation
    missing_policy: str = "reject"    # reject / fillna / drop
    range: tuple = None          # (min, max) 或 None
    version: str = "1.0"
    validation_rule: str = ""    # 正则（str 类型）或空

    def as_dict(self) -> dict:
        d = asdict(self)
        d["range"] = list(self.range) if self.range else None
        return d


def validate_feature(contract: FeatureContract, value, layer="decision") \
        -> tuple:
    """校验单个特征：返回 (ok, errors)。
    - 层权限：allowed_layer 必须允许该层
    - missing：值缺失时按 missing_policy
    - 类型/范围/正则校验
    """
    errors = []
    if not feature_allowed(contract.name, layer):
        errors.append(
            f"FEATURE_GATE:{contract.name} 不允许进入 {layer} 层")
    if value is None or (isinstance(value, float) and value != value):
        if contract.missing_policy == "reject":
            errors.append(f"MISSING:{contract.name}（policy=reject）")
        return not errors, errors
    if contract.type == "float":
        try:
            v = float(value)
        except (TypeError, ValueError):
            errors.append(f"TYPE:{contract.name} 需要 float，得到 {value!r}")
            return False, errors
        if contract.range and not (contract.range[0] <= v <= contract.range[1]):
            errors.append(f"RANGE:{contract.name}={v} 超出 {contract.range}")
    elif contract.type == "int":
        try:
            v = int(value)
        except (TypeError, ValueError):
            errors.append(f"TYPE:{contract.name} 需要 int，得到 {value!r}")
            return False, errors
    elif contract.type == "str":
        v = str(value)
        if contract.validation_rule and \
                not re.fullmatch(contract.validation_rule, v):
            errors.append(f"RULE:{contract.name}={v!r} 不匹配 "
                          f"{contract.validation_rule}")
    return not errors, errors


def assert_feature_contract(contract: FeatureContract, value,
                            layer="decision") -> None:
    """校验失败 → FeatureGateError（Decision Abort）。"""
    ok, errors = validate_feature(contract, value, layer=layer)
    if not ok:
        raise FeatureGateError("; ".join(errors))


# 标准契约注册表：只登记已进入 Decision 层的核心特征
DECISION_FEATURE_CONTRACTS = {
    "institutional_permission": FeatureContract(
        name="institutional_permission", type="str", source="institutional",
        pit_required=True, allowed_layer="decision",
        missing_policy="reject",
        validation_rule="BLOCK|WATCH|TEST|ALLOW|STRONG_ALLOW"),
    "c_state": FeatureContract(
        name="c_state", type="str", source="qcfp_quarterly_structural",
        pit_required=True, allowed_layer="decision",
        validation_rule="C↑|C→|C↓"),
    "f_state": FeatureContract(
        name="f_state", type="str", source="qcfp_quarterly_structural",
        pit_required=True, allowed_layer="decision",
        validation_rule="F↑|F→|F↓"),
    "p_state": FeatureContract(
        name="p_state", type="str", source="qcfp_quarterly_structural",
        pit_required=True, allowed_layer="decision",
        validation_rule="P↑|P→|P↓"),
    "q_position_52w": FeatureContract(
        name="q_position_52w", type="float",
        source="qcfp_quarterly_structural", pit_required=True,
        allowed_layer="decision", range=(0.0, 1.0)),
    "data_quality": FeatureContract(
        name="data_quality", type="str", source="data_quality",
        pit_required=True, allowed_layer="decision",
        validation_rule="[A-D]"),
    # Evaluation-only 特征（决策层禁止）
    "future_return": FeatureContract(
        name="future_return", type="float", source="evaluation",
        pit_required=False, allowed_layer="evaluation"),
    "wave_label": FeatureContract(
        name="wave_label", type="str", source="evaluation",
        pit_required=False, allowed_layer="evaluation"),
}


def validate_evidence_features(evidence: dict, layer="decision") -> tuple:
    """批量校验证据字典中的特征：返回 (ok, errors)。"""
    errors = []
    for name, contract in DECISION_FEATURE_CONTRACTS.items():
        if name in evidence:
            ok, errs = validate_feature(contract, evidence[name], layer)
            errors += errs
    return not errors, errors


def assert_evidence_features(evidence: dict, layer="decision") -> None:
    ok, errors = validate_evidence_features(evidence, layer)
    if not ok:
        raise FeatureGateError("; ".join(errors))


EVALUATION_ONLY_FEATURES = ("future_return", "future_peak", "wave_label")


def assert_decision_layer_features(evidence: dict,
                                   decision_time=None) -> None:
    """引擎级硬门（6 号）：只禁止两类违规——
    1) Evaluation-only 特征（future_return/future_peak/wave_label）进入
       Decision → FeatureGateError；
    2) 带 available_at 字段且晚于决策时间 → PITViolation。
    值域/缺失校验属于数据质量层（validate_evidence_features），
    不在引擎硬门内执行，避免阻断合成/部分回测数据。
    """
    from ..data.information_set import PITViolation
    for name in EVALUATION_ONLY_FEATURES:
        if name in evidence and evidence[name] is not None:
            raise FeatureGateError(
                f"FeatureGate: {name} 不允许进入 decision 层")
    if decision_time:
        dt = str(decision_time)[:10]
        for key, value in evidence.items():
            if (key.endswith("_available_at")
                    or key.endswith("_available_date")):
                if value is None:
                    continue
                s = str(value).strip().lower()
                # NaN/NaT → 无可用时点（DATA_INSUFFICIENT 不算违规），
                # 不能把 "nan" 当字符串比较（"nan" > 任何日期 → 假违规）
                if s in ("", "nan", "nat", "none", "<nat>"):
                    continue
                if s[:10] > dt:
                    raise PITViolation(
                        f"PIT: {key}={str(value)[:10]} > "
                        f"decision_time={dt}")
