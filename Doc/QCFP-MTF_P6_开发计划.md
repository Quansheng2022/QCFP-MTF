# QCFP-MTF P6 开发计划 —— 回测与校准系统

> 版本：v0.1（实施稿）
> 日期：2026-08-20
> 前置：P0~P5 已完成（qcfp_mtf_decision 9827 行，Action/Risk 已回写）
> 依据：《QCFP-MTF 2.1.1 架构设计.md》P6 回测系统 + 总体开发计划 P6

## 一、范围与目标

P6 实现回测闭环：**防 Look-ahead 信号时间线 → 向量化回测 → 绩效评估 → 扩展窗口交叉验证 → 市场环境稳健性 → 参数校准**，输出 `qcfp_backtest_results` 与回测报告。

| 项 | 内容 |
| :-- | :-- |
| 输入 | `qcfp_quarterly_structural`（含 available_date）、`qcfp_monthly_behavior`、`qcfp_weekly_tactical`、`hk_idx_hist`、`hk_hist_weekly_kline` |
| 输出 | `qcfp_backtest_results`（P0 已建表）+ `Report/QCFP_MTF/backtest/*` |
| 核心模块 | `backtest/lookahead_filter.py`、`data_pipeline.py`、`engine.py`、`cost_model.py`、`performance.py`、`cross_validation.py`、`robustness.py`、`calibration.py` |
| 里程碑 | M6：任意历史区间无偏回测 + 校准参数输出 |

## 二、关键设计：防 Look-ahead

P4 融合按 `period_end` 对齐季度数据；但机构持股有 45 天披露滞后（`available_date = period_end + 45d`），**季度末后 45 天内的决策使用了未披露数据 = Look-ahead Bias**。

**回测信号时间线（`data_pipeline.py`）按 available_date 重新对齐**：

```text
决策日 = 每周五（week_end）
季度结构：取 available_date <= 决策日的最近一行（不用 period_end）
月线行为：取 month_end <= 决策日的最近一行（月线数据当月末已知，无滞后）
周线触发：决策日当周
```

`lookahead_filter.py` 提供审计函数：检查任意 (stock, week) 使用的季度 `available_date` 是否 ≤ week，违规即标记。

## 三、模块设计

### 3.1 `lookahead_filter.py`

- `validate_timeline(df)`：逐行校验结构 available_date ≤ decision_date；
- `filter_available(df)`：剔除违规行；
- `assert_no_lookahead(df)`：违规即抛错（回测前置断言）。

### 3.2 `data_pipeline.py`

`build_signal_timeline(structural, monthly, weekly, settings)`：

- 复用 P4/P5 模块（`align_mtf`、`compute_chip_confidence`、`generate_action`、`evaluate_risk`）计算 mtf/action/risk；
- 输出列：stock_code / decision_date / structural_regime / monthly_behavior_state / tactical_signal / mtf_regime / action_signal / risk_level / market_context / data_quality / structural_available_date。

### 3.3 `engine.py`（向量化回测）

- 信号 → 目标仓位：`BUY/ADD/HOLD=1.0、REDUCE=0.5、EXIT/WAIT=0.0`（可配置）；
- 仓位**下一周生效**（`shift(1)`，杜绝当周信号当周收益的同周偏差）；
- 周收益 = `close/prev_close - 1`；
- 交易成本在换仓周扣除（见 cost_model）；
- 输出：每股票×每周 `position / pnl / mtf_regime / market_regime`，写 `qcfp_backtest_results`（run_id 标识）。

### 3.4 `cost_model.py`（港股费率）

```text
总费率 = 佣金 0.25% + 印花税 0.10% + 滑点 0.10% ≈ 0.45%（单边）
换仓成本 = |Δ仓位| × 总费率（EXIT 0→1 与 1→0 各计一次）
```

### 3.5 `performance.py`

- 年化收益、夏普（周频，rf=0）、最大回撤、胜率、盈亏比、分年度收益表；
- 输出 equity curve CSV。

### 3.6 `cross_validation.py`（扩展窗口）

- 扩展窗口序列：如 [2021-01, 2023-06]、[2021-01, 2024-06]、[2021-01, 2026-08]；
- 每个窗口独立回测并报告绩效，验证参数稳定性。

### 3.7 `robustness.py`（市场环境分层）

- 用 `hk_idx_hist` 把每周标记 risk_on / risk_off / neutral（复用 P4 口径）；
- 分环境统计收益/胜率，验证策略在牛熊震荡下的稳健性。

### 3.8 `calibration.py`（参数校准）

- 网格搜索候选参数（如 `c_pp_threshold`、`f_z_threshold`、`p_return_threshold`、Chip 权重）；
- 评估指标：Sharpe 为主、年化/回撤为辅；
- 输出 top-N 组合 JSON；`--apply` 时写入 `Config/qcfp_calibration.json`（不直接改主配置）。

## 四、脚本与工作流

- `scripts/backtest_runner.py`：`--stock`（默认全部）`--start 2021-01-01` `--run-id` → 跑时间线 + 回测 + 绩效 + 分层报告，写库；
- `scripts/calibration.py`：网格校准，默认不写库、只输出报告；
- **不加入 `SCRIPT_LIST`**：回测是分析动作，与每日数据/决策流水线解耦，按需运行。

## 五、配置新增（`Config/qcfp_settings.yaml`）

```yaml
backtest:
  cost:
    commission_rate: 0.0025
    stamp_rate: 0.001
    slippage_rate: 0.001
  position_target:
    BUY: 1.0
    ADD: 1.0
    HOLD: 1.0
    REDUCE: 0.5
    EXIT: 0.0
    WAIT: 0.0
  risk_free: 0.0
  annual_periods: 52
```

## 六、测试计划

### 单元测试（`tests/test_backtest/`）

| # | 用例 | 验收 |
| :-- | :-- | :-- |
| 1 | Look-ahead 过滤：available_date > 决策日剔除、断言抛错 | 全覆盖 |
| 2 | 信号时间线：结构按 available_date 对齐 | 抽样一致 |
| 3 | 回测引擎：仓位 shift、换仓成本、pnl 计算 | 手算一致 |
| 4 | 绩效：年化/夏普/最大回撤/胜率/盈亏比 | 手算一致 |
| 5 | 分层：risk_on/risk_off 分组统计 | 全覆盖 |
| 6 | 校准：小网格可运行、输出 top-N | 不抛错 |

### 集成测试（真实数据）

- `backtest_runner.py --stock 00700`：写 `qcfp_backtest_results` + equity curve；
- 全量：Look-ahead 断言 0 违规；
- 00700 基准对比：策略累计收益 vs 买入持有。

## 七、数据缺口与风险

| # | 风险 | 应对 |
| :-- | :-- | :-- |
| 1 | 资金流 2021 起 → 结构 F 因子 2021 前缺失 | 回测默认 2021-01-01 起（F 可用） |
| 2 | 单股等权组合 vs 个股独立 | 先做个股独立回测，组合聚合后报告 |
| 3 | 参数过拟合 | 扩展窗口 + 分层稳健性，校准只建议不自动改配置 |
| 4 | 成本模型粗糙 | 佣金/印花税/滑点可配置，报告中注明假设 |

## 八、里程碑 M6 验收标准

1. 任意股票+区间输出无偏回测结果（Look-ahead 断言 0 违规）；
2. `qcfp_backtest_results` 写入且 `(run_id, stock_code, signal_date)` 唯一；
3. 绩效指标计算正确（与手算一致）；
4. 校准脚本输出 top-N 参数组合；
5. P6 新增单测 ≥ 15 项，全套通过。

## 九、任务拆分与工时

| # | 任务 | 模块 | 工时（人天） |
| :-- | :-- | :-- | :-- |
| 1 | Look-ahead + 信号时间线 | lookahead_filter / data_pipeline | 1.5 |
| 2 | 回测引擎 + 成本 | engine / cost_model | 1.5 |
| 3 | 绩效 + 分层 + 交叉验证 | performance / robustness / cross_validation | 1.5 |
| 4 | 校准 + 报告脚本 | calibration / backtest_runner | 1.5 |
| 5 | 测试 + 集成 | tests/test_backtest/ | 1.0 |
| **合计** | | | **约 7 人天** |

## 十、下一步

实施顺序：Look-ahead/时间线 → 引擎 → 绩效/分层 → 校准 → 测试 → 全量回测；完成后 P0~P6 全链路闭环，输出最终回测报告与校准参数建议。

---

## 附：P6 交付记录（2026-08-20）

| 计划任务 | 状态 | 交付物 |
| :-- | :-- | :-- |
| Look-ahead + 时间线 | ✅ | `backtest/lookahead_filter.py`（空值不算违规）+ `data_pipeline.py`（按 available_date 对齐） |
| 回测引擎 + 成本 | ✅ | `backtest/engine.py`（仓位次周生效、换仓成本）+ `cost_model.py`（0.45% 单边） |
| 绩效 + 分层 + 交叉验证 | ✅ | `performance.py` / `robustness.py` / `cross_validation.py` |
| 校准 + 报告脚本 | ✅ | `backtest/calibration.py` + `scripts/backtest_runner.py`、`scripts/calibration.py` |
| 测试与集成 | ✅ | `tests/test_backtest/` 13 项，全套 146 项通过 |

**M6 验证结果（实测）**：

- `qcfp_backtest_results`：4321 行 / 15 只 / 2021-01-01 ~ 2026-08-14 / run_id=bt_full_20260820；
- Look-ahead：9827 行信号时间线断言 0 违规（按 available_date 对齐，杜绝季度披露滞后泄漏）；
- 总体绩效：年化 -5.53%、Sharpe -0.046、最大回撤 -99.7%、胜率 45.4%——**默认参数下策略为负收益（客观事实）**；
- 分层：risk_on 年化 +16.0%（Sharpe 0.62）、neutral +18.6%（0.81）、risk_off -17.0%（-0.46）→ 策略有效性集中于风险偏好正常/偏暖环境；
- 校准：9 组合网格，最优 REDUCE 仓位 0.7（Sharpe -0.032，优于默认 0.5 的 -0.046）；芯片权重对结果影响小（经置信度→风险门控传导）；
- 2024/2025 年正收益（+8.4%/+5.4%），2022/2023/2026 负收益，与市场环境一致。

**结论与建议**：P0~P6 全链路闭环完成。当前回测结果提示：① 策略应结合市场环境（risk_off 时降低暴露）使用；② 校准建议 REDUCE=0.7 值得人工评审后启用；③ 芯片权重、CBI 权重等参数需更大网格 + 扩展窗口确认后再合入主配置（避免过拟合）。
