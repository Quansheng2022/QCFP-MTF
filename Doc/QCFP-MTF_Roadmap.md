# QCFP-MTF 项目全开发周期 Roadmap

建议把整个项目生命周期正式定义成一条 **“Specification → Build → Prove → Qualify → Validate → Shadow → Promote → Operate”** 的受治理开发主线。

核心产品终点是 **Production DSS**，而不是自动交易。当前 Canonical Spec 已明确：QCFP-MTF 是散户决策支持系统，核心 Scope 为 `PIT → Permission → Opportunity → Lifecycle → Governance → Decision → Ledger → Validation`，自动下单和 Broker 执行属于 Non-Scope。

---

## 一、全生命周期总图

```text
                         QCFP-MTF FULL DEVELOPMENT ROADMAP


PHASE 0
System Goals / Product Charter
        │
        ▼
PHASE 1
Canonical Specification
"What must always be true?"
        │
        ▼
PHASE 2
Architecture Design + ADR
        │
        ▼
Architecture Baseline
        │
        ▼
PHASE 3
Minimal Trusted Production Core
Authority / Decision Path / Legacy Closure
        │
        ▼
PHASE 4
Flow Governance Closure
FGC-1
        │
        ▼
──────────────────── DEVELOPMENT BASELINE READY ────────────────────
        │
        ▼
PHASE 5
Implementation
        │
 DeepSeek Builder
        │
        ▼
Candidate Patch
        │
        ▼
PHASE 6
Deterministic Verification
Static / Unit / Integration
Golden / Invariant / Replay
Failure Injection / Scope Audit
        │
        ▼
ChatGPT Evidence Review
        │
        ▼
Review Resolution
        │
        ▼
Evidence Pack
        │
        ▼
PHASE 7
Pure Release Judge
        │
        ├──────── REJECTED
        │
        ├──────── NOT_PROVEN
        │
        ▼
SOFTWARE_QUALIFIED
        │
        ▼
──────────────── SOFTWARE QUALIFICATION COMPLETE ────────────────
        │
        ▼
PHASE 8
Research Validation
PIT / Backtest / Benchmark
        │
        ▼
PHASE 9
Formal Strategy Validation
OOS
Ablation
Stress
Non-Inferiority
        │
        ▼
PHASE 10
Shadow Validation
Full-Universe
No-Trade Quality
Decision Stability
Practicality
        │
        ▼
PRODUCTION_ELIGIBLE
        │
        ▼
PHASE 11
Human Approval
        │
        ▼
PRODUCTION_DSS
        │
        ▼
PHASE 12
Continuous Certification
Monitoring / Drift / Replay
Periodic OOS / Ablation
Revalidation / Retirement
        │
        └──────────────► Next Change Cycle
```

这与已经冻结的 Canonical Decision Chain 一致：生产链固定为 `INPUT(PIT) → PERMISSION → OPPORTUNITY → LIFECYCLE → GOVERNANCE → OUTPUT → FACT → VALIDATION`。

---

# 二、12 个正式 Phase

| Phase  | 阶段                         | 核心目标                                    | 主要产物                                   | Exit Gate              | 当前建议状态            |
| ------ | -------------------------- | --------------------------------------- | -------------------------------------- | ---------------------- | ----------------- |
| **0**  | Product Charter            | 固定系统目标、用户、Scope/Non-Scope               | System Goals                           | Human Approval         | ✅ 完成              |
| **1**  | Canonical Specification    | 定义“什么必须永远正确”                            | `CANONICAL_SPEC.md`                    | Spec Conformance       | ✅ 基本完成            |
| **2**  | Architecture Baseline      | 定义系统如何满足 Spec                           | Architecture、ADR、Baseline              | Architecture Gate      | ✅ 完成              |
| **3**  | Minimal Trusted Core       | 收敛 Production Decision Path / Authority | Manifest、Authority Graph、MTR Evidence  | MTR Gate               | ✅ 大部分完成           |
| **4**  | Flow Governance Closure    | 让 AI 开发流程不可绕过                           | Impact/Contract/Oracle/Judge/Promotion | Governance Bypass Gate | 🟡 最后 Closure     |
| **5**  | Implementation             | 根据 Contract 实现功能                        | Candidate Patch                        | Scope Lock             | 持续阶段              |
| **6**  | Verification               | 证明实现没有破坏系统                              | Tests + Evidence                       | Evidence Gate          | 持续阶段              |
| **7**  | Software Qualification     | 判断代码/实现是否可信                             | Release Verdict                        | Pure Judge             | 🟡 依赖 FGC Closure |
| **8**  | Research Validation        | 验证研究假设和基本实用性                            | PIT/Backtest/Benchmark                 | Research Gate          | 🟡 部分完成           |
| **9**  | Formal Strategy Validation | 真正证明策略可推广                               | OOS/Ablation/Stress                    | Strategy Evidence Gate | 🔴 OOS 未闭合        |
| **10** | Shadow Validation          | 用真实时间流积累决策证据                            | Shadow Evidence                        | Production Eligibility | 🟡 已开始            |
| **11** | Production Promotion       | Human 决定是否成为正式 DSS                      | Approval Artifact                      | Human Gate             | 未开始               |
| **12** | Continuous Certification   | 上线后持续证明系统仍可信                            | Continuous Evidence                    | Periodic Certification | 后续长期运行            |

---

# 三、Phase 0–2：Specification / Architecture Foundation

这是项目的“宪法阶段”。

### Phase 0 — Product Charter

固定：

```text
目标用户        熟练散户 / 牛散
系统定位        Institutional State Filter + Swing DSS
核心目的        降低错误参与
核心输出        Governed Decision Support
Non-Scope       自动 Broker 下单
```

这里一旦冻结，AI 不应在后续开发过程中自行改变系统定位。

---

### Phase 1 — Canonical Specification

最高 Authority：

```text
CANONICAL_SPEC.md
```

内容只定义：

```text
Purpose
Scope
Canonical Chain
Authority
Invariant
Decision Identity
Research / Production Boundary
Release Qualification
Change Governance
```

目前 Canonical Spec 已经明确 Software Qualification 与 Strategy Promotion 必须是两个独立 Gate，并规定 Missing Evidence 只能得到 `NOT_PROVEN`。

**Exit Criteria：**

```text
100% Core Authority → Spec ID
100% Constitutional Invariant → Spec ID
Release Gate → Spec Traceable
Implementation Detail = 0
```

---

### Phase 2 — Architecture Baseline

Architecture 回答：

> 怎样实现 Canonical Specification？

不是永久冻结架构文档，而是冻结一个具体 Baseline。

当前架构已经明确采用这种模式，Spec Hash 与 Architecture Hash 分开冻结。

标准变成：

```text
Canonical Spec
      ↓
Architecture
      ↓
ADR
      ↓
Baseline Candidate
      ↓
Validation
      ↓
Human Approval
      ↓
Frozen Baseline
```

---

# 四、Phase 3：Minimal Trusted Production Core

这一阶段的目标不是继续开发功能，而是回答：

> **到底哪一条代码路径真正拥有 Production Decision Authority？**

核心指标：

```text
Production Decision Path          = 1
Canonical Decision Authority      = 1
Final Target Owner                = 1
Ledger Fact Writer                = 1
Duplicate Authority               = 0
Unauthorized Writer               = 0
Legacy Production Path            = 0
Unwired ACTIVE Feature            = 0
Retired code physically absent
```

目前项目已经完成大量 MTR Closure：Production Decision Path 已收敛为单一路径、ACTIVE Feature 已收敛、Duplicate Authority / Unauthorized Writer 为 0，并完成真实 Failure Injection 与物理删除。

这一步完成后：

> **不再通过增加模块来证明成熟，而通过删除、合并和收敛来提高可信度。**

---

# 五、Phase 4：Flow Governance Closure — 当前最重要阶段

这就是现在正在做的工作。

目标：

```text
AI 可以：
propose
review
build
patch

AI 不可以：
change truth
invent evidence
approve release
approve human promotion
```

当前 7 个大 Closure 已完成主体，现在只剩最后的 Surgical Fix：

```text
SF-1  Observed Diff Mandatory
SF-2  Patch Actual Evidence Mandatory
SF-3  Evidence Pack Read-Only
SF-4  Manifest + Full Identity Mandatory
SF-5  Promotion Identity Hardening
```

最终 DoD 不再看模块数量，而只看：

```text
Bypass Path → SOFTWARE_QUALIFIED = 0
Bypass Path → PRODUCTION_DSS     = 0
```

完成这个阶段后：

> **治理架构冻结，不再继续增加 Governance Feature。**

---

# 六、Phase 5：正式 Implementation Cycle

以后每一次功能修改都走同一条 Change Cycle：

```text
Change Request
      ↓
Observed Diff / Planned Surface
      ↓
Change Impact
      ↓
ADR（需要时）
      ↓
Implementation Contract
      ↓
Acceptance Contract
      ↓
DeepSeek Builder
      ↓
Candidate Patch
```

Canonical Spec 当前已经规定：

> Change Impact 必须先于 Implementation Contract；Patch 必须遵守 Allowed/Protected Surface。

这里 DeepSeek 的角色非常明确：

> **Builder，而不是 Architect Authority / Release Authority。**

---

# 七、Phase 6：Verification

Candidate Patch 完成后不立即交 ChatGPT 主观评审，而先进入确定性验证：

```text
Static Check
Unit Test
Integration Test
Golden Test
Invariant Test
Replay Test
PIT Test
Failure Injection
Authority Audit
Patch Scope Audit
Complexity Diff
```

HIGH Change 进一步要求：

```text
OOS
Ablation
Stress
Shadow
```

然后：

```text
Deterministic Evidence
        ↓
ChatGPT Evidence-Aware Review
        ↓
Review Resolution
```

ChatGPT 的职责是：

```text
SPEC_VIOLATION
ARCHITECTURE_VIOLATION
AUTHORITY_VIOLATION
IMPLEMENTATION_DEFECT
TEST_GAP
EVIDENCE_GAP
COMPLEXITY_REGRESSION
SCOPE_CREEP
```

而不是：

```text
RELEASE_PASS
```

---

# 八、Phase 7：Software Qualification

所有事实最终进入：

```text
Immutable Evidence Artifacts
        ↓
Evidence Manifest
        ↓
Pure Release Judge
```

Judge 只能：

```text
READ
COMPARE
ISSUE VERDICT
```

最终只有三态：

```text
SOFTWARE_QUALIFIED
NOT_PROVEN
REJECTED
```

最重要的是：

```text
SOFTWARE_QUALIFIED
        ≠
Strategy proven
        ≠
Production approved
```

这是整个系统治理模型最重要的分层之一。

---

# 九、Phase 8–9：Strategy Validation

软件正确以后，才开始回答另一个完全不同的问题：

> **这个策略实际上有没有价值？**

### Phase 8 — Research Validation

主要验证：

```text
PIT correctness
Backtest validity
Benchmark
No-Trade Quality
Regime behavior
Practicality
```

研究输出：

```text
Hypothesis
Research Candidate
```

不能直接 Production。

---

### Phase 9 — Formal Validation

证据升级到：

```text
OOS
Ablation
Stress
Non-Inferiority
Decision Stability
```

项目当前最明确的剩余研究证据缺口就是 **OOS**。

当前代码已经做到 Golden 与 Current Release Replay 闭合，但正式 Previous-vs-Current OOS 仍是 `OOS_NOT_COMPARABLE`，原因是旧 V9 Release 资产和对应 Frozen OOS Artifact 尚未完整归档。

当前状态因此非常合理：

```text
Golden    PASS
Replay    PASS
OOS       NOT_PROVEN / NOT_COMPARABLE
```

而不是为了发布强行制造 PASS。

---

# 十、Phase 10：Shadow

这是策略从研究走向正式 DSS 的关键阶段。

建议生命周期：

```text
RESEARCH_CANDIDATE
        ↓
OOS_VALIDATED
        ↓
ABLATION_STRESS_VALIDATED
        ↓
SHADOW
```

Shadow 不改变用户实际仓位，只积累：

```text
Decision
No-Trade
Abstain
Safe Mode
Halted
Outcome
MFE / MAE
Decision Stability
Risk Behavior
```

当前项目已经有 Full-Universe Shadow 能力，并实际记录过 CERTIFIED / NO_TRADE / ABSTAIN 等终态。

Shadow 应成为未来很多问题的真实答案来源，而不是继续依赖回测猜测。

---

# 十一、Phase 11：Production Promotion

Promotion 状态机固定为：

```text
DEVELOPMENT
        ↓
SOFTWARE_QUALIFIED
        ↓
RESEARCH_CANDIDATE
        ↓
OOS_VALIDATED
        ↓
ABLATION_STRESS_VALIDATED
        ↓
SHADOW
        ↓
PRODUCTION_ELIGIBLE
        ↓
HUMAN_APPROVED
        ↓
PRODUCTION_DSS
```

任何状态：

> **禁止跳级。**

其中 AI 最多做到：

```text
PRODUCTION_ELIGIBLE
```

最后两步属于 Human Authority：

```text
Human Approval
        ↓
Production DSS
```

---

# 十二、Phase 12：Continuous Certification

Production 不是生命周期终点。

正式上线后进入：

```text
Continuous Evidence
```

长期检查：

```text
PIT Drift
Feature Drift
Permission Drift
Decision Flip Rate
Replay Determinism
No-Trade Quality
OOS Decay
MFE / MAE
Risk Behaviour
Complexity
Shadow / Production Divergence
```

并执行周期性：

```text
OOS Revalidation
Ablation Revalidation
Stress Revalidation
Authority Audit
Replay Audit
Evidence Certification
```

Feature 生命周期：

```text
ACTIVE
  │
  ├── evidence healthy → ACTIVE
  │
  ├── evidence weak    → SHADOW / RESEARCH_ONLY
  │
  └── no value         → RETIRED → Physical Delete
```

这样 QCFP-MTF 才真正具备：

> **可审计 + 可回测 + 可 Ablation + 可退役**

而不是只会不断增加 Feature。

---

# 十三、当前项目在 Roadmap 中的位置

按最新代码状态，我建议标记为：

```text
Phase 0  Product Charter             ✅
Phase 1  Canonical Specification     ✅
Phase 2  Architecture Baseline       ✅
Phase 3  Minimal Trusted Core        ✅ / 基本闭合

Phase 4  Flow Governance Closure     🟡
         └─ 最后 5 个 Surgical Fix

Phase 5  Core Implementation         ✅ 已有成熟主体
Phase 6  Verification Framework      ✅ 已有成熟主体

Phase 7  Software Qualification      🟡
         └─ 等待 FGC zero-bypass

Phase 8  Research Validation         🟡

Phase 9  Formal Strategy Validation  🟡
         └─ OOS 是主要未闭合证据

Phase 10 Shadow                      🟡 已启动

Phase 11 Production DSS Promotion    ⬜

Phase 12 Continuous Certification    ⬜
```

所以现在**不应该再大规模扩建系统功能**。

当前正确优先顺序是：

```text
① 完成 FGC 最后 5 个 Surgical Fix

② 做 zero-bypass governance certification

③ 冻结治理体系

④ 补齐 Previous-vs-Current Formal OOS

⑤ 继续积累 Current Release Shadow Evidence

⑥ Ablation + Stress + OOS 全闭合

⑦ PRODUCTION_ELIGIBLE

⑧ Human Approval

⑨ PRODUCTION_DSS

⑩ Continuous Certification
```

---

# 十四、可选的 Execution Extension

核心 Roadmap 到 `PRODUCTION_DSS` 已经完整。

如果未来真的希望研究自动执行，则另开：

```text
OPTIONAL EXECUTION EXTENSION

Production DSS
      ↓
Certified Decision
      ↓
Execution Certificate
      ↓
Paper
      ↓
Runtime Evidence
      ↓
Broker Adapter
      ↓
Small-Live
```

但它应当继续保持：

```text
QCFP-MTF Core DSS
        ≠
Automated Trading System
```

这样不会因为未来执行实验，把现在已经逐渐收敛的核心架构重新变复杂。

---

## 最终建议的项目里程碑

```text
M0  SYSTEM PURPOSE FROZEN
M1  CANONICAL SPEC FROZEN
M2  ARCHITECTURE BASELINE
M3  MINIMAL TRUSTED CORE
M4  GOVERNANCE CLOSED          ← 当前主要目标
M5  SOFTWARE QUALIFIED
M6  OOS VALIDATED
M7  ABLATION/STRESS VALIDATED
M8  SHADOW VALIDATED
M9  PRODUCTION ELIGIBLE
M10 HUMAN APPROVED
M11 PRODUCTION DSS
M12 CONTINUOUSLY CERTIFIED
```

如果把整个项目压缩成一句工程路线，就是：

> **先固定什么必须正确，再收敛谁有权做决定；然后让 AI 构建、测试系统证明、Evidence 保存事实、Pure Judge 资格裁决；最后通过 OOS/Ablation/Shadow 证明策略价值，由 Human 决定是否晋升为 Production DSS。**
