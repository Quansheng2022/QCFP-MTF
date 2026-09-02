# QCFP-MTF Canonical System Specification（系统最高真理）

> 本文件是 QCFP-MTF 的 **Canonical Specification（Canonical Spec）**，回答且只回答一个问题：
> **What must always be true?（什么必须永远为真？）**
>
> 它不承载实现设计。Architecture / Implementation 可以变化，而无需修改本文件的实现细节。
> 本文件不写 class、function、文件路径、具体算法代码、某个 Python helper。
>
> 版本权威：所有版本号以 `decision/versions.py` 为唯一来源，冻结状态以
> `audit/baseline/governance_baseline.json` 为准（见 CS-70 / QCFP-SPEC-CHG-003）。
>
> 本 Spec 中的每一条永久 ID 都必须在 `governance/canonical_spec.py` 的机器索引中登记，
> 并由 `spec_conformance` 审计保证「MD 含全部 ID」「Spec 不含实现细节」。

---

## CS-00 System Purpose（系统目的）

- **QCFP-SPEC-PUR-001**：QCFP-MTF 是面向散户的**决策支持系统（DSS）**，不是自动交易系统；它产生建议与风险约束，不直接向 Broker 下达指令。
- **QCFP-SPEC-PUR-002**：系统存在意义是**降低散户在未知/高风险环境下的错误参与**，而非最大化短期收益。

---

## CS-01 Scope / Non-Scope（范围 / 非范围）

- **QCFP-SPEC-SCO-001**（Scope）：系统覆盖「PIT 证据 → 权限 → 机会 → 生命周期 → 治理 → 规范决策 → 事实台账 → 验证」的完整决策支持链。
- **QCFP-SPEC-SCO-002**（Non-Scope）：不覆盖自动下单、经纪商执行、收益承诺、个股买卖建议的最终承诺。
- **QCFP-SPEC-SCO-003**：任何生产能力必须能映射到本 Spec 的某个核心链条环节；回答不了 → 不得进入 Production（CS-50 边界）。

---

## CS-10 Canonical Decision Chain（规范决策链）

- **QCFP-SPEC-CHAIN-001**：生产决策链固定为
  `INPUT(PIT) → PERMISSION → OPPORTUNITY → LIFECYCLE → GOVERNANCE → OUTPUT → FACT → VALIDATION`，
  顺序不得颠倒、环节不得缺省。
- **QCFP-SPEC-CHAIN-002**：链上的每一环节只能产生其被授权的产物：INPUT 产生证据、PERMISSION 产生风险上限、
  OPPORTUNITY 产生机会提案、LIFECYCLE 产生生命周期提案、GOVERNANCE 产生决策、OUTPUT 产生规范决策对象、
  FACT 保存事实、VALIDATION 产生验证状态。

---

## CS-20 Authority Model（权力模型）

### CS-21 Institutional Permission Authority（机构权限权威）

- **QCFP-SPEC-AUTH-001**：Institutional Permission 是风险上界（RISK_UPPER_BOUND），
  是唯一可提高风险上限的权威；任何信号、机会、时间周期都不得升级它。

### CS-22 Wave Authority（Wave 权威）

- **QCFP-SPEC-AUTH-002**：Wave 只产生机会提案（OPPORTUNITY_PROPOSAL），
  提案不等于决策；Wave 不能改变权限或最终目标。

### CS-23 FSM Authority（生命周期权威）

- **QCFP-SPEC-AUTH-003**：Retail FSM 拥有仓位生命周期提案（LIFECYCLE_PROPOSAL）；
  生命周期状态只能降低或维持风险暴露，不能提高。

### CS-24 Risk Authority（风险权威）

- **QCFP-SPEC-AUTH-004**：风险相关权威（含 Hard Exit / Stop / 下行风险）是下游
  **只能降低风险**的强制通道；Hard Exit 是覆盖所有普通看多信号的 Kill Switch。

### CS-25 FinalTarget Authority（最终目标权威）

- **QCFP-SPEC-AUTH-005**：Final Target 有**唯一 Owner**；任何下游只能减少最终目标，
  不得提高（Downstream Risk Monotonicity，见 CS-35）。

### CS-26 Validation Authority（验证权威）

- **QCFP-SPEC-AUTH-006**：正式验证/认证状态（FORMAL_RESEARCH_STATUS / Validation Status）
  由唯一验证权威产生；测试系统证明，评审者与生成者均不得自行声明 PASS。

### CS-27 Ledger Fact Authority（事实权威）

- **QCFP-SPEC-AUTH-007**：事实台账（Ledger）是**只追加（Append-only）** 的事实记录，
  有唯一写入者；任何已提交事实不可修改、不可删除。
- **QCFP-SPEC-AUTH-008**：Report 不能产生 Decision；报告只能投影已存在的事实/决策。

---

## CS-30 Constitutional Invariants（宪法不变量）

### CS-31 Permission > Signal

- **QCFP-SPEC-INV-001**（Permission > Signal）：任何信号不得升级权限。

### CS-32 PIT > Prediction

- **QCFP-SPEC-INV-002**（PIT > Prediction）：未来可知数据不得进入过去决策；
  PIT-invalid 数据不得产生 Research-valid 信号。

### CS-33 Risk > Return

- **QCFP-SPEC-INV-003**（Risk > Return）：任何收益提升都不能违反风险优先原则。

### CS-34 Proposal != Decision

- **QCFP-SPEC-INV-004**（Proposal != Decision）：提案不是决策；只有 Governance 产生决策。

### CS-35 Downstream Risk Monotonicity

- **QCFP-SPEC-INV-005**（Downstream Risk Monotonicity）：最终风险沿决策链只能下降。

### CS-36 UNKNOWN Degrades

- **QCFP-SPEC-INV-006**（UNKNOWN Degrades）：未知/缺失必须降级，不得默认放行。

### CS-37 Production Cannot Self Modify

- **QCFP-SPEC-INV-007**（Production Cannot Self-Modify）：生产环境不能修改自身规则或代码。
- **QCFP-SPEC-INV-008**：每个生产决策必须可审计、可重放。
- **QCFP-SPEC-INV-009**：Research 可以挑战 Production，但绝不能静默改变 Production。
- **QCFP-SPEC-INV-010**：任何新增复杂度必须证明增量实用价值，否则不进入 Production。

---

## CS-40 Decision Identity（决策身份）

### CS-41 Release Identity

### CS-42 Replay Identity

- **QCFP-SPEC-ID-001**：每个决策必须携带完整身份：
  Model Version、Rule Version、Schema Version、Run ID、Input Fingerprint；
 缺任一 → 不认证。
- **QCFP-SPEC-ID-002**：每个生产发布必须有唯一 Release Identity
  （Release ID + Manifest Hash 链），决策必须能唯一反查其发布。
- **QCFP-SPEC-ID-003**：同一输入 + 同一发布身份必须产生同一决策（Replay Determinism）；
  任何确定性漂移 = 发布失败。

---

## CS-50 Research / Production Boundary（研究 / 生产边界）

- **QCFP-SPEC-BND-001**：Research 代码与 Production 代码物理/逻辑隔离；
  Research 不得写入 Production 事实，Production 不得依赖 Research 模块。
- **QCFP-SPEC-BND-002**：证据等级阶梯为
  `Theory → In-sample → Backtest → OOS → Ablation+Stress → Shadow → Production`；
  低等级证据只能产生 Hypothesis，不能直接成为 Production Change。

---

## CS-60 Release Qualification（发布资格）

- **QCFP-SPEC-RLS-001**：Release 判定只允许三态：`SOFTWARE_QUALIFIED` / `NOT_PROVEN` / `REJECTED`。
- **QCFP-SPEC-RLS-002**：Software Qualification（系统实现是否可信）与
  Strategy Promotion（策略是否可成为正式 DSS 版本）是两个完全独立的 Gate。
- **QCFP-SPEC-RLS-003**：Missing Evidence != PASS；证据不完整只能 NOT_PROVEN，fail-closed。
- **QCFP-SPEC-RLS-004**：任何 AI（Reviewer / Builder / Judge）都无权执行
  `HUMAN_APPROVED`；最终晋升只能由 Human 执行。

---

## CS-70 Change Governance（变更治理）

- **QCFP-SPEC-CHG-001**：任何代码任务必须先有 Change Impact，才能生成 Implementation Contract；
  没有 Change Impact 的编码任务不得开始。
- **QCFP-SPEC-CHG-002**：Implementation Contract 定义 Allowed Change Surface 与 Protected Surface；
  Patch 完成后必须通过 Scope Lock 审计，出现计划外文件/权威/Schema/功能 → SCOPE_VIOLATION。
- **QCFP-SPEC-CHG-003**：Baseline 是 Create-Only 且不可变；测试失败不得修改 Baseline 让测试重新 PASS。
  变更必须走「新 Baseline Candidate → Validation → Approval → 新 Baseline」。
- **QCFP-SPEC-CHG-004**：Builder 默认不得修改 Frozen Golden Expected Result、不得删除失败测试；
  如确实需要，必须走独立 ADR + Human Approval。

---

## 验收标准（Acceptance）

- [ ] Production 每个核心 Authority 都有 Spec ID（CS-20/CS-21~27 全覆盖）。
- [ ] 所有最高级 Invariant 都有 Spec ID（CS-30/CS-31~37 全覆盖）。
- [ ] 所有 Release Gate 都能追溯到 Spec ID（CS-60 / CS-70 提供 Release/Change Gate 追溯）。
- [ ] Spec 不依赖具体实现（spec_conformance 扫描禁止 class/function/路径/算法代码）。
- [ ] Architecture 可以改变而无需修改 Spec 的实现细节（Baseline 分别冻结 Spec 与 Architecture Hash）。
