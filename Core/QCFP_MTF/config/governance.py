# coding: utf-8
"""Config Governance（QCFP-MTF 2.8：32 号配置治理）

所有影响决策的参数进入 versioned config，并区分：
    DECISION_CRITICAL / RESEARCH_ONLY / DISPLAY_ONLY

关键参数缺失时不得悄悄采用默认值，应直接 UNKNOWN / INVALID_CONFIG。
（默认值也属于决策规则，因此必须被审计。）
"""


class InvalidConfigError(ValueError):
    pass


DECISION_CRITICAL_PARAMS = (
    "permission_policy", "risk_caps", "portfolio_caps", "liquidity_caps",
    "execution_caps", "drawdown_caps", "data_quality_gate",
    "pit_contract", "governance_rule_version",
)


def classify_param(name) -> str:
    """参数分类：DECISION_CRITICAL / RESEARCH_ONLY / DISPLAY_ONLY。"""
    if name in DECISION_CRITICAL_PARAMS or name.startswith(
            ("permission", "risk_", "portfolio_", "liquidity_",
             "execution_", "drawdown_")):
        return "DECISION_CRITICAL"
    if name.startswith(("display_", "report_")):
        return "DISPLAY_ONLY"
    return "RESEARCH_ONLY"


def validate_config_governance(config: dict) -> dict:
    """关键参数缺失 → INVALID_CONFIG（不悄悄采用默认值）。"""
    invalid = []
    unknown = []
    for name in DECISION_CRITICAL_PARAMS:
        if name not in config:
            unknown.append(name)
    # 关键参数存在但值为 None/空 → 视为缺失
    for name in DECISION_CRITICAL_PARAMS:
        v = config.get(name)
        if v is None or v == "":
            unknown.append(name)
    if unknown:
        return {"status": "INVALID_CONFIG",
                "missing_critical_params": sorted(set(unknown)),
                "valid": False,
                "note": "默认值也属于决策规则，关键参数缺失必须显式"
                        "UNKNOWN/INVALID_CONFIG"}
    return {"status": "VALID", "missing_critical_params": [],
            "valid": True}


def assert_config_valid(config: dict) -> None:
    r = validate_config_governance(config)
    if not r["valid"]:
        raise InvalidConfigError(
            f"Config Governance：缺失关键参数 "
            f"{r['missing_critical_params']}")


def assert_decision_critical_config(config: dict) -> dict:
    """新 32 号：DECISION_CRITICAL 缺失 → INVALID_CONFIG → NO_DECISION /
    SAFE_MODE，而不是自动用默认值继续交易。"""
    r = validate_config_governance(config)
    if not r["valid"]:
        return {"status": "INVALID_CONFIG",
                "missing_critical_params": r["missing_critical_params"],
                "decision_mode": "NO_DECISION",
                "safety_mode": "SAFE_MODE",
                "valid": False,
                "rule": "决策关键参数缺失 → 禁止静默 fallback，"
                        "直接 NO_DECISION/SAFE_MODE"}
    return {"status": "VALID", "missing_critical_params": [],
            "decision_mode": "NORMAL", "safety_mode": "NORMAL",
            "valid": True}


def decision_critical_hidden_default_count(config: dict,
                                           defaults_used: dict) -> dict:
    """新 32 号：正式 Canonical Decision 中 decision-critical hidden
    default count = 0。defaults_used：{param: value}（实际 fallback 的）。"""
    hidden = []
    for param in DECISION_CRITICAL_PARAMS:
        if param in (defaults_used or {}) \
                and param not in config:
            hidden.append(param)
    return {"hidden_default_count": len(hidden),
            "hidden_defaults": hidden,
            "decision_critical_clean": not hidden,
            "rule": "正式 Canonical Decision 中 decision-critical "
                    "hidden default count = 0"}
