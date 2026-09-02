# QCFP-MTF 决策架构（Architecture Baseline，非文档冻结）

> 定位：机构行为状态过滤器 + 散户波段交易决策系统。
> 版本：以 `decision/versions.py` 为唯一权威（当前 `QCFP-MTF-2.5.0` /
> `GOV-2.5.0` / `DECISION-1.1` / `canonical-2.8`）。
> 本文件是 **Architecture Baseline**：不是“文档永不变化”，而是随变更演进；
> 演进后的冻结状态由 `audit/baseline/governance_baseline.json` 记录
> （Canonical Spec Hash 与 Architecture Hash 分别冻结，Spec 不受影响，
> 见 CANONICAL_SPEC.md CS-70 / QCFP-SPEC-CHG-003）。

## 分层与职责

```text
C / F / P → Institutional State → Institutional Permission（交易上限）
Q / M / W → Trading Setup（波段机会）   D → Timing Trigger
Risk（DES / Hard Exit / Stop）→ Kill Switch
Retail Position FSM → 仓位生命周期      Position Sizing → 数值仓位
```

四个概念严格分离：Institutional State ≠ Permission ≠ Setup ≠ Position State。

## 十条规则（RULE）

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

## Canonical Rule Map（CS-30/40/50/60/70 映射）

> 十条规则之外的架构级规则，逐条映射 CANONICAL_SPEC.md 永久 ID
> （见 `Core/QCFP_MTF/CANONICAL_SPEC.md` 与
> `governance/traceability_manifest.yaml`）。本清单与 Spec 一起被
> `governance_baseline.json` 冻结（architecture_hash）；Spec 不变时
> 架构可以演进，演进后需重算 Baseline（Create-Only → 新 Candidate）。

```text
RULE 11  UNKNOWN must degrade（QCFP-SPEC-INV-006）
RULE 12  Production cannot self-modify（QCFP-SPEC-INV-007）
RULE 13  Every production decision must be auditable and replayable（INV-008）
RULE 14  Research may challenge Production, never silently change it（INV-009）
RULE 15  Complexity must prove incremental practical value（INV-010）
RULE 16  Final target can only be reduced downstream（INV-005）
RULE 17  Validation authority is the sole certification source（AUTH-006）
RULE 18  Ledger is append-only with a single fact writer（AUTH-007）
RULE 19  Reports cannot create decisions（AUTH-008）
RULE 20  Production decisions require complete identity + release identity（ID-001/002）
RULE 21  Same input + same release identity → same decision（ID-003）
RULE 22  Change impact precedes implementation contract（CHG-001）
RULE 23  Patch scope lock（CHG-002）
RULE 24  Baseline is create-only and immutable（CHG-003）
RULE 25  Builder cannot change frozen golden results or delete failing tests（CHG-004）
RULE 26  Release verdict is three-state, fail closed（RLS-001/003）
RULE 27  Qualification and Promotion are separate gates（RLS-002）
RULE 28  AI cannot execute HUMAN_APPROVED（RLS-004）
RULE 29  Evidence hierarchy ladder（BND-002）
RULE 30  Research and Production are isolated（BND-001）
```

## 优先级（最高→最低）

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

## 目录

```text
institutional/   状态/压力/持续性/背离/置信度/权限（正式领域包）
setup/          波段机会识别（swing_setup）
decision/       hard_exit / retail_position_fsm / retail_position_sizing /
                institutional_*（薄转发）
```

## 边界约束

- 第一版固定规则矩阵，不放过多可调参数（避免参数过拟合）；
- Daily Timing 保持关闭，重新设计后再评估；
- 新增模块走 Shadow Mode（legacy 与 new 双轨输出），通过单元/集成/PIT/OOS/Ablation 后才替换旧路径。

---

# MTR Closure Release（Sprint A–E）—— 证据与物理收口

> 发布标签：`MTR-CLOSURE-1`（`decision/versions.py::RELEASE_TAG`）。
> 原则：不再开发新的 MTR 功能；只做**真实 Decision Path、真实 Authority
> Audit、独立 Manifest、真实 Failure Injection、真实 Physical Delete、
> 纯裁判 MTR Runner**。

## Sprint A — Authority Closure（问题 1/5/6）

- `scripts/decision_engine.py` 从「第二次 Canonical 计算适配器」改为
  **Ledger Projection Adapter**：只允许
  `load_canonical_snapshot() → project_display_fields()`，禁止
  `evaluate()`/`DecisionConfig`/FLAT-0 强制状态；缺失 Ledger 决策 → 不投影、
  不伪造（`ledger_status=LEDGER_MISSING`）。
- `governance/pwc2_authority_graph.py`：
  - `behavioral_authority_audit` 只统计 `production_reachable` 模块；
  - 同一模块内 ASSIGN/SQL/CALLS 只计 1 个 owner（`set(module)`）；
  - 新增 `OWNER_CONTRACT`：非 Owner 写入最终字段 → `UNAUTHORIZED_WRITER`；
  - 修复 `==` 被误判为赋值的扫描缺陷；
  - `PRODUCTION_ROOTS` 移除 `backtest_canonical`（Backtest 是研究/验证，
    不是生产 Root），生产域只含 Canonical Engine / Certification /
    Execution / Ledger / Runtime Safety。

## Sprint B — Independent Truth（问题 3/4/7）

- `FROZEN_PRODUCTION_MANIFEST`：治理冻结的 Production Feature Manifest
  （状态只允许 ACTIVE / RESEARCH_ONLY / RETIRED），ACTIVE 状态**不由 Graph
  即时推导**。
- `verify_frozen_manifest()`：Frozen Manifest（Artifact A）× Authority Graph
  （Artifact B）独立比对——每个 ACTIVE 必须 owner 存在、production_reachable、
  无 forbidden dependency。
- `V9_PRODUCTION_BASELINE_MANIFEST` + `active_feature_diff()`：
  before/after ACTIVE 集合真实对比，`newly_active=0`（本次 Closure 禁止新增
  Production ACTIVE Feature）。
- `critical_loc_metrics()` + `critical_loc_baseline()`：只统计 Production
  Roots 可达代码的 DecisionCriticalLOC；baseline 不可修改（已存在拒绝覆盖）。

## Sprint C — Trust Evidence（问题 8/9）

- `run_failure_qualification()`：**真实执行** 12 类 Failure Injection
  （future PIT / 缺 liquidity cap / NaN cap / ledger tamper / replay mismatch /
  release mismatch / evidence pack missing / future-aware wave /
  bare snapshot execution / broker UNKNOWN / broker position mismatch /
  report action rewrite），每个 case 保存
  `input_before / injected_change / expected / actual / escaped / event /
  ledger_result`；`failure_escaped_count>0 → RELEASE_REJECTED`。
- 修复真实漏洞：`finalize_target` / `caps_governance_check` /
  `assert_target_within_caps` 对 **NaN cap 静默放行**——现改为 UNKNOWN →
  no-new-risk。
- `golden_result.json / replay_result.json / oos_result.json`：
  真实运行 Golden 宪法测试、真实从 `qcfp_decision_ledger` 重放对比；
  OOS 缺真实回测 artifact → 诚实 `NOT_PROVEN`。

## Sprint D — Physical Retirement（问题 10/3/4/5）

- 真实删除 `decision/score_calculator.py` 及其测试；`run_all_tests.py`
  移除注册；`test_production_cannot_import_retired_module` 保留。
- `physical_delete()`：`DELETE_COMPLETE` 只能来自
  `actual_removed_count>0 AND 候选文件全部不存在 AND 残余引用=0`；
  禁止 `actual_removed=[]` 却宣布完成。
- `scan_residual_references()`：全工程扫描 retired module 的
  import/CLI/config 残余；物理删除后重新从源码构图（禁止手工标
  `production_reachable=False` 当 detach 证据）。
- Golden 测试迁移 Canonical-only（`test_golden_cases.py`），
  legacy 决策权威（`action_generator`/`position_sizing`）仅保留在
  Research/Shadow/Archive 引用，Production 路径引用 = 0。

## Sprint E — Pure MTR Judge

- `scripts/minimal_trusted_release.py` 双模式：
  - `--generate-artifacts`（Build/CI 测量入口）：从真实源码构图 →
    冻结 Manifest/Baseline → 真实 Failure Injection → Golden/Replay →
    物理删除扫描 → 写出 9 类 artifact；
  - 默认（纯裁判）：只读取 `audit/mtr/` 下 8 类 artifact →
    `evaluate_mtr()` → 输出 10 问 Boolean 与三态 verdict
    （MTR-CONVERGED / MTR-NOT-CONVERGED / MTR-NOT-PROVEN）。
- 裁判禁止 run measurements / invent baseline / fix graph / default PASS。

## 当前诚实状态

```text
Production Decision Path        1/1     ✓
Canonical Authority             1/1     ✓
ACTIVE Features                 41→34   ✓（newly_active=0）
Decision-critical LOC           ↓       ✓（backtest 不再计入生产域）
Legacy Production Path          0       ✓（研究工具允许引用并标注）
Duplicate Authority / Unauthorized Writer  0/0  ✓
Unwired ACTIVE                  0       ✓
Failure Injection               12/12 执行、0 escaped  ✓
Retired code physically deleted >0、残余引用 0        ✓
Golden                          PASS    ✓
Replay                          真实证据（当前历史台账 0 精确重放 → 诚实失败）
OOS                             NOT_PROVEN（需真实 PIT/OOS 回测 artifact）
```

Replay/OOS 是真实证据缺口：历史 Ledger 由旧引擎写入，当前 Release 无法精确
重放；正确做法是**在 Shadow/Paper 阶段用当前 Release 重新生成 Ledger**，
再重跑 Replay + OOS，不能靠伪造 PASS 通过 MTR 门。

---

# Runtime Evidence Wiring & Fail-Closed Closure（Sprint A–D）

> 唯一目标：**一条 Canonical Decision Chain，三种 execution_mode，
> 两类事实 Ledger，一份 Runtime Evidence。**
> 完成 Sprint A+B → 全 Universe Shadow Evidence 积累；
> 完成 Sprint C → Paper 长期运行；Sprint D 全通过 → 才讨论 Small-Live。

## Sprint A — Runtime Backbone（1/2/8）

- `execution/execution_context.py`：`dispatch_runtime()` 唯一 Runtime
  Dispatcher——Canonical evaluate 只执行一次，三种 mode 只改变 Execution；
  `deployment_cap` 改 `Optional[float]=None`（SHADOW/PAPER N/A，
  SMALL_LIVE 必填）；mode-specific validation。
- `execution/runtime_event_ledger.py`：`event_seq AUTOINCREMENT` 链顺序；
  Hash 覆盖全部不可变事实字段（费用/内外仓位/incident_id…）；
  `verify` 重新计算 payload_hash + current_event_hash + sequence
  continuity；写入前强制 `validate_runtime_identity`
  （event → decision → release → certificate；mismatch →
  EVENT_APPEND_REJECTED）；表结构由 SQL 迁移拥有。
- `execution/execution_gate.py`：资格检查 `assert_execution_eligible()`
  与 `execute(CertifiedDecision)` 分离。

## Sprint B — Shadow Truth（3/4/10）

- `scripts/shadow_universe.py`：Daily Full-Universe Runner——每只股票必须
  落在 CERTIFIED/NO_TRADE/SAFE_MODE/ABSTAIN/HALTED 五态之一；异常不能
  让股票消失；输出 Coverage Artifact（decision_count==universe_count、
  missing==[]、duplicates==0 硬门）。
- `research/research_outcome.py`：写入前强制
  `validate_research_outcome`（research_only/future_aware/decision→release
  cross-bind/时间顺序/source snapshot/hash），缺失 →
  OUTCOME_APPEND_REJECTED；`scripts/backfill_research_outcomes.py`
  异步回填（5D/20D/60D，TRADE/NO_TRADE/ABSTAIN，INSERT ONLY）。
- `monitoring/runtime_evidence.py`：Required Field Contract（缺 key →
  NOT_PROVEN，消灭 missing→0→PASS）；正式证据只能由
  `build_runtime_evidence_from_ledger()` 构造（绑定
  decision/runtime/outcome 链尾）；SHADOW execution 显式
  NOT_APPLICABLE；`continuous_certification` 只接受 artifact dict。

## Sprint C — Paper Reality（5/6/10-PAPER）

- `execution/order_state_machine.py`：显式 `reject()`。
- `execution/paper_pipeline.py`：唯一 Status Mapping
  （FILLED→ack / PARTIAL→ack / REJECTED→reject / CANCELLED→cancel /
  UNKNOWN→timeout；未知状态→timeout，绝不默认 ACK）；订单事件先落
  Runtime Event Ledger；EOD 对账 broker_position 缺失 → UNKNOWN（禁止
  internal 伪装）；coverage=matched/expected；unexpected 单独报告；
  Calibration 样本接线（estimated/realized slippage·fill·exit·
  participation，禁止自动改参数）。

## Sprint D — Small-Live Eligibility（7/8/9/10-SMALL_LIVE）

- `execution/deployment_cap.py`：负 Cap / 超 approved_max →
  INVALID_DEPLOYMENT_CAP；删除 `executed_target`（只能来自 Fill/Broker）；
  Cap 只来自 Governance 批准，禁止自动上调。
- `execution/broker_adapter.py`：Contract 校验要求 subclass 真正 override
  全部 5 方法（否则 NOT_IMPLEMENTED）；统一 Response Schema；任何
  Broker Response 先落 Event（event-first）；UNKNOWN Resolution
  （query→fills→positions→reconcile，只有 Resolved 才恢复新风险）。
- `safety/reactivation_gate.py`：ReactivationCertificate 绑定
  incident_id/release_id/checkpoint_hash/replay_hash/approval_identity；
  restart ≠ REACTIVATED，必须 REACTIVATION Runtime Event。
- `sql/create_qcfp_tables.sql`：正式纳入 qcfp_runtime_event_ledger /
  qcfp_decision_certificate / qcfp_research_outcome（runtime_event_seq /
  execution_mode / broker_order_id / incident_id / outcome_hash 全部进
  Schema Migration；Runtime helper 不再偷偷自动建表）。

## Gate 摘要

```text
Sprint A  Canonical 决策永不因 mode 改变；Event identity 有效；
          Runtime Ledger tamper detection PASS
Sprint B  Universe Coverage=100%；Missing=0；Future→Production leak=0；
          Shadow Evidence=EVIDENCE_READY
Sprint C  UNKNOWN→ACK=0；Blind resend=0；Reconciliation=100%；
          Calibration wired=YES
Sprint D  DeploymentTarget<=CanonicalTarget；Real Broker override 全实现；
          ACK/Fill/Fee/Position 100% 持久化；Incident→Recovery→Replay→
          Reactivation 全链有 Event Evidence
```

---

# MTR 剩余 3 问 Closure（Q4 / Q8 / Q10）

## Q4 — Complexity Closure

- `critical_loc_diff.json` 同时输出
  `production_reachable_loc_down` 与 `decision_critical_loc_down`；
  **MTR Q4 只读取 `decision_critical_loc_down`**（不能用 reachable LOC
  替代——删 Backtest Root 不代表决策关键代码减少）。
- `decision.governance_caps` 从 CAP 降级为 **CAP_SUPPORT**
  （不可变数据结构 + validation helper，不是独立决策 Authority；
  FINAL_TARGET 唯一 Owner 仍是 `decision.governance`）→
  不再计入 Decision-critical LOC。
- `wave.stage_gate` **MERGE** 进 `wave.canonical` 并物理删除
  （Wave Authority 唯一 Owner = wave.canonical；一个 Authority 的规则
  放回一个 Owner）→ Decision-critical 模块数下降。
- 真实结果：Decision-critical LOC 1912 → 1776；模块数 8 → 6；
  Golden PASS / Failure Injection 0 escaped 不变。

## Q8 — Trust Evidence Closure

- Replay 拆成两个概念：
  - **Historical Release Replay**：REL-V9 decision 用 REL-V9 引擎重放
    （facts immutable）；不能用当前引擎要求旧决策 EXACT_MATCH；
  - **Current Release Replay**：当前 Release 自己产生的 Decision 必须
    eligible=100%、exact=100%、critical mismatch=0。
- `decision_ledger.replay_eligibility()`：Ledger commit 时标记
  settings_hash → settings_blob 是否 100% 可解析 + release/evidence/
  path 材料是否齐全（replay_eligible=False 不阻止记录，
  但 Certification 应阻止长期出现）。
- OOS：`run_oos_evidence()` 真实 Previous vs Current 同口径比较；
  任何契约缺失/泄露 → **OOS_NOT_COMPARABLE**（不是 PASS 也不是 FAIL）。
- 当前诚实状态：Golden PASS；Current-Release Replay = 0 条
  （Ledger 尚无 MTR-CLOSURE-1 决策，需 Shadow 阶段积累）；
  OOS_NOT_COMPARABLE（dataset 契约未冻结）→ Q8 保持未闭合。

## Q10 — Physical Retirement Closure

- 语义固定：**RETIRED = 当前 Production Tree 中源码不存在**；
  **RESEARCH_ONLY = 文件存在、Research 可 import、Production 不可达**。
  只要源码还存在就不叫 RETIRED。
- Manifest 状态修正：`score_calculator` → RETIRED（已删除）；
  `action_generator` / `position_sizing` / `permission_gate` →
  RESEARCH_ONLY（Legacy Comparator / research backtest / boundary audit
  保留，Production 不可达）。
- `physical_retirement_audit()`：集合等价验证
  `DeclaredRetiredSet ⊆ PhysicallyAbsentSet` 且残余=0；
  MTR Q10 读取 `all_retired_physically_deleted`（不再只读
  removed_count>0）。

## MTR 当前诚实判定

```text
Q1–Q7、Q9          PASS
Q4（decision_critical_loc_down） PASS（1912 → 1776，8 → 6 模块）
Q10（Declared RETIRED ⊆ 物理删除） PASS（score_calculator 已删，
      action_generator/position_sizing/permission_gate 已改 RESEARCH_ONLY）
Q8（Golden PASS；Current Replay=0 条；OOS_NOT_COMPARABLE） 未闭合——
      需 Shadow 阶段用当前 Release 生成 Ledger 后再 Replay + OOS
```

---

# Runtime Evidence Accumulation（Closure 1–7）

## Closure 1 — 统一 Decision 读取接口

- `execution/execution_context.py` 新增 `canonical_target_of(decision)` 与
  `decision_identity_of(decision)`：
  DecisionSnapshot → `target_position`；CertifiedDecision →
  `snapshot["target_position"]`。Paper / Small-Live 一律走同一 helper，
  禁止各模块分别 getattr（修复 Paper 把 CertifiedDecision 20% 读成 0% 的 P0）。

## Closure 2 — Small-Live Delta Order

- `dispatch_runtime(SMALL_LIVE)` 复用 Paper 的 `order_intent(current_position,
  deployment_target)`——OrderQty = DeploymentTarget − CurrentPosition，
  绝不直接下 DeploymentTarget（修复 current=4%、target=5% 却下单 5% 的 P0）。

## Closure 3 — Broker Event Identity + Event-first Gate

- `broker_response_event()` 现在必须携带 decision_id / release_id /
  certificate_id / event_time；
- Dispatcher 检查 `inserted`：Broker Event 落库失败 →
  `BROKER_RESPONSE_UNPERSISTED:NO_NEW_RISK`，**绝不返回 dispatched=True**
  （修复“订单已提交但 Broker Evidence 未落库”的 P0）。

## Closure 4 — Shadow 全终态成为 Ledger Fact

- `qcfp_shadow_decision_fact`（SQL 迁移）+ `record_coverage_fact()`：
  ABSTAIN / SAFE_MODE / HALTED 也持久化，不允许只存在于 Coverage JSON；
  CERTIFIED / NO_TRADE 走 qcfp_decision_ledger。
- `classify_terminal_state()` 从 Snapshot 语义识别 SAFE_MODE
  （context.safety_status），不再只有三态。
- 语义区分：数据行缺失 / PIT-DataQuality 无法证明 → ABSTAIN；
  必需表不存在 / SQL 故障 → HALTED（schema broken）。

## Closure 5 — Daily Runtime Runner

- `scripts/runtime_evidence_runner.py`：Shadow Universe（全终态→Fact）→
  Outcome Backfill → Paper EOD Reconciliation（从 Runtime Event +
  Decision Ledger 两个独立事实集合）→ Calibration Aggregation →
  Runtime Evidence（fail-closed）。paper_daily_reconciliation /
  paper_calibration_samples / build_runtime_evidence_from_ledger 正式接线，
  不再是“capability exists, no caller”。

## Closure 6 — 消灭 Runtime Evidence 硬编码零

- `pit_violations` 从 qcfp_decision_ledger.pit_grade 事实列计算；
- `uncertified_count` 从 ORDER_SENT/FILL/PARTIAL_FILL 事件中
  certificate_id 缺失数计算；
- `critical_replay_mismatch` 从 REPLAY 事件 payload verified=False 计算；
- Expected Reconciliation 来自 eligible Order/Position 事件集合，
  Actual 来自 RECONCILIATION 事件集合——两者不同事实集合，不能自证 100%。
- Incident/Recovery/Replay/Reactivation 事件补齐 event_time
  （默认当前时间），可进入 period evidence 聚合。

## Closure 7 — Real Broker Adapter（真钱前置）

- 只有 ACK/FILL/FEE/POSITION/UNKNOWN/RECONCILIATION/Incident 全链测试
  通过后才实现 RealXXXBrokerAdapter；当前保持 Contract Ready。

## 当前诚实状态

```text
Shadow    SHADOW_COVERAGE_OK（17 只：CERTIFIED 1 / NO_TRADE 15 /
          ABSTAIN 1 / SAFE_MODE 0 / HALTED 0；dry-run 实测）
Paper     4 个 P0 已修复（target 读取 / delta / broker identity /
          event-first gate）；EOD + Calibration 已接入 daily runner
Small-Live 仍无 Real Broker（Closure 7 前置）
Runtime Evidence NOT_PROVEN（真实库尚未迁移 runtime event 表——
          缺表即 fail-closed，不是伪造 PASS）
```

---

# Q8 Closure（Golden / Replay / OOS 无退化）

## Q8-A — Golden Freeze

- `golden_result.json` 冻结：release_id / golden_corpus_version /
  golden_corpus_hash / n_total / n_passed / n_failed /
  critical_failures / generated_at（GOLDEN-2 schema）。
- Golden 保持 canonical-only，不再扩展。

## Q8-B — Current-Release Replay Closure

- `replay_eligibility()` 修复：
  * settings_blob 必须**真正 JSON parse 成功**（SETTINGS_NOT_FOUND /
    SETTINGS_UNPARSABLE 显式区分，不是 SELECT 1）；
  * 完整 Replay material：release/model/rule/schema/data/universe/
    prev 状态/decision_path/path_hash/production manifest/
    participating feature hash。
- 修复引擎缺陷：`data_snapshot_id` 计算后未写入 Snapshot 构造函数。
- Shadow 决策把输入行存入 context（`shadow_evidence`）——Replay 用
  持久化输入行重建（Ledger 不复制整份数据集，只存单条输入行）。
- `run_replay_evidence()`（REPLAY-2 schema）：
  * Current Release 全量（按 release identity 过滤，无 LIMIT 20）；
  * 同一 (stock, date) 多 run 取最新 ACTIVE；
  * n_mismatch = n_eligible − n_exact（Historical skipped 不计入）；
  * critical fields 与 Golden 一致：Permission / Wave / FSM /
    Wave Proposal / FinalTarget / CanonicalAction（派生）/
    BindingConstraint（重派生）/ DecisionPathHash；只比较 Ledger
    实际持久化或可确定性派生的事实。
- **真实结果：16/16 Current Release Shadow Decision，eligible=100%、
  exact=100%、critical mismatch=0。**

## Q8-C — Formal Previous-vs-Current OOS Closure

- `oos_contract.json`（OOS-2）：contract_version / dataset /
  universe / pit / train-validation-oos 窗口 / cost / execution /
  metric 契约 / previous+current release / holdout_locked /
  used_in_selection。缺任一字段 → OOS_NOT_COMPARABLE。
- Previous vs Current 在**同一 Frozen OOS** 上比较（复用同一
  canonical_runs.run_canonical_oos，不建第二套引擎）；Previous
  artifact 必须身份一致（release/contract/dataset/universe/metric）。
- `compare_oos()`：Frozen Non-Inferiority Contract
  （metric/direction/max_allowed_regression/hard_or_soft），
  evidence_not_down 只从比较结果计算，不硬编码 True。
- `_load_df(required=True)`：必需表缺失 → DATASET_CONTRACT_FAILURE →
  OOS_NOT_COMPARABLE（不是空 DataFrame 让下游猜）。
- 当前诚实状态：**OOS_NOT_COMPARABLE**——previous release（V9）
  源码/容器与 frozen OOS artifact 均未归档，无法同口径比较。
  这不是"测试没过"，而是**没有资格比较**（fail-closed）。

## Q8 Judge（GOLDEN-2 / REPLAY-2 / OOS-2）

```text
Q8 = golden.status==PASS AND golden.schema==GOLDEN-2
     AND replay.schema==REPLAY-2 AND n_current_release>0
     AND eligible_rate==1.0 AND exact_rate==1.0
     AND critical_mismatch==0
     AND oos.schema==OOS-2 AND oos.status==OOS_PASS
     AND oos.comparable==True AND oos.evidence_not_down==True
```

旧 artifact fallback 已移除；任何字段缺失 → Q8 NOT_PROVEN。

## 当前 MTR 诚实判定

```text
Q1–Q7、Q9、Q10          PASS
Q4（decision_critical_loc_down） PASS（1912 → 1776，8 → 6 模块）
Q8-Golden               PASS（GOLDEN-2，corpus 冻结）
Q8-Replay               PASS（REPLAY-2：16/16 eligible + exact，
                         critical mismatch=0）
Q8-OOS                  OOS_NOT_COMPARABLE（V9 未归档，
                         previous release OOS artifact 缺失）——唯一剩余项
```

OOS 关闭路径：归档 V9 源码/容器 + 冻结 OOS Contract（含 dataset/
universe/cost/metric 哈希与 non-inferiority 阈值），在同一个 Frozen
OOS 上跑 V9 与当前 Release，再 `compare_oos()`。此步属于发布工程
（需要 V9 Release 资产），不是继续改代码。
