# QCFP-MTF 2.2 使用手册

> 环境：Windows + `.venv\Scripts\python.exe`；先执行
> `$env:PYTHONIOENCODING="utf-8"; $env:PYTHONUTF8="1"`
> 所有命令在项目根目录执行。

## 一、完整工作流

```powershell
.venv\Scripts\python.exe run_QCFP_MTF_workflow.py
```

步骤：init_db → audit → quality → structural → monthly → weekly → **daily_tactical（L4）** → mtf_fusion → decision。

## 二、个股决策报告（含散户决策卡）

```powershell
.venv\Scripts\python.exe Core\QCFP_MTF\scripts\dss_report.py --stock 00371
.venv\Scripts\python.exe Core\QCFP_MTF\scripts\all_in_one_report.py --stock 00371
```

报告顶部含：决策卡（Strategic/Structural/.../Position）、**散户决策卡**（红黄绿灯 / 机构状态→权限 / 交易状态 / 仓位状态(FSM) / 建议仓位 / 禁止事项）、Q/M/W/D 四层、DES、研究状态。

（V31）散户决策卡的 **红黄绿灯 / 机构状态（压力/持续性/降级理由）/ 交易状态 /
仓位状态(FSM)（prev→next）/ 建议仓位** 全部派生自同一个 `DecisionSnapshot`
（优先 Stateful Shadow，缺失时 FLAT/0 单点推算），报告层零重算；
`action_from_snapshot` 由 FSM 状态唯一映射（FLAT→WAIT / TESTING→TEST / BUILDING→BUILD /
HOLDING→HOLD / TRIMMING→REDUCE / EXITING→EXIT / COOLDOWN→COOLDOWN）；
决策卡的 `Position（Legacy A0）` 为旧管道参考口径，两者可并存对照。

（V32）散户卡与 All-in-One 审计新增 **仓位动作**（`NO_RISK_INCREASE` = 权限封顶）
与 **决策原因**（primary/secondary reason codes）展示；All-in-One 审计优先读取
决策台账 `qcfp_decision_ledger`（数据源标注 `ledger:run_id`），
仅在无台账且 Shadow 版本严格匹配时回退，FLAT/0 单点推算会明确标注"非正式决策"。

（V33）唯一决策入口为 `decision/engine.py::evaluate()`（Shadow / Ablation /
报告全部走同一引擎）；台账 **只追加不可覆盖**（七元审计身份去重），
发现错误用 `invalidate_snapshot` 失效重发，不修改历史；
正式模式（research_validation / production / audit）下无台账即报
"无正式决策"，不再单点重算。

（V34）四层架构：**Institutional Permission → Participation Budget →
Swing FSM → Position Sizing**。散户卡与 All-in-One 审计新增
**参与预算**（STAND/OBSERVE/EXPLORE/TRADE + 上限）、**仓位类别**
（观察仓/风险仓/空仓）与**退出等级**（L1 纪律性 / L2 风险性 / L3 致命）。
WATCH + Setup + 低/中风险时允许 5% 观察仓（探索性暴露），权限仍为 WATCH
（不可越权）；HOLDING 持仓享有更宽的趋势存活缓冲（默认 5%）。

（V35）2.5 Governance Hardening——
- 报告顶部新增 **Governance Decision Card**（Institutional State / Permission /
  Participation / Setup / Trade Quality / Risk / FSM / Final Target / 治理核验）；
- **Trade Quality（TQS）**：允许交易≠值得交易，TQS<40 时压仓为 0；
- 版本三维身份：MODEL=QCFP-MTF-2.5.0 / RULE=GOV-2.5.0 / SCHEMA=DECISION-1.1，
  Ledger 记录 feature_manifest_hash；
- **回测同源**：`backtest_runner.py --engine canonical` 用唯一决策引擎产生
  target（与 Live/Shadow 同一引擎）；
- **牛散效用指标**：Wave Capture / MAE / MFE / 机会错失率 / 错误参与率 /
  资金效率 + Retail Utility Score（见 wave_capture 报告"牛散效用"章节）；
- 参与预算按 Market Context 缩放（risk_on 全预算 / neutral 0.6 / risk_off 0.3），
  并可用 Ablation A11（Full−Market Scale）验证其贡献。

（V36）剩余四项落地：
- **执行层压力**：`python Core\QCFP_MTF\scripts\execution_ablation.py
  --stock 01951 [--engine canonical]`（成本 1/1.5/2/3× + T+1 无偏验证）；
- **Permission×Opportunity 矩阵**：散户卡内 5×3 矩阵（OBS/TEST/TRADE/A+），
  Opportunity 由 Setup+TQS 派生，不改变 Permission；
- **组合约束**：`backtest_runner.py --constraints`（单股≤30%、行业≤50%、
  总暴露≤100%，target 层生效）；
- **Ablation A12/A13**：`permission_fsm_ablation.py` 新增 Full−Stop 与
  Full−Observation 单模块消融。

（V37）P2 收口：
- **Legacy→New 验收**：`python Core\QCFP_MTF\scripts\legacy_replace_check.py
  --stock 01951`（Consistency/OOS/Ablation/Governance 四关，PASS 后可把
  `backtest.engine_source` 默认切到 canonical）；
- **报告三拆分**：`decision_report.py --stock 01951`（一屏决策）、
  `audit_report.py --stock 01951`（七元审计身份+证据链）、All-in-One=研究报告；
- **Research Gate**：回测汇总新增 G0–G7 分层门（Research Validated /
  Conditional / Not Validated）；
- **PIT 真实披露表**：复制 `Config/qcfp_disclosure_dates.template.csv` 为
  `qcfp_disclosure_dates.csv` 并填真实披露日 → disclosure_mode=REAL（PIT-A）。

（V39）2.6 执行纪律落地：
- **验收测试**：`G-001..G-010` 治理契约（tests/test_governance_contract.py）；
- **Live Shadow**：`shadow_live.py --stock 01951`（今日决策+证书+模拟成交+
  REGIME_DRIFT 漂移监控）；
- **执行情景**：`execution_ablation.py --scenarios base,stress,extreme`；
- **Release Gate**：`release_gate.py --stock 01951`（12 门验收，
  当前 CONDITIONAL——补真实披露日与 PIT Universe 后才可能 RELEASE）。

DSS JSON 输出 `decision_2_2` 章节（2.2 决策链完整结果：permission/exit/setup/FSM/target/
action/rule_ids/fingerprint/settings_hash），`decision.*` 仅标注为 `legacy_mtf` 对比口径。

All-in-One 报告（MD+HTML）在“二、决策报告（详细版）”之后新增 **2.5 2.2 决策链审计（Stateful Shadow）** 章节：

- 优先读取 `Report/QCFP_MTF/shadow/shadow_stateful_*.json` 中与当前股票/决策日匹配的最新快照，展示 Institutional State → Permission（含上限）→ Exit Event → Swing Setup → Retail FSM（prev→next）→ Matrix Base → Position（raw→final）→ Override Rules → Decision Path → Rule/Model/Schema 版本 → 输入 Fingerprint；
- 若未运行 P8 或无匹配快照，则按 FLAT/0 做 point-in-time 单点推算并在数据源标注；
- 该章节为研究输出（PIT-C Estimated），非交易指令。

## 三、股票池（四池）

```powershell
.venv\Scripts\python.exe Core\QCFP_MTF\scripts\stock_pool_report.py
# → Report/QCFP_MTF/stock_pool/stock_pool_YYYYMMDD.{md,csv,json}
```

- A 池 Institutional Trend（权限 ALLOW/STRONG_ALLOW）；B 池 Recovery（52W 低位 + 周线突破，**非立即买**）；
- C 池 Swing Watch（WATCH + 日线 Setup + Risk≤Medium）；D 池 Risk（派发/破位/投降，应回避）。

## 四、Shadow Mode（2.2 双轨，不改交易）

```powershell
.venv\Scripts\python.exe Core\QCFP_MTF\scripts\shadow_mode.py
# → Report/QCFP_MTF/shadow/shadow_mode_YYYYMMDD.{csv,json}
```

（V32）`shadow_mode.py` 同时把全部快照写入决策台账 `qcfp_decision_ledger`
（run_id=`shadow_YYYYMMDD_HHMMSS`），生成报告前先运行一次 Shadow，
报告审计章节即显示 `ledger:run_id`（正式事实源）。

## 四.5 波段捕获报告（Wave Capture）

```powershell
.venv\Scripts\python.exe Core\QCFP_MTF\scripts\wave_capture_report.py `
    --stock 01951 --min-gain 0.5 --year 2024
# → Report/QCFP_MTF/wave_capture/wave_capture_01951_YYYYMMDD_2024.{md,csv,json}
```

指标：波段捕获率（capture ratio）/ 进入延迟（周）/ MFE / MAE / 峰值捕获 /
错失率 / 错误试仓率——验收"日线波段捕捉效率"，而非只看 Sharpe。

## 四.6 正交 Ablation × 大波段 Replay

```powershell
# 全市场 2024 ≥50% 波段：A0–A9 逐一测算整体绩效 + 波段捕获，并输出贡献分解
.venv\Scripts\python.exe Core\QCFP_MTF\scripts\permission_fsm_ablation.py `
    --wave-year 2024 --wave-min-gain 0.5
# 单股 2024 ≥90% 波段
.venv\Scripts\python.exe Core\QCFP_MTF\scripts\permission_fsm_ablation.py `
    --stock 01951 --wave-year 2024 --wave-min-gain 0.9
# → Report/QCFP_MTF/backtest/permission_fsm_ablation_wave_YYYYMMDD.md
#   + permission_fsm_ablation_YYYYMMDD.{json,csv}（含 wave_replay.contributions）
```

贡献口径（正交单变量）：机构过滤器=A5−A2、散户波段系统=A2−A0、
软退出=A3−A2、硬退出=A4−A2、Daily=A8−A9；同时报告整体与 2024 大波段的
年化/MDD/捕获比/错失率/进入延迟增量。

同屏输出 Legacy（DB action/target）vs New（Permission→Setup→FSM→target）。

## 五、Permission + FSM Ablation

```powershell
.venv\Scripts\python.exe Core\QCFP_MTF\scripts\permission_fsm_ablation.py
# → Report/QCFP_MTF/backtest/permission_fsm_ablation_YYYYMMDD.{json,csv}
```

比较 A Legacy / B Legacy+PermGate / C FSM / D Perm+FSM（年化/Sharpe/MDD/PF/换手/暴露/上下行捕获）。

## 六、其他研究工具

```powershell
# 层级消融（Q/QM/QMW/Full + IC 衰减/ICIR + 上下行捕获）
.venv\Scripts\python.exe Core\QCFP_MTF\scripts\layer_ablation_test.py

# 触发器×缓冲敏感性（--buffers 0.02,0.05,0.08,0.12）
.venv\Scripts\python.exe Core\QCFP_MTF\scripts\trigger_sensitivity.py

# 成本压力（0.5x~4x）
.venv\Scripts\python.exe Core\QCFP_MTF\scripts\cost_stress_test.py

# 2024 波段事件回放
.venv\Scripts\python.exe Core\QCFP_MTF\scripts\wave_replay.py --year 2024 --min-gain 0.5

# 12 门研究验证
.venv\Scripts\python.exe Core\QCFP_MTF\scripts\research_validation.py --run-id bt_YYYYMMDD
```

## 七、测试

```powershell
.venv\Scripts\python.exe Core\QCFP_MTF\tests\run_all_tests.py
# 57 模块：单元 / 集成 / 金标准（00371/01951）/ 金融不变量 / 2.2 引擎
```

## 八、配置（Config/qcfp_settings.yaml）

| 节 | 关键项 |
| :-- | :-- |
| decision.tactical_override | 方案 B 试多（enabled/min_trigger/max_52w_position） |
| decision.downside_risk | DES 权重 / 风险下限 / release_weeks / exit_at_score |
| decision.stop_loss_policy | 唯一止损来源（entry_week_low / buffer_pct） |
| decision.retail | 仓位带 / fsm（cooldown_weeks / chase_52w / position 阶梯） |
| institutional.permission | persistence_min_quarters / 降级开关 |
| risk.hard_exit | des_threshold=7 |
| backtest.mode | research_exploration / research_validation / production |

## 九、完整个股测试（test_QCFP-MTF.py，P1~P8）

```powershell
# 完整链路（含报告与 2.2 审计，跳过回测）
.venv\Scripts\python.exe test_QCFP-MTF.py --stock 00371 --skip-backtest --no-interactive

# 全链路含回测
.venv\Scripts\python.exe test_QCFP-MTF.py --stock 00371
```

链路（9 引擎）：

```text
P1 季度结构 → P2 月线行为 → P3 周线战术 → P3.5 日线战术（L4，新增）
→ P4 融合 → P5a 决策 → P5b DSS 报告 → P7 All-in-One
→ P8 2.2 决策链审计（Stateful Shadow，全历史滚动重放，新增）
```

单引擎：

```powershell
.venv\Scripts\python.exe test_QCFP-MTF.py --stock 00371 --single P3.5   # L4 日线
.venv\Scripts\python.exe test_QCFP-MTF.py --stock 00371 --single P8      # 2.2 审计
```

说明：

- `P3.5` 保证 DSS“日线战术层”与散户 FSM 使用最新日线状态（此前只跑历史值）；
- `P8` 只计算不写库，输出 `Report/QCFP_MTF/shadow/shadow_stateful_*.{csv,json}`
  （每只股票逐周 prev_state→next_state→target、permission_cap、exit_event）；
- `--skip-reports` 会同时跳过 P5b/P7/P8；`--no-interactive` 出错自动继续。
