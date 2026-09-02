# coding: utf-8
"""Canonical Specification 机器索引与一致性审计（流程治理 Sprint A #1）

`Core/QCFP_MTF/CANONICAL_SPEC.md` 是系统最高真理（What must always be true），
本模块只做三件事：
  1. 登记全部 Spec 永久 ID（单点来源）；
  2. 校验 MD 与索引一致（无孤儿 ID / 无缺失 ID）；
  3. 校验 Spec 不含实现细节（class / function / 文件路径 / 算法代码）。

任何新 Spec 条目：先在 CANONICAL_SPEC.md 落章节，再在 SPEC_ENTRIES 登记，
spec_conformance 不通过 → Baseline 不允许更新。
"""

import json
import re
from pathlib import Path


def get_qcfp_root() -> Path:
    return Path(__file__).resolve().parents[3]


# Canonical Spec 位于 QCFP_MTF 包根（Core/QCFP_MTF/CANONICAL_SPEC.md）
SPEC_PATH = Path(__file__).resolve().parents[1] / "CANONICAL_SPEC.md"

# 章节固定顺序（CS-00 … CS-70），与 CANONICAL_SPEC.md 一致
SPEC_CHAPTERS = (
    "CS-00 System Purpose",
    "CS-01 Scope / Non-Scope",
    "CS-10 Canonical Decision Chain",
    "CS-20 Authority Model",
    "CS-21 Institutional Permission Authority",
    "CS-22 Wave Authority",
    "CS-23 FSM Authority",
    "CS-24 Risk Authority",
    "CS-25 FinalTarget Authority",
    "CS-26 Validation Authority",
    "CS-27 Ledger Fact Authority",
    "CS-30 Constitutional Invariants",
    "CS-31 Permission > Signal",
    "CS-32 PIT > Prediction",
    "CS-33 Risk > Return",
    "CS-34 Proposal != Decision",
    "CS-35 Downstream Risk Monotonicity",
    "CS-36 UNKNOWN Degrades",
    "CS-37 Production Cannot Self Modify",
    "CS-40 Decision Identity",
    "CS-41 Release Identity",
    "CS-42 Replay Identity",
    "CS-50 Research / Production Boundary",
    "CS-60 Release Qualification",
    "CS-70 Change Governance",
)

# 每个 Spec 条目：永久 ID / 章节 / 类别 / 一句话陈述 / 权威 Owner（如适用）/
# 可追溯的 Release Gate
SPEC_ENTRIES = (
    # ---- CS-00 目的 ----
    {"id": "QCFP-SPEC-PUR-001", "chapter": "CS-00",
     "kind": "PURPOSE",
     "statement": "系统是决策支持系统，不直接向 Broker 下达指令",
     "authority_owner": "", "release_gates": ()},
    {"id": "QCFP-SPEC-PUR-002", "chapter": "CS-00",
     "kind": "PURPOSE",
     "statement": "系统价值是降低未知/高风险下的错误参与，而非最大化短期收益",
     "authority_owner": "", "release_gates": ("QUALIFICATION_GATE",)},
    # ---- CS-01 范围 ----
    {"id": "QCFP-SPEC-SCO-001", "chapter": "CS-01", "kind": "SCOPE",
     "statement": "覆盖 PIT→权限→机会→生命周期→治理→决策→事实→验证完整链",
     "authority_owner": "", "release_gates": ("ARCHITECTURE_CONFORMANCE",)},
    {"id": "QCFP-SPEC-SCO-002", "chapter": "CS-01", "kind": "SCOPE",
     "statement": "不覆盖自动下单、经纪商执行、收益承诺",
     "authority_owner": "", "release_gates": ("ARCHITECTURE_CONFORMANCE",)},
    {"id": "QCFP-SPEC-SCO-003", "chapter": "CS-01", "kind": "SCOPE",
     "statement": "任何生产能力必须能映射到核心链条，否则不得进入 Production",
     "authority_owner": "", "release_gates": ("ARCHITECTURE_CONFORMANCE",)},
    # ---- CS-10 决策链 ----
    {"id": "QCFP-SPEC-CHAIN-001", "chapter": "CS-10", "kind": "CHAIN",
     "statement": "生产决策链固定为 INPUT→PERMISSION→OPPORTUNITY→LIFECYCLE→"
                 "GOVERNANCE→OUTPUT→FACT→VALIDATION，顺序与环节不得缺省",
     "authority_owner": "", "release_gates": ("ARCHITECTURE_CONFORMANCE",)},
    {"id": "QCFP-SPEC-CHAIN-002", "chapter": "CS-10", "kind": "CHAIN",
     "statement": "每一环节只能产生其被授权的产物",
     "authority_owner": "", "release_gates": ("AUTHORITY_AUDIT",)},
    # ---- CS-21~27 权威 ----
    {"id": "QCFP-SPEC-AUTH-001", "chapter": "CS-21", "kind": "AUTHORITY",
     "statement": "Institutional Permission 是唯一可提高风险上限的权威",
     "authority_owner": "decision.institutional_permission",
     "release_gates": ("AUTHORITY_AUDIT", "CONSTITUTION_GATE")},
    {"id": "QCFP-SPEC-AUTH-002", "chapter": "CS-22", "kind": "AUTHORITY",
     "statement": "Wave 只产生机会提案，提案不等于决策",
     "authority_owner": "wave.canonical",
     "release_gates": ("AUTHORITY_AUDIT",)},
    {"id": "QCFP-SPEC-AUTH-003", "chapter": "CS-23", "kind": "AUTHORITY",
     "statement": "Retail FSM 拥有仓位生命周期提案",
     "authority_owner": "decision.retail_position_fsm",
     "release_gates": ("AUTHORITY_AUDIT",)},
    {"id": "QCFP-SPEC-AUTH-004", "chapter": "CS-24", "kind": "AUTHORITY",
     "statement": "风险权威是只能降低风险的下游强制通道；Hard Exit 是 Kill Switch",
     "authority_owner": "decision.hard_exit",
     "release_gates": ("CONSTITUTION_GATE", "AUTHORITY_AUDIT")},
    {"id": "QCFP-SPEC-AUTH-005", "chapter": "CS-25", "kind": "AUTHORITY",
     "statement": "Final Target 有唯一 Owner，下游只能减少不得提高",
     "authority_owner": "decision.governance",
     "release_gates": ("AUTHORITY_AUDIT", "CHANGE_IMPACT_GATE")},
    {"id": "QCFP-SPEC-AUTH-006", "chapter": "CS-26", "kind": "AUTHORITY",
     "statement": "验证/认证状态由唯一验证权威产生，不得自行声明 PASS",
     "authority_owner": "governance.validation_certificate",
     "release_gates": ("VALIDATION_GATE",)},
    {"id": "QCFP-SPEC-AUTH-007", "chapter": "CS-27", "kind": "AUTHORITY",
     "statement": "事实台账只追加，有唯一写入者，已提交事实不可改删",
     "authority_owner": "decision.decision_ledger",
     "release_gates": ("LEDGER_GATE", "REPLAY_GATE")},
    {"id": "QCFP-SPEC-AUTH-008", "chapter": "CS-27", "kind": "AUTHORITY",
     "statement": "Report 不能产生 Decision，只能投影既有事实/决策",
     "authority_owner": "",
     "release_gates": ("REPORT_GATE",)},
    # ---- CS-31~37 宪法不变量 ----
    {"id": "QCFP-SPEC-INV-001", "chapter": "CS-31", "kind": "INVARIANT",
     "statement": "Permission > Signal：任何信号不得升级权限",
     "authority_owner": "decision.institutional_permission",
     "release_gates": ("CONSTITUTION_GATE", "CHANGE_IMPACT_GATE")},
    {"id": "QCFP-SPEC-INV-002", "chapter": "CS-32", "kind": "INVARIANT",
     "statement": "PIT > Prediction：未来数据不得进入过去决策",
     "authority_owner": "data.pit_registry",
     "release_gates": ("PIT_GATE", "CONSTITUTION_GATE")},
    {"id": "QCFP-SPEC-INV-003", "chapter": "CS-33", "kind": "INVARIANT",
     "statement": "Risk > Return：收益提升不能违反风险优先",
     "authority_owner": "decision.governance",
     "release_gates": ("CONSTITUTION_GATE", "QUALIFICATION_GATE")},
    {"id": "QCFP-SPEC-INV-004", "chapter": "CS-34", "kind": "INVARIANT",
     "statement": "Proposal != Decision：只有 Governance 产生决策",
     "authority_owner": "decision.governance",
     "release_gates": ("AUTHORITY_AUDIT",)},
    {"id": "QCFP-SPEC-INV-005", "chapter": "CS-35", "kind": "INVARIANT",
     "statement": "Downstream Risk Monotonicity：最终风险沿决策链只能下降",
     "authority_owner": "decision.governance",
     "release_gates": ("CONSTITUTION_GATE", "REPLAY_GATE")},
    {"id": "QCFP-SPEC-INV-006", "chapter": "CS-36", "kind": "INVARIANT",
     "statement": "UNKNOWN Degrades：未知/缺失必须降级，不得默认放行",
     "authority_owner": "",
     "release_gates": ("CONSTITUTION_GATE", "FAILURE_INJECTION_GATE")},
    {"id": "QCFP-SPEC-INV-007", "chapter": "CS-37", "kind": "INVARIANT",
     "statement": "Production Cannot Self-Modify：生产环境不能修改自身规则/代码",
     "authority_owner": "",
     "release_gates": ("CONSTITUTION_GATE", "SCOPE_LOCK")},
    {"id": "QCFP-SPEC-INV-008", "chapter": "CS-30", "kind": "INVARIANT",
     "statement": "每个生产决策必须可审计、可重放",
     "authority_owner": "decision.decision_ledger",
     "release_gates": ("REPLAY_GATE", "LEDGER_GATE")},
    {"id": "QCFP-SPEC-INV-009", "chapter": "CS-30", "kind": "INVARIANT",
     "statement": "Research 可以挑战 Production，但绝不能静默改变 Production",
     "authority_owner": "",
     "release_gates": ("ARCHITECTURE_CONFORMANCE", "SCOPE_LOCK")},
    {"id": "QCFP-SPEC-INV-010", "chapter": "CS-30", "kind": "INVARIANT",
     "statement": "新增复杂度必须证明增量实用价值",
     "authority_owner": "",
     "release_gates": ("COMPLEXITY_GATE", "QUALIFICATION_GATE")},
    # ---- CS-40~42 身份 ----
    {"id": "QCFP-SPEC-ID-001", "chapter": "CS-40", "kind": "IDENTITY",
     "statement": "每个决策携带完整身份，缺任一 → 不认证",
     "authority_owner": "decision.decision_snapshot",
     "release_gates": ("RELEASE_IDENTITY_GATE",)},
    {"id": "QCFP-SPEC-ID-002", "chapter": "CS-41", "kind": "IDENTITY",
     "statement": "每个生产发布有唯一 Release Identity，决策可唯一反查",
     "authority_owner": "decision.release_identity",
     "release_gates": ("RELEASE_IDENTITY_GATE",)},
    {"id": "QCFP-SPEC-ID-003", "chapter": "CS-42", "kind": "IDENTITY",
     "statement": "同输入+同发布身份必须产生同决策（Replay Determinism）",
     "authority_owner": "decision.replay_engine",
     "release_gates": ("REPLAY_GATE",)},
    # ---- CS-50 边界 ----
    {"id": "QCFP-SPEC-BND-001", "chapter": "CS-50", "kind": "BOUNDARY",
     "statement": "Research 与 Production 隔离，Research 不得写 Production 事实",
     "authority_owner": "",
     "release_gates": ("ARCHITECTURE_CONFORMANCE",)},
    {"id": "QCFP-SPEC-BND-002", "chapter": "CS-50", "kind": "BOUNDARY",
     "statement": "证据等级阶梯固定，低等级证据只能产生 Hypothesis",
     "authority_owner": "",
     "release_gates": ("PROMOTION_GATE", "QUALIFICATION_GATE")},
    # ---- CS-60 发布资格 ----
    {"id": "QCFP-SPEC-RLS-001", "chapter": "CS-60", "kind": "RELEASE",
     "statement": "Release 判定只允许三态：QUALIFIED / NOT_PROVEN / REJECTED",
     "authority_owner": "",
     "release_gates": ("RELEASE_JUDGE",)},
    {"id": "QCFP-SPEC-RLS-002", "chapter": "CS-60", "kind": "RELEASE",
     "statement": "Software Qualification 与 Strategy Promotion 是两个独立 Gate",
     "authority_owner": "",
     "release_gates": ("QUALIFICATION_GATE", "PROMOTION_GATE")},
    {"id": "QCFP-SPEC-RLS-003", "chapter": "CS-60", "kind": "RELEASE",
     "statement": "Missing Evidence != PASS，证据不完整只能 NOT_PROVEN",
     "authority_owner": "",
     "release_gates": ("RELEASE_JUDGE", "VALIDATION_GATE")},
    {"id": "QCFP-SPEC-RLS-004", "chapter": "CS-60", "kind": "RELEASE",
     "statement": "任何 AI 无权执行 HUMAN_APPROVED，最终晋升只能由 Human 执行",
     "authority_owner": "",
     "release_gates": ("HUMAN_APPROVAL",)},
    # ---- CS-70 变更治理 ----
    {"id": "QCFP-SPEC-CHG-001", "chapter": "CS-70", "kind": "CHANGE",
     "statement": "没有 Change Impact 不得生成 Implementation Contract",
     "authority_owner": "",
     "release_gates": ("CHANGE_IMPACT_GATE", "SCOPE_LOCK")},
    {"id": "QCFP-SPEC-CHG-002", "chapter": "CS-70", "kind": "CHANGE",
     "statement": "Patch 必须通过 Scope Lock 审计，计划外变更 → SCOPE_VIOLATION",
     "authority_owner": "",
     "release_gates": ("SCOPE_LOCK",)},
    {"id": "QCFP-SPEC-CHG-003", "chapter": "CS-70", "kind": "CHANGE",
     "statement": "Baseline Create-Only 且不可变；变更走新 Baseline Candidate 流程",
     "authority_owner": "",
     "release_gates": ("BASELINE_GATE",)},
    {"id": "QCFP-SPEC-CHG-004", "chapter": "CS-70", "kind": "CHANGE",
     "statement": "Builder 不得改 Frozen Golden / 删失败测试；必须走 ADR + Human Approval",
     "authority_owner": "",
     "release_gates": ("REVIEW_GATE", "HUMAN_APPROVAL")},
)


def spec_entries() -> tuple:
    """机器索引（唯一来源）。"""
    return SPEC_ENTRIES


def spec_ids() -> list:
    return [e["id"] for e in SPEC_ENTRIES]


def spec_entries_by_kind(kind: str) -> list:
    return [e for e in SPEC_ENTRIES if e["kind"] == kind]


def spec_entries_for_authority(authority_owner: str) -> list:
    return [e for e in SPEC_ENTRIES
            if e["authority_owner"] == authority_owner]


# Spec 中禁止出现的实现细节模式（class / function / 文件路径 / 算法代码）
FORBIDDEN_SPEC_PATTERNS = (
    (r"^\s*(class|def|async def)\s+\w+", "class/function 定义"),
    (r"^\s*(import|from)\s+\w+", "import 语句"),
    (r"\b\d+\.py\b", "Python 文件路径"),
    (r"[A-Za-z]:\\", "Windows 绝对路径"),
    (r"```\s*(python|py)", "Python 代码块"),
)


def load_spec_text(spec_path=None) -> str:
    path = Path(spec_path) if spec_path else SPEC_PATH
    return path.read_text(encoding="utf-8") if path.exists() else ""


def spec_conformance(spec_path=None) -> dict:
    """校验 MD 与机器索引一致且不含实现细节。"""
    text = load_spec_text(spec_path)
    missing_ids = [e["id"] for e in SPEC_ENTRIES
                   if e["id"] not in text]
    forbidden = []
    for pattern, label in FORBIDDEN_SPEC_PATTERNS:
        if re.search(pattern, text, re.M):
            forbidden.append(label)
    chapter_missing = []
    for chapter in SPEC_CHAPTERS:
        if f"## {chapter}" not in text \
                and f"### {chapter}" not in text:
            chapter_missing.append(chapter)
    ok = not missing_ids and not forbidden and not chapter_missing
    return {
        "schema": "SPEC-CONFORMANCE-2",
        "spec_path": str(Path(spec_path) if spec_path else SPEC_PATH),
        "n_entries": len(SPEC_ENTRIES),
        "missing_spec_ids": missing_ids,
        "missing_chapters": chapter_missing,
        "implementation_detail_found": forbidden,
        "conformant": ok,
        "pass": ok,
        "verdict": "SPEC_CONFORMANT" if ok else "SPEC_NON_CONFORMANT",
        "acceptance": {
            "core_authorities_covered": all(
                e["id"] in text
                for e in spec_entries_by_kind("AUTHORITY")),
            "invariants_covered": all(
                e["id"] in text
                for e in spec_entries_by_kind("INVARIANT")),
            "release_gates_traceable": all(
                e["release_gates"] for e in SPEC_ENTRIES
                if e["kind"] in ("RELEASE", "CHANGE")),
            "no_implementation_detail": not forbidden,
            "architecture_change_without_spec_change":
                "见 governance_baseline.json：Spec Hash 与 Architecture Hash 分别冻结",
        },
    }


def spec_conformance_artifact(out_dir) -> dict:
    """写 spec_conformance.json + MD 摘要（Evidence Artifact）。"""
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    result = spec_conformance()
    (out_dir / "spec_conformance.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2),
        encoding="utf-8")
    lines = [
        "# QCFP-MTF Canonical Spec Conformance",
        "",
        f"**Verdict：{result['verdict']}**",
        f"- 条目数：{result['n_entries']}",
        f"- 缺失 ID：{result['missing_spec_ids'] or '无'}",
        f"- 缺失章节：{result['missing_chapters'] or '无'}",
        f"- 实现细节：{result['implementation_detail_found'] or '无'}",
        "",
        "## Acceptance",
    ]
    for k, v in result["acceptance"].items():
        lines.append(f"- {k}: {v}")
    (out_dir / "spec_conformance.md").write_text(
        "\n".join(lines), encoding="utf-8")
    return result
