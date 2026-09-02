# QCFP-MTF Phase 4 —— Flow Governance Closure 开发与验证规范

> 文档角色：Phase 4（Roadmap「Flow Governance Closure / FGC」）的
> **Development & Validation Specification**。
> 版本：v1.0（2026-09-02）
> 依据：《QCFP-MTF_Roadmap.md》Phase 4、`CANONICAL_SPEC.md` CS-20/CS-60/CS-70、
> `ARCHITECTURE.md` 版本变更记录 V95/V96 流程治理工程段落。
> 状态：本规范冻结后作为 audit/phase4 证据与验收的依据；规范本身不授予
> AI Release Authority（QCFP-SPEC-RLS-004）。

---

## 一、范围与目标（Scope）

Phase 4 的目标是 **Flow Governance Closure（FGC-1）**：
让「AI 开发流程」在通往 `SOFTWARE_QUALIFIED` 与 `PRODUCTION_DSS` 的两条路径上
不可绕过。

```text
AI 可以：propose / review / build / patch
AI 不可以：change truth / invent evidence / approve release / approve human promotion

最终 DoD：
    Bypass Path → SOFTWARE_QUALIFIED = 0
    Bypass Path → PRODUCTION_DSS     = 0
```

本阶段**不新增决策 Authority**、不新增 Alpha/评分模块、不改变生产决策链
（Production Decision Path 保持 = 1），只对既有流程治理能力做**收口 + 自证**。

### Scope

1. 五个 Surgical Fix 的强制契约与机器验证：
   - SF-1 Observed Diff Mandatory（真实 diff 证据，OBSERVED-DIFF-2）
   - SF-2 Patch Actual Evidence Mandatory（PATCH-EVIDENCE-2 + 权威图 before/after + Feature Manifest after）
   - SF-3 Evidence Pack Read-Only（READ / VERIFY / HASH / INDEX，禁止 MODIFY/REPAIR）
   - SF-4 Manifest + Full Identity Mandatory（evidence_manifest 强制 + 3/3 identity 精确匹配）
   - SF-5 Promotion Identity Hardening（Qualification / Promotion 两级 Gate 消费 Pure Judge 产物与 Human Approval Hash）
2. FGC-1 C1~C7 全部可重复执行（Traceability / Change Impact / Contract / Oracle / Review / Patch Scope / Promotion）。
3. Zero-Bypass 攻击面测试（test_governance_bypass）作为最终验收必跑套件。
4. Phase 4 自己的开发流程按 CS-70 走同一 Change Cycle（Observed Diff →
   Change Impact → Implementation Contract → Acceptance Contract → Patch Evidence）。
5. 治理体系冻结：Phase 4 验收通过后 **不再继续增加 Governance Feature**，
   后续变更一律走受治理 Change Cycle。

### Non-Scope（本阶段明确不做）

- 不执行 Phase 7 `SOFTWARE_QUALIFIED` / `REJECTED` / `NOT_PROVEN` 发布判定
  （Pure Release Judge 属于 Phase 7；本阶段只产出 Evidence Pack 证明其输入可被只读打包）。
- 不执行 Phase 8~10 策略验证（OOS / Ablation / Shadow 属于策略证据，不属于本阶段）。
- 不新增生产决策能力、不修改生产权限矩阵、不改变 Canonical Decision Chain。

---

## 二、Spec 锚点（Traceability）

| Closure | 需求来源 | 规范条款 |
| :-- | :-- | :-- |
| C1 Traceability | QCFP-SPEC-CHG-001/002 | Spec → Architecture → Owner → Test → Evidence → Gate 全连通 |
| C2 Change Impact | QCFP-SPEC-CHG-001 | 无 Change Impact 不得生成 Implementation Contract |
| C3 Frozen Oracle | QCFP-SPEC-CHG-004 | Builder 不得修改 Frozen Golden Expected / 删除失败测试 |
| C4 Patch Scope Lock | QCFP-SPEC-CHG-002 | Allowed/Protected Surface 机器审计 |
| C5 Evidence Integrity | QCFP-SPEC-RLS-003 | Missing Evidence ≠ PASS；只读打包 |
| C6 Qualification/Promotion 分离 | QCFP-SPEC-RLS-002/004 | Software Qualification ≠ Strategy Promotion ≠ Human Approval |
| C7 Evidence-Aware Review | QCFP-SPEC-RLS-003/004 | Reviewer 可输出 REVIEW_CLEAN，禁止 RELEASE_PASS |
| SF-1~SF-5 | CS-70 + Roadmap Phase 4 | 见第一节 |

---

## 三、开发范围（Deliverables）

| # | 交付物 | 路径 | 类型 |
| :-- | :-- | :-- | :-- |
| D1 | Phase 4 开发与验证规范（本文档） | `Doc/QCFP-MTF_Phase4_FGC_开发验证规范.md` | 文档 |
| D2 | Phase 4 纯证据聚合器（Gate + Acceptance） | `Core/QCFP_MTF/governance/phase4.py` | 代码 |
| D3 | Phase 4 独立回归 Runner | `Core/QCFP_MTF/scripts/phase4_regression_runner.py` | 代码 |
| D4 | Phase 4 Evidence Builder（CS-70 变更自证） | `Core/QCFP_MTF/scripts/phase4_evidence_builder.py` | 代码 |
| D5 | governance_flow `phase4` CLI 命令 | `Core/QCFP_MTF/scripts/governance_flow.py` | 代码 |
| D6 | Phase 4 Gate 单测 | `Core/QCFP_MTF/tests/test_governance/test_phase4.py` | 测试 |
| D7 | 验收证据包 | `audit/phase4/` | 证据 |

约束：
- D2 是**纯证据聚合器**：READ evidence → COMPARE → ISSUE verdict；
  不得硬编码 PASS、不得补齐缺失证据（QCFP-SPEC-RLS-003）。
- D3 是 Test System：Judge/Acceptance 只消费 D3 产出的计数文件，不自行跑 pytest。
- D4 只在 Evidence Generation 阶段运行；Evidence Pack 阶段只读。
- 禁止触碰 `CANONICAL_SPEC.md`、`ARCHITECTURE.md`、system_constitution、
  FROZEN_PRODUCTION_MANIFEST、golden corpus 冻结文件（Baseline 不得漂移）。

---

## 四、Validation Specification（验证要求）

### 4.1 必跑回归套件（Independent Regression）

| Suite | 内容 | 最低要求 |
| :-- | :-- | :-- |
| phase4_flow | test_flow_governance + test_governance_bypass | PASS，collected ≥ 85 |
| bypass | test_governance_bypass（攻击面） | PASS，failed=0，escaped=0 |
| phase1 | test_phase1（规范/权威基线） | PASS，无 skipped |
| phase3 | test_phase3（Phase 3 Gate 回归） | PASS，无 skipped |
| decision | tests/test_decision | PASS，无 skipped |
| governance | tests/test_governance | PASS，无 skipped |
| full_core | 全部 QCFP_MTF 测试 | PASS，无 skipped |

计数一致性：`collected == passed + failed + errors + skipped`；
`status=PASS` 时 passed>0 且 failed/errors/skipped=0；
证据矛盾（PASS+失败）→ REGRESSION_EVIDENCE_INVALID → FAIL。

### 4.2 Phase 4 Gate 清单

| Gate | 证据 | 通过标准 |
| :-- | :-- | :-- |
| SPEC | spec_conformance.json | SPEC_CONFORMANT |
| BASELINE | baseline.json | BASELINE_PASS（无漂移） |
| TRACEABILITY | traceability.json | TRACEABILITY_PASS |
| CHANGE_PROCESS | change_impact.json / implementation_contract_result.json / acceptance_result.json | approved_for_contract + CONTRACT_OK + ACCEPTANCE_PASS |
| PATCH_SCOPE_SF2 | scope_audit.json | PATCH_ACCEPTED，violations=0 |
| FLOW_GOVERNANCE | phase4_regression_summary.json | phase4_flow PASS |
| ZERO_BYPASS | phase4_regression_summary.json（bypass） | bypass PASS → derived escaped=0 |
| REVIEW_RESOLUTION | review_report.json / review_resolution.json | open CRITICAL=0、open MAJOR=0、Gate allowed |
| EVIDENCE_PACK_SF3 | evidence_pack_readonly.json + evidence_manifest.json | PACK_ACCEPTED + 全部 artifact sha 不变 |
| MANIFEST_IDENTITY_SF4 | evidence_manifest_verification.json | manifest valid + identity 3/3 全 artifact |
| PROMOTION_SF5 | fgc_bypass_suite.json | AI approval / 旧 Release / hash mismatch 全部 BLOCKED |
| REGRESSION | phase4_regression_summary.json | 全部 required suite PASS |

三态语义：FAIL / PASS / NOT_PROVEN；缺证据 → NOT_PROVEN，不允许默认 PASS。

### 4.3 代码审查（Evidence-Aware Review）

Review 输入必须包含：change_id / spec_ids / architecture_baseline /
implementation_contract / actual_diff / test_evidence / authority_audit /
complexity_diff / changed_decision_samples / known_not_proven_items。

Findings 分类：SPEC_VIOLATION / ARCHITECTURE_VIOLATION / AUTHORITY_VIOLATION /
IMPLEMENTATION_DEFECT / TEST_GAP / EVIDENCE_GAP / COMPLEXITY_REGRESSION /
SCOPE_CREEP / DOCUMENTATION_DRIFT / NO_ISSUE。

收口规则（C7）：CRITICAL open>0 → REJECTED；MAJOR open>0 → REJECTED；
MINOR open → 允许但记录 accepted risk；全部处理 → REVIEW_RESOLVED。
Reviewer 无权输出 RELEASE_PASS。

### 4.4 Evidence Pack（SF-3 只读）

- Packer 只执行 READ / VERIFY / HASH / INDEX；
- 每个 artifact 必须自带 schema + change_id/release_id/baseline_id（3/3）；
- 打包前后对全部 artifact 计算 SHA256，前后必须一致（evidence_pack_readonly.json）；
- 输出 `evidence_manifest.json`（EVIDENCE-BUNDLE-2），含 bundle_hash。

---

## 五、Acceptance 标准与 Exit Gate

Exit Gate：**Governance Bypass Gate（FGC_GATE）**

```text
PHASE4_PASS 成立条件：
    Zero Bypass Path to SOFTWARE_QUALIFIED = 0
    Zero Bypass Path to PRODUCTION_DSS     = 0
    Open CRITICAL Review = 0
    Open MAJOR Review    = 0
    12 个 Gate 无 FAIL / 无 NOT_PROVEN
    Frozen Baseline 无漂移
```

机器判定 → `PHASE4_PASS` / `PHASE4_FAIL` / `PHASE4_NOT_PROVEN`；
Freeze State 只允许：`GOVERNANCE_FREEZE_CANDIDATE` / `BLOCKED` / `NOT_PROVEN`。

最终由 Human 决定是否把治理体系冻结（FROZEN）；AI 不得自行执行冻结。

---

## 六、变更纪律（本阶段自身按 CS-70 执行）

1. Phase 4 代码变更先产出 Observed Diff（OBSERVED-DIFF-2）；
2. 再产出 Change Impact（CHANGE-IMPACT-2）并批准 Contract 入口；
3. Implementation Contract（Allowed/New/Forbidden Surface）→ Patch；
4. Patch 后 Scope Lock 审计（Diff + Authority Graph before/after + Feature Manifest after）；
5. Acceptance Contract + 测试结果比对；
6. Evidence-Aware Review + Resolution；
7. Evidence Pack（只读）→ Phase 4 Acceptance。

违反任一环节 → 对应 Gate FAIL / NOT_PROVEN，禁止进入下一步。

---

## 七、交付记录

见 `audit/phase4/phase4_acceptance.md`（机器验收记录）与
`audit/phase4/phase4_human_approval.txt`（Human Freeze Approval）。
