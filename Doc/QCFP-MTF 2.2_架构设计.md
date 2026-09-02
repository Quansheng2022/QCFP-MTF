# QCFP-MTF 2.2 架构设计

> **文档角色：Historical Design / Evolution Record（历史设计与演进记录，非当前 Authority）**
>
> 本文件记录 QCFP-MTF 2.2 时代的设计背景与决策过程，**不是当前权威文档**，
> 也不自行维护版本号。当前权威如下：
>
> - Highest System Authority：`Core/QCFP_MTF/CANONICAL_SPEC.md`
> - Current Architecture Authority：`Core/QCFP_MTF/ARCHITECTURE.md`
> - Runtime version authority：`Core/QCFP_MTF/decision/versions.py`
>   （MODEL_VERSION / DECISION_RULE_VERSION / SCHEMA_VERSION / engine_version
>   一律以该文件为准）
> - Governance Baseline：`audit/baseline/governance_baseline.json`（Create-Only / Immutable）
>
> 任何与本文件不一致的历史版本号（如 QCFP-MTF-2.1.1 / DECISION_RULE=2.2 /
> SCHEMA_VERSION=1.0）均属历史留档，不作为当前生产事实。

> 版本：QCFP-MTF 2.2（在 2.1.1 之上新增正式领域层，不推翻现有代码）
> 定位：**机构行为状态过滤器 + 散户波段交易决策系统**
> 代码级冻结文档：`Core/QCFP_MTF/ARCHITECTURE.md`（十条规则）

## 一、系统定位

```text
机构负责发现机会；QCFP 识别机构行为与市场状态；
散户利用"可以空仓"的优势，等待确认，只在赔率与风险同时有利时参与。
```

- 不是"预测收益的量化模型"，而是"机构行为状态过滤器 + 散户择时/空仓系统"；
- **Bottom ≠ Buy**；Risk Reduction + Structural Improvement + Price Confirmation = Buy Permission；
- 红灯 = "我不参与"（不是看空做空）。

## 二、分层职责（L0~L8）

```text
L0 Data / PIT / Universe
L1 Institutional Behavior（C 筹码 / F 资金 / P 价格 → 状态/压力/持续性/背离/置信度）
L2 Strategic Trend（Q 季度结构 / P 价格体制）
L3 Stage（月线行为）
L4 Swing Setup（周线突破/回踩/盘整 → setup_type）
L5 Execution（日线触发，只产生 signal，不决定仓位）
L6 Risk（DES / Hard Exit / Stop / Cooldown）
L7 Retail Position FSM（FLAT/TESTING/BUILDING/HOLDING/TRIMMING/EXITING/COOLDOWN）
L8 Position Sizing / Backtest / Validation
```

## 三、决策链与四个分离

```text
① Institutional Permission（有没有资格）→ 交易上限
② Swing Setup（有没有机会）
③ Daily Timing（现在是不是时机）——默认关闭，重新设计后再评估
④ Retail FSM（应该处于什么仓位状态）
⑤ Position Sizing（具体多少仓位）
⑥ Risk / Hard Exit（是否必须退出）——执行层级最高优先级
```

四个概念严格分离：**Institutional State ≠ Permission ≠ Setup ≠ Position State**。

## 四、十条规则（RULE）

```text
RULE 01  Institutional Permission 是交易上限（upper-bound gate）。
RULE 02  Daily Timing 不能升级 Institutional Permission。
RULE 03  Daily Timing 不能直接决定仓位大小。
RULE 04  Retail FSM 拥有仓位生命周期。
RULE 05  Position Sizing 拥有数值仓位目标。
RULE 06  Hard Risk Exit 覆盖所有普通看多信号。
RULE 07  Permission 不是交易信号。
RULE 08  Trading Setup 不是仓位状态。
RULE 09  PIT-invalid 数据不能产生 Research-valid 信号。
RULE 10  新架构必须通过 Shadow Mode 后才允许替换 Legacy。
```

## 五、优先级（最高→最低）

```text
1. Hard Exit（Kill Switch）
2. Stop
3. Cooldown
4. Institutional Permission
5. Risk
6. Weekly Setup
7. Daily Trigger
8. Position State
```

## 六、Institutional Permission 五档

| Permission | 含义 | 散户权限 |
| :-- | :-- | :-- |
| BLOCK | 机构明显不支持 | 禁止新增多仓（持有→TRIMMING） |
| WATCH | 尚未确认 | 观察 |
| TEST | 有改善迹象 | 允许小试仓（10%） |
| ALLOW | 机构行为支持 | 正常波段交易 |
| STRONG_ALLOW | 强机构支持 | 允许正常/较高仓位 |

规则矩阵（第一版冻结）：

| State | Pressure | Persistence | Permission |
| :-- | --: | --: | :-- |
| ACCUMULATION | ≥+1 | ≥2 | ALLOW |
| ACCUMULATION | +2 | ≥2 | STRONG_ALLOW |
| NEUTRAL / UNKNOWN | — | — | WATCH |
| RECOVERY | ≥+1 | ≥1 | TEST |
| DISTRIBUTION | ≤-1 | ≥2 | BLOCK |
| DISTRIBUTION_STRONG | ≤-2 | ≥2 | BLOCK |
| CAPITULATION | -2 | ≥1 | BLOCK |

降级条件（downgrade-only）：Divergence / Low Confidence → WATCH；Poor Data Quality(D) → BLOCK；Market Risk Off → TEST。

## 七、Retail Position FSM 七状态

```text
FLAT → TESTING → BUILDING → HOLDING → TRIMMING → EXITING → COOLDOWN → FLAT
```

- **TESTING** 首仓 10%；**BUILDING** 每次 +10%（上限 70%）；**TRIMMING** 每次 -15%；**HOLDING** 保持；**EXITING/COOLDOWN** 0%；
- 禁止乘法加仓（废除 0.75×1.25）；禁止状态跳跃（FLAT 不得直接 HOLDING）；
- 追高过滤（Chase Filter）：日线突破但 52W 位置 > 0.6 → 不追，等回踩；
- 冷却期：EXIT → COOLDOWN（默认 2 周）→ 重新满足权限 + Setup 才允许 TEST。

## 八、模块目录

```text
Core/QCFP_MTF/
├── institutional/   状态/压力/持续性/背离/置信度/权限（正式领域包）
├── setup/           波段机会识别（swing_setup）
├── decision/        hard_exit / retail_position_fsm / retail_position_sizing /
│                    downside_risk / retail / catalyst_quality / stop_loss /
│                    institutional_*（薄转发）
├── structural/      季度 C/F/P 与 FSM-1
├── behavioral/      月线行为（CBI/VP/Stage）
├── tactical/        周线战术 + 日线战术（DAILY_*）
├── fusion/          MTF 对齐 / 日线时机门 / 防推断
├── backtest/        引擎 / 时间线 / 横截面 / 基准 / 绩效 / PIT / 组合风险 / Run Status
├── scripts/         引擎与实验脚本（见目录与结构图）
└── tests/           单元/集成/金标准/不变量（65 模块）
```

## 九、Canonical Decision Contract（V29 收口）

所有 action / card / report / shadow 都从统一决策链派生，禁止各模块各自作为最终决策源：

```text
Raw Evidence
  → Institutional State
  → Institutional Permission（交易上限）
  → Exit Events（HARD_EXIT / STOP_EXIT / FORCED_DELEVERAGE / NONE）
  → Swing Setup
  → Retail FSM Transition
  → Position Sizing
  → Target Position
  → Execution（T+1）
```

### 9.1 DecisionSnapshot

`decision/decision_snapshot.py::DecisionSnapshot`（不可变对象）：
decision_id / stock / date / inst_state / permission / **permission_cap** /
**exit_event(kind+reason)** / setup_type / prev_fsm / next_fsm / prev_position /
target_position / decision_path / rule_version / model_version /
**schema_version** / **base_fsm_state（矩阵基准）** / **raw_target_position** /
**permission_constraint_applied** / **override_rule_ids（生效规则）** /
**input_fingerprint（输入哈希）** / **settings_hash** /
**institutional_pressure/persistence/reasons** / **context（structural/mtf/market）**。

版本冻结：`MODEL_VERSION=QCFP-MTF-2.1.1`、`DECISION_RULE_VERSION=2.2`、
`SCHEMA_VERSION=1.0`，三者分开记录，不互相承担版本含义。

### 9.2 Permission Policy（V31：风险增量语义，取代绝对状态上限）

| Permission | new_risk（新增风险） | maintain（维持既有） | de_risk（去风险） |
| :-- | :-- | :-- | :-- |
| BLOCK | ✕ | ✕ | 必须 |
| WATCH | ✕ | ✓ | 允许 |
| TEST | 有限 | ✓ | 允许 |
| ALLOW | ✓ | ✓ | 允许 |
| STRONG_ALLOW | ✓ | ✓ | 允许 |

审计不再用"FSM Rank > Permission Cap"判定越权（该口径会把矩阵合法的
WATCH×BUILDING 维持误判为违规），改为两道不变量：

1. **风险增量不变量**：BLOCK/WATCH 下 `target_position ≤ previous_position`
   （`apply_permission_position_cap` + `assert_no_risk_increase`）；
2. **状态-仓位一致性**：`target_position=0` 时不得停留在
   TESTING/BUILDING/HOLDING（→FLAT）；TRIMMING 归零 → EXITING → COOLDOWN → FLAT
   （`state_position_consistent`）。

`permission_cap_exceeded()` 仅保留 BLOCK 的状态级违规语义（TESTING/BUILDING/HOLDING
即违规，维持被禁止），`assert_permission_bound()` 相应更新。

### 9.3 ExitEvent 统一（可审计）

`hard_exit.evaluate_exit_events()` 返回不可变 `ExitEvent`（kind + reason + hard 属性），
是 **FSM 唯一退出输入**：

| kind | 触发 | hard |
| :-- | :-- | :-- |
| `HARD_EXIT` | DES≥7 | 是 |
| `FORCED_DELEVERAGE` | Extreme / 破位+持仓 | 是 |
| `STOP_EXIT` | 止损触发 | 是 |
| `RISK_EXIT` | DES 5~6（软退出） | 否 |
| `BREAKDOWN` | 周线破位（空仓，软退出） | 否 |
| `NONE` | 无 | 否 |

FSM 通过 `TransitionInput` 只消费**已计算完成**的 ExitEvent / Setup / Permission 领域对象，
不再从原始 row 二次解释 DES/Extreme/Stop——报告可回答"这次 EXIT 是谁触发的"。
`transition()` 以 **Permission × FSM 矩阵为实际基准源**（`permission_fsm_base`，
覆盖全部 7 个状态），再叠加 Hard Exit / Lifecycle / Soft Exit / Permission 降级 /
Setup / Risk 覆盖；`transition_audit()` 返回 (state, rule_ids) 供审计。

### 9.4 Stateful Shadow

`scripts/shadow_mode.py`：按 stock_code×decision_date 全历史滚动重放
（prev_state/prev_position 持续演化），**输入完整复现 Canonical Input**：
stock/date/prev_fsm/prev_position/c_state/f_state/**prev_f_state**/p_state/
risk/DES/daily/monthly/weekly/settings_hash（V31 起补齐 prev_f_state，
修复 persistence 被低估的问题）；输出完整 DecisionSnapshot 字段
（含 base/raw target/constraint/rule_ids/fingerprint/schema_version），
不写库不改交易。

### 9.5 Ablation A0~A4

`scripts/permission_fsm_ablation.py`：
A0 Legacy / A1 Legacy+PermCap（Cap 裁剪，非二值门）/ A2 FSM /
A3 Perm+FSM+**Soft Exit**（RISK_EXIT/BREAKDOWN）/ A4 再 +**Hard Exit**；报告年化/Sharpe/MDD/PF/
换手/暴露/暴露效率/坏暴露比/越权数/非法跳跃数/**风险增量越权数**。

口径冻结（V31）：

- **A4−A3 = Hard Exit 的增量贡献**（每次实验只改变一个模块）；
- A2 无权限门默认 `STRONG_ALLOW`、无退出事件；
- A1 与 A3/A4 共用同一 `PERMISSION_POSITION_CAP`（permission_policy.py）；
- BLOCK/WATCH 下 `target_position ≤ previous_position`，逐行统计
  `risk_increase_violations`；越权判定为位置感知的 `permission_state_violation`；
- 实验 JSON 记录 `shared_input_hash / shared_settings_hash / enabled_modules`，
  保证 Attribution 可复核。

实测：A1 把 MDD -21.87%→-11.32%、换手 2.93→1.59；A2 Sharpe +0.50、PF 2.71、
暴露效率 +0.86；A2~A4 零越权、零非法跳跃；当前市场权限全 WATCH/TEST → A3/A4 正确空仓。

## 十、研究边界

- 第一版固定规则矩阵，不放过多可调参数；
- Daily Timing 保持关闭；
- 新增模块走 Shadow Mode（legacy 与 new 双轨），通过 PIT/OOS/Ablation 后才替换 Legacy；
- 当前研究状态：**RESEARCH NOT VALIDATED**（PIT-C + 无 PIT Universe + OOS 为负）——不把回测结果当作有效 alpha 证据。

## 十一、版本变更记录

- **V96（2026-08-28）**：QCFP_MTF Runtime Evidence Closure
  （Shadow → Paper → Small-Live Evidence Accumulation）按 4 个 Sprint
  落地——不新增 Alpha / 不新增决策 Authority，只新增事实、执行现实与
  证据（仅两个新持久化事实对象：qcfp_runtime_event_ledger +
  qcfp_research_outcome）：
  **Sprint 1 — Runtime Identity**：execution_context.py（SHADOW/PAPER/
  SMALL_LIVE 三态；execution_mode 是 Operational Context，禁止进入
  Permission/Wave/FSM/FinalTarget/CanonicalAction/DecisionPathHash；
  same_decision_across_modes 证明同样 Evidence+Release 下三种 mode
  Canonical Hash 完全一致）；
  **Sprint 2 — Outcome + Paper**：research_outcome.py（Research Outcome
  与 Decision Ledger 物理分离，future_aware/research_only/outcome_hash，
  Production import 禁止）；paper_pipeline.py（OrderIntent 差额 → 复用
  OrderStateMachine+Simulator → ACK/PARTIAL/FILLED/REJECTED/UNKNOWN →
  Event/EOD Reconciliation，evidence_source=PAPER_PROXY）；
  **Sprint 3 — Small-Live Reality**：deployment_cap.py（DeploymentTarget
  = min(CanonicalTarget, Cap)，硬不变量 ≤ CanonicalTarget，Cap 只减权
  不改变决策、不阻止 Hard Exit）；broker_adapter.py（仅 5 方法，禁止
  决策计算；timeout → UNKNOWN 必须保留）；runtime_event_ledger.py
  （15→14 类事件 + previous/current 双链，可篡改检测）；
  **Sprint 4 — Failure + Evidence**：monitoring/runtime_evidence.py
  （Runtime Evidence Artifact 聚合真实 Ledger/Event/Outcome；
  Hard Gate 优先——PermissionViolation/UncertifiedExecution/PITViolation/
  CriticalReplayMismatch → CERTIFICATION_SUSPENDED；
  UnresolvedBrokerUNKNOWN/PositionMismatch → NO_NEW_RISK；
  缺证据 → NOT_PROVEN，不允许硬编码 PASS；
  continuous_certification 持续认证）。
  测试总数由 441 模块 → **448 模块全绿**。

- **V95（2026-08-28）**：QCFP_MTF MTR Closure Release（Sprint A–E）
  落地——10 问全部从"声明"变成"机器证据"，不新增 Alpha/Authority/
  评分/平行治理模块：
  **Sprint A — Authority Closure**：
  - scripts/decision_engine.py 重写为薄适配器（只调用
    decision.engine.evaluate 做展示投影，删除 generate_action /
    effective_position_cqs / apply_downside_risk 第二套决策权威，
    engine_source=canonical，authority=CANONICAL_DISPLAY_ONLY；
    正式真值在 Ledger）；
  - execution_ablation.py 移除 --engine legacy|canonical 并改用
    run_canonical_ablation（正式 Ablation Canonical-only）；
  - Authority Graph 升级为行为级（Action 13）：AST 扫描字段赋值 /
    SQL UPDATE·INSERT / 决策写函数调用（permission/wave_stage/target/
    final_target/action/position/certified/validation_status）；
    behavioral_authority_audit() 无视 STATIC_AUTHORITY 登记表，
    两个平行路径都能写同一最终字段 → DUPLICATE_*_AUTHORITY；
  **Sprint B — Feature/Complexity Truth**：
  - production_feature_manifest_artifact() 唯一 Production ACTIVE truth
    （state/owner/reachable/participating/evidence_level/release_id/
    retirement_condition）；FEATURE_SET 降级为 Code Capability Catalog；
  - freeze_mtr_baseline() 不可变（已存在拒绝覆盖，工具不能改 before）；
  **Sprint C — Evidence Closure**：
  - regression_evidence() 缺证据 → NOT_PROVEN（不再默认 PASS）；
  **Sprint E — Independent MTR Acceptance**：
  - evaluate_mtr(evidence_bundle) 纯裁判——READ evidence → COMPARE →
    ISSUE verdict；禁止 invent baseline / default PASS / 手工标 1 /
    手工标 zero escaped；缺任一 artifact → NOT_PROVEN。
  测试总数由 440 模块 → **441 模块全绿**。

- **V94（2026-08-28）**：QCFP_MTF Minimal Trusted Production Release
  （MTR）——真正做减法（12 项工作步骤，非 12 个新模块）：
  1. Freeze Baseline → baseline.json；
  2. Production Roots → roots.json；
  3. Authority Graph（复用 PWC-2）；
  4. Audit（duplicate/orphan/legacy/leakage/island）→ audit.json；
  5. 全模块分类 → retirement_register.csv；
  6. Removal Candidates → removal_candidates.json；
  7. Necessity+Ablation Review（mandatory_governance 例外）→
     retirement_evidence.json；
  8. Logical Detachment（Batch A/B/C）→ detached_graph.json；
  9. Verify Unreachable → graph_diff.json；
  10. Physical Delete（诚实：无孤儿库文件；已逻辑断开候选保留为
      Shadow/Research NON_CERTIFIABLE）→ code_diff.json；
  11. Golden/OOS/Replay/Safety 五层证明 + Deletion Invariant
      （Complexity↓ 但 Trust Evidence 不得↓）→ regression_evidence.json；
  12. Convergence Certificate（三态 CONVERGED / SAFE_BUT_NOT_CONVERGED /
      REJECTED）+ 4 个 Release Gate（Authority / Shrinkage / Trust /
      Physical Retirement）+ 10 问 DoD → convergence_certificate.json。

  真实代码库运行结果（scripts/minimal_trusted_release.py）：
      Executable paths       3 → 1      (-67%)
      ACTIVE features       17 → 8      (-53%)
      Decision-critical LOC 2455 → 1885 (-23%)
      Duplicate authorities  2 → 0      (-100%)
      Legacy imports         2 → 0      (-100%)
      Canonical/Replay/Invariant/OOS  不得下降（Trust PASS）
      Certificate = CONVERGED，DoD = MTR_SUCCESS
  产物输出到 Report/QCFP_MTF/audit/mtr/（12 个 Artifact）。
  测试总数由 439 模块 → **440 模块全绿**。

- **V93（2026-08-28）**：QCFP_MTF Production Authority Graph +
  Physical Retirement（PWC-2）落地——从"继续完善系统"正式切换为
  "第一次让三个指标真实下降"：
  - **Authority Graph**（governance/pwc2_authority_graph.py）：从真实
    Production roots（canonical_replay/evaluate/certify_decision/
    execution_gate/record_snapshot/incident_protocol）经静态 import
    扫描（含相对导入解析）自动建立节点+边（IMPORTS/CALLS/CAPS/
    CERTIFIES/EXECUTES/PERSISTS）+ Authority 类型（INPUT/
    RISK_UPPER_BOUND/OPPORTUNITY_PROPOSAL/LIFECYCLE_PROPOSAL/CAP/
    FINAL_TARGET/EXECUTION_ELIGIBILITY/FACT/FORMAL_RESEARCH_STATUS）；
  - **五类危险节点审计**：Duplicate Authority（仅真正平行、互不可达的
    权威）、Production Orphan（ACTIVE_BUT_UNWIRED）、Dead Production
    Path、Research Leakage、Governance Island；
  - **Retirement Classification + Register**：ACTIVE_CORE /
    ACTIVE_SUBCAPABILITY / RESEARCH_ONLY / SHADOW_ONLY / APPENDIX /
    ARCHIVE / RETIRED，证据驱动（binding=0 + ablation=0 + 非强制 →
    RETIRED）；只允许 KEEP/MERGE/RESEARCH_ONLY/ARCHIVE/DELETE；
  - **Logical Detachment**：候选必须从 Production 真正断开
    （production_reachable=False）才能进入删除；
  - **Convergence Before/After + 三降硬门**：ExecutableDecisionPaths /
    ACTIVE Features / Production-critical LOC 必须下降，Duplicate
    Authorities / Legacy imports 必须 = 0，覆盖/OOS 质量不得下降 →
    PHYSICAL_CONVERGENCE_PROVEN；
  - **5 个 Release Artifact**：authority_graph / retirement_register /
    convergence_before_after / regression_evidence / production_manifest
    （JSON + MD）；
  - **运行器**（scripts/pwc2_convergence.py）：在真实代码库上跑出
    Executable paths 3→1、ACTIVE features 52→39、decision-critical LOC
    下降，Convergence = PHYSICAL_CONVERGENCE_PROVEN，
    产物输出到 Report/QCFP_MTF/audit/pwc2/。
  测试总数由 438 模块 → **439 模块全绿**。

- **V92（2026-08-28）**：QCFP_MTF Production Wiring Closure — PWC-1
  （10 项）落地——只做修接线、堵旁路、Fail-Closed、绑定身份、
  统一正式研究入口、物理删除：
  1. **DecisionPathHash 重新接线**（decision/engine.py）：CanonicalAction
  先于 Hash 生成；PathHash 覆盖 FinalTarget/Wave/Action/Release/
  EvidencePack/Data/Universe/Participating 完整材料状态——
  Decision material state changes ⇒ PathHash changes；
  2. **DataQualityGate 绝对 Fail-Closed**（data/quality.py）：
  CRITICAL_QUALITY_CHECKS（available_date/price_continuity/suspension/
  schema/source_version）；状态 PASS/DEGRADED/BLOCK/UNKNOWN——
  critical FAIL→BLOCK、critical UNKNOWN/缺失→UNKNOWN（≠PASS）、
  非关键异常→DEGRADED、全部明确 PASS→PASS；
  3. **Daily Data Trust 真实指标**（scripts/check_data_quality.py +
  monitoring/data_trust_report.py）：移除 timeliness=1.0 等硬编码，
  缺失→UNKNOWN；universe_snapshot/disclosure_mode 缺失→UNKNOWN；
  无 Transformation telemetry→UNKNOWN；Critical 证据缺失时总体不能
  NORMAL；
  4. **Certification Cross-Binding**（decision/certified_decision.py）：
  Snapshot/Manifest/EvidencePack 必须同属一个 Release；
  RELEASE_ID_MISMATCH / MANIFEST_HASH_MISMATCH /
  EVIDENCE_PACK_RELEASE_MISMATCH / EVIDENCE_HASH_MISMATCH /
  DATA_SNAPSHOT_MISMATCH / UNIVERSE_SNAPSHOT_MISMATCH 精确拒绝；
  5. **Release 身份进入 Snapshot + Ledger**（decision/decision_snapshot.py
  + decision_ledger.py + engine）：release_context 单参数接线；
  Snapshot 写入 release_id/release_manifest_hash/evidence_pack_hash/
  production_manifest_hash/data_snapshot_id/universe_snapshot_id/
  participating_feature_hash；record_snapshot 把 release_identity 写入
  Ledger context（Ledger 保存事实，不重新发明事实）；
  6. **Ledger Commit Invariant Gate**（decision/decision_ledger.py）：
  assert_snapshot_commit_invariants() I1 Permission / I2 Wave 单调 /
  I3 CanonicalAction / I4 HardCaps / I5 PIT / I6 Identity；
  Production mode 失败 → LedgerCommitRejected（不是第二决策引擎）；
  7. **UNKNOWN Caps → No-New-Risk**（decision/engine.py）：
  UNKNOWN critical caps → target = min(target, previous_position)；
  空仓 0、已持仓维持/减仓、Hard Exit 才 0（UNKNOWN 不制造市场退出）；
  8. **Formal Stress Canonical-Only**（scripts/cost_stress_test.py）：
  build_signal_timeline+run_backtest → run_canonical_stress()；
  正式验证脚本 build_signal_timeline 直接调用 = 0；
  9. **Engine ACTIVE Production Manifest + Participating Manifest**
  （decision/engine.py + governance/production_feature_manifest.py）：
  每笔 Decision 计算 participating_feature_hash（实际经过的能力），
  全局 FEATURE_SET Hash 不再作为每笔交易最关键身份；
  10. **Retirement Table + PWC-1 验收矩阵**
  （governance/convergence_release.py）：retirement_table()
  KEEP/MERGE/RESEARCH_ONLY/ARCHIVE/DELETE（不新增状态）；
  pwc1_acceptance_matrix() 15 问总验收（"不要测试函数存在，
  要测试系统能否绕过它"）。
  测试总数由 431 模块 → **438 模块全绿**。

- **V91（2026-08-28）**：数据健康检查报告优化——升级为正式
  Daily Data Trust Report（monitoring/data_trust_report.py +
  scripts/check_data_quality.py）：
  - 现有 check_data_quality.py 继续输出 data_quality_report CSV/JSON +
    qcfp_data_quality_audit 历史快照；
  - 新增 daily_data_trust_report_v2() 串成统一主报告：Overall（DHS/
    Status/Evidence Grade/Decision Readiness/Risk Cap）→ Source Health →
    Source Integrity（Schema/Source Version/Duplicate/Timestamp/Price
    Continuity/Corporate Action/Suspension/Cross-source；Source Version=
    UNKNOWN → 总体不能 NORMAL）→ PIT 专节（Integrity/Grade/Future
    Timestamp/AvailableDate Fail/Universe/Disclosure Mode）→
    Transformation Health（Stage Input/Output/NaN/Version/Status，
    中间步骤把数据处理坏必须被发现）→ Evidence Quality →
    Decision Readiness（YES/DEGRADED/NO/UNKNOWN 四态）→ Critical
    Issues → Action；
  - trust_report_to_md() 输出给人看的主报告，细节进 JSON/CSV
    （Appendix）；
  - continuous_validation_report.py 默认指标已是 None →
    UNKNOWN → SAFE_MODE（没有数据 ≠ 默认正常），保持 fail-closed。
  测试总数由 430 模块 → **431 模块全绿**。

- **V90（2026-08-28）**：QCFP_MTF Release 3（21–30）——
  Evidence of Necessity & Controlled Evolution 落地：
  21. **Schema Contract Release Hard Gate**
  （decision/schema_contract.py）：release_id/release_manifest_hash/
  decision_path_hash/canonical_action/wave_proposal_target 正式纳入
  REQUIRED；schema_release_hard_gate()——未变→DIRECT_REPLAY、
  变且有迁移→MIGRATION_REQUIRED→PASS、变且无迁移→RELEASE_REJECTED、
  FORBIDDEN future 字段→NOT_REPLAYABLE；
  22. **Historical Integrity Corpus**
  （decision/historical_integrity.py）：9 类市场/权限/退出历史 case 冻结
  EvidenceSnapshotID/ReleaseID/DecisionHash/FinalTarget/Action/Binding/
  LedgerHash；历史事实静默变化数量必须 = 0；
  23. **Version Impact Release Gate**
  （governance/version_impact.py）：Change Severity LEVEL 0–4；
  Permission/HardExit/FinalTarget 大面积 Flip →
  FULL_OOS_ABLATION_STRESS_SHADOW_HUMAN；所有 Production-critical
  commit 必须 Change Impact Report；
  24. **OOS Coverage 强制绑定**
  （monitoring/decision_coverage.py）：oos_coverage_requirement()——
  正式 OOS 必须同时报告 Sharpe/MDD/WaveCapture + Certified/NoTrade/
  Abstain/Safe/Halted + 原因分布；缺 Coverage → INCOMPLETE_REPORT，
  不能用于 Promotion；
  25. **Binding Attribution → 规则去留**
  （monitoring/binding_constraint_frequency.py）：constraint_keep_verdict()
  ——每个非宪法级 Governance Rule 必须有 Binding/Ablation Evidence，
  否则 RETIRE/MERGE/REVIEW（KEEP 需 binding + 独立影响）；
  26. **Risk Budget Lineage**
  （monitoring/risk_budget_utilization.py）：risk_budget_lineage()——
  Available→Requested→Approved→Executed→Broker Actual 完整链路，
  回答"35% 是主动选择还是被 Liquidity/Portfolio 压下来"；
  27. **Retail Practicality Hard Gate**
  （evaluation/retail_scorecard.py）：retail_operating_envelope()——
  阈值版本化为 Default Retail Operating Envelope（PRACTICALITY-1.0）；
  practicality_hard_gate()——Statistical Valid=YES + Practicality=C
  → PROMOTION_BLOCKED（不能因 Sharpe 高破例）；
  28. **Benchmark Ladder B2–B6 必跑**
  （research/benchmark_ladder.py）：oos_benchmark_table() 固定输出
  B2–B6 对照；benchmark_missing_gate()——Ladder missing →
  PROMOTION_BLOCKED；
  29. **Major Release Minimum Canonical 必答**
  （research/minimum_viable_canonical.py）：major_release_minimal_answer()
  ——每个大版本必须给出 MINIMAL_SUFFICIENT 或 FULL_REQUIRED，不能没有
  答案；
  30. **Complexity Ceiling Veto**
  （governance/complexity_ceiling.py）：complexity_veto_release()——
  Ceiling FAIL + 无强增量证据 → RELEASE REJECTED（不是 warning）；
  有证据 → HUMAN_REVIEW。
  测试总数由 420 模块 → **430 模块全绿**。

- **V89（2026-08-28）**：Release 2（11–20）——Production Identity +
  Execution Reality + Deterministic Trust 落地：
  11. **PermissionPolicy 唯一权限语义源**（decision/permission_policy.py
  + permission_gate.py + governance.py）：BLOCK 统一为渐进去风险
  （target ≤ previous），Hard Exit → 0；permission_gate/
  governance_matrix_ok 不再把 BLOCK+正仓位一律判违规（带 previous 上下文
  时允许渐进降风险）；
  12. **Release 身份链**（decision/decision_snapshot.py）：Snapshot 增加
  release_id/release_manifest_hash/evidence_pack_hash/universe_snapshot_id，
  decision→ReleaseManifest→EvidencePack→ValidationCertificate 100% 可反查；
  13. **DecisionPathHash Release 2**（decision/path_hash.py）：纳入
  wave_id/wave_stage/wave_strength/wave_proposal_target、FinalTarget、
  CanonicalAction、ReleaseManifestHash、EvidencePackHash、DataSnapshotID、
  UniverseSnapshotID；任一变化 → PathHash 必变；
  14. **Golden Corpus Release Gate**（governance/golden_decision_corpus.py）：
  golden_release_gate()——Golden Hash 变化必须有批准的 Change Reason，
  否则 Release 阻塞（不能只是"更新 expected 值"）；
  15. **ExecutableTarget 链**（execution/executable_target.py）：
  FinalTarget→Tradability→MarketSession→ExecutableTarget；
  SUSPENDED/HALTED/DELISTING/NO_VOLUME→no order、CorporateAction→降低、
  HalfDay→半容量、AfterClose→下一 session；
  16. **Order State Machine + Position Reconciliation**
  （execution/order_state_machine.py）：INTENT→SENT→ACKNOWLEDGED→
  PARTIAL/FILLED/REJECTED/CANCELLED/UNKNOWN；UNKNOWN→禁止重发/新订单→
  查询 broker→reconcile；Canonical/Internal/Broker 三方
  IN_SYNC/PARTIAL/MISMATCH/UNKNOWN，MISMATCH/UNKNOWN→NO_NEW_RISK；
  17. **Critical Path Runtime 事件**（monitoring/critical_path_observability.py）：
  build_runtime_critical_path()——真实 stage event（latency/version/
  input/output hash/reason），SKIPPED≠MISSING；任何决策类型生成
  CriticalPathTrace；
  18. **PerformanceMetricContract**（governance/performance_metric_contract.py）：
  backtest.performance.evaluate 唯一指标层；正式路径自行算
  Sharpe/MDD/CAGR → METRIC_AUTHORITY_VIOLATION；同一 returns 指标一致；
  19. **Participating Manifest**（governance/production_feature_manifest.py）：
  Release Feature Manifest（仅 ACTIVE）+ Decision Participating Manifest
  （实际参与能力）；DecisionHash = ReleaseManifestHash + ParticipatingHash；
  20. **Failure Injection Qualification**（governance/failure_injection.py）：
  12 类注入（含 Broker UNKNOWN/Position mismatch），结果分类
  BLOCKED_AS_DESIGNED/SAFE_MODE/DECISION_HALTED/RECOVERY_REQUIRED/
  FAILURE_ESCAPED；FAILURE_ESCAPED>0 → Release REJECTED。
  测试总数由 410 模块 → **420 模块全绿**。

- **V88（2026-08-28）**：QCFP_MTF Convergence Release —— Canonical
  Authority & Production Trust 收敛版（1–10）落地，目标唯一决策链、
  唯一事实链、唯一认证链：
  1. **certify_decision 绝对 fail-closed**（decision/certified_decision.py）：
  废弃 boolean 默认参数，改证据对象型；missing/UNKNOWN/FAIL/expired/
  scope/hash mismatch → REFUSED；Evidence Pack 在 Certification 内部校验；
  2. **ProposalAction 分类器**（decision/action_classifier.py）：唯一
  ENTRY/ADD/HOLD/REDUCE/EXIT/NO_TRADE 分类，修复 CONFIRMING+FLAT 被误判
  ADD；
  3. **WaveProposalTarget 唯一传递**（decision/engine.py）：
  FSM→FSMProposalTarget→Wave→WaveProposalTarget→State Consistency（不产生
  新 Target）→Governance→FinalTarget；强不变量 FinalTarget ≤
  WaveProposal ≤ FSMProposal；
  4. **CanonicalAction = FinalTarget Delta**（decision/canonical_action.py）：
  最终 Action 只由 Previous→Final 派生；不一致 → CANONICAL_ACTION_
  INVARIANT_FAIL 阻止 Ledger commit；
  5. **Caps UNKNOWN/degrade**（decision/governance_caps.py）：Production
  缺 REQUIRED cap（portfolio/liquidity/execution）→ UNKNOWN → 不新增风险
  → NOT_CERTIFIED；Exploration → ASSUMED 1.0 + NON_CERTIFIABLE；
  6. **Ledger Global/Run 双链拆分**（decision/decision_ledger.py）：
  verify_global_chain() / verify_run_chain() 分开验证，绝不在 run 过滤行上
  验证 Global；interleaved runs 测试通过；
  7. **Formal Research 全面 Evidence-only**
  （scripts/research_validation.py）：build_signal_timeline →
  build_evidence_timeline；正式路径禁止 legacy target/action；
  8. **ValidationCertificate 唯一权威**：Research Script 只产生
  ResearchEvidenceBundle → validation_certificate() → certificate_display()；
  删除散落 "Research Validated" 判断；
  9. **退役旧 Ablation + Wave taxonomy 唯一**
  （ablation/experiments.py + wave/stage_gate.py）：Legacy permutation
  ablation → RESEARCH_ARCHIVE/NON_CERTIFIABLE；Formal Ablation Authority=1；
  wave_stage 只允许 6 态生命周期，诊断阶段 → wave_phase_diagnostic
  （RESEARCH_ONLY）；
  10. **Convergence Release Gate**（governance/convergence_release.py）：
  module_classification_gate（ACTIVE_CORE/SUB_CAPABILITY/RESEARCH_ONLY/
  SHADOW_ONLY/APPENDIX/ARCHIVE/RETIRED）+ convergence_release_gate
  （A Canonical Semantics / B Fail Closed / C Fact Integrity /
  D Research Authority / E Convergence）。
  测试总数由 399 模块 → **410 模块全绿**。

- **V87（2026-08-28）**：新一轮 91–100 优先修改项落地——
  P8：证据封装 + 认证边界 + 规则退出/重启 + 治理瘦身 + 架构定稿 +
  复杂度停止规则（1–100 收口）。
  91. **Evidence Pack 写入 Ledger**
  （governance/production_evidence_pack.py）：evidence_pack_ledger_binding()
  ——DecisionSnapshot.release_id + EvidencePackID + EvidenceHash 写入
  Ledger；decision_qualification_answer()——任意 Production Decision
  回答"凭什么有资格被正式使用"，反查不到 → NOT_CERTIFIED；
  92. **Certification Scope 子集**
  （governance/certification_scope.py）：claim_within_certified()——
  ClaimScope ⊆ CertifiedScope 否则 NOT_CERTIFIED
  （验证的是一个明确系统实例，不是一个模糊模型名字）；
  93. **Evidence Hierarchy 绑定生命周期**
  （research/evidence_hierarchy.py）：evidence_level_lifecycle()——
  L0–1→HYPOTHESIS、L2→CANDIDATE、L3→SHADOW、L4→PRODUCTION_ELIGIBLE、
  L5/6→持续认证；active_feature_evidence_required()——ACTIVE Feature
  无 Evidence Level → RESEARCH_ONLY；
  94. **Evidence Contradiction 报告保留**
  （research/evidence_contradiction.py）：contradiction_promotion_report()
  ——强 CONTRADICTING 证据必须保留到 Research Review/Promotion Report，
  禁止平均成综合分（Risk > Return ≠ 所有指标平均）；
  95. **Sunset Policy Retirement Condition**
  （governance/sunset_policy.py）：retirement_condition_required()——
  没有 Retirement Condition 不得进入 Production；ACTIVE 是"暂时获得
  继续存在资格"，命中触发 → ENTER_SUNSET；
  96. **Strategy Kill 整策略级判定**
  （safety/strategy_kill.py）：strategy_not_stock_answer()——明确回答
  "什么时候不是股票错了，而是整个 StrategyVersion SUSPENDED"；
  97. **Reactivation 必须引用证书**
  （safety/reactivation_gate.py）：reactivation_requires_certificate()——
  SUSPENDED→PRODUCTION 状态变化必须引用 ReactivationCertificate
  （修复 ≠ 重新获得可信资格）；
  98. **Governance 组件判定**
  （governance/governance_minimalism.py）：governance_component_verdict()
  ——治理组件也接受 KEEP/MERGE/DROP；governance_certificate_consolidation()
  ——多种证书检查是否共享 schema；
  99. **One-Page Canonical Architecture Contract**
  （governance/one_page_canonical.py）：architecture_contract_check()——
  新增 Production 模块必须说明属于哪一个核心 stage；
  回答不了 → RESEARCH_ONLY/APPENDIX/SHADOW_ONLY/RETIRE；
  100. **Final Design Principles 停止规则**
  （governance/final_design_principles.py）：final_design_principle_gate()——
  FinalDesignPrincipleCheck = CONFORMANT 否则 PROMOTION REJECTED，
  无论收益改善多少；这是 1–100 的"停止功能堆积、开始系统收敛"制度边界。
  测试总数由 389 模块 → **399 模块全绿**。

- **V86（2026-08-28）**：新一轮 81–90 优先修改项落地——
  P7：规则老化 + 证据过期 + 主动删除 + 状态压缩 + 研究隔离 +
  历史事实保护 + 最小治理核心。
  81. **Governance Aging 接 Release**
  （governance/governance_aging.py）：aging_promotion_gate()——到期规则
  失去自动续证资格，必须重新拿 PIT/OOS/Ablation/Stress Evidence；
  2026 年无人验证的规则不能因 2024 年通过一次测试就永久 ACTIVE；
  82. **Evidence Expiry 绑定 Certificate + EvidencePack**
  （governance/evidence_expiry.py）：expired_certificate_block()——
  Expired Certificate 不能为新 Production Release 提供认证；
  evidence_pack_certificate_valid()——证书过期则证据包失效；
  83. **Rule Removal Candidate**
  （governance/rule_removal_test.py）：rule_removal_candidates()——
  周期性产生删除候选，删除同样走 FULL_VALIDATION，
  目标反过来：证明没有它仍然足够好；
  84. **Dominated → 删除测试入口**
  （research/dominated_rule_detection.py）：dominated_to_removal()——
  REDUNDANT/DOMINATED 真正进入第 83 项删除测试，
  而不是只输出分类报告；
  85. **Decision Compression 采用**
  （evaluation/decision_compression.py）：RECOMMENDED_COMPRESSED_TAXONOMY
  = NO_TRADE/ENTRY/HOLD/REDUCE/EXIT；compression_adoption()——
  风险/Wave Capture 基本不变且 Flip 更低/解释更容易 → 采用更少
  taxonomy（减少认知复杂度，不用 smoothing 掩盖治理边界）；
  86. **State Value Audit**
  （monitoring/state_transition_audit.py）：state_value_audit()——
  每个 Production State 必须证明独立生命周期含义或决策价值；
  从不改变 FinalTarget 的状态 → 压缩候选；
  87. **Cross-Layer 权力边界**
  （governance/cross_layer_contradiction.py）：SEMANTIC_BOUNDARIES 固化
  Opportunity≠Permission / Proposal≠Decision / Decision≠Execution /
  Outcome≠DecisionQuality；authority_boundary_violation()——下游升级
  Permission / Report 改写 Action / Execution 绕过 FinalTarget 才报警；
  88. **Research/Production 隔离零容忍**
  （governance/research_production_leakage.py）：leakage_ci_zero_tolerance()
  ——Production 可达的 Research-only 节点 = 0，否则 CI FAIL（不是 warning）；
  89. **Historical Integrity 接 Release**
  （decision/historical_integrity.py）：release_historical_replay_check()——
  升级后历史 CanonicalDecisionHash 变化 = RELEASE_FAILURE，
  除非明确记录 migration/correction event（不能修改历史事实）；
  90. **Minimal Governed Core 十阶段链**
  （governance/minimal_governed_core.py）：production_chain_completeness()——
  Production 必须用一条十阶段链完整解释（SINGLE_CHAIN），
  出现第二套权力链 → SECOND_AUTHORITY_CHAIN_DETECTED；
  remap_to_core()——全部模块重映射到十个核心，
  无法映射且无独立必要性 → 降级/删除。
  测试总数由 379 模块 → **389 模块全绿**。

- **V85（2026-08-28）**：新一轮 71–80 优先修改项落地——
  P6：必要性证明 + 唯一规则归属 + 主动删重 + 错误归因 + 故障恢复 +
  研究债务清理 + Production 简洁度制度化。
  71. **Decision Necessity 周期性资格审查**
  （governance/decision_necessity.py）：necessity_verdict()——
  有唯一职责+独立价值 → KEEP；有价值但高度重合 → MERGE；
  无独立价值 → DROP；无法证明 → REVIEW
  （不能因为"一直都在"就永久 ACTIVE）；
  72. **Rule Ownership 唯一 Owner**
  （governance/rule_ownership.py）：CANONICAL_RULE_OWNERS 固定 9 条
  决策关键规则的唯一 Owner（Permission→PermissionPolicy、FinalTarget→
  Governance、Wave→WaveStagePolicy、FSM→RetailFSM、HardExit→RiskExit、
  Tradability→ExecutionTradability、Validation→ValidationCertificate、
  Historical fact→Ledger）；rule_owner_violation_check()——非 Owner 实现
  → RULE_OWNER_VIOLATION（只能 CONSUME，不能 REINTERPRET）；
  73. **Duplicate Logic → Release Gate**
  （governance/duplicate_logic_detector.py）：BUSINESS_RULE_PATTERNS 8 类
  业务决策规则；duplicate_authority_release_gate()——业务规则重复 →
  RELEASE_BLOCKED（Duplicate Authority=0；普通 helper 重复不阻止）；
  74. **Decision Surface Cliff 分类**
  （evaluation/decision_surface_audit.py）：cliff_classification()——
  EXPECTED_GOVERNANCE_CLIFF（Permission 硬边界合理）/ UNEXPECTED_MODEL_
  CLIFF（模型脆弱性需审查）/ STATE_FLAPPING；发现跳变 ≠ 自动平滑；
  75. **Risk Reduction Attribution 模块判定**
  （evaluation/risk_reduction_attribution.py）：risk_module_verdict()——
  risk reduction=0 + ablation=0 + duplicate coverage>0 → DELETE_REVIEW；
  每个风险模块必须证明 Independent Risk Reduction；
  76. **Decision Error Taxonomy 接交易复盘**
  （failure/decision_error_taxonomy.py）：trade_postmortem()——
  Outcome → Error Classification → Root Cause → Corrective Layer
  （按最长关键词归类，最具体优先）；盈利但 PIT 污染仍属 PIT_ERROR；
  77. **Recovery Replay 状态一致性**
  （safety/recovery_replay_test.py）：recovery_state_consistency()——
  恢复 Production 前必须 Ledger/Position/FSM/Permission/Release/Config/
  DecisionHash 全一致；服务启动 ≠ 恢复，不一致仍 DECISION_HALTED；
  RecoveryReplayCertificate REQUIRED；
  78. **Research Debt 实验功能老化**
  （governance/research_debt_register.py）：experimental_feature_aging_
  report()——EXPERIMENTAL ≥2 周期无结果 → DELETE_REVIEW，OOS 失败 →
  REJECTED；EXPERIMENTAL 不能成为永久状态；
  79. **Production Simplicity KPI Release 判定**
  （governance/production_simplicity_kpi.py）：release_simplicity_verdict()
  ——复杂度显著上升而 OOS/Risk/Practicality 无改善 → SIMPLIFY_REQUIRED；
  Performance 与 Simplicity KPI 并列；
  80. **System Constitution 12 条最高优先级 Gate**
  （governance/system_constitution.py）：CONSTITUTION_PRINCIPLES 扩展为
  12 条（新增 Ledger+Hash+Replay / OOS+Ablation+Stress>主观判断 /
  Opportunity 不能升级 Permission / Report 不能创建 Decision /
  Research 不能写 Production）；constitution_gate()——任一失败 →
  CONSTITUTION_FAIL → Promotion REJECTED（Sharpe+30% 也不能破例）。
  测试总数由 369 模块 → **379 模块全绿**。

- **V84（2026-08-28）**：新一轮 61–70 优先修改项落地——
  P5：人工责任闭环 + 规则删重 + 风险资金效率 + "为什么没交易"解释 +
  报告压缩 + 1–70 治理关门。
  61. **Human Override 接 Execution + Ledger**
  （governance/human_override.py）：override_ledger_chain()——Canonical →
  Override → Executed 正式事实链，ExecutedTarget≠CanonicalTarget 必须
  存在 OverrideEvent 否则 Ledger Integrity FAIL；override_permission_
  boundary()——人工默认只能 SKIP/REDUCE/EXIT/HALT，不能私下扩大风险权限；
  62. **Override Outcome Review 接真实 Outcome**
  （evaluation/override_outcome_review.py）：override_quarterly_review()——
  季度回答"人工干预是增加价值还是噪声"（count/avoided/missed/wrong/
  net value），结果只进 Research Evidence + Human Review，
  人工连续成功 ≠ 自动提高人工权限；
  63. **Decision-Critical 阈值 REVIEW**
  （research/threshold_sensitivity_map.py）：DECISION_CRITICAL_THRESHOLDS
  只查 7 类关键阈值；critical_threshold_review()——发现悬崖 → REVIEW，
  禁止自动寻优（好规则应该有平台，不应只在一个小数点上成立）；
  64. **Rule Interaction → 删重工具**
  （research/rule_interaction_audit.py）：rule_action_candidates()——
  最终产物是 KEEP / MERGE / DROP / RESOLVE_AUTHORITY 候选
  （REDUNDANT→MERGE、DOMINATED→DROP、CONFLICTING→明确 Authority）；
  65. **Binding Constraint Frequency 作为退役证据**
  （monitoring/binding_constraint_frequency.py）：retirement_evidence()——
  binding=0 + ablation value=0 + 非强制治理 → RETIRE_REVIEW；
  liquidity_high_binding_diagnosis()——Liquidity 高频 binding 65% →
  修改上游 Proposal 而非放宽 Liquidity；
  66. **Risk Budget Utilization 资金效率报告**
  （monitoring/risk_budget_utilization.py）：risk_efficiency_report()——
  正式报告必须展示 Available/Approved/Executed/Unused Risk +
  utilization band + 诊断，而不是只有仓位百分比；
  67. **Opportunity Funnel 接真实 Canonical Ledger**
  （evaluation/opportunity_funnel.py）：funnel_from_ledger()——数字全部
  来自 Ledger/Snapshot/ConstraintTrace（第二事实源禁止）；
  no_trade_explanation()——任意 NO_TRADE 回答在哪层退出 + 为什么；
  68. **Decision Latency 增量价值证明**
  （monitoring/decision_latency_budget.py）：latency_value_justification()——
  延迟显著增加但 OOS 增量 ≤1% → ROLLBACK_COMPLEXITY；
  69. **Report Information Budget 六块主报告**
  （report/information_budget.py）：MAIN_REPORT_SECTIONS 固定六块
  （Permission/Wave Stage/Final Target/Decision Delta/Binding Risk/
  Exit Invalidation）；report_field_justification()——不改变理解或行动
  → APPENDIX（报告复杂度也属于系统复杂度）；
  70. **Governance Closeout 1–70 关门检查**
  （governance/completeness_review.py）：governance_closeout()——
  十类关键项全部 CLOSED 才 ENTER_LONG_TERM_MAINTENANCE；
  测试数量与 Feature 数量不能替代治理关门。
  测试总数由 359 模块 → **369 模块全绿**。

- **V83（2026-08-28）**：新一轮 51–60 优先修改项落地——
  把已有模块从"代码存在 + 测试存在"升级为不可绕过的
  Production / Research Gate。
  51. **Production Acceptance 唯一总闸**
  （governance/production_acceptance.py）：production_acceptance_gate()——
  REJECTED Release → CertifiedDecision 数量必须为 0（验收不通过就不能执行）；
  52. **Benchmark Ladder 强制进入 Promotion**
  （research/benchmark_ladder.py）：promotion_requires_ladder()——
  没有 Ladder 结果（至少 Permission+Wave 与 WaveOnly 基线）→ 不允许
  Production Promotion；
  53. **Decision Cost Budget 进入牛散实战验收**
  （evaluation/decision_cost_budget.py）：retail_practicality_gate()——
  OOS 表现接近时优先选择决策负担更低、仓位变化更少、人工关注更低的版本；
  54. **Counterfactual 接真实 Ledger + Outcome**
  （evaluation/counterfactual_audit.py）：counterfactual_from_snapshot()——
  从真实 DecisionSnapshot + ConstraintTrace + Outcome 自动产生反事实，
  只能进入 Research Evidence Store（cannot_modify_ledger）；
  55. **Research Artifact Bundle 唯一可重现载体**
  （research/research_artifact_bundle.py）：promotion_requires_artifact()——
  无唯一 ResearchArtifactID 或未通过 reproducibility verification →
  不能进入 Candidate（跑一个脚本看结果不错 ≠ 进入 Candidate）；
  56. **Negative Result Registry 接入 Feature Proposal**
  （research/negative_result_registry.py）：feature_proposal_gate()——
  立项前先查 Registry；被删模块换名字重入必须解释为何过去失败
  现在可能不再适用，否则 BLOCKED_NO_JUSTIFICATION；
  57. **Critical Path 接真实 Canonical Runtime**
  （monitoring/critical_path_observability.py）：decision_layer_outcome()——
  任何 CertifiedDecision / NO_TRADE / ABSTAIN 都能回答在哪一层
  被通过或过滤（FILTERED/CERTIFIED_DECISION/NO_TRADE）；
  58. **Decision Coverage 与 Performance 强制绑定**
  （monitoring/decision_coverage.py）：report_completeness_check()——
  只显示 Sharpe/MDD 不显示 Coverage → INCOMPLETE_REPORT；
  严格区分 NO_TRADE ≠ ABSTAIN；
  59. **Minimum Viable Canonical 真正运行**
  （research/minimum_viable_canonical.py）：minimum_canonical_recommendation()
  ——Minimal 保留 ≥95% 实战价值且复杂度仅 Full 一半 → SIMPLIFY；
  每版回答"当前最小可信 Canonical Core 是什么"；
  60. **Complexity Ceiling 拥有否决权**
  （governance/complexity_ceiling.py）：complexity_promotion_veto()——
  超过 Ceiling 且缺 Incremental Value Evidence → PROMOTION_REJECTED。
  测试总数由 349 模块 → **359 模块全绿**。

- **V82（2026-08-28）**：新一轮 41–50 优先修改项落地——
  P4：确定性、Replay 精度、Schema 稳定、历史事实完整性、故障攻击测试、
  复杂度硬封顶。
  41. **DecisionSchemaContract + Migration**
  （decision/schema_contract.py）：wave_stage/binding_constraint 升级为
  REQUIRED，legacy_action_signal 升级为 FORBIDDEN；SCHEMA_MIGRATIONS
  显式迁移（1.1→1.2→1.3）；schema_change_release_gate()——
  Schema 变化无迁移规则 → Release REJECTED（兼容不能靠猜）；
  42. **Golden Decision Corpus**（governance/golden_decision_corpus.py）：
  14 个永久 case 覆盖 5 权限 × 4 Wave 阶段 × HardExit/Liquidity/
  Portfolio/PIT/Replay/SafeMode；每 case 保存 ExpectedDecisionHash；
  golden_change_requires_review()——Critical Golden Case 变化必须进入
  Change Impact Review；
  43. **DeterminismContract Replay Identity**
  （governance/determinism.py）：determinism_identity() 冻结
  random_seed/determinism_version/numpy_version/sampling_method/
  block_size/n_permutations；replay_determinism_check()——相同
  Evidence/Release/Config/Feature/Universe 必须得到完全相同
  Decision/PathHash/FinalTarget/ReasonCodes；
  44. **Field Lineage 接真实 Snapshot**
  （decision/field_lineage.py）：field_lineage_from_snapshot()——从
  FinalTarget 反查 RawTarget→约束链→Permission→原始 PIT Evidence，
  每节点带 source_field/source_snapshot_id/rule_id/version，
  无需重跑系统；
  45. **DecisionPathHash 强化**（decision/path_hash.py）：
  纳入 8 个 binding caps + binding_constraint + engine_version +
  governance_rule_version + config_hash；path_hash_determinism_check()——
  输入相同配置不同 → PathHash 必不同；identity 相同却不同 →
  DETERMINISM FAILURE；
  46. **Historical Decision Integrity Contract**
  （decision/historical_integrity.py）：assert_historical_fact_immutable()——
  Ledger 只能 INSERT/APPEND，任何 UPDATE/DELETE = 历史被改写；
  新知识可以重新评价历史，不能重新书写历史；
  47. **ABSTAIN / NO_DECISION 一级语义**
  （decision/abstain.py）：abstain_semantics() 区分 HOLD ≠ NO_TRADE ≠
  ABSTAIN ≠ DECISION_HALTED；never_map_to_hold()——PIT UNKNOWN/
  证据不足/Replay 不可用/关键数据缺失不能映射成 HOLD；
  48. **Governance Failure Injection Suite**
  （governance/failure_injection.py）：11 类注入攻击
  （PIT 超前/Permission 缺失/Portfolio NaN/Liquidity 负值/Ledger 篡改/
  Replay mismatch/ConfigHash 变化/Future WaveLabel/Certificate 缺失/
  ReleaseManifest mismatch/裸 Proposal 执行）全部要求 fail-closed；
  五条最高原则分别有 adversarial test；
  49. **Production Dependency Allowlist**
  （governance/production_dependency_allowlist.py）：白名单制——
  未批准依赖默认禁止；research.*/ablation.*/legacy.*/report.*/
  wave.outcome 一律 FAIL；Research-only 与 Legacy authority 依赖数 = 0；
  50. **Complexity Ceiling v2**（governance/complexity_ceiling.py）：
  AUTHORITY_CEILING_TARGETS（Canonical/Permission/FinalTarget/
  Validation/Wave Authority=1、Report=0、Legacy Paths=0）；
  active_feature_gate()——新增 Feature 进 ACTIVE 需六项证据否则
  RESEARCH_ONLY；release_complexity_report()——复杂度上升缺增量证据
  → 不能 Promotion。
  测试总数由 339 模块 → **349 模块全绿**。

- **V81（2026-08-28）**：新一轮 31–40 优先修改项落地——
  P3：发布治理 + 运行期安全 + 研究/生产漂移 + 故障恢复 + 物理退役。
  31. **ReleaseManifest / ProductionBundle 唯一身份**
  （governance/release_manifest.py）：production_release_identity() 冻结
  release_id/strategy/engine/governance/schema/config/feature/code/
  data_contract 九身份；release_required_check()——Production Decision
  缺 release_id → NOT CERTIFIED；
  32. **Config Governance 决策关键参数门**
  （config/governance.py）：assert_decision_critical_config()——
  DECISION_CRITICAL 缺失 → INVALID_CONFIG → NO_DECISION/SAFE_MODE；
  decision_critical_hidden_default_count() 保证正式 Canonical Decision
  中 decision-critical hidden default count = 0；
  33. **Market Session Time Contract**（data/asof_contract.py）：
  MARKET_SESSIONS（before_open/continuous/lunch_break/after_close/
  auction/suspension/half_day）；trading_session_contract()——财报
  16:45 发布（after_close）→ 当天收盘价不可执行，至少 next tradable
  session；execution_time_resolution() 统一 Backtest/Replay/Execution；
  34. **Universe 历史可投资状态**（data/universe_snapshot.py）：
  INVESTABILITY_STATES（eligible/suspended/special_event/zero_volume/
  new_listing/delisting_window/corporate_action_locked/
  insufficient_history）；universe_investability_state() 唯一判定，
  universe_snapshot_id 可独立 Replay；
  35. **Tradability 唯一权威**（data/tradability.py）：
  TRADABILITY_STATES 七态统一（NORMAL/SUSPENDED/HALTED/NO_VOLUME/
  CORPORATE_ACTION_PENDING/DELISTING/NOT_ELIGIBLE）；
  tradability_authority() 唯一读取入口——Backtest/Execution/Portfolio/
  Report 只能读同一状态，只能降低执行权限；
  36. **Shadow–Production Divergence Reason**
  （governance/shadow_divergence.py）：shadow_divergence_reason()——
  每次 divergence 必有 reason_code（MODEL/CONFIG/DATA/VERSION_DELTA、
  GOVERNANCE_INTERCEPTION、EXECUTION_CONSTRAINT）+ decision_delta，
  而不是只记录"不同"；
  37. **Drift 接入 Review 生命周期**
  （monitoring/research_production_drift.py）：drift_lifecycle_transition()
  ——HIGH_DRIFT → NORMAL→REVIEW_REQUIRED（触发 revalidation），
  MODERATE → WATCH；禁止自动改参数；
  38. **Change Blast Radius**（governance/change_impact.py）：
  change_blast_radius()/decision_impact_report()——关键 Release 必须带
  影响层/历史决策比例/决策翻转（ADD→HOLD 等）/Report/Replay/Certificate
  的 Decision Impact Report；
  39. **Incident Policy Table**（safety/incident_protocol.py）：
  每种 Incident 定义 new decision/new order/risk reduction/forced
  liquidation/replay/human approval 六项策略；SYSTEM_FAILURE 停新指令
  ≠清仓，MARKET_RISK 才 force liquidation；
  40. **Dead Authority Dependency Check**
  （governance/dead_authority.py）：RETIRED 模块必须在 Production
  dependency graph 真正消失（token 级匹配），只保留 historical replay
  artifact / migration support。
  测试总数由 329 模块 → **339 模块全绿**。

- **V80（2026-08-28）**：新一轮 21–30 优先修改项落地——
  P2：PIT 时间完整性 + 实盘可执行性 + 决策变化解释 + 牛散实战评估
  + 进一步压缩复杂度。
  21. **AsOfTimeContract 时间完整性**（data/asof_contract.py）：
  TIME_ROLES 扩展为 8 角色（observation/period_end/source_publish/
  system_available/available/decision/execution/outcome）；
  evidence_time_completeness() 要求 Production Evidence 至少带
  as_of_time/available_time/decision_time 且 available<=decision
  （PIT 不只是日期没穿越，而是市场当时真的已经知道）；
  22. **UniverseSnapshot 可交易字段**（data/universe_snapshot.py）：
  冻结当时 universe 增加 tradable/board/currency/lot_size/
  universe_reason/as_of_date；Survivorship 控制保持——
  过去退市的股票不能因今天不存在而自动消失；
  23. **Tradability Execution Hard Gate**（data/tradability.py）：
  状态扩展 DELISTING/NOT_TRADABLE；tradability_hard_gate() 位于
  Governance→Execution 之间，只能降低/阻止 Execution，
  绝不能提高机会评分（理论上应该买 ≠ 实际可以买）；
  24. **DecisionDelta v2**（decision/decision_delta.py）：
  增加 Wave Stage/Participation/Liquidity Cap/Risk Cap 变化解释；
  delta_completeness() 保证 target 变化必有
  WHAT_CHANGED/WHY_CHANGED/BINDING_CONSTRAINT；
  25. **Binding Constraint Attribution**
  （monitoring/binding_constraint_frequency.py）：
  binding_constraint_attribution() 长期统计每个 ACTIVE 模块的
  triggered frequency / binding frequency / independent impact
  （存在一个约束 ≠ 这个约束有实际价值）；
  26. **Execution Reality Calibration 降级**
  （monitoring/execution_calibration.py）：
  execution_calibration_downgrade()——执行假设长期偏乐观 →
  CERTIFICATION_DOWNGRADED（只走 Detect→Review→Candidate→Shadow，
  禁止自动重校准 Production）；
  27. **Decision Coverage v2**（monitoring/decision_coverage.py）：
  状态增加 NO_TRADE（Certified/No trade/Safe/Abstain/Halted），
  弃权原因增加 NO_WAVE/PERMISSION_BLOCK/LIQUIDITY_FAIL/DATA_MISSING；
  正式验证报告同时展示 Performance + Decision Coverage；
  28. **Benchmark Ladder B0–B6**
  （research/benchmark_ladder.py）：固定永久基线
  Cash/Buy&Hold/SimpleTrend/WaveOnly/Permission+Wave/
  Permission+Wave+FSM/Risk/FullCanonical；core_vs_full() 判定
  Full 复杂度翻倍但无稳定增量 → CORE_PREFERRED
  （系统最危险的对手是简单模型）；
  29. **Retail Practicality Promotion**
  （evaluation/retail_scorecard.py）：Scorecard 增加
  capital_utilization / false_participation；promotion_requirement()
  要求 Production Promotion 同时通过 Statistical Validity +
  Retail Practicality（A/B），统计能赚钱 ≠ 牛散能执行；
  30. **Minimum Governed Core 决策**
  （governance/minimal_governed_core.py）：
  minimum_governed_core_decision()——Full 复杂度 ≥2× 但实战价值
  增量 <5% → 默认 SIMPLIFY；每版回答"最少保留哪些模块能保持
  95%–100% 实战价值和 100% 治理完整性"。
  测试总数由 319 模块 → **329 模块全绿**。

- **V79（2026-08-28）**：新一轮 11–20 优先修改项落地——
  统一认证 → 修正报告证明 → 统一版本身份 → 治理模块变发布/运行机制
  → 开始删除冗余。
  11. **ValidationCertificate 唯一权威**（governance/validation_certificate.py
  + scripts/all_in_one_report.py）：新增 research_validated_from_summary()
  作为全项目唯一"RESEARCH VALIDATED"来源；Report/Script 删除自行判断
  （median OOS>0 && Sharpe>0）逻辑；缺失 gate → UNKNOWN（fail-closed），
  只有 certificate_display() 能输出 RESEARCH VALIDATED；
  12. **Governance Decision Card 真实证明**（decision/governance_card.py
  + scripts/all_in_one_report.py）：删除恒真伪证明（perm==snap.
  institutional_permission、input_fingerprint 当 PIT）；Card 每个 ✓
  反查真实字段：governance_proof.proof / pit_grade / binding_constraint /
  raw→final 单调不增 / run_id；
  13. **VersionIdentity 唯一版本来源**（scripts/*）：清除运行代码硬编码
  "QCFP-MTF-2.5.0"（backtest_runner/all_in_one/dss_report/各引擎/
  dss_output 全部改读 versions.MODEL_VERSION / DECISION_RULE_VERSION），
  仅 versions.py/配置/__init__ 保留定义；
  14. **ProductionEvidencePack 绑定决策**（decision/certified_decision.py）：
  CertifiedDecision 增加 release_id / evidence_pack_id / evidence_pack_hash；
  assert_evidence_pack_bound() 保证 decision→release→evidence pack 反查，
  缺 Evidence Pack → NOT CERTIFIED；
  15. **Change Impact Matrix → Release Gate**
  （governance/change_impact.py）：新增 change_impact_release_gate()——
  关键变更（Permission/FinalTarget/PIT/DecisionSchema）必须有
  ChangeImpactRecord + 全套 PIT/OOS/Ablation/Replay/Shadow 证据，
  否则 Release Promotion 直接 FAIL；
  16. **Critical Path 接真实 Snapshot**
  （monitoring/critical_path_observability.py）：新增
  critical_path_from_snapshot()——由真实 DecisionSnapshot 自动发出
  8 段 stage event（evidence/pit/permission/wave/governance/snapshot/
  ledger/execution），PIT C/D → FAIL，Execution 未生成 = PENDING；
  某天无交易时可准确定位停在哪个 stage；
  17. **FEATURE_SET → Production Feature Manifest**
  （governance/production_feature_manifest.py）：状态
  DEFINED→WIRED→VALIDATED→CERTIFIED→ACTIVE→RETIRED，只有 ACTIVE 进入
  ProductionManifestHash；participating_features() 从真实
  decision_path 反推本次实际参与的 feature；
  18. **Physical Retirement Gate**（governance/module_trim.py）：
  physical_retirement_gate()——RETIRED 必须删除 Production import/
  运行入口/报告展示，且 executable path 数量必须下降
  （RETIRED_CLEAN / RETIRE_INCOMPLETE）；
  19. **Opportunity Funnel 接真实决策数据**
  （evaluation/opportunity_funnel.py）：opportunity_funnel_from_snapshots()
  累积口径（通过前面所有 stage 才进入下一 stage），stage counts 全部
  来自真实 DecisionSnapshot/ConstraintTrace，回答"机会在哪里被过滤"；
  20. **Architecture Conformance Gate**
  （governance/architecture_conformance.py）：FORBIDDEN_IMPORT_EDGES
  （report→position_sizing、production→WaveOutcomeLabel、
  research→legacy_target、execution→uncertified_decision），
  architecture_conformance_gate() 违反直接 CI FAIL。
  测试总数由 309 模块 → **319 模块全绿**。

- **V78（2026-08-27）**：新一轮 1–10 优先修改项落地——
  先消灭旁路 → 接通硬约束 → 修事实链 → Wave 成为机会核心 →
  统一研究验证。
  1. **Evidence Builder 去决策权**（backtest/data_pipeline.py）：
  build_signal_timeline() 降级为 Legacy Shadow Comparator，输出带
  legacy_action/legacy_target + authority=SHADOW_ONLY +
  non_certifiable=True；新增 build_evidence_timeline()（纯证据，
  无 target/action）+ assert_evidence_no_decision_authority()；
  正式路径只有 canonical_replay → evaluate 能产生 FinalTarget；
  2. **GovernanceCaps 全接入**（decision/governance_caps.py +
  decision/engine.py）：Portfolio/Liquidity/Execution/Sector/Theme/
  Drawdown/DataQuality 收敛成不可变容器，engine.evaluate 读取 row 中的
  hard caps 传入 finalize_target；每笔 DecisionSnapshot 携带
  ConstraintTrace + BindingConstraint + GovernanceCaps，
  FinalTarget <= 所有 hard caps；
  3. **PermissionPolicy 唯一化**（decision/permission_policy.py）：
  BLOCK 语义收敛为"禁新增/禁加仓/必须去风险"，derisk_mode 由 Risk/Exit
  决定（默认 PROGRESSIVE，Hard Exit → IMMEDIATE_EXIT）；新增
  PermissionPolicy frozen dataclass + permission_derisk_mode()；
  4. **Ledger 事实链**（decision/decision_ledger.py）：
  DataSnapshotID = content-sensitive（schema+rows+as-of range+content+
  universe+corporate action+disclosure override）；invalidate_snapshot
  改为追加 DECISION_INVALIDATED 事件（不再 UPDATE，原行不可变）；
  双链：global_prev/current + run_prev/run_current，global 与单 run
  均可独立验证；
  5. **Wave → Canonical Engine 接入**（decision/engine.py +
  wave/canonical.py）：Permission → AsOfWaveOpportunity → Wave Stage
  Gate → TradeProposal → FSM → RawTarget；DecisionSnapshot 保存
  wave_id/wave_stage/wave_strength/wave_action_allowed/
  wave_entry_scale/wave_invalidation/wave_proposal_target
  （future-aware 字段永不进入）；
  6. **CertifiedDecision 唯一出口**（decision/certified_decision.py +
  execution/execution_gate.py）：PIT/Ledger/Replay/Governance/Safety/
  Acceptance 任一失败 → REFUSED；execute() 只接受 CertifiedDecision，
  裸 DecisionSnapshot 被拒（不知道就降级，降级具有执行权）；
  7. **Report Snapshot/Ledger/Certificate-only**
  （scripts/dss_report.py）：删除 effective_position/
  effective_position_cqs 重算与 REDUCE→TEST_BUY 改写；
  CanonicalAction 原样展示，试多语义由 trade_interpretation 单独解释；
  仓位建议只读 final_target（Legacy 仅标注对照）；
  8. **OOS/Ablation/Stress 全部 Canonical-only**
  （backtest/canonical_runs.py + scripts/research_validation.py）：
  正式 API run_canonical_backtest/oos/ablation/stress 全部
  evidence→canonical_replay→run_backtest，产物带 engine=canonical/
  decision_provenance/feature_manifest_hash/strategy_version/
  data_snapshot_id；Legacy 永远 run_legacy_shadow_comparator
  （SHADOW_ONLY/NON_CERTIFIABLE）；
  9. **Paired Ablation 修复 + 统一指标**（ablation/statistical.py +
  ablation/portfolio_counterfactual.py）：置换改为 Block Sign-Flip
  （旧 treat[perm]-base[perm]=delta[perm] 均值不变，null 无效）；
  块切分支持非整数倍；portfolio_counterfactual 指标统一为复利
  total_return + CAGR（与 backtest.performance.evaluate 同口径）；
  10. **Convergence & Simplification Release**
  （governance/convergence_release.py）：Feature 生命周期
  DEFINED→WIRED→VALIDATED→CERTIFIED→ACTIVE→RETIRED（仅 ACTIVE 进
  Manifest）；发布报告只报 KPI 升降（决策路径↓/重复权限↓/Legacy import↓/
  ACTIVE 数↓/决策 LOC↓；Canonical/Replay/Invariant 覆盖↑、
  OOS 质量↑）；10 类旧路径逐项审计（CLOSED/ACTION_REQUIRED）。
  测试总数由 299 模块 → **309 模块全绿**。

- **V77（2026-08-27）**：终局治理/证据压缩/长期退役/系统退出机制
  （新 91–100）落地——
  91. **Production Evidence Pack**（governance/production_evidence_pack.py）：
  每个 Release 只对应一份证据包（ReleaseManifest / ValidationCertificate /
  PIT / OOS / Ablation / Stress / Replay / Shadow / Governance Approval +
  Evidence Hash）；任何 Decision 可反查
  decision → release → evidence pack，缺任一 → NOT CERTIFIED；
  92. **Certification Scope**（governance/certification_scope.py）：
  每张 Certificate 明确 component/strategy_version/config_hash/
  dataset_snapshot/universe/time_range/market/frequency/
  feature_manifest；认证不允许跨市场/数据/配置/Feature/频率自动继承；
  93. **Evidence Hierarchy**（research/evidence_hierarchy.py）：
  L0 Theory → L1 In-sample → L2 Backtest → L3 OOS → L4 Ablation+Stress
  → L5 Shadow → L6 Production；PRODUCTION 要求 ≥L4；
  低等级证据只能产生 Hypothesis，不能直接产生 Production Change；
  94. **Evidence Contradiction Handling**
  （research/evidence_contradiction.py）：按维度输出
  SUPPORTING/CONTRADICTING/INCONCLUSIVE 并显式保存 trade-off；
  重大冲突禁止自动平均（Risk > Return：
  risk positive + return negative → KEEP because
  risk mandate dominates return loss）；
  95. **Sunset Policy**（governance/sunset_policy.py）：
  ACTIVE → REVIEW_DUE → SUNSET_CANDIDATE → SHADOW_ONLY → RETIRED
  （只进不退）；触发：evidence_expired / no_incremental_value /
  never_binding / dominated / repeated_oos_failure /
  excessive_complexity；默认不是永久 ACTIVE，
  必须持续证明自己值得 ACTIVE；
  96. **Strategy Kill Criteria**（safety/strategy_kill.py）：
  策略级终止（PIT/Ledger integrity failure、Repeated replay mismatch、
  Severe governance breach、Persistent OOS deterioration、
  Execution assumptions invalid、Certification expired）→
  PRODUCTION→SUSPENDED；明确区分 Trade Exit / Strategy Suspend /
  System Halt 三者；
  97. **Reactivation Gate**（safety/reactivation_gate.py）：
  SUSPENDED → Root Cause → Fix → Replay → Invariant → PIT →
  Regression → Shadow → Governance Approval → REACTIVATED
  （HIGH 全 8 步，LOW 子集）；恢复必须产生新的
  ReactivationCertificate，不能直接改状态字段；
  98. **Governance Minimalism Test**
  （governance/governance_minimalism.py）：治理自身也进 Complexity
  Budget——≥4 registry → 合并一表、≥3 certificate → 共享 schema、
  ≥5 checks → 同一 gate；不能为了治理复杂度再制造另一套复杂度；
  99. **One-Page Canonical Specification**
  （governance/one_page_canonical.py）：生产核心一页规格
  INPUT(PIT)→PERMISSION→OPPORTUNITY(Wave)→LIFECYCLE(FSM)→
  GOVERNANCE(Risk/Portfolio/Liquidity/Execution)→OUTPUT(Canonical
  Decision)→FACT(Ledger)→VALIDATION；明确谁能提高风险、谁只能
  降低风险、谁产生 Proposal/Decision、谁保存事实；
  100. **QCFP-MTF Final Design Principle**
  （governance/final_design_principles.py）：冻结十条最高过滤器；
  新 Feature Proposal 必须填写 Problem/Existing insufficiency/
  Expected value/Complexity cost/OOS test/Ablation plan/
  Retirement condition，缺任一 → RESEARCH ONLY。
  测试总数由 289 模块 → **299 模块全绿**。

- **V76（2026-08-27）**：防回归/长期证据维护/治理老化检查/最终删减
  （新 81–90）落地——
  81. **Governance Aging Review**（governance/governance_aging.py）：
  每个 ACTIVE 核心规则保存 certified_at / last_revalidated_at /
  evidence_window / current_status / next_review_due；距上次再验证
  ≥12 个月 → REVALIDATE，≥24 个月 → RETIRE（不能因曾经认证就永久
  ACTIVE）；
  82. **Evidence Expiry Policy**（governance/evidence_expiry.py）：
  ValidationCertificate 记录 evidence_start/end、regimes、sample_size、
  certificate_expiry；FRESH/AGING/EXPIRED 三档，
  Evidence expired → Certification downgraded → Revalidation →
  Research → Shadow → Approval（不自动改参数）；
  83. **Rule Removal Test**（governance/rule_removal_test.py）：
  Current Canonical vs Canonical−Rule X，比较 CAGR/Sharpe/MDD/
  Tail/Wave capture/Turnover/Decision burden/Practicality/Binding
  coverage；Performance≈、Risk≈、Practicality↑、Complexity↓
  → REMOVE；删除功能也必须像增加功能一样正式验证；
  84. **Dominated Rule Detection**
  （research/dominated_rule_detection.py）：统计 triggered/binding/
  independently_changed/prevented_violation → ESSENTIAL / USEFUL /
  REDUNDANT / DOMINATED；trigger>0 且 binding=0 且独立影响=0
  → RETIRE REVIEW；
  85. **Decision Compression Test**
  （evaluation/decision_compression.py）：Full vs Compressed action
  taxonomy，比较 OOS/Turnover/Decision flip/用户理解/Risk；
  动作数减少且不恶化 → MERGE_RECOMMENDED；
  86. **State Transition Audit**
  （monitoring/state_transition_audit.py）：记录 from/to/reason/
  duration/decision_impact；找出不可能转换、从未使用转换、
  高频来回（双向往返 ≥3）、无决策意义转换 → 简化 FSM
  （而不是新增状态）；
  87. **Cross-Layer Contradiction Audit**
  （governance/cross_layer_contradiction.py）：不同层可意见不同但
  必须不越权、能解释、只有一个 Canonical Decision；
  BLOCK+Wave ACTIVE+FSM ADD+Target 0 → EXPLAINED
  （Opportunity detected but participation denied）；
  BLOCK+Target>0 → AUTHORITY_VIOLATION；
  88. **Research-to-Production Leakage Test**
  （governance/research_production_leakage.py）：WaveOutcomeLabel/
  future MFE/MAE/research rank/ablation result/shadow alpha/
  diagnostic score 全部标记 RESEARCH_ONLY；Production dependency
  graph 中 research-only node count=0，否则 CI FAIL；
  89. **Historical Decision Integrity Test**
  （decision/historical_integrity.py）：区分 Historical Fact /
  Old-release Replay / New-release Counterfactual；旧版本重放必须与
  冻结事实一致（INTEGRITY_OK），新模型只能生成 counterfactual，
  不能修改历史事实；
  90. **Minimal Governed Core**
  （governance/minimal_governed_core.py）：最终架构目标 10 组件
  （PIT Evidence / Institutional Permission / Wave Opportunity /
  FSM Proposal / Risk+Portfolio+Liquidity Governance / Canonical
  Final Target / Execution Plan / DecisionSnapshot / Append-only
  Ledger / Research Validation）；其他功能必须是核心的必要子能力，
  否则只能 RESEARCH_ONLY/SHADOW_ONLY/APPENDIX/ARCHIVE/RETIRE；
  ALIGNED / ACTION_REQUIRED。
  测试总数由 279 模块 → **289 模块全绿**。

- **V75（2026-08-27）**：证据闭环/长期可维护性/规则退役/系统防回复杂
  （新 71–80）落地——
  71. **Decision Necessity Audit**（governance/decision_necessity.py）：
  每个 ACTIVE 模块必须有唯一且清晰的 Purpose / Independent Value /
  Failure if Removed / Current Evidence；无法说明 → REVIEW；
  被 covered_by 覆盖且无独立价值 → REVIEW；
  72. **Rule Ownership Registry**（governance/rule_ownership.py）：
  关键规则登记唯一 owner（Permission upper bound→PermissionPolicy、
  Final target→Governance、Wave lifecycle→WaveStagePolicy、
  Execution feasibility→ExecutionLiquidity）；同一 rule_id 只能由
  一个 production module 决定，其余只能读取引用，
  重复实现 → DUPLICATE_AUTHORITY；
  73. **Duplicate Logic Detector**（governance/duplicate_logic_detector.py）：
  按 pattern 聚合生产代码中的同义条件（多处 permission==BLOCK、
  多处 position cap、多处 action 映射）；同一决策关键逻辑出现在
  ≥2 个 production module → CI WARN（逻辑复用，而非语义复制）；
  74. **Model Decision Surface Audit**
  （evaluation/decision_surface_audit.py）：小幅输入（≤5%）导致
  target 大幅跳变（>30%）→ jump event → REVIEW；
  只做研究诊断、不自动平滑；surface stability index 定量记录；
  75. **Risk Reduction Attribution**
  （evaluation/risk_reduction_attribution.py）：按层拆解
  Drawdown/Tail/Concentration/Liquidity/Gap/Turnover 六维风险削减；
  无独立风险贡献且无其他证据 → SIMPLIFICATION_REVIEW；
  76. **Decision Error Taxonomy**（failure/decision_error_taxonomy.py）：
  统一 9 类错误（DATA/PIT/PERMISSION/WAVE_TIMING/SIZING/EXIT/
  EXECUTION/GOVERNANCE/HUMAN_OVERRIDE），关键词归类 +
  UNCLASSIFIED 告警（无法归类 = 架构责任边界不清楚）；
  77. **Recovery Replay Test**（safety/recovery_replay_test.py）：
  从最后可信 checkpoint 重放，恢复后的 Canonical Decision 必须与
  可信历史逐条一致（RECOVERY_OK）才能回 NORMAL；
  恢复 ≠ 服务能启动；
  78. **Research Debt Register**（governance/research_debt_register.py）：
  未完成研究项只能处于 HYPOTHESIS/EXPERIMENTAL/VALIDATED/REJECTED/
  RETIRED；EXPERIMENTAL 超过两个版本周期无实验结果 →
  DELETE_ARCHIVE_REVIEW；
  79. **Production Simplicity KPI**
  （governance/production_simplicity_kpi.py）：6 项简洁度 KPI
  （Active modules / Duplicate authorities / Critical parameters /
  Canonical path length / Report decision logic / Legacy imports），
  每版汇报升降（IMPROVING/STABLE/REGRESSING/BASELINE），
  版本越高不代表越复杂；
  80. **System Constitution Test**
  （governance/system_constitution.py + tests/test_governance/
  test_system_constitution.py）：8 条宪法不可回归——
  Permission>Signal / PIT>Prediction / Risk>Return / Production 不可
  自改 / Future 数据不可进入过去决策 / Final Target 只能下游压减 /
  Unknown 必须降级 / 每个生产决策必须可 Replay；
  违反任一条 → PROMOTION_REJECTED（收益提升也不能 Promotion）；
  测试已直接接线真实引擎/特征门禁/仓位链行为。
  测试总数由 269 模块 → **279 模块全绿**。

- **V74（2026-08-27）**：长期治理/边界管理/防止系统重新复杂化
  （新 61–70）落地——
  61. **Human Override Contract**（governance/human_override.py）：
  人工干预正式化（OVERRIDE_SKIP/REDUCE/EXIT/HALT），记录原 Canonical
  Decision、动作、reason code、时间、操作者、执行结果；人工默认只能
  降风险，不能突破 Canonical 风险上限；任何
  executed_position != canonical_target 都必须能被事件解释
  （允许人工负责，不允许人工无痕）；
  62. **Override Outcome Review**（evaluation/override_outcome_review.py）：
  长期统计 Canonical vs Actual，分类避免损失/错过收益/提前退出/
  错误干预；HELPFUL/HARMFUL/NEUTRAL/INCONCLUSIVE 由证据判定，
  Research-only，禁止自动学习修改 Production；
  63. **Decision Threshold Sensitivity Map**
  （research/threshold_sensitivity_map.py）：对 permission/wave
  confirmation/position cap/liquidity cap/stop distance 只扰动 ±5%、±10%，
  相邻探测点 metric 突变 >0.20 → CLIFF → OVERFIT_RISK
  （0.69 好、0.70 崩 → 过拟合风险而非精确锁死）；
  64. **Rule Interaction Audit**（research/rule_interaction_audit.py）：
  Rule A only / B only / A+B / neither 的 OOS 对比 → COMPLEMENTARY /
  REDUNDANT / CONFLICTING / DOMINATED；拦截行为重叠 >90% 且无独立
  增量 → 删除其中一条（直接服务 Complexity Budget）；
  65. **Binding Constraint Frequency**
  （monitoring/binding_constraint_frequency.py）：统计各约束实际绑定
  频率（Permission/Liquidity/Portfolio/Drawdown/Execution）；
  长期 0 binding + 0 Ablation 增量 → RETIRE_CANDIDATE；
  66. **Risk Budget Utilization Audit**
  （monitoring/risk_budget_utilization.py）：available/requested/
  approved/executed/unused 五值 + 利用率 band；<30% → 排查
  Permission/Wave/Portfolio/市场，≥90% → 集中风险告警
  （不是只报"持仓 35%"，而是知道是选择还是约束结果）；
  67. **Opportunity Funnel**（evaluation/opportunity_funnel.py）：
  Universe→PIT→Permission→Wave→FSM→Risk→Liquidity→Final Trade 漏斗，
  计算每级 drop ratio + bottleneck，回答机会在哪里被过滤；
  68. **Decision Latency Budget**
  （monitoring/decision_latency_budget.py）：Data→Evidence→Canonical→
  Ledger→Executable 五段延迟；当前相对上一版增长 >20% →
  ROLLBACK_ADVICE（复杂度无增量价值却增延迟 → 优先回退）；
  69. **Report Information Budget**（report/information_budget.py）：
  正式牛散报告只回答 6 问（能不能参与/机会阶段/建议仓位/为什么变化/
  最大风险/退出失效条件）；研究统计、Ablation、Shadow、Legacy
  comparator 进 Appendix；新增字段必须证明改变理解或行动，否则不进
  主报告（报告复杂度也需要预算）；
  70. **Governance Completeness Review**
  （governance/completeness_review.py）：对 1–70 关门检查——非
  Canonical 路径/重复 Permission authority/future-aware import/
  Report-side decision/mutable Ledger/hidden defaults/uncertified
  feature/legacy default/不可 Replay/不可解释 override 十项，
  每项输出 CLOSED / ACCEPTED RISK / ACTION REQUIRED / RETIRE；
  全部 CLOSED 才进入长期稳定迭代模式。
  测试总数由 259 模块 → **269 模块全绿**。

- **V73（2026-08-27）**：生产证据/基准对照/研究可重复/决策成本/
  可观测性/最终瘦身（新 51–60）落地——
  51. **Production Acceptance Contract**
  （governance/production_acceptance.py）：8 道门槛
  PIT/REPLAY/LEDGER/OOS/STRESS/SHADOW/GOVERNANCE/NO_CRITICAL_UNKNOWN
  全部 PASS 才 ACCEPTED；结论只允许 ACCEPTED/REJECTED，
  每条结论引用证据，治理失败不能被 Sharpe 覆盖；
  52. **Benchmark Ladder**（research/benchmark_ladder.py）：固定阶梯
  Simple Baseline（Cash/BuyAndHold/SimpleTrend）→ Core Model（Wave-only）
  → Governed Model（Permission+Wave）→ Full Production（Full Canonical）；
  每级必须证明相对更简单层级的增量，缺档即不得宣称已证明；
  53. **Decision Cost Budget**（evaluation/decision_cost_budget.py）：
  decisions/week / position changes/month / simultaneous positions /
  binding reasons / manual attention / emergency actions；
  OOS 相近时优先负担更低的版本（单位决策复杂度的实战价值）；
  54. **Counterfactual Decision Audit**
  （evaluation/counterfactual_audit.py）：把 Ablation 落到单笔决策，
  Without Liquidity Cap / Without Permission / Without Wave Gate → X/Y/Z，
  结合实际结果判定 SAVED_BY_CONSTRAINT / MISSED_OPPORTUNITY /
  NEUTRAL；永远 Research Evidence，不能回写历史 Snapshot；
  55. **Research Artifact Bundle**（research/research_artifact_bundle.py）：
  冻结 experiment_id/hypothesis/code commit/config/dataset snapshot/
  universe snapshot/seed/metric contract/results/plots/validation status，
  唯一 ResearchArtifactID（内容 hash），无法重现 → UNVERIFIED；
  56. **Negative Result Registry**
  （research/negative_result_registry.py）：登记被 DROP 模块的
  Hypothesis/Experiment/OOS/Ablation/Failure reason/Retired version；
  归一化假设 key 精确+模糊匹配，防止重新引入已验证失败的想法
  （REJECT_REINTRODUCTION）；
  57. **Critical Path Observability**
  （monitoring/critical_path_observability.py）：只监控 8 步 Canonical
  决策链（Evidence→PIT→Permission→Wave→Governance→Snapshot→Ledger→
  Execution），每步 latency/status/version/io_hash；
  无 Decision 时立即定位卡在哪一步（first_blocker）；
  58. **Decision Coverage / Abstention Coverage**
  （monitoring/decision_coverage.py）：Certified/Safe-mode/Abstain/Halted
  占比 + 弃权原因拆分（PIT unknown/evidence missing/permission/
  liquidity/replay）；Production 报告必须同时报告 Performance 与 Coverage，
  certified<70% 触发成熟度告警；
  59. **Minimum Viable Canonical**
  （research/minimum_viable_canonical.py）：极简核心
  PIT→Permission→Wave→FSM→Risk/Position Cap→Final Target→Ledger 与完整
  系统比较，价值保留率 ≥95% → MINIMAL_SUFFICIENT（优先保留更小版本）；
  60. **Complexity Ceiling**（governance/complexity_ceiling.py）：
  Production 硬上限（ACTIVE modules/stages/parameters/scoring systems/
  duplicate authorities=0）；新模块默认"一进一出"；
  净增 ≥3 个 ACTIVE 模块必须有 OOS/Ablation/Stress 强证据，否则拒绝。
  测试总数由 249 模块 → **259 模块全绿**。

- **V72（2026-08-27）**：收尾/证明/减法（新 41–50）落地——
  ㊶ **DecisionSchemaContract**（decision/schema_contract.py）：字段状态
  REQUIRED/OPTIONAL/DEPRECATED/FORBIDDEN；旧 Snapshot 判定
  REPLAY / MIGRATE / NOT_REPLAYABLE（禁止静默兼容，FORBIDDEN 字段
  （future_return/wave_label/realized_mfe/capture_ratio）→ 不可回放）；
  ㊷ **Golden Decision Constitution**（tests/test_golden/
  test_golden_constitution.py）：3 条宪法级用例——BLOCK+强信号→0；
  ALLOW+Liquidity 20% 绑定；PIT invalid→无正式决策（不是"测试收益"，
  而是"测试宪法有没有被改坏"）；
  ㊸ **DeterminismContract**（governance/determinism.py）：Production
  必须 seed=None；audit_random_usage 供 Research 审查随机用法；
  相同 Evidence+Code+Config+Version+Seed → 相同结果；
  ㊹ **Field Lineage**（decision/field_lineage.py）：FinalTarget 的每个
  binding constraint 反查 EvidenceSnapshot 字段（permission_cap ←
  institutional evidence；liquidity_cap ← ADV ← raw_target）；
  ㊺ **Execution Reality Calibration**（monitoring/execution_calibration.py）：
  Estimated vs Realized Slippage/Exit Days → OPTIMISTIC/PESSIMISTIC/
  NEUTRAL；长期偏移只进 Research Review，
  auto_param_modify_forbidden=True；
  ㊻ **Decision Impact Changelog**（governance/decision_changelog.py）：
  每次 Release 回答"历史决策受影响的百分比 + 主要变化
  （HOLD→EXIT / ADD→HOLD / No change）"；
  ㊼ **ABSTAIN / NO_DECISION**（decision/abstain.py）：PIT/Replay/Ledger/
  证据/证书任一缺失 → NO_DECISION（HOLD 也是决策，不能冒充）——
  并同步补强引擎 PIT 硬门：`*_available_date` 字段晚于决策时间
  同样拦截（堵住 structural_available_date 超前漏洞）；
  ㊽ **Failure Injection**（tests/test_governance/test_failure_injection.py）：
  5 个注入攻击——PIT 超前 / WaveOutcomeLabel 进生产 / Replay mismatch /
  隐性版本冲突 / Report 重算（攻击自己的系统）；
  ㊾ **Architecture Conformance**（governance/architecture_conformance.py）：
  6 条可执行架构规则（Production 禁 import future、Report 禁 import
  sizing、Legacy 非默认、Execution 禁消费 Proposal、仅 Governance 建
  Decision、仅 ACTIVE 进 Manifest）→ CI PASS/FAIL；
  ㊿ **Simplification Release Gate**（governance/simplification_release.py）：
  简化发布必须三证齐备——复杂度真实下降（执行路径/生产模块/决策 LOC/
  重复规则）+ 覆盖不降（Canonical/Replay/不变量）+ OOS/Ablation/Replay
  无显著损失；APPROVED/REVIEW/REJECTED，只允许减法、不夹带新 Alpha。
  测试总数由 239 模块 → **249 模块全绿**。

- **V71（2026-08-27）**：P3 工程确定性/生产一致性/Shadow 监督/变更控制/
  真正退役（新 31–40）落地——
  ㉛ **ReleaseManifest / ProductionBundle**（governance/release_manifest.py）：
  strategy/engine/governance/config/feature/code/data_contract/schema
  八身份冻结 → manifest_hash，任何 Production Decision 唯一反查；
  相同 hash 不同 release_id → 隐性版本冲突拒绝；
  ㉜ **Config Governance**（config/governance.py）：参数分类
  DECISION_CRITICAL/RESEARCH_ONLY/DISPLAY_ONLY；关键参数缺失 →
  INVALID_CONFIG（默认值也属于决策规则，必须被审计）；
  ㉝ **AsOfTimeContract**（data/asof_contract.py）：统一 observation/
  available/decision/execution/outcome 五类时间；
  available≤decision≤execution≤outcome 因果序校验；
  ㉞ **UniverseSnapshotContract**（data/universe_snapshot.py）：冻结当时
  真实可交易 universe（含今日已退市但当时存在的股票），
  universe_snapshot_id 成为 DataSnapshot 组成部分（Survivorship 控制）；
  ㉟ **Tradability Governance**（data/tradability.py）：SUSPENDED/HALTED/
  NO_LIQUIDITY/CORPORATE_ACTION_PENDING/NORMAL 五态 →
  Execution/Liquidity Cap（不判断好坏，只判断能否执行）；
  ㊱ **Shadow–Production Divergence Monitor**
  （governance/shadow_divergence.py）：差异分类
  MODEL/CONFIG/DATA/GOVERNANCE_INTERCEPTION/VERSION_DELTA，
  无法解释的差异 → 治理告警；
  ㊲ **Research→Production Drift**（monitoring/research_production_drift.py）：
  Wave stage/持仓/换手/权限/成本/捕获率分布 PSI 漂移 →
  Detect→Evidence→Review→Candidate→Shadow→Human Approval→Production
  （漂移≠自动重训）；
  ㊳ **Change Impact Matrix**（governance/change_impact.py）：变更自动
  标识影响 Evidence/Permission/Wave/FSM/Risk/Portfolio/Execution/Ledger/
  Report/Research-only；Permission/FinalTarget/PIT/Schema 变更 →
  FULL_VALIDATION；
  ㊴ **Production Incident Protocol**（safety/incident_protocol.py）：
  NORMAL→DEGRADED→SAFE_MODE→DECISION_HALTED→RECOVERY_VALIDATION→NORMAL；
  区分 SYSTEM_FAILURE（停新指令≠清仓）与 MARKET_RISK_HARD_EXIT（退出），
  恢复必须 Replay 验证；
  ㊵ **Dead Authority Removal**（governance/dead_authority.py）：退役审计
  确认删除 Production import/默认配置/入口/Report 展示（只保留 frozen
  artifact）+ 可执行路径减少验证（退役必须减少路径数量）。

- **V70（2026-08-27）**：实战校准/边界验证/研究治理/运维可控（新 21–30）
  落地——
  ㉑ **DecisionReplayContract**（decision/replay_contract.py）：
  DecisionReplayInput（EvidenceSnapshot/Strategy/Engine/Governance/
  Config/Feature/Universe/RandomSeed）+ Original/Replay Hash + ExactMatch
  + 四类回放（Data/Decision/Execution/Research），Production 认证要求
  hash 完全一致；
  ㉒ **EvidenceQualityContract**（data/quality.py）：PIT_VALID/COVERAGE/
  STALENESS/MISSINGNESS/SOURCE_CONSISTENCY/CORPORATE_ACTION/QUALITY_GRADE
  → A(正常)/B(降仓位)/C(禁新增)/D(不生成正式决策)/UNKNOWN(Fail Closed)，
  数据问题直接降低 Governance Cap；
  ㉓ **Proposal/Decision 类型隔离**（decision/types.py）：
  TradeIdea→TradeProposal→GovernedProposal→CanonicalDecision→
  ExecutionInstruction；TradeProposal 无法被 Execution 直接消费
  （上游只能建议，Governance 才能决定）；
  ㉔ **DecisionDelta**（decision/decision_delta.py）：Previous vs Current
  target → WHAT/WHY/WHO/风险是否增加/Binding Constraint，
  每次 target 变化产生 machine-readable delta；
  ㉕ **决策稳定性诊断**（evaluation/decision_stability_diag.py）：
  DecisionFlipRate/TargetTurnover/StatePersistence/MedianHolding/
  UnnecessaryReversalRate（Research Metric，先证明抖动再治理，
  不先发明平滑算法）；
  ㉖ **Trade Outcome Attribution**（evaluation/trade_outcome.py）：
  Raw opportunity / Entry delay / Early exit / Slippage / Position cap /
  Permission → Realized contribution + biggest leak；
  ㉗ **Wave Quality Matrix**（evaluation/wave_quality_matrix.py）：
  Wave Recall/Precision/Capture Ratio/False Entry Rate/Missed Wave Rate
  双向错误框架（WaveOutcomeLabel 仅事后 Research，不回流 Production）；
  ㉘ **Permission Opportunity Cost**（evaluation/permission_value.py）：
  Benefit（Avoided Loss/Drawdown/False Entry/Tail）vs Cost（Missed
  Return/Wave/Entry Delay/Capture）→ Net Permission Value
  （JUSTIFIED/NEUTRAL/REVIEW）；
  ㉙ **Retail Practicality Scorecard**（evaluation/retail_scorecard.py）：
  10 指标（Trades/年、持仓期、并发仓位、换手、退出天数、ADV 参与、
  MDD、决策变化/月、遗漏、解释复杂度）→ A/B/C/D，高频/高换手硬降级；
  ㉚ **Feature Freeze**（governance/feature_freeze.py）：允许 Bug/Governance/
  PIT/Replay Fix + Ablation/Stress/Simplification/Retirement；新决策模块
  必须回答"解决什么已测量问题"+ 增量价值>0 + OOS/Ablation/Stress/Shadow
  全过，否则默认 DROP 不进入生产。

- **V69（2026-08-27）**：统一口径/证明约束/删除冗余（新 11–20）落地——
  ⑪ **Performance Metric Contract**（performance/contract.py）：唯一
  标准指标层（equity_curve → CAGR/Total/Vol/Sharpe/Sortino/MDD/Calmar/
  Turnover/Cost/Win Rate），统一 annualization/compounding/rf/NaN 规则
  （同一组 trades 进 Backtest/Ablation/Stress/Report 结果一致）；
  ⑫ **交易日模型修复**（execution/liquidity_exit.py）：build_deleverage_plan
  改为仅实际可交易日推进（跳过周末/休市/停牌，半日市容量减半），
  cumulative_pct 改为真正累计值；
  ⑬ **Canonical Research 默认**（cross_sectional_backtest/execution_ablation/
  retail_swing_report）：legacy 默认全部改为 canonical；
  legacy 显式使用时标注 NON_AUTHORITATIVE/SHADOW_ONLY；
  ⑭ **ValidationCertificate**（governance/validation_certificate.py）：
  PIT/OOS/Ablation/CostStress/ExecutionStress/Regime/Replay/Governance/
  Shadow 九门 → CERTIFIED/UNKNOWN/NOT_CERTIFIED；报告只显示证书，
  无证书 → UNKNOWN（绝不显示 RESEARCH VALIDATED）；
  ⑮ **Feature Production Manifest**（decision/feature_manifest.py）：
  Feature 生命周期 DEFINED→WIRED→VALIDATED→CERTIFIED→ACTIVE→
  DEPRECATED→RETIRED，Production Manifest 只允许 ACTIVE；
  ⑯ **唯一 VersionIdentity**（decision/versions.py）：model/schema/rule/
  engine/commit/config/feature hash 七字段权威单例，所有消费者从此读取；
  ⑰ **标准机器 ReasonCode**（decision/reason_codes.py）：
  PERMISSION_BLOCK_NEW_RISK/WAVE_MATURE_NO_ADD/PORTFOLIO_GROSS_CAP/
  LIQUIDITY_EXIT_LIMIT/DRAWDOWN_SAFE_MODE/HARD_EXIT_STOP 等 13 码
  + constraint_name → 标准码映射；
  ⑱ **对抗性不变量测试**（test_property_invariants.py）：极端 Alpha+BLOCK+
  ACTIVE+组合可用 → 仍不能越权；FinalTarget≤全 cap；Daily 不能提升
  权限；future label 阻断；Report 不改变 Snapshot；
  ⑲ **标准压力场景库**（stress/scenario_library.py）：BASE/COST_1.5X/
  COST_2X/SLIPPAGE_2X/ADV_50%/ADV_25%/ENTRY_DELAY_1D/2D/GAP_DOWN/
  BEAR_REGIME/HIGH_VOL/LIQUIDITY_SHOCK 12 场景固定库 + version，
  Certification 使用固定场景集（策略不能挑场景）；
  ⑳ **模块删除执行**（governance/module_trim.py）：Ablation → 增量价值 →
  复杂度成本 → KEEP/REVIEW/DROP → RETIRED 真正执行（四类贡献
  Alpha/Risk/Execution/Governance 均无 → 删除）+ quarterly_trim_report
  （"这一次除了增加什么，实际删除了什么"）。

- **V68（2026-08-27）**：权力边界收敛/生产治理闭环/Wave 强化（新 1–10）
  落地——
  ① **Canonical Provenance 强制**（backtest/engine.py）：run_backtest
  正式模式（research_validation/production）拒绝无 canonical_target/
  canonical_provenance 的 target（禁止 Evidence→target 旁路）；研究模式
  警告并标注非正式；
  ② **统一 PermissionPolicy 对象**（decision/permission_policy.py）：
  permission_policy_object 返回 new_risk_allowed/add_allowed/
  maintain_allowed/max_target/mandatory_derisk/observation_allowed，
  BLOCK=禁新增+禁加仓+强制去风险（Policy 明确规定，无双语义）；
  ③ **Ledger 不可变事实源强化**（decision/decision_ledger.py）：
  dataset_manifest_hash（row count + id 范围 + content hash——历史改值
  行数不变也检测）+ ledger_event 追加式 DECISION_INVALIDATED（不再
  UPDATE 原决策）；
  ④ **FinalTarget 全 cap 验证**：V53 finalize_target min-chain
  （Raw/Permission/Risk/Portfolio/Liquidity/Execution/Drawdown/DataQuality）
  已覆盖，测试锁定；
  ⑤ **Fail-Closed 持续验证**（safety/continuous_validation.py）：
  PASS/WARN/FAIL/UNKNOWN 四态；Production-required（ledger/replay/pit/
  execution）为 UNKNOWN → 至少 SAFE_MODE，关键证据缺失绝不显示 NORMAL；
  ⑥ **StrategyLifecycle Provenance 保留**（governance/lifecycle.py）：
  promote/retire 改用 dataclasses.replace 完整继承 commit/config/data/
  strategy/feature 字段 + assert_provenance_preserved（字段丢失→拒绝）；
  ⑦ **Report Contract**（report/contract.py）：报告字段必须与 Ledger
  完全一致（institutional_permission/fsm/final_target/reason），
  报告重算决策 → ReportContractError（报告只解释事实不产生事实）；
  ⑧ **Wave Stage → Canonical 提案链**（wave/canonical.py）：
  wave_to_canonical——Stage → 权限 → 动作 → max_entry_scale → 提案目标
  （DISCOVERY 禁入/CONFIRMING 小仓/ACTIVE 可加/MATURE 禁加/EXHAUSTING 减/
  INVALID 退出）；
  ⑨ **AsOfWaveOpportunity / WaveOutcomeLabel 代码级隔离**
  （wave/asof_opportunity.py + wave/outcome_label.py）：as-of 机会仅含
  stage/strength/entry zone/invalidation/expected band/expiry；
  outcome/future 字段被 FeatureGate 阻断；WaveOutcomeLabel
  （Evaluation-only）从 Production 包 import → 拒绝；
  ⑩ **Paired time-series Ablation**（ablation/statistical.py）：
  Δ_t = Treatment−Baseline，block/stationary bootstrap + 500-1000
  permutation（保持块结构）+ Regime 分层 + Effect Size →
  KEEP/REVIEW/DROP + 贡献类型（Alpha/Risk Reduction/Execution/None）。

- **V67（2026-08-27）**：Adaptive Intelligence（新 41–50：系统进化/机构级
  研究能力）落地——
  ㊶ **Alpha Discovery Pipeline**（research/alpha_discovery.py）：候选
  Feature/Relationship → Hypothesis → Evidence → Expected Mechanism →
  Test → Confidence → ALPHA_REGISTRY（自动产生候选，但未经验证不能进
  生产）；
  ㊷ **Counterfactual Decision Value**（evaluation/counterfactual_value.py）：
  Actual vs BUY4%/NO TRADE/EXIT earlier/Permission OFF/Wave OFF →
  Decision Value = Actual − Counterfactual（Ablation 研究模块，
  Counterfactual 研究单次决策价值）；
  ㊸ **Causal Evidence Level**（research/causal_evidence.py）：L0 Observation
  → L5 Causal Hypothesis Supported 六级证据等级 + 报告措辞随等级调整
  （不写"导致上涨"，写"存在稳定的条件相关关系"）；
  ㊹ **Decision Policy Optimizer**（research/policy_optimizer.py）：优化
  "状态→行动"映射（State=Permission+Regime+Wave+Risk+Portfolio），
  硬边界：不能修改 Permission，Governance > Risk > Policy；
  ㊺ **Regime Transition Early Warning 验证**：V52 transition early_warning
  已覆盖（Transition Probability → Risk Budget↓/Position↓/Entry↑）；
  ㊻ **Alpha Half-Life Engine**（alpha/halflife.py）：IC(t)=IC0×(0.5)^(t/hl)
  → 半衰期/衰减率/Strength Ratio/Weight Scale（IC↓ → Weight↓，不固定
  Weight）；
  ㊼ **Cross-Sectional Opportunity 验证**：V55 九维排序已覆盖；
  ㊽ **Strategy Competition / Champion-Challenger**
  （research/strategy_competition.py）：多策略持续竞争
  （Sharpe/Return/MDD/Turnover/Capacity/Robustness/Decision Quality
  平衡分）→ Champion/Challenger/Retired；
  ㊾ **Transferability Validation**（research/transferability.py）：跨市场
  验证 → Market-General/Sector-Specific/Market-Specific/Stock-Specific
  （结构性机制可迁移，市场特有指标不可迁移）；
  ㊿ **Autonomous Research Loop**（research/autonomous_loop.py）：
  Discover→Hypothesis→Sandbox→PIT/OOS→Ablation→Stress→Certification→
  Shadow→Production→Monitor→Decay→Challenger→Retire→Research 闭环，
  AI 只能发现候选、不能未经治理改变决策。

- **V66（2026-08-27）**：克制层（新 31–40：复杂度控制/反过拟合/统计可信/
  退役机制）落地——
  ㉛ **Module Value Attribution**（evaluation/module_value.py）：模块贡献
  矩阵（Return/MDD/Sharpe/Turnover/Decision Quality Δ）+ Module Net
  Value 公式（增量 Alpha + 风险降低 + 决策质量 + 资本效率 − 复杂度 −
  数据风险 − 过拟合 − 维护成本），Net≤0 → 退役候选；
  ㉜ **Complexity Budget v2**（governance/complexity_budget.py）：预算上限
  （Feature≤80/Rule≤40/参数≤25/异常≤10/分支≤50）+ budget_consumption
  消耗核算（超限标记）；
  ㉝ **Feature Pruning**（research/feature_pruning.py）：特征价值
  （预测贡献/增量 Alpha/稳定性/相关性/数据成本/PIT/复杂度/失效风险）
  → KEEP/SHADOW/REVIEW/RETIRE；
  ㉞ **Overfitting Firewall**（research/overfitting_firewall.py）：记录
  实验/参数搜索/模型变体/特征变体/选择规则/Holdout →
  Data Snooping Risk（区分"发现"与"筛选"的 Alpha）；
  ㉟ **CI Engine**（research/ci_engine.py）：Bootstrap Sharpe CI /
  Return CI / Win Rate CI / MFE-MAE CI（自相关感知，非 IID 假设）；
  ㊱ **Rolling OOS 验证**：V55 rolling_oos_evaluation + oos_summary 已覆盖；
  ㊲ **Regime × Strategy Matrix**（evaluation/regime_matrix.py）：每 Regime
  Trades/Win Rate/Return/MDD/Sharpe/Expectancy + Permission×Regime×Wave
  交互（如 ALLOW+STRONG 在 Transition 胜率下降）；
  ㊳ **Capacity/Scalability 验证**：V79 alpha_capacity 已覆盖；
  ㊴ **Simplification Engine**（research/simplification.py）：Full vs
  Simplified（复杂度↓≥30% 且 Sharpe 损失≤5% → 推荐简化），
  minimum_effective_system 选择最低复杂度候选；
  ㊵ **Module Retirement Governance**（governance/module_retirement.py）：
  模块生命周期 PROPOSED→...→RETIRED（RETIRE 是正常状态），
  Incremental Alpha≈0 + Complexity↑ + Data Risk↑ → RETIRE。

- **V65（2026-08-27）**：Intelligence Layer（新 21–30：决策质量精细化/
  统计严谨性/组合优化/反事实验证/安全生产）落地——
  ㉑ **Decision Provenance Graph**（explainability/graph.py）：9 节点
  因果链（Institutional/Permission/Regime/Wave/FSM/Risk/Portfolio/
  Execution/Final），每节点 value/timestamp/source/version/evidence/
  dependency/decision_effect（可审计从日志级 → 因果链级）；
  ㉒ **Signal Conflict Resolver + Regime**（governance/conflict.py）：
  Decision Authority Hierarchy 补 REGIME_BLOCK（Governance > Permission
  > Risk > Portfolio > Regime > Liquidity > FSM > Wave > Entry），
  Bear/Crisis 压过 Wave；
  ㉓ **Confidence Calibration 强化**（monitoring/confidence_calibration.py）：
  补 Log Loss + Expected Calibration Error（ECE）+ 既有 Brier/可靠性曲线；
  ㉔ **Threshold Stability 验证**：V55 parameter_stability_surface 已覆盖
  （稳定区域 vs 最优点）；
  ㉕ **Position Sizing 2.0**（decision/optimal_position.py）：
  Maximum Allowed → Risk-optimal（Kelly 风格 edge/risk×confidence）→
  Liquidity-optimal → Executable，绑定约束识别；
  ㉖ **Opportunity Ranking/Allocation 验证**：V55/57 九维排序 + 资本分配
  已覆盖；
  ㉗ **Trade Attribution 验证**：V55/68 P&L 归因已覆盖；
  ㉘ **False Positive/Negative Lab**（evaluation/fpfn_lab.py）：TP/FP/FN/TN
  四象限 + Precision/Recall/F1 + FP/FN 成本与原因分布 + 平衡告警
  （不能只压 FP 而错过牛股）；
  ㉙ **Benchmark / Challenger System**（evaluation/challenger.py）：QCFP
  vs Buy&Hold/Wave-only/Permission-only/Challenger 排名 + Sharpe Edge +
  MDD Advantage + BEATS_CHALLENGERS/CHALLENGED；
  ㉚ **Production Architecture 2.0**（governance/three_worlds.py）：
  RESEARCH（实验不影响生产）/SHADOW（并行对比）/PRODUCTION（只读
  Certified）三态隔离 + 晋升链（Research→Candidate→Shadow→Certified→
  Production）+ shadow_comparison。

- **V64（2026-08-27）**：实战能力/研究效率/系统质量（新 11–20）落地——
  ⑪ **Data Health Score**（data/quality.py）：8 维健康度
  （Completeness/Accuracy/Timeliness/Consistency/PIT/Outlier/Duplicate/
  Source）→ DHS 0-100（NORMAL≥95/CAUTION/90/DEGRADED/80/BLOCK<80），
  关键字段失败 → Hard Block（不平均分稀释）；
  ⑫ **Feature Registry**（data/feature_registry.py）：feature_id/name/
  definition/source/table/column/calculation/frequency/available_at/
  lookback/PIT_grade/transform_version/owner/status（Feature→Lineage→
  Decision，不再黑箱 Wave=0.73）；
  ⑬ **Regime-conditioned Decision**（market/regime_conditioned.py）：
  Regime → Permission Modifier↓/Wave Threshold↑/Risk Budget↓/
  Position Size↓，Regime 不能提高 Permission
  （Institutional > Regime > Wave）；
  ⑭ **Wave Multi-stage Output**（wave/stage_output.py）：stage/score/
  strength/age/velocity/acceleration/exhaustion/breakdown 八字段，
  Formation→Trigger→Expansion→Acceleration→Distribution→Decay；
  ⑮ **Position Lifecycle Analytics**（evaluation/position_lifecycle.py）：
  Entry/Initial Risk/Add/Hold/Trim/Exit/Cooldown 每阶段 Price/Target/
  Position/Risk Budget/MFE/MAE/P&L/Holding Days/Reason/Hash +
  阶段质量统计（定位最易犯错阶段）；
  ⑯ **Portfolio Risk Aggregator**（portfolio/aggregator.py）：Gross/Net/
  Sector/Factor/Liquidity/Correlation/Crowding/VaR/ES 聚合 + 名义 vs
  有效暴露（A+B+C 同 AI → 1 因子）；
  ⑰ **Executable Target**（execution/simulator.py）：Decision Target →
  容量/冲击/成交率 → Executable Target（理论 10% 可能只执行 6.5%）；
  ⑱ **Joint Scenario Engine**（stress/joint_stress.py）：A 市场-10%+VIX+
  流动性-30% / B 行业-20%+权限↓+Wave 破位 / C 崩盘+流动性崩塌+滑点×2+
  相关性↑ 三联合情景 → Expected/Max Loss/Exit Days/Liquidity Shortfall/
  Capital Remaining/System State（自动 SAFE_MODE/HALTED）；
  ⑲ **Research Experiment Factory**（research/factory.py）：experiment
  spec → 统一 Runner → Artifacts/Metrics/Comparison/Report → Registry
  （Hypothesis/Dataset/PIT/Baseline/Treatment/Sweep/OOS/Ablation/
  Stress/Replay/Statistical/Certification）；
  ⑳ **System Health / Incident / Kill-Switch**
  （safety/system_health.py）：7 维健康度 + GREEN/YELLOW/ORANGE/RED/HALT
  状态阶梯，与 Model Doubt Index 合并（MDI≥80 → HALT）。

- **V63（2026-08-27）**：Evidence-First 可信底座（新 1–10）落地——
  ① **Canonical-only**（scripts/backtest_runner.py）：默认引擎改为
  canonical，legacy 必须显式 --shadow-comparator 才允许（仅供对比，
  非正式结果）；canonical_only_gate 单元测试锁定；
  ② **Ledger 不可篡改哈希链**（decision/decision_ledger.py）：每条记录
  带 previous/current ledger_hash（current = hash(prev + 决策核心字段)），
  verify_ledger_chain 校验链完整性（P0-2）；
  ③ **Evidence Provider**（governance/evidence_provider.py）：PIT/Ledger/
  Replay/OOS/Ablation/Version/DataQuality 证据由真实检查产生，
  bundle 拒绝手工注入 PASS（ledger_ok=True 这类声明被拒）；
  ④ **Zero-Trust Certification**（governance/zero_trust.py）：C1-C6
  硬门任一 FAIL → 立即 NOT_CERTIFIED；全过后才计算 Quality Score
  （不是"17/18 过 → 94 分"）；
  ⑤ **PIT Universe Registry**（data/pit_registry.py）：universe_id/
  effective_from/to/stock/source/available_at/snapshot_hash +
  stocks_known_at(date) + PIT Integrity Score（A=100/B=90/C 仅探索）；
  ⑥ **Release/Artifact Registry**（governance/artifact_registry.py）：
  Git Commit/Code/Model/Rule/Config/Schema/Feature/Data/Execution/
  Test/OOS/Ablation/Replay/Certification 制品 → Release Hash；
  ⑦ **Risk Constraint Attribution**（decision/constraint_trace.py）：
  binding_constraint（决定最终目标的那层）+ 各级减少归因
  （Permission/Risk/Portfolio/Liquidity/Execution Reduction）；
  ⑧ **Governance Alpha**（evaluation/governance_alpha.py）：Governed vs
  Unrestricted 的 Alpha + Drawdown/Turnover/Capital Efficiency/
  Opportunity Cost + avoided_loss（BLOCK 交易中本会亏损的 Avoided Loss）；
  ⑨ **Entry/Exit Timing Alpha**（evaluation/timing_alpha.py）：Entry
  Alpha（实际 vs 最优入场）+ Exit Alpha（实际 vs MFE 峰值）+
  Timing Alpha = Entry + Exit；
  ⑩ **Model Doubt Index**（governance/doubt_index.py）：11 项指标 →
  MDI 0–100（NORMAL/CAUTION/DEFENSIVE/SAFE_MODE/HALTED），
  MDI↑ → Risk Budget↓ → Position Size↓。

- **V62（2026-08-27）**：第十层（新 91–100：系统自证/压力生存/决策鲁棒性/
  联合退化/生产自治）落地——
  ⑨① **Decision Robustness Score**（decision/stability.py）：六类扰动
  （Feature/Data/Parameter/Timing/Cost/Regime）→ 跳变率 →
  ROBUST/FRAGILE/UNSTABLE，Fragile → 降仓或 Watch；
  ⑨② **Scenario Stress Matrix**（stress/stress_matrix.py）：Market×Vol×
  Liquidity×Institutional 五情景矩阵 + Permission>Risk>Signal 验证；
  ⑨③ **Data Degradation Simulator**（stress/data_degradation.py）：Missing/
  Delayed/Stale/Duplicate/Outlier/Wrong Timestamp/CA Error/Volume Anomaly
  → DATA_HEALTH（GOOD/DEGRADED/BAD），BAD → NEW_ENTRY BLOCK；
  ⑨④ **Joint Degradation Stress**（stress/joint_stress.py）：Data+Model+
  Execution 联合退化 → Worst Case Loss / Max Position / Exit Feasibility /
  Liquidity Requirement / Recovery Time（三退 → CRITICAL）；
  ⑨⑤ **Decision Boundary Test**（decision/boundary_test.py）：B1 Cap Chain
  / B2 BLOCK / B3 Risk Block / B4 Hard Exit / B5 Flat BLOCK 五边界测试
  套件（下层不能突破上层）；
  ⑨⑥ **No-Trade Quality Score**（evaluation/no_trade.py）：Correct/False
  Trade + Correct/False No-Trade 混淆矩阵 + No-Trade Score +
  avoided_loss / missed_gain；
  ⑨⑦ **Opportunity Miss Analysis**（evaluation/miss_analysis.py）：遗漏
  原因分布（Permission/Risk/Entry/Liquidity...）+ Capture Rate + Missed
  Alpha（Wave→实战转化效率）；
  ⑨⑧ **Regret Analysis**（evaluation/regret.py）：Best Feasible − Actual
  （Entry/Exit/Sizing/No-Trade/Capital Allocation），基于当时可获得信息；
  ⑨⑨ **System Safety Case**（safety/safety_case.py）：六 Claim
  （Permission 不可覆盖/Risk Cap 不可覆盖/PIT/OOS 可复现/Ablation 完整/
  版本一致）→ Requirement→Test→Evidence→Certification；
  ⑩〇 **Production Autonomy Governor**（governance/autonomy.py）：四级自治
  （READ_ONLY→CONTROLLED_EXECUTION）+ 行为矩阵（计算/建议可自动、
  修改 Permission/Risk/Model/PIT、绕过 OOS/Ablation、自批新版本
  永远禁止）。

- **V61（2026-08-27）**：第九层（新 81–90：Alpha 资产治理/因果归因/
  状态切换/组合交互/全链路溯源）落地——
  ⑧① **Alpha Source Registry**（alpha/registry.py）：alpha_id/source/
  hypothesis/feature_dependencies/market_regime/expected_holding/
  risk_dependencies/validation/production，共享依赖检测（防重复下注）；
  ⑧② **Alpha Correlation Monitor**（alpha/correlation.py）：Signal/
  Position/P&L 相关性 + 特征值法 Effective Alpha Count + 高相关对
  （"5 个信号 → 有效独立 2.1"）；
  ⑧③ **Incremental Alpha Test**（ablation/incremental.py）：Base vs
  Base+Module 的 ΔReturn/ΔSharpe/ΔMFE Capture/ΔMDD/ΔTurnover/ΔCost/
  ΔTail → net_alpha + KEEP/REVIEW/DELETE 建议（零增量 → 删除）；
  ⑧④ **Causal Attribution Layer**（ablation/incremental.py）：Observed
  vs Incremental Effect + Regime Effect → attributable_share +
  MODULE_CAUSAL / ENVIRONMENT_DRIVEN（防把市场 Beta 误认为 Wave Alpha）；
  ⑧⑤ **Counterfactual 验证**：决策级（counterfactual_replay）与组合级
  （portfolio_counterfactual）已覆盖，补测锁定；
  ⑧⑥ **Regime Transition FSM**（market/regime_fsm.py）：
  BULL_STABLE→BULL_WEAKENING→TRANSITION→BEAR_CONFIRMING→BEAR_STABLE
  （反向 RECOVERY→BULL_CONFIRMING），每步定义 Permission/Wave/Risk/
  Position 效果，非法跳转拒绝；
  ⑧⑦ **Portfolio Interaction Graph**（portfolio/interaction_graph.py）：
  Stock/Sector/Theme/Factor 节点 + Industry/Theme/Factor/Corr 边 →
  簇 + Nominal vs Effective Exposure（"5 股=1 主题"）；
  ⑧⑧ **Strategy Capacity Allocation**（portfolio/strategy_allocation.py）：
  多策略共享风险预算（Performance/Correlation/Capacity/Drawdown/
  Regime/Confidence/Cost 动态），Governance > Portfolio > Strategy >
  Signal；
  ⑧⑨ **Alpha Health Early Warning**（governance/model_decay.py）：
  90–100 HEALTHY / 75–90 WATCH / 60–75 WARNING / <60 DEGRADED，
  WARNING → INCREASE_VALIDATION（不自动改参数，与 Sandbox 一致）；
  ⑨〇 **Research-to-Production Provenance**（governance/provenance.py）：
  Production→Release ID→Certification→OOS→Ablation→Experiment→
  Hypothesis→Dataset→PIT→Feature→Code→Config→Approved-by 13 环
  溯源链，缺失任何环节 → ProvenanceError。

- **V60（2026-08-27）**：第八层（新 71–80：市场机会环境/时机/组合生存/
  长期 Alpha 稳定性）落地——
  ⑦① **Market Opportunity Regime**（market/opportunity_regime.py）：
  REGIME_0 防御~REGIME_4 极强机会五层 + Capital Aggression 系数，
  "允许做"≠"现在值得积极做"；
  ⑦② **Permission Strength**（decision/permission_gate.py）：权限强度
  连续化（BLOCK=0/TEST=0.25/LIMITED=0.50/ALLOW=0.75/FULL=1.0），
  Cap=raw×strength 只会降低上限、永不提高（不是 Alpha 分数）；
  ⑦③ **Wave Quality Decomposition**（wave/quality.py）：Strength/
  Persistence/Acceleration/Maturity/Remaining/Confirmation/FailureRisk
  七分量 → composite，区分"早期强机会"与"已成熟 Wave"；
  ⑦④ **Entry Timing 验证**：V54 timing_band（EARLY/OPTIMAL/ACCEPTABLE/
  LATE/INVALID）已覆盖，补测锁定；
  ⑦⑤ **Exit Efficiency**（decision/exit_quality.py）：Exit Efficiency =
  Captured MFE / Available MFE（EXCELLENT/GOOD/FAIR/POOR）+ EXIT_*
  分类映射（HARD/SIGNAL/DECAY/TIME/RISK/REGIME/TRAILING）；
  ⑦⑥ **Position Scaling Policy**（decision/position_scaling.py）：
  生命周期扩缩（2%→3%→5%→4%→2%→0）+ Signal↑/Risk↓→扩、
  Signal↓/Risk↑→缩，Final ≤ Permission ≤ Risk ≤ Portfolio ≤ Liquidity；
  ⑦⑦ **Concentration Governor**（portfolio/concentration.py）：
  Sector/Theme/Beta/相关性有效集中度，单股合规但组合隐性集中 → 收缩；
  ⑦⑧ **Tail-Risk / Gap-Risk Engine**（portfolio/tail_gap.py）：Gap Risk/
  Liquidity Collapse/Trading Halt/Event Risk → Worst Expected Loss +
  tail_position_scale（仓位按 Tail Risk 而非仅 Normal Risk）；
  ⑦⑨ **Alpha Capacity**（execution/capacity.py）：Capital→Sharpe 衰减
  曲线（指数衰减），max_efficient_capital + EFFICIENT/DEGRADED/
  CAPACITY_LIMITED 判定；
  ⑧〇 **Strategic Decision Review**（review/strategic_review.py）：
  周期级复盘（What Worked/Failed/Changed/Retire/Test/Must NOT Change）
  + 治理路径（Review→Hypothesis→Research→OOS→Ablation→Stress→
  Governance→Release，禁止直接改生产）。

- **V59（2026-08-27）**：第七层（新 61–70：决策校准/组合优化/行为控制/
  Alpha 归因/自适应治理）落地——
  ⑥① **Confidence Calibration**（monitoring/confidence_calibration.py）：
  Brier Score / Calibration Error / Reliability Curve / 分桶实际胜率 /
  校准映射（Raw→Calibrated），校准参数必须 OOS 验证后才可用；
  ⑥② **Opportunity Decay Model**（wave/aging.py）：Opportunity Value(t)
  = 100%×(0.5)^(t/half_life)×因子（动量/波动/流动性/Regime/阶段），
  识别"Wave 仍强但机会已进尾部"；
  ⑥③ **MFE/MAE Benchmark**（monitoring/benchmark.py）：按 Wave×Entry×
  Regime×Holding 分层建立 MFE/MAE/最佳持仓期基准 + 当前交易偏离判定；
  ⑥④ **Holding-period Efficiency**（backtest/retail_utility.py）：
  Return/Capital/Time + MFE/Holding Days + Return per Capital-Day +
  年化折算，衡量单位资金单位时间收益；
  ⑥⑤ **Capital Turnover Optimization**（replacement/replacement_engine.py）：
  capital_rotation——B 日化收益折算 A 剩余期 vs A 剩余收益 + 成本 + 风险
  罚金，优化资本周转而非交易次数；
  ⑥⑥ **Portfolio Rebalancing Governance**（portfolio/rebalancing.py）：
  Rebalance Band / Min Trade Size / Min Benefit / Cooldown / Cost
  Threshold，微小偏差 → NO TRADE；
  ⑥⑦ **Trade Frequency Governor**（governance/trade_frequency.py）：
  Daily/Weekly/Portfolio Turnover/Cooldown 四限 + 频率↑+边际↓ 自动收紧
  （TIGHTENED→WATCH→HOLD）；
  ⑥⑧ **Alpha Attribution Decomposition v2**（performance/attribution.py）：
  新增 portfolio_allocation_alpha（排名价值：高分半组收益−低分半组），
  归因桶补 Portfolio_Allocation；
  ⑥⑨ **Adaptive Policy Sandbox**（learning/adaptive_sandbox.py）：
  Certified vs Experimental 策略隔离，生产只读 Certified，
  候选必须过 Backtest/OOS/Ablation/Stress/Replay/Release 六门；
  ⑦〇 **Continuous Validation Controller**（monitoring/validation_controller.py）：
  HEALTHY→WARNING→DEGRADED→REVIEW→HALTED 状态机 + 恢复流程
  （HALTED→Root Cause→Research→Validation→Certification→Shadow→
  PROMOTION，禁止人工直接恢复交易）。

- **V58（2026-08-27）**：第六层（新 51–60：资本配置智能/冲突/实盘偏差/
  闭环归因）落地——
  ㊿ **Opportunity Ranking 验证**：V55 已实现九维排序（Wave/Remaining/
  Entry/Risk/Liquidity/Holding/Capital Efficiency），本版补测试锁定；
  ⑤① **Risk-adjusted Opportunity Score**
  （ranking/opportunity_ranking.py）：Expected Edge / Expected Risk
  （MFE×概率×Remaining×Entry 质量 ÷ MAE+持有+成本+流动性），单位风险
  机会价值；
  ⑤② **Capital Allocation v2**（ranking/allocator.py）：逐仓钳制
  Position ≤ Permission ≤ Risk ≤ Liquidity（permission/risk/liquidity
  caps），分配不得绕过权限；
  ⑤③ **Position Replacement 验证**：V54 已实现 utility+switching cost+
  阶段调整，本版补测；
  ⑤④ **Opportunity Queue / Watchlist**（ranking/queue.py）：WATCH/TEST/
  READY/ACTIVE/BLOCKED/EXPIRED 六态 + 自动推进（Entry Late+TEST→TEST、
  Pullback+OPTIMAL+ALLOW→READY）；
  ⑤⑤ **Signal Conflict Resolver v2**（governance/conflict.py）：优先级
  Governance > Permission > Risk > Portfolio > Liquidity > FSM > Wave >
  Entry（补 GOVERNANCE_BLOCK/PORTFOLIO_BLOCK/LIQUIDITY_BLOCK）；
  ⑤⑥ **Confidence → Position Multiplier**
  （decision/confidence.py）：>0.85→100% / 0.70–0.85→70% /
  0.55–0.70→40% / <0.55→观察，BLOCK→0、WATCH≤0.2、≤Governance Cap
  （置信度不能绕过风险/权限）；
  ⑤⑦ **Module Consensus**（decision/consensus.py）：Wave/Trend/Momentum/
  Liquidity/FSM 加权共识 → HIGH/MEDIUM/LOW，Wave 强但共识低 → 自动 Reduce；
  ⑤⑧ **Live-vs-Backtest Gap Monitor**（monitoring/gap_monitor.py）：
  Return/MFE/MAE/Slippage/Entry/Exit/Holding/Cost 八维偏差 →
  HEALTHY→WARNING→DEGRADED→MODEL_REVIEW；
  ⑤⑨ **Post-trade Attribution & Closed-loop**（learning/post_trade.py）：
  Wave/Entry/Exit/Risk/Portfolio/Execution 六模块归因 + 闭环守卫
  （生产写 Outcome、研究建 Hypothesis、候选不能自动晋升生产）。

- **V57（2026-08-26）**：第五层（新 41–50：系统工程化/规模化/长期稳定/
  生产闭环）落地——
  ㊶ **Decision Schema Registry**（decision/schema_registry.py）：Schema
  版本兼容治理（BACKWARD_COMPATIBLE / MIGRATE_REQUIRED / INCOMPATIBLE +
  migration_rule），旧 Schema 决策可迁移读取后 Replay/Audit；
  ㊷ **Full Data Lineage**（data/lineage.py）：LineageNode 补
  source_timestamp / transformation_id，feature_lineage 输出单特征全链
  （feature→transformation→raw→source→available_at + source_version）；
  ㊸ **Deterministic Replay Engine**（decision/replay_engine.py）：逐字段
  比较 permission/wave/fsm/risk/raw/governed/final/action/reason →
  EXACT_MATCH / REPLAY_MISMATCH（final target 相同但决策链改变也判不一致）；
  ㊹ **Portfolio Decision Ledger**（portfolio/portfolio_ledger.py）：组合级
  事实源（gross/net/sector/theme/risk_budget/cash/positions_before/after/
  rejected/replacements），支持"为什么 A 没买/为什么 B 被卖"查询；
  ㊺ **Cross-Symbol Allocation**（ranking/allocator.py）：风险调整排序 →
  资本分配（A→5%/B→4%/C→2%/D→WATCH），受总预算与单股上限约束；
  ㊻ **Scenario Stress Engine**（stress/scenario_engine.py）：7 情景
  （市场-10%/波动×2/流动性-50%/行业崩盘/权限恶化/Wave 失败/滑点×3）
  重跑决策链，验证 Permission→Target→Exposure 自动收缩
  （risk_responsive 判定）；
  ㊼ **Decision Quality Monitor**（monitoring/decision_quality.py）：
  Permission/Wave/Entry/Exit/FSM 五维质量（ALLOW 胜率、BLOCK 避免损失、
  MFE Capture、Optimal/Late/Early 占比、异常 Transition）；
  ㊽ **Model Decay / Retirement**（governance/model_decay.py）：8 项衰减
  指标 → 健康度评分 + 退役阶梯（Production→Aging→Degraded→
  Retirement Candidate→Retired），持续恶化不等回撤严重才人工发现；
  ㊾ **Operational Observability**（monitoring/observability.py）：六环节
  延迟 + Error/Missing/Queue + Data/Decision/Execution/Ledger/Research
  五维健康；Ledger 写入失败 → Decision DEGRADED → HALT（硬规则）；
  ㊿ **Governance Certification**（governance/certification.py +
  scripts/governance_certification.py）：五维认证（不可越权/可审计/
  可回测/可Ablation/牛散实战）→ CERTIFIED / NOT_CERTIFIED。

- **V56（2026-08-26）**：第四层（新 31–40：模型可信度/决策解释/研究可复现/
  异常处理/版本治理/生产发布）落地——
  ㉛ **Decision Explanation Engine**（explainability/engine.py）：六问解释
  （为什么允许/为什么现在/为什么这个仓位/为什么不是更大/为什么不是更小/
  为什么退出）+ 自然语言叙述（Decision Certificate 顶部）；
  ㉜ **Constraint Trace**（decision/constraint_trace.py + finalize_target
  接入）：每级约束记录 input/limit/output/reason/version，输出各级
  Reduction（如 Permission Reduction=2%），返回 dict 增补
  constraint_trace；
  ㉝ **Reason Code 标准化**（decision/reason_codes.py）：14 个标准原因码
  + primary/secondary/constraint_reasons 三结构 + 按码聚合统计
  （"过去 12 个月多少交易因 ENTRY_LATE 被阻止"）；
  ㉞ **Decision Path Hash**（decision/path_hash.py + engine 接入）：
  Data+Feature+Permission+Wave+FSM+Risk+Portfolio+Execution+Governance
  共同哈希，Input 一致但 Path 不一致 → 隐藏版本漂移检测；
  ㉟ **Release Identity / Version Lock**（decision/release_identity.py）：
  model+rule+config+schema+feature+data+execution → release_id，
  ReleaseRegistry 校验已批准组合，混版本 → ReleaseLockError；
  ㊱ **Research Registry 完整化**（ablation/statistical.py）：
  register_research 补 PIT 规格/特征版本/参数空间/训练-验证-OOS 期/
  成本模型/执行模型/消融定义/晋升状态；
  ㊲ **Holdout Lock**（ablation/statistical.py）：最终 OOS 不得参与参数
  选择（used_in_selection=True → 禁止作为最终 OOS，须冻结独立窗口）；
  ㊳ **Regime Robustness / Transition**（market/regime_robustness.py）：
  五类 Regime + REGIME_STABLE/TRANSITION/UNCERTAIN，TRANSITION →
  Permission 自动收紧（overall_permission_scale = min 各尺度）；
  ㊴ **Failure Safe Degradation**（failure/degradation.py）：11 类失败 →
  正常/DEGRADED/OBSERVE/BLOCK/HALTED 阶梯，Data→权限收紧、PIT→BLOCK、
  Ledger→NO_TRADE、Replay→HALTED，apply_degradation 压缩目标；
  ㊵ **Promotion Gate**（governance/promotion_gate.py）：13 步晋升链
  （Research→Unit→Invariant→PIT→OOS→Ablation→Cost→Execution→Regime→
  Replay→Shadow→Governance→PROMOTE）+ Release 状态阶梯
  EXPERIMENTAL→VALIDATED→SHADOW→PRODUCTION→DEGRADED→HALTED。

- **V55（2026-08-26）**：第三层（新 21–30：组合约束/成交真实/研究验证/
  数据质量/生产监控）落地——
  ㉑ **Portfolio Exposure Budget**（portfolio/budget.py）：Gross/Net/
  Sector/Theme/Single/Liquidity/Risk 七维预算，约束链
  Final ≤ Stock ≤ Portfolio ≤ Available Risk；行业/主题超限自动收缩
  可用新增风险；
  ㉒ **Effective Risk Exposure**（portfolio/exposure_engine.py）：
  名义暴露 → 相关性调整等效暴露（sqrt(w̄'Σw̄)）+ 主题等效暴露，
  识别"表面分散、实际同风险"；
  ㉓ **Capacity Cap Target**（execution/capacity.py）：Target →
  订单市值 → 单日容量/冲击容量 → 可成交仓位，超容量自动压缩；
  ㉔ **Execution Simulator gap 模型**（execution/simulator.py）：新增
  gap_bps（跳空成本）与 fill_price_basis（open/close 成交基准）；
  ㉕ **Cost Break-even Analysis**（backtest/cost_model.py）：
  成本乘数扫描 → Robust(<1.8×)/Acceptable(1.8–2.4×)/Broken(>2.4×)
  + break_even_factor，回答"成本变差后何时失效"；
  ㉖ **OOS Summary**（backtest/cross_validation.py）：跨 OOS 窗口汇总
  Return/Sharpe/MDD/Hit Rate/Turnover + 正窗口占比 + 一致性判断
  （优势是否跨时间持续）；
  ㉗ **Parameter Stability Surface**（backtest/robustness.py）：
  参数扫描 → 稳定区间/稳定性得分/STABLE vs PEAKY（尖峰=过拟合可疑），
  不再只报"最佳参数"；
  ㉘ **Ablation Matrix**（ablation/matrix.py）：Full/No Permission/
  No Wave/No FSM/No Risk/No Execution 统一矩阵 + Return Alpha/Risk
  Alpha/Loss Avoidance/Turnover/MFE Capture/Capital Efficiency +
  模块间增量重叠检查；
  ㉙ **Data Quality Gate 硬门禁**（data/quality.py + engine 接入）：
  11 项检查 → PASS/DEGRADED/BLOCK，BLOCK（可用日期/价格连续性/停牌/
  架构/数据源版本异常）→ DataQualityGateError 中止决策，默认开启；
  ㉚ **Production Drift Monitor**（monitoring/drift_monitor.py）：
  Data/Model/Trade/Risk 四类漂移累积评分 → Healthy→Warning→Degraded→
  Halted，Degraded→SAFE_MODE、Halted→HALTED，与 kill_switch 连接。

- **V54（2026-08-26）**：新 11–20 规格增量落地（V49 已实现基础模块，
  本版按"Wave 实战决策"规格补齐）——
  ⑪ **Unified Decision Object v2**（decision/object.py）：顶层暴露
  wave_stage / governed_target / evidence（input_fingerprint +
  data_snapshot_id + PIT/evidence 分级），消除消费者字段漂移；
  ⑫ **Wave Stage×Action 矩阵验证**（wave/stage_gate.py）：Discovery 禁建/
  禁加、Confirming TEST(≤50%)、Active 全允许、Mature 限建(≤50%)禁加、
  Exhausting 禁建禁加优先减、Invalid 全禁 EXIT——规格表测试落地；
  ⑬ **Wave Opportunity v2 验证**：aging.py 已实现 Remaining MFE
  （Expected−Realized），测试覆盖 MATURE 50% / LATE 禁满仓；
  ⑭ **Entry Quality v2**（decision/entry_quality.py）：新增时机分档
  timing_band（EARLY/OPTIMAL/ACCEPTABLE/LATE/INVALID）与第 8 因子
  趋势/动量（trend_score + momentum + pullback + wave_stage），
  与质量分 band（HIGH/MED/LOW）并存；
  ⑮ **Exit Quality v2**（decision/exit_quality.py）：九类退出新增
  WAVE（波段结束 EXHAUSTING/INVALID）与 LIQUIDITY（流动性恶化），
  优先级 HARD>GOVERNANCE>REGIME>LIQUIDITY>TIME>WAVE>SIGNAL>RISK>PROFIT；
  ⑯ **Time-in-Trade 验证**：V49 已实现 HOLD/REDUCE/EXIT 三档，测试覆盖
  超预期/超最大/无确认漂移；
  ⑰ **Progressive Sizing 验证**：V49 已实现 TEST→BUILD→CONFIRM→FULL
  递进 + add_requalification 四门重过，测试覆盖不越权限/风险/组合；
  ⑱ **Liquidity Exit v2**（execution/liquidity_exit.py）：新增
  liquidity_target_scale——OK×1.0 / FAIR×0.7 / LOW×0.4 /
  LOW+EXIT_REQUIRED×0.0，流动性恶化主动压缩 Target；
  ⑲ **Counterfactual Replay 验证**：决策级（counterfactual_replay.py）
  与组合级（portfolio_counterfactual.py）均已落地，测试覆盖
  Return/MDD/Loss Avoidance Alpha；
  ⑳ **Replay Certificate v2**（decision/replay_cert.py）：新增
  certify_and_safety——REPLAY_MISMATCH → replay_failure → HALTED
  （禁止新决策），VERIFIED 保持原安全状态。

- **V53（2026-08-26）**：收敛工程（新 1–10 系统宪法）落地——
  ① **Canonical Decision Path 唯一化**（scripts/canonical_audit.py）：
  验证 build_decision_snapshot / build_report_snapshot 与唯一引擎
  engine.evaluate 同源输出，审计脚本 6 项全过；
  ② **Permission Gate 前置不可绕过**（decision/permission_gate.py）：
  权限上限唯一出口（BLOCK→0 / TEST≤0.20 / ALLOW≤0.50 /
  STRONG_ALLOW≤0.70），assert_wave_cannot_upgrade 强制 Wave↑≠Permission↑；
  ③ **Governance Proof 硬门禁**：proof 只能由 prove() 计算
  （禁止调用方设置），违规 → GovernanceViolation 中止；
  build_certificate 的 governance_passed 改为从 proof 派生而非恒真；
  ④ **raw→governed→final 目标链**：GovernanceProof 新增 governed_target +
  portfolio/liquidity/execution/sector/theme/drawdown cap，
  finalize_target 按 min(raw, permission, risk, portfolio, liquidity,
  execution, sector, theme, drawdown) 收敛，全链入库；
  ⑤ **Ledger 唯一事实源**：写入前强制 FSM 权威校验
  （目标变化必须有合法状态依据，无法解释的仓位变化拒绝写入），
  保持 append-only 不可变；
  ⑥ **InformationSet(t) + Feature Contract 引擎门**
  （data/information_set.py + feature_contract.assert_decision_layer_features）：
  引擎默认禁止 future_return/future_peak/wave_label 穿透 +
  available_at > decision_time → PITViolation；
  ⑦ **Wave Stage Gate**（wave/stage_gate.py）：DISCOVERY/CONFIRMING/
  ACTIVE/MATURE/EXHAUSTING/INVALID 直接决定 entry/add/hold/reduce 与
  最大进场比例；
  ⑧ **FSM 唯一持仓状态解释器**（decision/fsm_authority.py）：
  目标增加仅限 TESTING/BUILDING、0 仓位仅限 FLAT/EXITING/COOLDOWN、
  正仓位必须处于风险承载状态，接入 record_snapshot 拒绝非法写入；
  ⑩ **P0 Governance Invariants**（test_convergence_invariants.py）：
  I1 BLOCK 不新增风险 / I2 final≤permission_cap / I3 final≤risk_cap /
  I4 exposure≤portfolio_limit / I5 hard_exit→0 / I10 Permission
  Monotonicity，共 14 项测试全绿。

- **V52（2026-08-26）**：41–50 优先修改项落地——
  ㊶ **Regime Transition Engine 强化**（market/transition.py）：转折概率/
  速度/持久性/早期预警 + 阈值调整（Risk Budget ↓ / Entry Threshold ↑ /
  Add Threshold ↑ / Exit Sensitivity ↑）；
  ㊷ **Opportunity Aging Engine**（wave/aging.py）：机会年龄 / 已实现 MFE /
  预期剩余 MFE / MFE Decay / 确认后时长，STRONG 波但已实现 ≥90% 预期
  → 禁止 Full Entry（EARLY→EXPANSION→MATURE→LATE→EXPIRED）；
  ㊸ **Dynamic Risk Budget**（decision/dynamic_risk_budget.py）：
  Base × Permission × Wave × Regime × Portfolio × 波动/流动性/相关性因子，
  动态只能降、不能突破 Governance Hard Cap；
  ㊹ **Drawdown Response Engine**（portfolio/drawdown_response.py）：
  0–3/3–5/5–8/8%+ → NORMAL/CAUTION/DEFENSIVE/SAFE_MODE，
  亏损越大新风险越小（新仓上限/加仓权限/风险预算/退出阈值/现金比联动）；
  ㊺ **Loss Cluster Detector**（failure/loss_cluster.py）：连续亏损 +
  滚动胜率/MFE/MAE/假进场率 + Regime，连续错误 → Strategy Confidence ↓ /
  Risk Budget ↓；
  ㊻ **Opportunity Competition Engine**（ranking/competition.py）：
  同主题/簇机会共享风险预算（A+B+C ≤ Theme Budget），单股上限为最终约束，
  防止"同时买入高度相关前三名"；
  ㊼ **Counterfactual Portfolio Engine**（ablation/portfolio_counterfactual.py
  + scripts/counterfactual_portfolio.py）：Actual vs No Permission/Wave/
  Risk/Portfolio 组合级对比（Return/MDD/Turnover/MFE/MAE/资本利用/Tail），
  突出 Risk Alpha / Loss Avoidance Alpha（实测 Permission MDD 改善 +8.39%）；
  ㊽ **Failure Taxonomy Engine 强化**（failure/failure_modes.py）：新增
  F13 Wrong Regime / F14 Oversizing / F15 Execution Failure，
  taxonomy_summary 输出频率/亏损贡献/Regime 分布/修正动作；
  ㊾ **Strategy Health Score**（monitoring/strategy_health.py）：Data/
  Permission/Wave/Execution/Risk/Drift/Ledger/Research 八维 →
  HEALTHY/DEGRADED/CRITICAL（赚钱不能掩盖系统失效）；
  ㊿ **Autonomous Research Guard**（governance/research_guard.py）：
  搜索会话记录 Search Space/Trials/Best/Selection Rule/Multiple Testing，
  晋升候选必须预注册 + 人工批准 + Ablation/OOS/统计全过，
  系统可自动研究但不能自动授予生产权限。

- **V51（2026-08-26）**：31–40 优先修改项落地——
  ㉛ **Data Lineage**（data/lineage.py + scripts/lineage_report.py）：
  Decision→Feature→Indicator→Transformation→Raw→Source→Available Time
  全链血缘，每节点记录 data_source_id/snapshot_id/available_at/
  transform_version/quality_status，lineage_hash 固化全链指纹；
  ㉜ **Feature Contract**（data/feature_contract.py）：特征契约
  （name/type/source/PIT_required/allowed_layer/missing_policy/range/
  version/validation_rule），future_return 等 Evaluation 特征进入
  Decision → FeatureGateError → Decision Abort；feature_gate 矩阵
  补齐 institutional_permission/c_state/f_state/p_state/q_position_52w/
  data_quality；
  ㉝ **Correlation & Exposure Engine**（portfolio/exposure_engine.py）：
  行业/Beta/主题/因子暴露 + 相关性簇 + 有效下注数 ENB，
  防止"看起来分散实际高度集中"；
  ㉞ **Risk Contagion Engine**（portfolio/risk_contagion.py）：Marginal/
  Component VaR、Conditional Loss(CVaR)、Cluster Stress、Liquidity
  Contagion，并输出 position_cap_scale 接入 Governance
  （可用风险预算 → 仓位上限缩放）；
  ㉟ **Strategy Capacity Engine**（execution/capacity.py）：
  Capacity @ 1%/3%/5%/10% ADV + 换手折算，Efficient/Acceptable/
  Capacity Degraded 三档；
  ㊱ **Strategy Version Registry 强化**（governance/lifecycle.py）：
  StrategyVersion 绑定 strategy_id/engine_version/commit_hash/
  config_hash/data_snapshot_id/release_status，
  bind_decision 登记每次 Production 决策的版本绑定；
  ㊲ **Version Impact Analysis**（governance/version_impact.py +
  scripts/version_impact_report.py）：同批数据旧/新版本对比
  （Permission/Wave/FSM/Position/Exit/P&L/Risk）+ Decision Flip Rate，
  实测 01951 两 run 翻转率 0.05%；
  ㊳ **Decision Explainability Graph 强化**（explainability/graph.py）：
  每条边补 threshold + version，回答"为什么不是 8% 而是 4%"；
  ㊴ **Research Experiment Registry**（ablation/statistical.py +
  scripts/research_registry_report.py）：完整登记 Hypothesis/Baseline/
  Treatment/Dataset/PIT Grade/OOS Window/Statistical Test/Selection Rule，
  未注册实验 → assert_registered 禁止作为正式结论；
  ㊵ **Production Quality Gate 强化**（scripts/release_gate.py）：
  原 12 门追加 Stress/Execution/Statistical/Capacity/Decision
  Consistency/Ledger Integrity 六门共 18 门；
  实测 Ledger Integrity 如实暴露历史台账缺 data_snapshot_id（20092/82192），
  体现"未验证不上线"。

- **V50（2026-08-26）**：21–30 优先修改项落地——
  ㉑ **Portfolio Lifecycle Gate**（portfolio/lifecycle_gate.py）：组合状态
  作用于持仓全生命周期（ENTRY/ADD/HOLD/REDUCE/EXIT 动作门 + EntryCap 缩放 +
  分散化 ADD 检查），不再只限新仓；与 V47 的 state_engine / V48 的
  finalize_target 组合门构成完整组合治理链；
  ㉒ **Opportunity Ranking 九维排序**（ranking/opportunity_ranking.py）：
  补全"预期持有期 + 资本效率"维度；BLOCK + Rank#1 仍不可交易（tradable
  标志强制，Ranking 不越权）；
  ㉓ **Opportunity Replacement 阶段感知**（replacement/replacement_engine.py）：
  换仓判定引入 Wave 生命周期调整（旧仓 MATURE/EXHAUSTING ×0.92 倾向换、
  ACTIVE ×1.05 倾向留；新仓 DISCOVERY/CONFIRMING ×0.95 保守），
  仍要求 New Utility > Existing Utility + Switching Cost；
  ㉔ **分层校准**（monitoring/forecast_realized.py）：按 Permission / Regime /
  Wave Stage / Trade Quality 四维分层统计 MFE/MAE/持有期误差，
  定位"哪个环境下系统性高估波段空间"；
  ㉕ **Controlled Learning Loop 验证**（learning/controlled_loop.py 已 V46
  落地，本版补测试）：生产只写 Evidence、研究只读并建 Candidate，
  七道门全过才晋升 Production；
  ㉖ **Stress Engine 流动性冲击**（stress/engine.py）：新增 ADV -30%/-50% ×
  Spread ×2/×5 流动性冲击情景 + Tail Loss(VaR95) / Risk Budget Breach /
  Forced Exit / Liquidity Risk / survivable 全量输出；
  ㉗ **Execution Simulator 全流水线**（execution/simulator.py）：新增
  simulate_execution（T+1/价差/滑点/部分成交/分批成交/流动性不足/涨跌停/
  停牌/市场冲击/退出延迟）+ return_decomposition
  （Signal→Gross→Execution→Net 四层收益分解）；
  ㉘ **P&L Attribution**（performance/attribution.py +
  scripts/attribution_report.py）：总收益拆解为 Market Beta / Wave /
  Entry Timing / Sizing / Exit Timing / Regime / Sector / Risk Avoidance /
  Execution Cost / Slippage / Alpha，并归入 Beta/Wave/Timing/Sizing/
  Risk_Avoidance/Execution/Alpha 七桶；
  ㉙ **Statistical Validation Layer**（ablation/statistical.py）：
  Bootstrap CI + Permutation p-value + Effect Size + 子区间/Regime 分层 +
  Experiment Registry（实验次数→α_eff 收紧 + 多重检验挑选风险告警）；
  ㉚ **Continuous Validation + Safety State**（safety/continuous_validation.py +
  scripts/continuous_validation_report.py）：数据/模型/权限/波段/执行/流动性/
  MFE-MAE/假进场/治理/台账/回放/风险 12 类监控聚合为 NORMAL→WARNING→
  SAFE_MODE→HALTED，governance_failure→SAFE_MODE、ledger/replay→HALTED
  已并入 kill_switch 系统级映射。

- **V49（2026-08-26）**：11–20 优先修改项落地——
  ⑪ **Unified Decision Object**（decision/object.py）：不可变统一决策对象
  （snapshot+wave+entry/exit quality+time_in_trade+constraints+confidence+
  version_hash），Live/Backtest/Replay/Shadow/Report/Audit 消费同一对象；
  `validate_unified_decision` 校验 version_hash 与消费者契约；
  ⑫ **Wave Opportunity 强化**（wave/opportunity.py）：wave_type/stage/
  strength/direction/expected_duration/expected_mfe/expected_mae/
  invalidation/entry_zone/confirmation/expiry 完整波段画像；
  ⑬ **Wave Lifecycle**（wave/lifecycle.py）：DISCOVERY→CONFIRMING→ACTIVE→
  MATURE→EXHAUSTING→INVALID 六阶段，记录起点/年龄/最大时长/失效条件/衰减；
  ⑭ **Entry Quality Engine**（decision/entry_quality.py + action_gate 接入）：
  价格位置/确认/量能/波动/失效距离/预期MFE/执行成本 七因子 →
  HIGH/MED/LOW；STRONG Wave + LOW Entry → WAIT（DecisionConfig
  use_entry_quality 开关，默认关闭保证 2.7 行为不变）；
  ⑮ **Exit Quality Engine**（decision/exit_quality.py）：PROFIT/RISK/SIGNAL/
  TIME/REGIME/GOVERNANCE/HARD 七类退出 + 原因 + REDUCE/EXIT 建议，
  已作为 quality 诊断写入 DecisionSnapshot.context；
  ⑯ **Time-in-Trade Governance**（decision/time_in_trade.py）：预期/最大
  持有期 + 最后确认日 → HOLD/REDUCE/EXIT 三档建议（诊断输出）；
  ⑰ **Progressive Position Sizing**（retail_position_sizing.py）：
  TEST→BUILD→CONFIRM→FULL 四级递进（2%→5%→8%→12%），加仓必须重过
  Permission+Wave+Risk+Portfolio 四门（add_requalification）；
  ⑱ **Liquidity-aware Exit**（execution/liquidity_exit.py +
  scripts/liquidity_exit_report.py）：退出天数/参与率/冲击/滑点/压力成本 →
  LIQUIDITY_LOW + EXIT_REQUIRED → DELEVERAGE_PLAN（分批退出计划）；
  ⑲ **Counterfactual Decision Replay**（scripts/counterfactual_replay.py）：
  同一次决策逐模块关闭（Permission/Wave/Risk/Portfolio/Daily/HardExit）
  对比 Actual vs Counterfactual，输出 JSON+MD；
  ⑳ **Replay Certification**（decision/replay_cert.py +
  scripts/replay_certify.py）：input→decision→certificate→ledger 指纹链，
  决策核心字段统一投影（跨快照/证书/台账可比），Live==Replay==Backtest==
  Ledger 否则 REPLAY_MISMATCH；输入/设置漂移作为独立诊断（不影响决策指纹）。

- **V48（2026-08-26）**：1–10 优先修改项落地——
  P0-1 **Canonical 唯一化**：backtest 默认引擎切换为 canonical（legacy 仅作
  Shadow Comparator，显式选择并警告）；
  P0-2 **Governance Hard Boundary**：唯一最终仓位产生点
  `governance.finalize_target()`（Risk Target → Permission Cap → Portfolio
  Gate → Data Quality → Regime → Proof），引擎全部改经它；其余模块只产生
  Proposal；
  P0-3 **Hard Exit 语义统一**：ExitEvent 拆分 is_exit/is_forced/is_hard
  （BREAKDOWN 软退出 / STOP·FORCED 强制但非致命 / HARD_EXIT 致命）；
  P0-4 **Portfolio Gate 接入最终决策**：RISK_OFF/OVERHEATED 禁新增、
  既有仓位压至 previous、DEFENSIVE/CONCENTRATED 降 Entry Cap；
  P0-5 **PIT 分级限制**：PIT-A/B 才可正式研究，PIT-C 仅探索（run_status/
  release_gate 硬门，已如实标注）；
  P1-6 **Validation 结果化**：04 交易成本改为读取实际 cost_metrics
  （年化成本/成本换手比），05 流动性改为结果检查，不再是"存在即 PASS"；
  P1-7 **Ablation 统计增量**：permutation_ablation 输出 Δmean / Bootstrap CI
  (2.5–97.5%) / Effect Size；
  P1-8 **OOS 校准**：calibration_table（TQ 分档 → 实际 MFE/MAE/持有期
  median/P75），从"预期代理"升级为实证分布；
  P1-9 **风险预算分配**：risk_budget_target = min(risk_budget/stop,
  permission/portfolio/liquidity cap)，finalize_target 接入；
  P1-10 **Ledger-first**：I10 测试验证 Report final == Ledger final_target；
  新增 I01–I10 命名验收测试（含 I04 Daily STRONG+BLOCK→0、I05 Wave STRONG+
  WATCH 禁 ADD、I09 invalidated 必带 superseded_by）。

- **V47（2026-08-26）**：㉖–㉚ 五项落地——
  ㉖ **Portfolio State Engine**（portfolio/state_engine.py +
  scripts/portfolio_state_report.py）：NORMAL/DEFENSIVE/RISK_OFF/
  CONCENTRATED/OVERHEATED/RECOVERY 六态 + 状态反向约束
  （RISK_OFF 禁 ADD、降 Entry Cap、优先 REDUCE）；
  ㉗ **Stress Scenario Engine**（stress/engine.py + scripts/stress_report.py）：
  市场冲击 −5..−20% / 波动 ×1.5–3 / 流动性成本×2–5 / 相关性 0.3→0.9；
  实测 B7：vol×3 → MDD −64.6% 且无恢复——如实揭示脆弱点；
  ㉘ **Causal / Incremental Evidence**（ablation/incremental.py +
  scripts/incremental_evidence_report.py）：模块价值判定
  risk_reduction / alpha / mixed / neutral（实测 fsm/soft/hard_exit=mixed、
  daily/budget/observation=neutral）；
  ㉙ **Decision Explainability Graph**（explainability/graph.py）：
  Feature→Institutional→Permission→Setup→Risk→FSM→Sizing→Final
  有向解释图，每条边带 rule/input/output/reason（"为什么不是 10% 而是 6%"），
  已接入决策报告；
  ㉚ **Safety Kill-Switch**（safety/kill_switch.py + scripts/safety_report.py）：
  NORMAL/WARNING/SAFE_MODE/HALTED 四态；ledger/replay 失败→HALTED，
  data/PIT/drift/execution→SAFE_MODE（禁新增风险、允许减仓），
  不可被 Wave/Permission/Strategy Override。

- **V46（2026-08-26）**：㉑–㉕ 五项落地——
  ㉑ **Regime Transition Detector**（market/transition.py +
  scripts/regime_transition_report.py）：转折检测（from/to/日期/置信度）
  + 转折期风险调整（Bull→Bear ×0.5、Trend→Sideway ×0.7 等），
  在状态切换阶段主动降低脆弱性；
  ㉒ **Cross-Section Ranking**（ranking/opportunity_ranking.py +
  scripts/opportunity_ranking_report.py）：机构/波强/进场/风险收益/流动性/
  MFE/MAE/权限稳定复合分 + Top-N；**BLOCK+Rank#1 仍不可交易**（不越权）；
  ㉓ **Opportunity Replacement Engine**（replacement/replacement_engine.py）：
  Replacement Utility = 新机会效用 > 旧仓效用 + 换仓成本才换仓；
  ㉔ **Forecast-to-Realized Monitor**（monitoring/forecast_realized.py +
  scripts/forecast_realized_report.py）：预期 vs 实际 MFE/MAE/持有期 →
  系统性偏差/校准误差（实测 01951：MFE 系统性高估 5.7pp、MAE 低估 4.0pp）；
  ㉕ **Controlled Learning Loop**（learning/controlled_loop.py）：
  Research Sandbox（生产只写证据/研究只读+建候选）+ LearningProposal
  晋升门（Ablation/OOS/Replay/Stability/CostStress/Shadow/审批），
  杜绝"结果→自动改模型"的过拟合与数据污染。

- **V45（2026-08-26）**：⑯–⑳ 五项落地——
  ⑯ **Decision Stability**（decision/stability.py + scripts/stability_report.py）：
  扰动价格/特征/数据质量/参数 → Permission/FSM/Exit 翻转率 + Position
  Sensitivity + Stability Score。实测 01951：Stability 84.4（FSM/Exit 稳定，
  Permission 对数据质量扰动敏感，PosSens=0）；
  ⑰ **Transaction Cost Sensitivity**：执行情景扩展 C0（低成本）–C3（极端），
  execution_ablation 输出净 Alpha 存活率（净收益/低成本净收益）；
  ⑱ **Capacity / Market Impact**（execution/capacity.py + scripts/capacity_report.py）：
  平方根冲击模型 + 参与率 + 退出压力天数 + 流动性调整风险。实测 01951
  （500 万、ADV≈2770 万）：2% 参与率 → 冲击 0.60%、退出 10 天（SLOW_EXIT）；
  10% → 冲击 1.34%（HIGH_IMPACT）；
  ⑲ **FSM 状态转移概率矩阵**（fsm/transition_matrix.py +
  scripts/fsm_transition_report.py）：整体 + 按权限分组矩阵 + 期望状态价值
  （实测 01951：EXITING −0.20、TESTING +0.12）；
  ⑳ **Strategy Lifecycle**（governance/lifecycle.py + qcfp_strategy_lifecycle 表
  + scripts/strategy_lifecycle.py）：Development→…→Production→Retired，
  生产变更门（Candidate→Ablation→OOS→Shadow→Approval），禁止回退/直接改参。

- **V44（2026-08-26）**：⑪–⑮ 五项落地——
  ⑪ **Decision Confidence / Evidence Score**（decision/confidence.py）：
  机构/波段/风险/数据/PIT 五维 → Confidence（0-100），不突破 Permission、
  不直接决定仓位，只影响等待/加仓节奏展示；证书携带 action + confidence_score；
  ⑫ **Entry/Add/Reduce/Exit 四级动作模型**（decision/action_gate.py）：
  每个动作经 Permission+Wave+FSM+Risk+Budget 五门（TEST+STRONG→ENTRY 小仓、
  ALLOW+BUILD→ADD、WATCH→禁止 ADD、HardExit→EXIT）；
  ⑬ **Re-entry/Cooldown 治理**（governance/reentry.py）：ReentryState
  （last_exit/exit_reason/cooldown/reentry_trigger/wave_id）+ reentry_allowed
  （冷却结束+机构/Setup/Risk 再确认）；
  ⑭ **Benchmark 基准体系**（backtest/benchmarks.py + scripts/benchmark_report.py）：
  B0 Buy&Hold / B1 Index / B2 Trend / B3 Breakout / B4 Wave / B5 Permission /
  B6 Permission+Wave / B7 Full + 风险调整增量效用。实测 01951：
  B7 年化 +0.1%、MDD −0.06%、Sharpe 0.53，相对 B0 增量效用 +0.172
  （系统价值=风险收敛，而非收益最大化）；
  ⑮ **失败模式数据库**（failure/failure_modes.py + scripts/failure_report.py）：
  F01–F12 自动归类 + 按 Regime/Module 聚合；实测 01951：
  F06 58 / F02 17 / F07 7 / F05 8 / F01 10——形成"交易→失败分析→Ablation→
  优化→再验证"闭环。

- **V43（2026-08-26）**：P3 五项落地——
  ⑥ **Regime-aware 参数**（market/regime.py）：Bull/Bear/Sideway/HighVolatility/
  Crisis 五态分类（指数趋势+波动率+回撤，as-of），regime_params 按环境缩放
  风险上限与 TQS（Bull +4 / Crisis −6），`DecisionConfig.use_regime_params` 可消融；
  ⑦ **信号冲突解决器**（governance/conflict.py）：固定优先级 Hard Exit > Risk
  Block > Institutional Permission > FSM > Wave > Setup > Technical Trigger，
  每次决策输出 conflict_id / winning_rule / suppressed / reason，写入快照；
  ⑧ **组合级治理**（portfolio_constraints.apply_portfolio_governance）：单股/
  行业/总暴露 + 现金储备(≥10%) + 总风险预算(Σ仓位×止损≤6%) + 高相关组合上限(≤30%)，
  backtest_runner --constraints 启用；
  ⑨ **多维度漂移监控**（shadow/drift.drift_report）：permission/setup/FSM 转移
  分布 + Wave/MAE/持有期标量，1 项→WARNING、≥2 项→RESEARCH_REVIEW；
  shadow_live 实测 01951：NORMAL（drifted=[]）；
  ⑩ **复杂度预算**（governance/complexity_budget.py + scripts/complexity_report.py）：
  基于边际效用矩阵判定 KEEP/REVIEW/DROP，实测评分 1.0（全部 KEEP）。

- **V42（2026-08-26）**：5 项最高优先级修改落地——
  ① **Permission Authority 化**：两阶段决策（Permission Gate → Opportunity），
  "Strong Wave + BLOCK = NO TRADE" 最高级不变量 + 随机化 1000 组 Hard Exit 测试；
  ② **Governance Proof 化**（decision/governance_proof.py）：前置证明
  （permission/raw/permission_cap/risk_cap/budget_cap/final/violations/proof），
  proof≠PASS 不得输出 Decision（不可越权而非事后发现）；
  **数据质量即约束**：A 1.0 / B 0.8 / C 0.5 / D→BLOCK；
  ③ **PIT+Universe+Data Snapshot 完整化**：审计身份升级为**九元组**
  （+data_snapshot_id+data_version），Ledger 每行记录数据快照指纹
  （实测 10046 行 data_snapshot_id=988f7122…）；
  ④ **Wave Opportunity Object**（wave/opportunity.py）：WaveOpportunity
  （wave_id/start/trigger/peak/permission_at_start/capture_by_model）+
  OQS（机会质量评分）+ 等待价值；**反事实分析**
  （scripts/counterfactual_report.py，实测 01951 错失 64 波：RISK 54 /
  PERMISSION_WATCH 10）；
  ⑤ **Ablation 边际效用**（ablation/marginal.py：Return/MDD/Capture/Turnover
  四维矩阵 + Alpha/Governance 分类）+ **Permutation Ablation**
  （override_permission 打乱权限）+ **Time-shift 泄漏检测**。

- **V41（2026-08-26）**：双层层级制度化（本轮审查增量）——
  ① **Feature Permission Matrix**（governance/feature_gate.py）：WaveLabel /
  future_peak / future_return 仅 Evaluation；WaveSignal（as-of）才可进
  Decision；违规即 FeatureGateError；wave/label.py 与 wave/signal.py 类型隔离；
  ② **越权矩阵函数** governance_matrix_ok（BLOCK→0 / WATCH≤Observe /
  TEST≤Explore / ALLOW≤Trade / STRONG≤Strong）+ Risk 单调不变量测试
  （Risk↑ → target 不↑）；
  ③ **Trade Ledger**（backtest/trade_ledger.py + scripts/retail_swing_report.py）：
  逐笔波段交易（entry/exit/加减仓/MFE/MAE/持有周/后验归因），实测 01951
  27 笔交易、胜率 22%、whipsaw 77.8%、错失波段机会成本 +64.8%；
  ④ **IFV（Institutional Filter Value）**：用 ΔMDD+ΔMAE+ΔFalseEntry−λΔMissed
  衡量机构过滤价值，加入 Ablation 贡献；
  ⑤ **Governance Certificate 升级**：authority_chain / constraint_chain /
  information_asof / data_quality_gate / pit_gate / ablation_mode /
  execution_assumption，证书哈希覆盖全字段；
  ⑥ 决策报告新增**牛散交易四问**（能不能做/为什么现在/最多做多少/错了怎么办）。

- **V40（2026-08-26）**：最终审查优化落地——
  ① **Decision Certificate 完整化**：constraint_trace（raw/permission_cap/
  hard_exit/final）+ decision_graph + reason_codes，证书哈希覆盖全部字段；
  ② **G1–G8 命名测试**（HardExit→0 / BLOCK→0（新仓）/ WATCH 非 OBSERVE≤prev /
  OBSERVE≤cap / Target≤Envelope / Daily 不升级 / Risk 只降风险 / Final 必经
  Governance）；并修正 I2 语义：BLOCK 允许既有仓位逐步去风险（与 G-008 一致）；
  ③ **全出口静态审查**：Final Target 唯一产生于 decision/engine.py
  （Governance 出口）；backtest.position_target / downside_risk 仅属 Legacy 路径；
  ④ **Institutional State Validation**（scripts/state_validation.py）：
  Forward 1/4/8/12W + MFE/MAE/胜率 per state——实测表明状态预测价值有限
  （ACCUMULATION 4W −1.9%、CAPITULATION −3.5%），名字≠预测力，如实记录；
  ⑤ **零售交易质量指标**：false_exit_rate + whipsaw_rate
  （00371 实测 whipsaw 29.3%）；Ablation 模型按 alpha_legacy/retail_fsm/
  governance 四组标注；PIT Evidence 增加 restatement 字段；
  ⑥ **报告**：Governance 卡增加 Permission Upgrade=NO、三类结论分层
  （Engineering/Research/Trading）、第一屏 Raw Target；
  ⑦ **Release Gate 5 大验收评分**：实测 governance 100 / audit 100 /
  backtest_integrity 66.7（PIT-C）/ ablation 100 / retail 100，整体 CONDITIONAL。

- **V39（2026-08-26）**：执行 QCFP-MTF 2.6 计划（Sprint 1–7 + Release Gate）——
  ① **Governance Contract**：PermissionLevel 偏序 + `can_add_risk` +
  **G-001..G-010 命名验收测试**（tests/test_governance_contract.py）；
  ② **Decision Certificate**（decision/decision_certificate.py）：快照 → 可审计
  证书（reason_codes/governance_passed/certificate_hash），序列化→加载→重放
  哈希一致；
  ③ **Deterministic Replay**：同输入→同证书哈希（测试覆盖）；
  ④ **Execution Simulator**（execution/simulator.py）：BASE/STRESS/EXTREME
  三情景（滑点×1/3/6、成交率 100%/80%/50%、参与率 10%/5%/2%）+ ADV 流动性
  与部分成交模型，execution_ablation 接入三情景；
  ⑤ **PIT 硬门**：Evidence 每层记录 source/revision，`PIT_ERROR` 别名，
  available_at > decision_time 直接阻止；
  ⑥ **Retail Gates**：ADD_RISK_GATE（6 条件）与 RE-ENTRY_GATE（再入场防护）
  + MFE/MAE 中位数；
  ⑦ **Live Shadow + Drift**（scripts/shadow_live.py + shadow/drift.py）：
  今日决策/证书/模拟成交（不下单）+ REGIME_DRIFT 漂移监控
  （实测 01951：NORMAL，worst=0.0003）；
  ⑧ **Release Gate**（scripts/release_gate.py）：12 门验收——实测
  **CONDITIONAL（10/12 PASS）**：Governance/Audit/Shadow/Replay/FSM/OOS/
  Ablation/Report PASS；PIT-C 与 Research 两项 WARN（需真实披露日 + PIT
  Universe 才能 RELEASE）；
  ⑨ 决策报告新增**第一屏交易者答案**（Institutional/Permission/Setup/Risk/
  FSM/Position/Target/ACTION + Why 列表）。

- **V38（2026-08-26）**：Governance Hardening 收口（审查 6 个 P0 + 4 个 P1）——
  ① **Decision Path 补全**：evidence → institutional → exit_events → setup →
  participation_budget → fsm → sizing → permission_cap → trade_quality →
  governance → final_target，context 记录逐步 trace；
  ② **证据分级入链**：evidence/snapshot.grade_evidence（PIT-A/B/C/D +
  Evidence 由数据质量映射），DecisionSnapshot/Ledger 直接保存，删除
  pit_grade="C"/evidence_grade="D" 硬编码（Shadow/Backtest 同步）；
  ③ **canonical 唯一化**：canonical_replay 一次 Evaluate → 快照列表 →
  Ledger（禁止二次 Evaluate）；run_id 尊重用户传入；cross_sectional_backtest
  支持 --engine canonical；
  ④ **Wave 口径修复**：daily_alpha_test realized 统一 26 周 horizon；
  wave_capture 缺失收益标记 DATA_INCOMPLETE（NO_DATA≠0）；
  false_participation 排除 NaN；
  ⑤ **版本统一**：全部 2.1.1 残留清理（__init__/各引擎/DSS），唯一来源
  decision.versions；
  ⑥ **Model Registry**（qcfp_model_registry）：settings_hash →
  settings_blob（含 code_commit/python/dependency_hash），Ledger 写入自动注册；
  ⑦ **Ablation 机制报告**：每模型输出 permission/transition/exit 分布、
  target 阳性率（A8 实测：WATCH 9640/BLOCK 258，阳性率 0.55%，
  FORCED_DELEVERAGE 5271——机制层面证明“风险闸门”主导）；
  ⑧ **牛散效用扩展**：Risk Budget Efficiency、Opportunity Cost（被过滤波段
  平均少赚）、Time-in-Position，Wave 报告改为 Wave/Risk/Capital 三维仪表盘。

- **V37（2026-08-25）**：P2 治理收口——
  ① **Legacy→New 验收替换**（scripts/legacy_replace_check.py）：Consistency/
  OOS/Ablation/Governance 四关，通过后才允许切换
  `backtest.engine_source=canonical`（01951 实测 PASS：New 年化 +0.02%、
  MDD −0.02%、OOS Sharpe 中位数 0.45）；
  ② **报告三拆分**：Decision Report（scripts/decision_report.py 一屏决策）、
  Audit Report（scripts/audit_report.py 七元审计身份+证据链）、
  All-in-One 保留为 Research Report；
  ③ **Research Gate G0–G7**（backtest/research_gate.py）：Governance /
  PIT / Signal / Statistical / OOS / Economic / Execution / Decision 八道
  分层门，接入回测汇总与 Run Status 输出；
  ④ **PIT 真实披露表**：structural_engine 接入
  Config/qcfp_disclosure_dates.csv（真实披露日覆盖 period_end+45d，
  disclosure_mode=REAL→PIT-A），提供模板文件与单元测试。

- **V36（2026-08-25）**：采纳剩余四项——
  ① **细粒度 Governance Ablation**：DecisionConfig 新增 `use_stop` /
  `use_observation` 独立开关，Ablation 扩展 A12（Full−Stop）与
  A13（Full−Observation），输出 stop/observation 的单模块贡献；
  ② **Execution Ablation**（scripts/execution_ablation.py）：成本
  1.0×/1.5×/2×/3× 多倍压力网格 + T+1 无偏验证 + 盈亏平衡档位；
  ③ **Permission × Opportunity 二维矩阵**：Opportunity 由 Setup+TQS 派生
  （Low/Mid/High），散户卡展示 5×3 矩阵并高亮当前格
  （BLOCK — / WATCH OBS / TEST TEST+ / ALLOW TRADE / STRONG_ALLOW A+），
  DSS JSON 输出 opportunity_level/cell；
  ④ **组合层暴露约束**（backtest/portfolio_constraints.py +
  backtest_runner --constraints）：单股≤30%、行业≤50%、总暴露≤100%，
  在 target 层生效（T+1 前），杜绝 10 股×30%=300% 毛暴露。

- **V35（2026-08-25）**：2.5 Governance Hardening——
  ① 三维版本身份（`decision/versions.py`）：MODEL=QCFP-MTF-2.5.0 /
  RULE=GOV-2.5.0 / SCHEMA=DECISION-1.1 + FEATURE_SET manifest +
  feature_manifest_hash，Settings/YAML/par 统一升级；
  ② 统一仓位治理器 `decision/governance.py::assert_position_governance`：
  FinalTarget ≤ ParticipationCap ≤ 权限风险包络，HardExit→0、BLOCK→0、
  WATCH(非观察)≤previous；新增 property-based **治理不变量矩阵**
  （5 权限×5 Setup×4 风险×5 仓位×2 日线 = 1000 组合）；
  ③ Ledger 唯一事实源强化：`load_canonical_decision()`（正式模式 Ledger ONLY，
  fallback 显式标记 NON_CANONICAL），报告/散户卡/DSS JSON 全部切换；
  ④ 回测同源：`backtest_runner.py --engine canonical` 由唯一引擎有状态重放
  产生 target（`backtest/canonical.py`），回测与 Live/Shadow 同一引擎；
  ⑤ **Market Context 真正启用**：参与预算按 risk_on/neutral/risk_off 缩放
  （保留市场环境），Ablation 新增 A11（Full−Market Scale）；
  ⑥ **Trade Quality Score**（`decision/trade_quality.py`）：允许交易≠值得交易，
  TQS<min_tradable 时压仓为 0（reason=TRADE_QUALITY_LOW），不改变权限；
  ⑦ **牛散效用指标**（`backtest/retail_utility.py`）：Wave Capture/MAE/MFE/
  机会错失/错误参与/资金效率 + Retail Utility Score 评价函数；
  ⑧ 报告顶部新增 **Governance Decision Card**（一屏决策+治理核验）；
  ⑨ 修复配置接线 bug：retail 配置实际位于 decision.retail，
  7 处消费点统一走 `retail_settings()`（此前全部静默用默认值）。

- **V34（2026-08-25）**：四层架构（Institutional Permission → **Participation
  Budget** → Swing FSM → Position Sizing）落地——
  ① 新增 `decision/participation_budget.py`：权限回答"最多承担多少风险"，
  预算回答"当前允许拿多少钱参与探索"（STAND/OBSERVE/EXPLORE/TRADE）；
  ② **Exploratory Exposure / Observation Position**：WATCH + Setup + 低/中风险
  允许进入观察仓（上限 5%，rule_id=`participation_observe`，矩阵基准仍为 FLAT），
  解决"WATCH 一律空仓 → 2024 大波段 100% 错过"的矛盾；
  ③ **Exit Severity 三级**：L1 纪律性（RISK_EXIT/BREAKDOWN）/
  L2 风险性（STOP/FORCED_DELEVERAGE）/ L3 致命（HARD_EXIT）；
  ④ **趋势存活权**：HOLDING 持仓在回测止损中使用更宽存活缓冲（默认 5%）；
  ⑤ Ablation 新增 A10（Full−Participation Budget），实测四层中间层的贡献：
  A8 错失率 −57.6pp（100%→42.4%）、A5 捕获比 0.01%→3.84% 且 MDD −9.45%→−3.02%；
  ⑥ DecisionSnapshot/Ledger/报告新增 participation_mode/cap、position_class、
  exit_severity 字段。

- **V33（2026-08-25）**：2.3 Governance 收口——
  ① **唯一决策引擎** `decision/engine.py::evaluate(evidence, prev_state,
  prev_position, settings, config)`：Evidence(PIT) → Institutional → Exit →
  Setup → FSM → Sizing → Cap → DecisionSnapshot；Shadow / Ablation /
  Report 全部调用它，禁止模块自行拼接 FSM+Permission+Sizing；
  `DecisionConfig`（use_permission/use_soft_exit/use_hard_exit/use_daily）
  支持 Ablation 单模块开关；
  ② **Ledger 不可变化**：`record_snapshot` 只追加（INSERT OR IGNORE），
  审计身份升级为七元组（decision_id+run_id+input_fingerprint+settings_hash+
  model_version+rule_version+schema_version）；发现错误用
  `invalidate_snapshot` 标记 INVALIDATED + superseded_by，绝不覆盖历史；
  ③ **正式模式门禁**：research_validation / production / audit 下
  `build_report_snapshot` 无 Ledger 匹配即抛 `LedgerRequiredError`，
  FLAT/0 单点推算仅限 research_exploration；
  ④ **DecisionEvidenceSnapshot**（evidence/snapshot.py）：Q/M/W/D/Flow/
  Universe 统一 as-of + `assert_evidence_asof` PIT Evidence Contract，
  任何输入 available_at > decision_time 直接拒绝进入引擎；
  ⑤ **Wave Capture 评价**（backtest/wave_capture.py +
  scripts/wave_capture_report.py）：波段捕获率 / 进入延迟 / MFE / MAE /
  峰值捕获 / 错失率 / 错误试仓率；
  ⑥ Ablation 扩展为正交 A0–A9（A9=Full−Daily），输出单模块效应与
  Perm×SoftExit、Perm×HardExit 交互项。

- **V32（2026-08-25）**：2.3 Decision Governance 预览——
  ① 新增决策台账 `qcfp_decision_ledger`（唯一决策事实源）：Shadow 写入、
  报告/审计只读 Ledger（`decision_ledger.py`，审计身份五元组
  decision_id+run_id+settings_hash+model_version+rule_version 严格匹配）；
  ② `build_report_snapshot` 改为 Ledger First（→ Shadow 文件严格版本匹配
  → FLAT/0 单点推算并明确标注"非正式决策"）；
  ③ DecisionSnapshot 新增 `primary_reason / secondary_reasons / run_id`
  决策原因码（PERMISSION_BLOCK / HARD_EXIT / SETUP_ABSENT / POSITION_CAP 等）；
  ④ 报告层新增"仓位动作"（NO_RISK_INCREASE）与"决策原因"展示，
  消除 WATCH+BUILDING 的语义误读；
  ⑤ 新增 `assert_all_inputs_asof` Evidence Timeline Contract
  （所有输入 usable_at ≤ decision_time）并接入回测前置断言；
  PIT Universe 记录不完整（valid_from/valid_to 缺失）→ 严格模式 PIT_INVALID，
  不再退化为 valid forever；
  ⑥ Ablation 升级为正交 A0–A8（每次只改一个模块），输出单模块效应
  （Permission=A5−A2、FSM=A2−A0、SoftExit=A3−A2、HardExit=A4−A2）与
  Interaction(Perm,FSM)=A5−A1−A2+A0；
  ⑦ 新增 2.3 硬不变量测试模块（10 条契约：不越权/零仓位状态/
  HardExit 归零/PIT 无效即不可研究/报告==Snapshot/台账回环与重放确定性）。

- **V31（2026-08-25）**：Canonical Contract 收口——
  ① Permission×FSM 矩阵扩展至 7 状态并真正驱动 `transition()`（`permission_fsm_base`
  为基准 + 覆盖，`transition_audit` 返回 rule_ids）；
  ② 权限语义改为“风险增量上限”（new_risk/maintain/de_risk Policy），消除
  WATCH×BUILDING“矩阵合法但 Cap 越权”矛盾，审计改为 target 增量 + 状态-仓位一致性；
  ③ 新增 `state_position_consistent`，修复 TRIMMING→0 仓位死锁（→EXITING→COOLDOWN→FLAT）；
  ④ 报告层零重算：散户卡 / All-in-One / DSS JSON（decision_2_2）全部只读
  DecisionSnapshot（`action_from_snapshot` / `snapshot_light`）；
  ⑤ Shadow 补齐 `prev_f_state` 等 Canonical Input，输出 input_contract + schema_version；
  ⑥ Ablation A3=Soft Exit、A4=+Hard Exit，A1 与 A3/A4 共用同一 Permission Policy，
  记录实验模块与输入/设置哈希；
  ⑦ DecisionSnapshot 审计字段增强（base/raw target/constraint/rule_ids/fingerprint/
  settings_hash/机构理由/context），版本常量 MODEL/RULE/SCHEMA 三分离。

- **V30（2026-08-25）**：决策内核收敛——Exit Event 成为 FSM 唯一退出输入（新增软退出
  `RISK_EXIT`/`BREAKDOWN`，`ExitEvent.hard` 只含硬事件）；FSM 改为
  `TransitionInput` 单点消费（Snapshot/FSM 不再重复计算 Exit/Setup）；
  Permission 明确为“风险增量上限”（BLOCK/WATCH 下 target≤previous，`assert_no_risk_increase`）；
  Ablation A2 默认 STRONG_ALLOW、A3 传 `ExitEvent(NONE)` 实现真正隔离；
  报告层（DSS 散户卡 / All-in-One 审计）统一读取 `build_report_snapshot`（优先 Stateful Shadow），
  报告不再自行决策；Legacy 仓位建议在报告中标注为 A0 参考。
