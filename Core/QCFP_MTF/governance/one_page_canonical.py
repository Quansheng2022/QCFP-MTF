# coding: utf-8
"""One-Page Canonical Specification（QCFP-MTF 2.8：99 号一页规格）

生产核心应能一页解释清楚：
    INPUT (PIT Evidence) → PERMISSION (Institutional Permission) →
    OPPORTUNITY (Wave) → LIFECYCLE (FSM) → GOVERNANCE (Risk/Portfolio/
    Liquidity/Execution) → OUTPUT (Canonical Decision) → FACT (Ledger)
    → VALIDATION (OOS / Ablation / Stress / Replay)

验收标准：熟悉量化的工程师仅凭一页理解
谁能提高风险、谁只能降低风险、谁产生 Proposal、
谁产生 Decision、谁保存事实。
"""


ONE_PAGE_CANONICAL = (
    ("INPUT", "PIT Evidence"),
    ("PERMISSION", "Institutional Permission"),
    ("OPPORTUNITY", "Wave"),
    ("LIFECYCLE", "FSM"),
    ("GOVERNANCE", "Risk / Portfolio / Liquidity / Execution"),
    ("OUTPUT", "Canonical Decision"),
    ("FACT", "Ledger"),
    ("VALIDATION", "OOS / Ablation / Stress / Replay"),
)

AUTHORITY_ROLES = {
    "can_increase_risk": "仅 Governance / PermissionPolicy",
    "can_only_decrease_risk": "FSM / Risk / Portfolio / Liquidity / "
                              "Execution 下游",
    "produces_proposal": "Wave / FSM",
    "produces_decision": "Governance（唯一）",
    "saves_fact": "Append-only Ledger",
}


def one_page_canonical_spec() -> dict:
    return {
        "stages": dict(ONE_PAGE_CANONICAL),
        "authority_roles": AUTHORITY_ROLES,
        "page_requirement": "一个熟悉量化系统的工程师应能仅凭一页理解；"
                            "若仍需几十张架构图，说明系统可继续简化",
    }


def canonical_chain_completeness(chain_stages) -> dict:
    """检查生产链是否覆盖全部一页规格环节。"""
    present = set(chain_stages or [])
    required = [k for k, _ in ONE_PAGE_CANONICAL]
    missing = [k for k in required if k not in present]
    return {"missing": missing,
            "complete": not missing,
            "required_stages": required,
            "verdict": "COMPLETE" if not missing else "SIMPLIFY_OR_FIX"}


def architecture_contract_check(module: str, stage: str) -> dict:
    """新 99 号：新增 Production 模块必须说明属于哪一个核心 stage；
    回答不了 → RESEARCH_ONLY / APPENDIX / SHADOW_ONLY / RETIRE。"""
    required = [k for k, _ in ONE_PAGE_CANONICAL]
    if stage in required:
        return {"module": module, "stage": stage,
                "verdict": "PRODUCTION_MAPPED",
                "production_allowed": True}
    if stage in ("RESEARCH_ONLY", "APPENDIX", "SHADOW_ONLY", "RETIRE"):
        return {"module": module, "stage": stage,
                "verdict": stage,
                "production_allowed": False}
    return {"module": module, "stage": stage or "UNMAPPED",
            "verdict": "RESEARCH_ONLY",
            "production_allowed": False,
            "reason": "无法映射到任一核心 stage → 不得进入 Production"}
