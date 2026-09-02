# QCFP-MTF P6 测试清单

> 适用范围：回测与校准系统（Look-ahead / 时间线 / 引擎 / 绩效 / 分层 / 校准）
> 验收口径：A~G 全部勾选 = P6 完成
> 记录：2026-08-20 实测基线（当前全部通过）

## 运行环境

- 项目根目录 `C:\Users\Quansheng\Documents\projects\TA_Workflow`；
- 使用 `.venv\Scripts\python.exe`；中文乱码先执行 `$env:PYTHONIOENCODING="utf-8"; $env:PYTHONUTF8="1"`；
- 数据库：`SQLiteDB/HK_Stock.db`。

---

## A. 单元测试（自动化）

- [ ] A1 全量回归：`.venv\Scripts\python.exe Core\QCFP_MTF\tests\run_all_tests.py`
  → 共 146 项全部 PASS（P0~P5 133 + P6 13），退出码 0
- [ ] A2 pytest：`.venv\Scripts\python.exe -m pytest Core\QCFP_MTF\tests -v`
  → 146 passed
- [ ] A3 P6 专项：`... python Core\QCFP_MTF\tests\test_backtest\test_lookahead_filter.py`（其余 5 个 P6 模块同理）
  → 每模块"全部通过 ✅"

## B. 回测模块单测（合成数据）

- [ ] B1 Look-ahead：available_date > 决策日剔除、空值不算违规、断言抛错
- [ ] B2 信号时间线：结构按 available_date 对齐（5/29 用 5/15 披露的季度、8/14 用 8/14 披露的季度）
- [ ] B3 引擎：仓位次周生效、建仓/清仓换手成本 0.45%、pnl 手算一致
- [ ] B4 绩效：年化/夏普/最大回撤/胜率/盈亏比/分年度
- [ ] B5 校准：小网格可运行、输出按 Sharpe 排序

## C. 数据表验证（qcfp_backtest_results）

- [ ] C1 行数与 run_id：`SELECT COUNT(*), COUNT(DISTINCT run_id) FROM qcfp_backtest_results`
  → 4321 行 / 1 个 run_id（bt_full_20260820）
- [ ] C2 股票与区间：15 只 / 2021-01-01 ~ 2026-08-14
- [ ] C3 信号分布：`SELECT action_signal, COUNT(*) ... GROUP BY 1`
  → EXIT 1962 / HOLD 1319 / REDUCE 678 / WAIT 359 / BUY 3
- [ ] C4 仓位与收益合理：`SELECT AVG(position), AVG(pnl) FROM ...`
  → 0.384 / -0.000267
- [ ] C5 唯一性：`(run_id, stock_code, signal_date)` 不重复（重复运行追加新 run_id）

## D. 回测运行

- [ ] D1 单股：`... backtest_runner.py --stock 00700 --dry-run` → Look-ahead 检查通过、退出码 0
- [ ] D2 全量：`... backtest_runner.py --run-id bt_full_20260820` → 写 4321 行
- [ ] D3 报告产物：`Report/QCFP_MTF/backtest/{equity_*.csv, summary_*.json}`
  → summary 含 overall / by_year / by_market_regime / expanding_windows
- [ ] D4 Look-ahead 断言：全量 9827 行信号时间线 0 违规

## E. 校准运行

- [ ] E1 `calibration.py --start 2021-01-01 --top 5` → 9 组合约 20 秒完成
- [ ] E2 输出 `Report/QCFP_MTF/backtest/calibration_*.json`，按 Sharpe 降序
- [ ] E3 `--apply` 写入 `Config/qcfp_calibration.json`（不覆盖主配置）

## F. 结果合理性

- [ ] F1 分层符合直觉：risk_on/neutral 正收益（年化 +16%/+19%）、risk_off 负收益（-17%）
- [ ] F1b（V1 更新）risk_on Sharpe 1.68 / neutral 2.45 / risk_off -1.04
- [ ] F2 组合口径总体年化 -1.94%、最大回撤 -33%（V1 修复池化伪影后）
- [ ] F3 校准（组合口径）reduce=0.7 优于 0.5；Walk-forward OOS 2024/2025 年正收益（Sharpe 1.17/1.12）
- [ ] F4 2024/2025 年正收益（+8.4%/+5.4%）、2022/2023/2026 负收益，与市场环境一致

## G. 工程约定

- [ ] G1 字典同步：`Code_utl\Generate_qcfp_Dictionaries.py` 重跑后 qcfp_backtest_results 字段数 = PRAGMA 列数
- [ ] G2 源表只读：`hk_*` 表结构未被 P6 改动
- [ ] G3 回测不进入每日工作流（`SCRIPT_LIST` 未包含），按需运行

## H. 方案 B / CQS（V10 新增）

- [ ] H1 单元测试：`tests\test_decision\test_catalyst_quality.py`（高质量反转 +3、中性 0~1、纯脉冲 -3、边界截断）
- [ ] H2 单元测试：`tests\test_fusion\test_tactical_override.py`（52W 过滤、Breakout 门控、`min_trigger=[]` 任意触发、CQS 仓位缩放、默认关闭行为）
- [ ] H3 时间线列：`build_signal_timeline` 输出含 `catalyst_score/catalyst_type/is_override/time_stop_weeks/override_run_weeks`
- [ ] H4 时间止损：试多连续周数 > CQS 上限时 `target=0`；周信号中断或季报披露更新后计数重置（01951 2024 波段实测 27 试多周中 18 周被归零、实际持有 9 周）
- [ ] H5 生产链路：`mtf_fusion_engine.py --stock 01951`（非 dry-run）写 `qcfp_mtf_decision` 含 `catalyst_score/catalyst_type/align_method`；`dss_report.py --stock 01951` 决策摘要显示 CQS，试多行仓位建议 = CQS 观察仓
- [ ] H6 触发器敏感性：`trigger_sensitivity.py` 输出 OFF/Breakout/B+P/B+P+C/ANY 五变体 CSV+JSON；OFF 的试多行数 = 0；默认 B+P+C 的 01951 波段收益 > 0
- [ ] H7 回测查询修复：`backtest_runner.py --stock 00700 --dry-run` 通过（V10 前因缺 `q_trend_score/q_position_52w/cbi_state` 报错）
- [ ] H8 全量回归：`run_all_tests.py` 全部通过（44 模块）
- [ ] H9（V11）移动止损引擎测试：`tests\test_backtest\test_engine.py::test_trailing_stop_exits_override_run`——试多持仓跌破建仓周最低价×0.98 后仓位归零，同段试多内不自动重进
- [ ] H10（V11）CQS 权重：趋势质量 ±2 → ±1（`test_catalyst_quality`：纯脉冲 -2→-1、边界 -3→-2、中性偏强 `time_stop_weeks is None`）
- [ ] H11（V11）行动标签：DSS/All-in-One 试多行显示"试多（TEST_BUY）"，DB `action_signal` 仍为 REDUCE
- [ ] H12（V11）回测重绑：`backtest_runner.py --stock 01951` 生成新 run_id（如 bt_20260824），01951 2024 年化为正（+4.64%），All-in-One 绑定新 run_id
- [ ] H13（V12）缓冲调参：`buffer_pct` 默认 0.05（settings.py 与 qcfp_settings.yaml 一致）；`trigger_sensitivity.py --buffers 0.02,0.05,0.08` 输出网格；全市场年化换手 < 2.0（实测最高 1.39）→ 维持 B+P+C 默认
- [ ] H14（V12）01951 单股：`backtest_runner.py --stock 01951` 2024 年化 +3.53%（buffer 5%）、MDD -2.53%；All-in-One 绑定 `bt_20260824_2`
- [ ] H15（V13）buffer 网格：`trigger_sensitivity.py --buffers 0.02,0.05,0.08,0.12` 输出 20 行 JSON/CSV + HTML；buffer=0.02 为 01951 波段最优（+7.31%）；默认 `buffer_pct` 回写 0.02
- [ ] H16（V13）回测重绑：01951 新 run_id=`bt_20260824_3`，2024 年化 +4.64%（Sharpe 0.85、MDD -2.18%）；All-in-One 绑定新 run_id；44 模块全量通过

## I. 日线战术层（L4，V14 新增）

- [ ] I1 单元测试：`tests\test_tactical\test_daily_tactical.py`（突破不早于窗口、flow_z PIT 前 20 日 NaN、状态合成顺序）
- [ ] I2 单元测试：`tests\test_fusion\test_daily_timing.py`（默认关闭不变、吸筹/突破→加仓、派发→减仓、回调→持有、WAIT→ENTER）
- [ ] I3 集成冒烟：`daily_tactical_engine.py --stock 00700 --dry-run` 退出码 0；全市场写 `qcfp_daily_tactical` 47,297 行
- [ ] I4 状态分布合理：NEUTRAL 36,093 / PULLBACK 8,345 / ACCUMULATION 1,874 / BREAKOUT 594 / DISTRIBUTION 391；flow_z 非空 19,831（2021+）
- [ ] I5 波段回放：`wave_replay.py --year 2024 --min-gain 0.5` 输出 14 个波段；01951 波段 +20% 节点四层均未识别；00268/03033 日线层最先识别
- [ ] I6 增量价值：`daily_alpha_test.py` 输出 Model A/B 对比；B 未过验收（波段捕捉提升 FAIL）→ `daily.timing.enabled=false` 默认
- [ ] I7 MFE/MAE：两模型 MFE 均值 21.96%、捕捉率 -73% → 退出机制为瓶颈（诊断结论）
- [ ] I8 报告：DSS/All-in-One 显示"战略 × 战术"行与"## 4.5 日线战术层"；快照含日线战术行；数据字典含 qcfp_daily_tactical
- [ ] I9 全量回归：`run_all_tests.py` 全部通过（46 模块）

## J. Correctness Hardening（V15 新增）

- [ ] J1 四概念语义：DSS 摘要显示 Action Signal=REDUCE / Tactical Override=True / Trade Intent=TEST_BUY（数据库 action_signal 不变）
- [ ] J2 战术覆盖全链路：`tests\test_decision\test_tactical_chain.py`（01951 场景 + DB 行一致性）通过
- [ ] J3 止损单一来源：`decision/stop_loss.py`；engine/DSS/All-in-One 同源；`trailing_stop.buffer_pct` 已移除
- [ ] J4 E2E 一致性：`tests\test_e2e\test_e2e_consistency.py`（State→Action→Target→Backtest→Report 全链断言）通过
- [ ] J5 RUN STATUS：`backtest_runner.py --stock 01951` summary 含 run_status（PASS_WITH_WARNING：披露 ESTIMATED + universe 缺失）与 cost_metrics（毛换手 1.87、成本 0.77%、成本/换手 0.41%、平均仓位 28.7%）
- [ ] J6 HTML 报告：含净值曲线 + 回撤曲线 + 滚动 12M Sharpe 三图
- [ ] J7 全量回归：`run_all_tests.py` 全部通过（48 模块）

## K. 口径修正与层级消融（V16 新增）

- [ ] K1 横截面语义：`cross_sectional.py` 的 turnover=毛换手、成本独立（不再 turnover=cost）
- [ ] K2 PIT 统一：Chip available_date 优先结构表披露日（data_pipeline 与 mtf_fusion_engine 一致）
- [ ] K3 止损语义：函数名 `_apply_entry_week_low_stop`；报告注明"周线收盘确认"
- [ ] K4 PIT 分级：run_status 含 pit_grade（PIT-A/PIT-C）；summary 含 config_hash/cost_model_version
- [ ] K5 层级消融：`layer_ablation_test.py` 输出四模型矩阵；Full 唯一 Sharpe 转正（+0.020）并捕捉 01951 波段（+7.31%）；试多周均 pnl +0.105%
- [ ] K6 不变量测试：`tests/test_backtest/test_invariants.py`（PIT/Position∈[0,1]/成本守恒/基准独立性）
- [ ] K7 决策卡：DSS 顶部显示 Strategic Regime=BEARISH（季度推导）、Tactical Opportunity=TEST_BUY
- [ ] K8 全量回归：`run_all_tests.py` 全部通过（49 模块）

## L. 回测完整性（V17 新增）

- [ ] L1 止损成交语义：`test_engine.py::test_trailing_stop_exits_override_run` 断言止损周
  `position_start=0.2`、`effective_return=stop/prev_close−1`、`pnl=position_start×effective_return−cost`
- [ ] L2 成本守恒（更新）：`test_invariants.py::test_cost_conservation` 使用 position_start/effective_return 精确一致
- [ ] L3 影响量化：Full Sharpe 0.020→0.014、01951 波段 7.31%→4.34%、2024 年化 4.64%→1.74%（修复后口径）
- [ ] L4 上下行捕获：`layer_ablation_test.py` 输出 upside/downside capture；Full 0.272/0.270（对称）
- [ ] L5 模型诊断页：All-in-One 含 `## 3.5 模型诊断（Layer Ablation）` 矩阵
- [ ] L6 全量回归：`run_all_tests.py` 全部通过（49 模块）

## M. 下行风险层（V18 新增）

- [ ] M1 MTF 兜底：BULLISH+任意阶段+Breakdown → BULLISH_WARNING（`test_00371_downtrend_exit::test_alignment_breakdown_now_warns`）
- [ ] M2 DES：`decision/downside_risk.py` 计算 des_score/des_band；权重可配置
- [ ] M3 风险下限：破位+close<MA20 → risk≥Extreme；8/21 情形 risk≠Low 且仓位单调不升
- [ ] M4 滞后解除：站回 MA20 + 连续 release_weeks 无破位才解除
- [ ] M5 DAILY_DECLINE：`qcfp_daily_tactical.d_decline` 生成；日线状态/flow 进入 DES
- [ ] M6 生产链路：`decision_engine.py` 回写 des_score/des_band；DSS 决策卡显示 DOWNTREND EVIDENCE
- [ ] M7 00371 金标准：6/19 EXIT/Extreme(DES=8)、6/26 EXIT/Extreme(DES=9)、8/21 EXIT/Extreme(DES=12)
- [ ] M8 全量回归：`run_all_tests.py` 全部通过（50 模块）

---

## 验收标准

- 必备：A1、B1~B5、C1~C5、D1~D4、E1~E2、F1~F4、G1~G3；
- 可选：A2~A3、E3；
- 说明：F2/F3 属结果性发现（默认参数下策略为负收益），验收的是系统正确性而非策略盈利性；校准参数仅作建议，是否启用由人工决定。
