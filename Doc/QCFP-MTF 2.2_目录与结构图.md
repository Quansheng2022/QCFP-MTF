# QCFP-MTF 2.2 目录与结构图

## 一、目录树（落地版）

```text
TA_Workflow/
├── run_QCFP_MTF_workflow.py          # 入口编排（init_db→audit→quality→P1~P5→L4日线）
├── Core/QCFP_MTF/
│   ├── ARCHITECTURE.md               # 2.2 十条规则（Design Freeze）
│   ├── institutional/                # 机构行为领域包（正式）
│   │   ├── state_engine.py           #   C/F/P → ACCUMULATION/NEUTRAL/RECOVERY/DISTRIBUTION/CAPITULATION
│   │   ├── pressure.py               #   +2 强吸筹 ~ -2 强派发
│   │   ├── persistence.py            #   连续 F↑ 季度数（0~4）
│   │   ├── divergence.py             #   背离（降级条件）
│   │   ├── confidence.py             #   High/Medium/Low
│   │   └── permission.py             #   evaluate_institutional_permission（五档 + 降级）
│   ├── setup/
│   │   └── swing_setup.py            # setup_type：NONE/BREAKOUT/PULLBACK/ACCUMULATION/RECOVERY
│   ├── decision/
│   │   ├── hard_exit.py              # Kill Switch（DES≥7/Extreme/Stop/破位+持仓）
│   │   ├── retail_position_fsm.py    # 七状态 FSM（正式事实源）+ RetailDecisionContext
│   │   ├── retail_position_sizing.py # 加法阶梯仓位（test 10%/build +10%/trim -15%/max 70%）
│   │   ├── retail.py                 # 红黄绿灯 + 六态 + 散户决策卡
│   │   ├── retail_fsm.py             # 薄转发（兼容）
│   │   ├── downside_risk.py          # DES / 风险下限 / 滞后解除 / 仓位单调性
│   │   ├── catalyst_quality.py       # CQS（-3~+3）
│   │   ├── stop_loss.py              # StopLossPolicy（唯一止损来源）
│   │   ├── institutional_filter.py / institutional_permission.py  # 薄转发
│   │   ├── action_generator.py / risk_evaluator.py / score_calculator.py
│   │   ├── position_sizing.py / dss_output.py
│   │   ├── object.py                 # 2.8 统一决策对象（snapshot+质量+约束+version_hash）
│   │   ├── entry_quality.py          # 2.8 进场质量（7 因子 → HIGH/MED/LOW，强波低质→WAIT）
│   │   ├── exit_quality.py           # 2.8 退出质量（PROFIT/RISK/SIGNAL/TIME/REGIME/GOVERNANCE/HARD）
│   │   ├── time_in_trade.py          # 2.8 持仓时间治理（预期/最大持有期 → HOLD/REDUCE/EXIT）
│   │   ├── replay_cert.py            # 2.8 回放证书（input→decision→certificate→ledger 指纹链）
│   │   ├── kill_switch.py            # 2.8 安全熔断（NORMAL→WARNING→SAFE_MODE→HALTED 系统级映射）
│   ├── portfolio/                    # 2.8 组合治理（state_engine 六态 + lifecycle_gate 动作门）
│   ├── ranking/                      # 2.8 横截面排序（opportunity_ranking 九维 + replacement 换仓）
│   ├── monitoring/                   # 2.8 持续监控（forecast_realized 分层校准）
│   ├── stress/                       # 2.8 压力引擎（市场/波动/相关性/流动性冲击）
│   ├── learning/                     # 2.8 受治理学习闭环（ResearchSandbox + 晋升门）
│   ├── performance/                  # 2.8 P&L 归因（attribution 收益来源分解）
│   ├── ablation/                     # 2.8 统计验证（experiments/permutation + statistical/CI+注册表）
│   ├── safety/                       # 2.8 持续验证（continuous_validation + kill_switch）
│   ├── data/                         # 2.8 数据治理（lineage 血缘 + feature_contract 特征契约）
│   ├── explainability/               # 2.8 决策解释（graph 因果链 + threshold/version）
│   ├── wave/                         # 2.8 波段对象（signal as-of / label 评价 / opportunity 画像 / lifecycle）
│   ├── execution/                    # 2.8 执行层（capacity 冲击模型 / liquidity_exit 分批退出）
│   ├── structural/                   # P1 季度结构（chip/flow/price/regime/divergence）
│   ├── behavioral/                   # P2 月线行为（turnover/volume/vp_matrix/cbi/cost/stage）
│   ├── tactical/                     # P3 周线战术 + L4 日线战术（daily_tactical.py）
│   ├── fusion/                       # P4（mtf_alignment / daily_timing / anti_inference / chip_confidence）
│   ├── backtest/                     # P6（engine/data_pipeline/cross_sectional/benchmark/performance/
│   │                                #      pit_universe/portfolio_risk/run_status/calibration/robustness）
│   ├── common/ config/ data/ sql/    # 共享 / 配置 / 加载 / 建表
│   ├── scripts/                      # 引擎与实验脚本（见下）
│   └── tests/                        # 448 模块（单元/集成/金标准/不变量/注入攻击/宪法）
```

## 二、scripts/ 脚本清单

| 类别 | 脚本 | 用途 |
| :-- | :-- | :-- |
| 引擎 | structural / monthly_behavior / weekly_tactical / **daily_tactical** / mtf_fusion / decision | P1~P5 + L4 |
| 报告 | dss_report / all_in_one_report / html_report | DSS / 一体化 / 回测 HTML |
| 回测 | backtest_runner / calibration / cross_sectional_backtest / sensitivity_backtest / trigger_sensitivity / cost_stress_test / regime_gate_test | 主回测与敏感性 |
| 验证 | ic_analysis / incremental_alpha_test / layer_ablation_test / **permission_fsm_ablation** / research_validation | IC/消融/12 门 |
| 诊断 | wave_replay / daily_alpha_test / **shadow_mode** / **stock_pool_report** / **counterfactual_replay** / **replay_certify** / **liquidity_exit_report** / **attribution_report** / **continuous_validation_report** / **lineage_report** / **version_impact_report** / **research_registry_report** / **counterfactual_portfolio** / **canonical_audit** / **governance_certification** | 事件回放/双轨/四池/反事实/证书/流动性退出/归因/持续验证/血缘/版本影响/实验注册/组合反事实/唯一决策链审计/全链路治理认证 |
| 工程 | init_db / audit_coverage / check_data_quality / validate_structural | 初始化与校验 |

## 三、决策链结构图

```text
            C / F / P
                ↓
      Institutional State（ACCUMULATION/NEUTRAL/RECOVERY/DISTRIBUTION/...）
                ↓
      Institutional Permission（BLOCK/WATCH/TEST/ALLOW/STRONG_ALLOW）→ 交易上限
                ↓
      Swing Setup（Q/M/W/D → NONE/BREAKOUT/PULLBACK/ACCUMULATION/RECOVERY）
                ↓
      Daily Timing（默认关闭）         Risk（DES/Hard Exit/Stop）→ Kill Switch
                ↓                            ↓
      Retail Position FSM（FLAT→TESTING→BUILDING→HOLDING→TRIMMING→EXITING→COOLDOWN）
                ↓
      Position Sizing（10%/+10%/-15%/max 70%）
                ↓
      Execution（T+1）
```

## 四、数据流

```text
SQLiteDB/HK_Stock.db
  → loader（日/周/月/季 K 线、资金流、机构持股、指数）
  → PIT/as-of（available_date <= decision_date）
  → qcfp_* 表（structural / monthly / weekly / daily_tactical / mtf_decision / backtest_results）
  → 报告（DSS / All-in-One / 股票池 / Shadow / 回测产物）
```
