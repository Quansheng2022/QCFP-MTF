# QCFP-MTF 2.1.1 开发计划（基于 TA_Workflow 现有数据底座）

> **文档维护说明（2026-08-25）**：本文件为 2.1.1 基线开发计划，V10~V29 的演进记录
> 已沉淀于此（历史留档）。**自 V28 起，版本演进统一维护在《QCFP-MTF 2.2_开发计划.md》**
> （本目录同组文件），2.1.1 文档冻结为历史基线，不再追加新版本记录。

> 版本：v0.1（评审稿）
> 日期：2026-08-19
> 依据：《QCFP-MTF 2.1.1 架构设计.md》（已冻结）
> 目标：在 TA_Workflow 现有 SQLite 原始数据之上，落地「季度筹码-资金-价格 三维多时间周期框架」分析系统

---

## 一、结论速览

### 1.1 新系统目录位置

**建议：放在 `PROJECT ROOT\Core\QCFP_MTF`（下划线），完全合适。**

理由：

1. 该框架是跨周期系统（季度结构 + 月线阶段 + 周线触发），不属于现有 `Core/Daily`、`Core/Weekly`、`Core/Monthly`、`Core/Quarterly` 中任何单一周期，独立成目录符合"单步单职责 + 周期×步骤"的项目结构；
2. 沿用项目四层组织：入口脚本放根目录（`run_QCFP_MTF_workflow.py`），业务脚本放 `Core/QCFP_MTF`，共享工具继续收口在 `Core/utl`，配置放 `Config`，产物写 `Report/Prompt/Log/Temp`；
3. 目录名建议用下划线 `QCFP_MTF` 而非连字符 `QCFP-MTF`：Windows 文件夹两者皆可，但 Python 包导入（`from QCFP_MTF.structural import ...`）不支持连字符；对外文档、入口脚本名、`model_version`（`QCFP-MTF-2.1.1`）仍保留连字符标识。

### 1.2 数据底座审计结论（2026-08-19 实测）

| 数据表 | 行数 | 股票数 | 时间范围 | 结论 |
| :--- | :--- | :--- | :--- | :--- |
| `hk_hist_daily_kline` | 46,312 | 15 | 2010-01-04 ~ 2026-08-19 | 完整，turnover/amount/volume 无缺失 |
| `hk_hist_daily_moneyflow` | 19,876 | 15 | 2021-02-03 ~ 2026-08-19 | 仅 2021 起 |
| `hk_idx_hist` | 2,860 | — | 2015-01-02 ~ 2026-08-19 | 大盘环境/回测分层可用 |
| `hk_hist_institutional_holdings` | 944 | 14 | 2004/Q1 ~ 2026/Q2 | A 级筹码唯一来源，14 只 |
| `hk_hist_weekly_kline` | 9,827 | 15 | 2010-01-08 ~ 2026-08-14 | 完整 |
| `hk_hist_weekly_moneyflow` | 4,229 | 15 | 2021-02-05 ~ 2026-08-14 | 仅 2021 起 |
| `hk_hist_monthly_kline` | 2,267 | 15 | 2010-01-31 ~ 2026-07-31 | 完整（close 有 7 条缺失） |
| `hk_hist_monthly_moneyflow` | 1,000 | 15 | 2021-02-01 ~ 2026-07-31 | 仅 2021 起 |
| `hk_hist_quarterly_kline` | 752 | 15 | 2010-03-31 ~ 2026-06-30 | 完整 |
| `hk_hist_quarterly_moneyflow` | 324 | 15 | 2021-03-31 ~ 2026-06-30 | 仅 2021 起 |

**关键发现**：

1. `stock_list.json` 含 17 只，但日/周/月/季 K 线仅 15 只（缺 `00579`、`02602`）；机构持股仅 14 只（`03033` ETF 无机构数据）。计划中按"缺失即降级"处理；
2. 已有季度分析表 `hk_quarterly_institutional_holdings_analysis`、`hk_quarterly_chip_analysis`（由 `Core/Quarterly` TA4C/TA4D 产出）已实现 QCFP 1.x 的 C/F/P 方向、背离与 Regime，**新系统应作为 L2 事实层直接复用，不重复造轮子**；
3. 规格书要求的 `available_date`（机构持股真实披露日）目前表内没有，只有 `period_text`（`2026/Q2`）与 `update_time`——这是必须解决的数据缺口，见 §8；
4. 资金流表只有大/中/小单与资金趋势，机构/散户净流入需沿用现有 IDR/FBI 派生逻辑（`hk_quarterly_chip_analysis` 已有 `institutional_flow`/`individual_flow`/`idr`/`fbi`）。

---

## 二、与现有系统的关系（复用清单）

| 能力 | 现有资产 | 新系统用法 |
| :--- | :--- | :--- |
| 配置/路径 | `Core/utl/stock_analysis_utl.py`、`GlobalConfig` | 直接复用 |
| 股票列表 | `Core/utl/stock_list_loader.py` + `Config/stock_list.json` | 直接复用 |
| 季度筹码事实 | `hk_quarterly_institutional_holdings_analysis`（qoq/yoy/4q 变化、迁移、集中度） | L2 Fact 输入 |
| 季度 C/F/P 联合 | `hk_quarterly_chip_analysis`（chip_direction/flow_direction/price_direction、Regime、integrated_score） | 校验基准 + 部分因子来源 |
| 资金流派生 | `hk_*_moneyflow_analysis`（institutional_flow/individual_flow/idr/fbi） | F 因子输入 |
| 数据字典 | `Config/*_dictionary.*` 全套生成脚本 `Code_utl/Generate_*_Dictionary.py` | 新表沿用同规范 |
| 报告/日志 | `Report/`、`Log/`、reportlab + Windows 中文字体 | 沿用 |

**边界约定**：

- 新系统只读现有 hist/analysis 表，不改写；写 `qcfp_*` 新表；
- 入口 `run_QCFP_MTF_workflow.py` 启动时校验前置表是否有数据，缺失则提示先运行 `run_Quarterly_TA_workflow.py` 与 `run_Daily_TA_workflow.py`；
- 新系统与 `Core/Quarterly` 的关系：Quarterly 是"季度单周期分析"，QCFP_MTF 是"季度定结构 + 月线定阶段 + 周线定时机的跨周期决策系统"，两者并存、互不覆盖。

---

## 三、目录结构（落地版）

```text
TA_Workflow/
├── run_QCFP_MTF_workflow.py            # 入口编排（仿 run_Quarterly_TA_workflow.py）
├── Core/
│   └── QCFP_MTF/                       # 新系统（下划线目录名）
│       ├── common/                     # 共享：logger、sqlite 读写、日期、标准化工具
│       ├── config/                     # qcfp_settings.yaml（权重/阈值/开关，可回测校准）
│       ├── data/                       # 数据加载与质量
│       │   ├── loader.py               # 从现有表加载并标准化
│       │   ├── quality.py              # data_quality A/B/C/D
│       │   └── evidence.py             # 证据等级 A/A-/B/C/D 静态映射 + 动态判定
│       ├── structural/                 # P1 季度结构引擎（Layer 1）
│       │   ├── chip_factors.py         # C 因子（复用机构持股分析表）
│       │   ├── flow_factors.py         # F 因子（复用资金流分析 + IFA Z-Score）
│       │   ├── price_factors.py        # P 因子（季度收益/Trend Score/52W 位置）
│       │   ├── structural_regime.py    # FSM-1（6 状态 + Core Score）
│       │   └── divergence.py           # CPD/FPD/CFD 背离
│       ├── behavioral/                 # P2 月线行为引擎（Layer 2）
│       │   ├── turnover_factors.py     # 换手 Z-Score/百分位/T1~T5
│       │   ├── volume_factors.py       # 量加速度/量比
│       │   ├── vp_matrix.py            # 9 种 VP_Regime
│       │   ├── cbi.py                  # CBI（Winsorize→Z→0~100→加权）
│       │   ├── cost_position.py        # 周/月/季 VWAP 成本位置
│       │   └── monthly_stage.py        # Improving/Stable/Deteriorating
│       ├── tactical/                   # P3 周线战术引擎（Layer 3）
│       │   ├── weekly_volume.py        # 放量/缩量检测
│       │   ├── weekly_turnover.py      # 换手偏离/极端换手
│       │   ├── weekly_vwap.py          # 周 VWAP 偏离
│       │   └── weekly_signal.py        # Breakout/Pullback/Consolidation/Breakdown
│       ├── fusion/                     # P4 多周期融合层（Layer 4）
│       │   ├── chip_confidence.py      # Chip Stability Confidence（60/40 可配置）
│       │   ├── mtf_alignment.py        # 硬编码对齐矩阵（12 条映射）
│       │   ├── mtf_fsm.py              # FSM-2（5 状态转换）
│       │   └── anti_inference.py       # 禁止推断过滤器
│       ├── decision/                   # P5 DSS 决策层（Layer 5）
│       │   ├── score_calculator.py     # State-First 评分
│       │   ├── action_generator.py     # 单向门控 Action
│       │   ├── risk_evaluator.py       # 风险等级
│       │   ├── dss_output.py           # JSON 协议
│       │   └── report_generator.py     # 个股 PDF/Markdown 报告
│       ├── backtest/                   # P6 回测与校准
│       │   ├── lookahead_filter.py     # available_date 防偏
│       │   ├── engine.py               # 回测引擎（pandas 向量化先行）
│       │   ├── cost_model.py           # 港股费用模型
│       │   ├── performance.py          # 绩效评估
│       │   ├── calibration.py          # 参数寻优
│       │   └── robustness.py           # 牛熊/震荡分层验证
│       └── tests/                      # 单元/集成测试（与模块一一对应）
└── Config/
    ├── qcfp_settings.yaml              # 新系统配置（权重、阈值、开关）
    └── qcfp_*_dictionary.json/md/xlsx  # 新表数据字典（沿用生成脚本）
```

> 注：规格书建议 PostgreSQL + YAML + Loguru + VectorBT；本项目落地时**保持 SQLite + INI/YAML + 项目自有日志/报告体系**，回测先用 pandas 向量化实现，性能不足再引入 VectorBT。此差异属于"工程实现适配"，不改变架构。

---

## 四、数据库新增表设计（`SQLiteDB/HK_Stock.db`）

按规格书建 5 张表，均加 `model_version`、`data_quality`、`update_time`，索引 `(stock_code, 周期末日期)` 唯一：

| 表 | 关键字段 | 数据来源映射 |
| :--- | :--- | :--- |
| `qcfp_quarterly_structural` | period_end、available_date、inst_ownership_pct_chg、holder_quantity_chg_pct、inst_participation_chg、q_inst_flow_raw、q_inst_flow_z、q_ifa_zscore、q_return、q_trend_score、q_position_52w、c_state/f_state/p_state、structural_regime、core_score | holder_pct_qoq_pp、holder_quantity_qoq_pct、institution_quantity_qoq_pct（来自 `hk_quarterly_institutional_holdings_analysis`）；institutional_flow/idr/fbi（来自 `hk_quarterly_chip_analysis`）；close/change_percent（来自 `hk_hist_quarterly_kline`） |
| `qcfp_monthly_behavior` | month_end、m_turnover_zscore、m_turnover_pctl、m_turnover_ma_ratio、m_volume_ma_ratio、m_volume_accel、m_vwap_deviation、m_vp_regime、turnover_liquidity_regime、monthly_behavior_state | `hk_hist_monthly_kline`（turnover_rate/volume/amount/amplitude/close） |
| `qcfp_weekly_tactical` | week_end、w_turnover_deviation、w_turnover_spike、w_volume_breakout、w_vwap_deviation、w_ma_slope、w_breakout、w_breakdown、tactical_signal | `hk_hist_weekly_kline` |
| `qcfp_mtf_decision` | decision_date、structural_regime、monthly_behavior_state、tactical_signal、cbi_score、cost_position、chip_stability_confidence、mtf_regime、qcfp_score、action_signal、risk_level、market_context | 三层引擎输出 + `hk_idx_hist`（HSI/HSTECH/VHSI/SouthboundFlow 派生大盘环境） |
| `qcfp_backtest_results` | stock_code、signal_date、action、position、pnl、market_regime 等 | 回测引擎输出 |

**实现约定**：

- 新增表必须同步生成数据字典（`Code_utl/Generate_*_Dictionary.py` 模板）；
- `period_end`/`month_end`/`week_end` 采用 `YYYY-MM-DD`；
- 机构持股无真实披露日时，`available_date` 先采用「季度末 + 固定披露滞后天数」配置化推算（默认 45 天），并在 `data_quality` 中降级为 B/C，同时在字典与报告中明确标注"推算值"。

---

## 五、开发阶段计划（P0 ~ P6）

### P0：基础设施与数据层（约 4~5 天）

| # | 任务 | 子模块 | 输入/产出 | 验收 |
| :--- | :--- | :--- | :--- | :--- |
| 0.1 | 建目录与入口脚本 | `Core/QCFP_MTF/` + `run_QCFP_MTF_workflow.py` | 目录结构 + 编排脚本 | 可顺序执行空流程 |
| 0.2 | 建 5 张 `qcfp_*` 表 + 索引 | SQL 脚本（沿用 `create_hk_stock_info.sql` 风格） | `HK_Stock.db` 新增表 | `SELECT` 正常 |
| 0.3 | 配置管理 | `Config/qcfp_settings.yaml` + 写入 `stock_data_analysis.par` 的 `[QCFP_MTF]` 节 | 权重/阈值/开关可读 | 配置热更新 |
| 0.4 | 数据加载器 | `data/loader.py` | 现有 10 张 hist/analysis 表 → 标准化 DataFrame | 单股全周期数据可加载 |
| 0.5 | 数据质量检测 | `data/quality.py` | A/B/C/D 标签 | 全部股票可出标签 |
| 0.6 | 证据等级标注 | `data/evidence.py` | 因子 → A/A-/B/C/D | 静态表 + 动态判定 |
| 0.7 | 港股日历与周期对齐 | `common/calendar.py` | 日→周→月→季切分对齐 | 周期边界正确 |
| 0.8 | 覆盖度审计脚本 | `scripts/audit_coverage.py` | 每股票×每表覆盖报告 | 输出缺口清单 |

**里程碑 M0**：任意股票可输出 `data_quality` 标签 + 覆盖度报告。

### P1：季度结构引擎（约 5~6 天）

> P1 详细计划见 [QCFP-MTF_P1_开发计划.md](QCFP-MTF_P1_开发计划.md)。

| # | 任务 | 子模块 | 说明 |
| :--- | :--- | :--- | :--- |
| 1.1 | C 因子 | `structural/chip_factors.py` | `inst_ownership_pct_chg`、`holder_quantity_chg_pct`、`inst_participation_chg` → `c_state`（阈值可配置） |
| 1.2 | F 因子 | `structural/flow_factors.py` | 季度资金流聚合 + IFA Z-Score → `f_state` |
| 1.3 | P 因子 | `structural/price_factors.py` | 季度收益、Trend Score（季末快照窗口）、52W 位置 → `p_state` |
| 1.4 | FSM-1 | `structural/structural_regime.py` | C/F/P → 6 状态 + Core Score（State-First） |
| 1.5 | 背离检测 | `structural/divergence.py` | CPD/FPD/CFD Z-Score 偏离 |
| 1.6 | 单元测试 | `tests/test_structural/` | 状态转换全覆盖，含 8 条规格书转换规则 |

**里程碑 M1**：输入任意股票，输出 `structural_regime` + `core_score` + 背离信号，并与 `hk_quarterly_chip_analysis.chip_flow_price_regime` 交叉验证一致性。

### P2：月线行为引擎（约 5~6 天）

| # | 任务 | 子模块 | 说明 |
| :--- | :--- | :--- | :--- |
| 2.1 | 换手因子 | `behavioral/turnover_factors.py` | 月换手 Z-Score/52W 百分位/MA6 比值 → T1~T5 |
| 2.2 | 量因子 | `behavioral/volume_factors.py` | 量加速度、量比 |
| 2.3 | 量价矩阵 | `behavioral/vp_matrix.py` | 9 种 VP_Regime（含 `VP_STABLE_ASCENT`） |
| 2.4 | CBI | `behavioral/cbi.py` | **严格** Winsorize(1%~99%)→Z-Score→0~100→加权（30/30/25/15，权重可配置） |
| 2.5 | Cost Position | `behavioral/cost_position.py` | 周/月/季 VWAP（amount/volume）偏离 + 三周期综合 |
| 2.6 | 月线阶段 | `behavioral/monthly_stage.py` | Improving/Stable/Deteriorating |
| 2.7 | 单元测试 | `tests/test_behavioral/` | CBI 标准化、VWAP 剥离、Stage 判定 |

**里程碑 M2**：输出 `CBI_Score`、`Cost_Position`、`Monthly_Stage`。

### P3：周线战术引擎（约 3 天）

| # | 任务 | 子模块 | 说明 |
| :--- | :--- | :--- | :--- |
| 3.1 | 周量检测 | `tactical/weekly_volume.py` | 放量突破（>MA20×1.8）/ 极度缩量（<MA20×0.5） |
| 3.2 | 周换手检测 | `tactical/weekly_turnover.py` | 偏离度 vs 季度周均、极端换手（>MA8×2.0） |
| 3.3 | 周 VWAP | `tactical/weekly_vwap.py` | close/VWAP_W−1 |
| 3.4 | 均线结构 | `tactical/weekly_signal.py` | 5/10/20 周 MA 斜率（二阶差分） |
| 3.5 | 信号合成 | `tactical/weekly_signal.py` | Breakout/Pullback/Consolidation/Breakdown |
| 3.6 | 单元测试 | `tests/test_tactical/` | 阈值与信号合成，防误触发 |

**里程碑 M3**：输出 `tactical_signal` + `w_breakout`/`w_breakdown` 布尔标记。

### P4：多周期融合层（约 4~5 天）

| # | 任务 | 子模块 | 说明 |
| :--- | :--- | :--- | :--- |
| 4.1 | 筹码稳定置信度 | `fusion/chip_confidence.py` | 60%×Quarterly_Chip_Score + 40%×CBI_Normalized（权重可配置）→ High/Medium/Low |
| 4.2 | 多周期对齐 | `fusion/mtf_alignment.py` | 规格书 12 条映射矩阵硬编码实现（含"禁止越权"两铁律） |
| 4.3 | FSM-2 | `fusion/mtf_fsm.py` | State(t)+Event(t)→State(t+1) |
| 4.4 | 禁止推断过滤 | `fusion/anti_inference.py` | 规则表驱动：扫描结论文本，触发即降级为允许表述（先用"警告+降级"模式） |
| 4.5 | 结构-行为背离 | `fusion/mtf_alignment.py` | 季度强势+月线恶化 / 季度弱势+月线改善 → 背离标记 |
| 4.6 | 集成测试 | `tests/test_fusion/` | 三层输入 → MTF Regime → 置信度 → 防推断全链路 |

**里程碑 M4**：输出 `mtf_regime` + `chip_stability_confidence`，两铁律用例（STRUCTURAL_BULLISH+Breakdown→BULLISH_WARNING 等）全部通过。

### P5：DSS 决策层（约 3~4 天）

| # | 任务 | 子模块 | 说明 |
| :--- | :--- | :--- | :--- |
| 5.1 | 评分 | `decision/score_calculator.py` | State-First：由 MTF Regime 映射 0~100 分 |
| 5.2 | Action | `decision/action_generator.py` | BUY/ADD/HOLD/REDUCE/EXIT/WAIT，单向门控（DECLINE/DISTRIBUTION 禁止 BUY/ADD；BULLISH 下 Breakdown 只给 REDUCE/HOLD） |
| 5.3 | 风险 | `decision/risk_evaluator.py` | Low/Medium/High/Extreme（背离 + 状态位置 + 数据质量） |
| 5.4 | DSS 输出 | `decision/dss_output.py` | 与规格书第七章 JSON 协议一致（含 evidence_summary、anti_inference_check、stop_loss_trigger） |
| 5.5 | 报告 | `decision/report_generator.py` | JSON → 个股 Markdown/PDF（沿用 reportlab + 中文字体方案） |
| 5.6 | 端到端测试 | `tests/test_e2e.py` | 单股全流程 |

**里程碑 M5**：输入股票代码+日期 → 完整 DSS JSON + 可读报告。

### P6：回测与校准（约 5~6 天）

| # | 任务 | 子模块 | 说明 |
| :--- | :--- | :--- | :--- |
| 6.1 | 防 Look-ahead | `backtest/lookahead_filter.py` | 强制按 `available_date` 切片，`period_end` 仅作展示 |
| 6.2 | 回测引擎 | `backtest/engine.py` | pandas 向量化回测（先实现），港股成本模型（佣金+滑点+印花税） |
| 6.3 | 绩效评估 | `backtest/performance.py` | 年化、夏普、最大回撤、胜率、盈亏比、分年度 |
| 6.4 | 扩展窗口交叉验证 | `backtest/calibration.py` | Expanding Window，避免全历史单次优化过拟合 |
| 6.5 | 参数校准 | `backtest/calibration.py` | CBI 权重、Chip Confidence 权重、Z-Score/百分位阈值网格搜索，回写 `qcfp_settings.yaml` |
| 6.6 | 稳健性 | `backtest/robustness.py` | 用 `hk_idx_hist`（HSI 趋势/波动）划分牛/熊/震荡环境分别回测 |
| 6.7 | 回测报告 | `Report/QCFP_MTF/backtest/` | 收益曲线、状态分布、参数敏感性 |

**里程碑 M6**：任意历史区间无偏回测 + 校准参数回写。

---

## 六、关键实现决策

1. **层级不可越权（最高宪法）**：在 `fusion/mtf_alignment.py` 用规格书 12 条映射矩阵 + 显式"禁止输出"断言实现，不允许用加权打分替代状态映射；
2. **State-First, Score-Second**：`score_calculator` 只做"状态→分数"查表，任何地方不得"先算分再推状态"；
3. **证据等级与数据质量双门禁**：任一关键因子为 D 级时该周期不产生决策信号，仅输出 `DATA_INSUFFICIENT`；
4. **Anti-Inference 先"警告+降级"后"阻断"**：初期不直接阻断输出，记录违规案例，积累后再收紧；
5. **权重与阈值全部配置化**：进 `qcfp_settings.yaml`，默认用规格书值，P6 回测校准后回写；
6. **复用优先**：能读现有分析表就不重算，重算时必须与现有表交叉验证（如季度 Regime 与 `hk_quarterly_chip_analysis` 对比）；
7. **版本可复现**：每张结果表带 `model_version`，运行日志记录 `qcfp_settings.yaml` 内容快照。

---

## 七、数据缺口与风险清单

| # | 缺口/风险 | 影响 | 应对 |
| :--- | :--- | :--- | :--- |
| 1 | 机构持股无真实披露日（`available_date` 缺失） | 回测存在 Look-ahead 风险 | 配置化披露滞后天数推算 + `data_quality` 降级标注；后续补充披露日历 |
| 2 | 资金流数据仅 2021 年起 | 季度 F 因子历史长度不足 | 回测区间以 2021 起为准；更早区间仅用 C/P 并标注数据质量 |
| 3 | `03033`（ETF）无机构持股；`00579`、`02602` 无行情 | 覆盖不全 | 覆盖度审计自动降级，ETF 可配置排除出结构引擎 |
| 4 | 月线 close 有 7 条缺失 | CBI/成本位置轻微失真 | 缺失月份剔除/前值填充，标注 B 级 |
| 5 | 机构/散户资金流为派生值（IDR/FBI），非原始拆分 | F 因子属 A-/B 级证据 | 证据等级按派生来源标注，报告中注明 |
| 6 | 换手率口径（自由流通股本变化） | 长期 T 状态可比性 | 使用分位数与 Z-Score 缓释，不做绝对阈值 |
| 7 | Anti-Inference 规则文本匹配 | 报告生成质量 | 规则表 JSON 化，先警告后阻断，迭代案例库 |
| 8 | 回测参数过拟合 | 校准失真 | 扩展窗口交叉验证 + 牛熊/震荡分层稳健性测试 |

---

## 八、里程碑与工时汇总

| 阶段 | 内容 | 预计工时（人天） |
| :--- | :--- | :--- |
| P0 | 基础设施与数据层 | 4~5 |
| P1 | 季度结构引擎 | 5~6 |
| P2 | 月线行为引擎 | 5~6 |
| P3 | 周线战术引擎 | 3 |
| P4 | 多周期融合层 | 4~5 |
| P5 | DSS 决策层 | 3~4 |
| P6 | 回测与校准 | 5~6 |
| **合计** | | **约 29~35 人天（约 6~7 周，1 人全职）** |

> 相比规格书 54 人天，因直接复用现有季度分析表、utl 与字典体系，预计节省约 1/3 工时。

---

## 九、测试策略

- 单元测试：每个模块 1 个测试文件，`tests/` 与模块目录一一对应；
- 关键断言用例（必须覆盖）：
  - `STRUCTURAL_BULLISH + Breakdown → BULLISH_WARNING`（严禁 BEARISH_CONFIRMED）；
  - `STRUCTURAL_DECLINE + Breakout → BEARISH_RECOVERY_CANDIDATE`（严禁 BULLISH_CONFIRMED）；
  - `data_quality = D → 无决策信号`；
  - CBI 标准化流程（Winsorize 边界、0~100 域）；
  - Anti-Inference 表全规则回归；
  - 回测 look-ahead 检测（人为注入未来数据应被拦截）。
- 集成测试：P4 与 P5 各一次端到端；P6 结束后全量回归。

---

## 十、下一步行动（建议顺序）

1. 确认目录方案（`Core/QCFP_MTF`）与本计划；
2. 启动 P0：建目录、建表、写数据加载器与覆盖度审计脚本（产出 M0）；
3. 并行调研：确认机构持股披露日历 / 补 `available_date` 的数据源（Longbridge/CCASS 备选）；
4. P1~P3 按依赖顺序推进，每阶段完成即跑测试与里程碑验证；
5. 全部阶段完成后，输出首份个股 QCFP-MTF 报告并进入回测校准。

---

## 附：P0 交付记录（2026-08-19）

| 计划任务 | 状态 | 交付物 |
| :--- | :--- | :--- |
| 0.1 建目录与入口脚本 | ✅ | `Core/QCFP_MTF/`（common/config/data/structural/behavioral/tactical/fusion/decision/backtest/scripts/tests/sql）+ `run_QCFP_MTF_workflow.py` |
| 0.2 建 5 张表 + 索引 | ✅ | `sql/create_qcfp_tables.sql`，6 张 `qcfp_*` 表已建入 `SQLiteDB/HK_Stock.db`（含审计快照表） |
| 0.3 配置管理 | ✅ | `Config/qcfp_settings.yaml` + `stock_data_analysis.par [QCFP_MTF]` 节 + `config/settings.py`（含无 PyYAML 兜底解析） |
| 0.4 数据加载器 | ✅ | `data/loader.py`（10 张源表 + 2 张季度派生表，统一 5 位代码/日期标准化） |
| 0.5 数据质量检测 | ✅ | `data/quality.py` + `scripts/check_data_quality.py`，写 `qcfp_data_quality_audit` 快照 |
| 0.6 证据等级标注 | ✅ | `data/evidence.py`（A/A-/B/C/D 静态表 + 派生降级规则） |
| 0.7 港股日历与周期对齐 | ✅ | `common/calendar.py`（交易日序列 + 周/月/季切分） |
| 0.8 覆盖度审计 | ✅ | `scripts/audit_coverage.py`，输出 `Report/QCFP_MTF/audit/coverage_report_*.{csv,json}` |
| 数据字典同步 | ✅ | `Code_utl/Generate_qcfp_Dictionaries.py`，6 表 × {json,md,xlsx} 已生成至 `Config/` |
| 测试 | ✅ | `tests/` 36 项全部通过（含无 pytest 的运行器 `run_all_tests.py`） |

> P0 验收细则见 [QCFP-MTF_P0_测试清单.md](QCFP-MTF_P0_测试清单.md)（A~G 逐项打勾）。

**P1（季度结构引擎）已交付（2026-08-19）**：C/F/P 因子 + FSM-1 + Core Score + 三维背离，`qcfp_quarterly_structural` 944 行；交叉验证 direct 一致率 90%；60 项测试全过。详见 [QCFP-MTF_P1_开发计划.md](QCFP-MTF_P1_开发计划.md) 交付记录。

> P1 验收细则见 [QCFP-MTF_P1_测试清单.md](QCFP-MTF_P1_测试清单.md)；使用实例见 [QCFP-MTF_P1_使用手册.md](QCFP-MTF_P1_使用手册.md)。

**P2（月线行为引擎）已交付（2026-08-19）**：T1~T5 + 9 种 VP_Regime + CBI + Cost Position + Stage，`qcfp_monthly_behavior` 2267 行；81 项测试全过；工作流 6 步端到端 ✅。详见 [QCFP-MTF_P2_开发计划.md](QCFP-MTF_P2_开发计划.md) 交付记录；验收细则见 [QCFP-MTF_P2_测试清单.md](QCFP-MTF_P2_测试清单.md)；使用实例见 [QCFP-MTF_P2_使用手册.md](QCFP-MTF_P2_使用手册.md)。

**P3（周线战术引擎）已交付（2026-08-19）**：放量/缩量 + 换手偏离/极端 + VWAP 偏离 + 均线斜率 + 4 种信号，`qcfp_weekly_tactical` 9827 行；97 项测试全过；工作流 7 步端到端 ✅。详见 [QCFP-MTF_P3_开发计划.md](QCFP-MTF_P3_开发计划.md) 交付记录；验收细则见 [QCFP-MTF_P3_测试清单.md](QCFP-MTF_P3_测试清单.md)；使用实例见 [QCFP-MTF_P3_使用手册.md](QCFP-MTF_P3_使用手册.md)。

**P4（多周期融合层）已交付（2026-08-19）**：Chip Confidence + MTF 对齐（12 矩阵+兜底）+ FSM-2 + Anti-Inference + 结构-行为背离，`qcfp_mtf_decision` 9827 行；全量不越权验证 0 违规；118 项测试全过；工作流 8 步端到端 ✅。详见 [QCFP-MTF_P4_开发计划.md](QCFP-MTF_P4_开发计划.md) 交付记录；验收细则见 [QCFP-MTF_P4_测试清单.md](QCFP-MTF_P4_测试清单.md)；使用实例见 [QCFP-MTF_P4_使用手册.md](QCFP-MTF_P4_使用手册.md)。

**P5（DSS 决策层）已交付（2026-08-20）**：Score + Action（单向门控）+ Risk + 标准 JSON/MD 报告，`qcfp_mtf_decision` 9827 行全部回写 action/risk；全量门控验证 0 违规；133 项测试全过；工作流 9 步端到端 ✅。详见 [QCFP-MTF_P5_开发计划.md](QCFP-MTF_P5_开发计划.md) 交付记录；验收细则见 [QCFP-MTF_P5_测试清单.md](QCFP-MTF_P5_测试清单.md)；使用实例见 [QCFP-MTF_P5_使用手册.md](QCFP-MTF_P5_使用手册.md)。

**P6（回测与校准）已交付（2026-08-20）**：防 Look-ahead 时间线 + 向量化回测 + 绩效/分层/扩展窗口 + 网格校准，`qcfp_backtest_results` 4321 行；146 项测试全过；P0~P6 全链路闭环 ✅。详见 [QCFP-MTF_P6_开发计划.md](QCFP-MTF_P6_开发计划.md) 交付记录；验收细则见 [QCFP-MTF_P6_测试清单.md](QCFP-MTF_P6_测试清单.md)；使用实例见 [QCFP-MTF_P6_使用手册.md](QCFP-MTF_P6_使用手册.md)。

---

## 附：Validation Hardening（V1）加固记录（2026-08-20）

基于外部设计/代码/回测审查（结论：研究型框架 6.5/10，4 个 P0 问题 + 3 个 P1 问题），已采纳并修复：

| 审查问题 | 修复 |
| :-- | :-- |
| P0-1 生产/回测时间对齐不一致（生产按 period_end，回测按 available_date） | 新增 `common/asof.py` 统一 as-of 对齐；`mtf_fusion_engine` 与 `data_pipeline` 均按 **available_date** 对齐季度结构，生产=回测同一规则 |
| P0-2 CBI 全历史标准化泄漏未来 | CBI 改为**横截面 as-of 标准化**（当月 Winsorize→Z→0~100），样本不足回退个股 expanding；新增无泄漏测试 |
| P0-3 Chip Score 时间对齐缺失 | `chip_structure_score` 按 `quarter_end + 45 天` 推算披露日对齐（生产与回测一致） |
| P0-4 回测池化 pnl 统计口径错误（-99% 伪影） | 新增 `portfolio_returns` 等权组合层；绩效改在组合净值上计算（年化 -1.94%、回撤 -33%），并新增 Sortino/Calmar/年化换手 |
| P1-1 港股成本模型过简 | 成本拆为买入/卖出不对称（佣金+滑点 vs 佣金+印花税+滑点+征费），方向感知计费 |
| P1-2 校准无 OOS | 新增 Walk-forward（训练窗选参→测试窗评估）+ 组合口径校准 |
| P1-3 缺因子/状态有效性验证 | 新增 `backtest/information_analysis.py` + `scripts/ic_analysis.py`（Rank IC + 状态前向收益分层） |
| Chip Confidence 权重未归一化 | `compute_chip_confidence` 强制 W_chip+W_cbi=1，消除校准尺度污染 |
| Anti-Inference 文档/实现漂移 | 规则加 RULE-001~013 编号，测试断言唯一性 |
| 测试混跑 | 新增 6 项金融逻辑测试（as-of/chip/normalization/组合/成本/权重），全套 152 项通过 |

**加固后关键证据（2021-01-01 ~ 2026-08-14，等权组合）**：

- 组合年化 -1.94%、Sharpe -0.09、最大回撤 -33%（原池化口径 -99.7% 为统计伪影）；
- 分年：2024 +14.3%（Sharpe 1.15）、2025 +7.5%（1.00）、2022/2023/2026 负；
- 分层：risk_on Sharpe 1.68、neutral 2.45、risk_off -1.04 → **策略有效性集中在风险偏好正常/偏暖环境**；
- IC：结构状态 26 周前向收益 spread 39%（BOTTOM +16.8% vs DISTRIBUTION -22.3%）、CBI 26 周 RankIC 0.167（ICIR 0.59）→ **Layer 1/2 有信息量**；
- 反直觉发现：MTF `BULLISH_CONFIRMED` 26 周前向收益 -18%（最低），说明 **问题在 MTF/Action 映射层，不在 C/F/P 框架**——下一步应调整 Action 映射而非修改状态机。

> 遗留项（未在本轮处理）：Universe Survivorship Bias（需历史股票池快照）；真实披露日历替代推算滞后；B 级权重更大网格寻优（需更长历史）。

---

## 附：Validation Hardening（V2）加固记录（2026-08-20）

基于第二轮系统级审查（重点：预测有效性证据、Risk→仓位脱节、缺横截面回测与基准），已采纳并实施：

| 审查建议 | 落地 |
| :-- | :-- |
| Risk→Position 必须真正联动 | 新增 `decision/position_sizing.py`：目标仓位 = min(MTF 基础仓位, Risk 上限)，Risk 从"标签"变为"门控"；回测时间线与个股报告同步生效 |
| 加入 Benchmark / Excess Return | 新增 `backtest/benchmark.py`（等权买入持有 + 恒指基准 + 年化超额/IR/相关性），回测报告输出 |
| 横截面股票池回测 | 新增 `backtest/cross_sectional.py` + `scripts/cross_sectional_backtest.py`（每周末按 QCFP 评分选 Top-N 等权组合，对比两基准） |
| C/F/P 独立增量信息验证 | `ic_analysis.py` 增加 **C×F×P 三维前向收益矩阵**（n/均值/中位数/命中率/t 值）与状态 IC |
| Walk-forward 参数稳定性 | 校准输出每窗 Train Sharpe/收益/回撤、最佳参数 JSON、参数稳定性统计（当前 4/4 窗口同参） |
| Core Score 与预测分分离 | 报告将 QCFP 评分标注为"结构质量分，State-First，非收益预测"，明确 State Validity 与 Predictive Validity 区别 |
| 测试 unit/integration 分层 | 新增 `pytest.ini` 标记；依赖真实数据库的 7 个模块标 `integration`；`run_all_tests.py --unit-only` 可跑纯单元（34 模块） |
| 交付包完整性 | `Core/QCFP_MTF/README.md` 明确"TA_Workflow 模块"依赖（Config/SQLiteDB/入口脚本） |
| 45 天披露滞后 | 保留估计模式，配置预留 `available_date_mode`；真实披露日历列遗留项 |

**V2 加固后关键证据（2021-01-01 ~ 2026-08-14）**：

- Risk 仓位上限生效后：组合年化 -0.79%、最大回撤 -24.3%（较 V1 的 -33% 改善）；risk_on Sharpe 1.73、neutral 2.26、risk_off -1.13；
- **基准对照**：等权买入持有年化超额 -3.22%（IR -0.002）、恒指超额 -0.52%（IR 0.009）→ 择时层尚未跑赢基准；
- **横截面选股有 alpha**：Top-5 年化 +8.6%、等权基准年化超额 +13.8%（IR 0.81）、恒指超额 +10.1%（IR 0.45）；Top-3/Top-10 次之 → **排名层有信息，择时/仓位层拖累组合**；
- C×F×P 矩阵 26 周显著分层：C↓F↑P↓ +23.9%（t=4.39）vs C↓F→P→ -22.3%（t=-14.1）；C↑F↑P→（ACCUMULATION）全期限负收益——状态定义需按证据复核；
- Walk-forward：参数稳定性 4/4；OOS 2024 +12.3%（Sharpe 1.31）、2025 +7.0%（1.21）、2023/2026 负。

**结论**：第二轮加固后，系统已具备"因子/状态有效性 → 横截面选股 → 组合/基准"的完整验证链路。核心证据指向：**QCFP 评分的横截面选股能力成立（Top-5 显著跑赢基准），但时间择时层（risk_off 减仓）与 Action 映射仍需校准**——与 V1 结论一致且更有数据支撑。

---

## 附：Validation Hardening（V3）加固记录（2026-08-20）

基于第三轮系统级审查（P0：横截面时间错位、证据/质量混用、IC 重叠样本；P1：PIT/披露日/流动性/参数平台；P2：增量信息实验；报告可视化），已实施：

| 审查建议 | 落地 |
| :-- | :-- |
| P0-1 横截面 Top-N 时间错位 | `cross_sectional_portfolio` 改为 **T 周选股 → T+1 周持仓收益**（权重按股票滞后一周），与主回测 `shift(1)` 同模型；新增时间对齐测试 |
| P0-2 Evidence 与 Data Quality 分离 | 报告/JSON 改为二维体系：季度结构=证据 A-（派生复合）、月线 B、周线 C、MTF D；数据质量单独成列，不再用质量推断证据 |
| P0-3 IC/C×F×P 重叠样本 | 三维矩阵与状态表增加 **非重叠采样 t 统计**（t_stat_nonoverlap） |
| P1 PIT Universe | `backtest/pit_universe.py` + 可选 `Config/qcfp_universe.csv`（stock_code/valid_from/valid_to），回测/横截面自动过滤 |
| P1 真实披露日 | `common/asof.load_disclosure_overrides` + 可选 `Config/qcfp_disclosure_dates.csv`，有真实日期优先、否则 +45 天估计 |
| P1 流动性 | 横截面回测支持 `min_weekly_amount` 周成交额下限（配置 `backtest.liquidity`） |
| P1 参数平台 | 校准输出"参数平台"统计（最优 Sharpe 邻域内组合数），取代单一 argmax 决策 |
| P2 增量信息实验 | `scripts/incremental_alpha_test.py`：Model 0~6（P → C+P → C+F+P → +Monthly → +Weekly → 完整 MTF）逐一对比 |
| P3 组合层风险 | `backtest/portfolio_risk.py`：VaR95 / 年化波动 / 平均暴露 / 现金占比，接入回测报告 |
| 报告可视化 | `scripts/html_report.py`：自包含 HTML（净值曲线/分年度/市场分层内联 SVG，零依赖） |

**V3 关键证据（2021-01-01 ~ 2026-08-14）**：

- **时间对齐修正后**：横截面 Top-5 年化 -0.9%、等权基准年化超额 +3.6%（IR 0.29）——V2 报告中的 +13.8% 含当周收益偏差，修正后显著回落（证实审查判断）；
- 组合层：平均暴露 27%、现金占比 73%、VaR95 -1.97%、年化波动 8.9%——**系统大部分时间空仓**，需与基准结合解读；
- 增量实验（Top-5）：P 方向主导（M1~M3 同构）、+Monthly 反而更差、+Weekly 无增量、完整 MTF（qcfp_score）最优（超额 +3.6%）→ **MTF 组合确实优于各子集，但绝对 alpha 仍弱**；
- C×F×P 26 周矩阵：C↓F↑P↓ +23.9%（t=4.39）vs C↓F→P→ -22.3%（t=-14.1），非重叠 t 已入报告。

**遗留项（需外部数据/更长历史）**：真实披露日历、历史退市/新上市股票池、ADV 冲击成本、波动率缩放仓位、分行业/规模分层。

---

## 附：Validation Hardening（V4）加固记录（2026-08-20）

基于第四轮系统级审查（横截面稀疏网格/方向成本、DSS JSON 证据残留、PIT 强制、HAC 统计、Walk-forward 术语、研究质量门），已实施：

| 审查建议 | 落地 |
| :-- | :-- |
| 报告/日志文件名加股票代码 | 全部 12 个脚本：`--stock` 时报告文件与日志均带股票代码（如 `monthly_behavior_00700_*.csv`、`monthly_behavior_engine_00700.log`） |
| P0-1 完整 stock×week 网格 | `cross_sectional` 先建完整网格再 `w.shift(1)`，消除稀疏信号导致的隐性跨周持仓 |
| P0-2 横截面真实方向成本 | 取消 avg_rate，改为 `加仓×buy_rate + 减仓×sell_rate` |
| P1-3 DSS JSON 证据/质量彻底分离 | `dss_output.py` 改为只读调用方传入的 evidence_level，禁止由 data_quality 推断（测试覆盖） |
| P1-4 PIT 强制 | `--require-universe`：正式回测缺 PIT 股票池即报错（默认仍研究模式 WARN） |
| P1-5 HAC + 自助法 | 三维矩阵增加 Newey-West HAC t、块自助法 95% CI、10/25/75/90 分位数与波动 |
| P2-6 术语严谨 | `run_walk_forward` 更名 `rolling_oos_evaluation`（固定参数滚动评价）；真正 train→calibrate→OOS 保留在 `run_walk_forward_grid` |
| 增量模型补全 | `incremental_alpha_test.py` 增加 M0_BuyHold / M1_C / M2_F，形成 Model 0~8 全谱系 |
| 研究质量门 | `scripts/research_validation.py`：10 项检查 → PASS/WARN/FAIL 表 + Research Grade（A/B/C/D） |
| 注释修正 | data_pipeline 注释改为"实际披露日或估算可用日" |

**V4 验证结果**：

- 完整网格 + 方向成本后横截面 Top-5：年化 -4.7%、等权超额 +0.24%（IR 0.10）——此前 +3.6% 进一步缩水至近零，**选股 alpha 证据进一步弱化**（方向成本与网格修正的累计效应）；
- 增量实验：M1_C 与 M2_F 同构（C→/F→ 主导，评分无区分度）、完整 MTF（M8）仍为最优排名（超额 +0.24%）；
- **研究质量门：Grade B（7 PASS / 2 WARN）**——WARN 均为数据门控项（未配置 PIT 股票池、未启用流动性过滤），配置后即可转 PASS；
- 全量 154 项测试通过；组合风险：平均暴露 27%、VaR95 -1.97%。

**结论**：V4 完成审查提出的全部 P0/P1 项。诚实的研究现状：随着每次方法学修正，横截面超额收益持续回落（+13.8% → +3.6% → +0.24%），说明**当前评分层的真实选股 alpha 很弱，尚未达到可实盘的证据强度**；系统本身的验证链条（Look-ahead/PIT/方向成本/HAC/质量门）已达到研究级。下一步建议：① 提供 `qcfp_universe.csv` 与 `qcfp_disclosure_dates.csv` 数据后复测；② 若 alpha 仍弱，回到 C×F×P 矩阵重新设计状态定义（如 ACCUMULATION 组合 26 周负收益问题）。

---

## 附：Validation Hardening（V5）加固记录（2026-08-21）

基于第五轮审查（评分上调至 8.9/10）与用户要求（文件名只含日期），已实施：

| 建议 | 落地 |
| :-- | :-- |
| 文件名只含日期 | 全部 13 个脚本的报告/日志时间戳从 `YYYYMMDD_HHMMSS` 改为 `YYYYMMDD`；回测 run_id 默认 `bt_20260821`（同日冲突自动加序号防覆盖） |
| production 模式强制 PIT | 配置 `backtest.mode: research/production`；production 缺 PIT 股票池直接报错，不再依赖 `--require-universe` |
| Factor Ablation 补全 | 增量实验扩展为 Model 0~10（BuyHold/C/F/P/CF/CP/FP/CFP/+Monthly/+Weekly/Full MTF） |
| Conditional Regression | `information_analysis.conditional_regression`：每周横截面 OLS（控制 P 后 C/F 的 β、t 与增量 R²），回答"C/F/P 是否独立信息维度" |
| 最低佣金 | `cost_model.directional_cost` 支持单笔最低佣金（max(成交额×费率, min_commission)），横截面与主回测共用 |
| 动量基准 | `benchmark.momentum_top_n`（过去 13 周动量 Top-N，T+1 生效），横截面回测新增超额(动量)对照 |
| 10 门槛验证协议 | `research_validation.py` 升级为 01~10 门槛（PIT/Available-date/对齐/成本/流动性/OOS Walk-forward/参数平台/HAC/因子消融/环境稳健性），10/10 PASS 才 "Research Validated" |
| 校准产物持久化 | 校准 JSON 落盘参数平台（plateau）与每窗最佳参数 |

**V5 关键证据（2026-08-21 实测）**：

- **条件回归（fwd_13w，控制 P 后）**：F β=+0.0058（t=2.10，显著）、C β=-0.003（t=-0.84，不显著）、P β=-0.010（t=-3.30）、增量 R²=0.146 → **F 提供独立于 P 的增量信息，C 目前不显著**（与 C→ 占比高、阈值无区分度一致）；
- 动量基准对照：Top-5 超额(动量) +8.0%（IR 0.47），超额(等权) +0.14%——**策略相对动量仍有正超额，但绝对 alpha 弱**；
- 10 门槛质量门：**PASS 8 / WARN 2 / FAIL 0**（WARN=PIT 股票池未配置、流动性过滤未启用，均为数据/配置门控项）；
- 文件命名：`monthly_behavior_00700_20260821.csv`、`summary_bt_20260821.json`（日期版）；
- 154 项测试通过。

**研究结论**：V5 完成了审查提出的全部 P0/P1 项与用户命名要求。当前证据链显示：**F 因子有独立信息、P 因子均值回归、C 因子受阈值限制暂无独立贡献、动量基准之上有正超额但绝对 alpha 弱**——系统进入"研究级验证框架"（8.9/10 档），下一步的核心是补充 PIT/披露日历数据后复测，并针对 C 因子阈值与状态定义做基于 C×F×P 矩阵的重构。

---

## 附：V6 交付记录（2026-08-22）

按用户改进要求：

| 要求 | 落地 |
| :-- | :-- |
| 生成 all-in-one MD 报告（文件名含股票代码） | 新增 `scripts/all_in_one_report.py`：聚合状态快照 + DSS 详细决策（10 节）+ 回测汇总（绩效/分年/分层/OOS/基准/风险）+ 产物清单；输出 `Report/QCFP_MTF/all_in_one/{stock}_all_in_one_{date}.md` |
| `html_report.py --stock X` 无 run-id 也可生成 | `--run-id` 改为可选：自动匹配该股票最新 `summary_*_{stock}.json`；输出文件名含股票代码（`report_{run_id}_{stock}.html`） |

实测（01951）：`html_report.py --stock 01951` 自动匹配 `bt_20260822` 生成 `report_bt_20260822_01951.html`；`all_in_one_report.py --stock 01951` 生成 `01951_all_in_one_2026-08-21.md`（含 2026-08-21 决策：BEARISH_CONFIRMED/EXIT/Extreme 与回测汇总）。154 项测试通过。

### V7 交付记录（2026-08-22）

| 要求 | 落地 |
| :-- | :-- |
| all_in_one_report.py 接入 test_QCFP-MTF.py | 新增第 9 步 "P7 All-in-One 一体化报告"（含 `--single P7`、engine_map、`--skip-reports` 联动） |
| All-in-One 同时生成 HTML | `all_in_one_report.py` 内置轻量 MD→HTML 渲染（标题/表格/列表/引用/代码/粗体），同时输出 `{stock}_all_in_one_{date}.{md,html}` |

实测（01951）：MD 与 HTML 双格式均生成；HTML 表格/章节渲染正常；`test_QCFP-MTF.py` 与 `all_in_one_report.py` 编译通过；154 项测试通过。

### V8 敏感性回测记录（2026-08-22）

**问题**：01951 回测未捕捉 2024-02~10 波段（+61.6% 买入持有）。

**根因链**：季度状态机保守保持 DECLINE（2024Q2 C↑F→P↑、Q3 C→F↑P↑ 均未命中规格书 6 状态/2 条退出路径）→ 结构空头 → 层级门控输出 39 周全 EXIT。

**敏感性回测**（新增 `scripts/sensitivity_backtest.py`，按变体重算季度结构→时间线→组合回测）：

| 变体 | 组合年化 | Sharpe | 组合回撤 | 01951 波段收益 | 持仓周 |
| :-- | --: | --: | --: | --: | --: |
| 基线 C0.5 | -0.58% | -0.022 | -23.97% | 0.00% | 0/39 |
| C0.5+RECOVERY（C→F↑P↑ 等 3 条） | +0.12% | 0.061 | -24.02% | 0.00% | 0/39 |
| C0.5+RECOVERY2（激进：加 C↑/C→F→P↑） | **-2.52%** | -0.124 | **-38.48%** | **+33.41%** | 10/39 |
| C0.3 / C0.2（放宽 C 阈值） | +0.44% / -0.12% | 0.093 / 0.036 | -25.2% / -26.9% | 0.00% | 0/39 |

**结论**：

- **单独放宽 C 阈值无法捕捉波段**（01951 在 2024Q2 阈值 0.5 时已是 C↑，C 不是瓶颈）；
- **标准恢复路径无效的根因是披露滞后**：2024Q3 恢复状态可用日期 2024-11-14，波段已于 10-31 结束；
- **激进恢复路径（RECOVERY2）能吃到波段（+33.4%）**，但以组合年化恶化（-0.58%→-2.52%）、回撤翻倍（-24%→-38%）为代价——在其他股票上过早翻多追高被套；
- **不建议直接启用激进恢复**；若需捕捉此类行情，正确方向是**真实披露日历（缩短滞后）**或**仅在特定市场环境（risk_on/neutral）启用恢复路径**，并先做扩展窗口 OOS 验证。

新增 `resolve_regime(recovery_paths, recovery_states)` 可开关参数（默认关闭，生产行为不变）+ 恢复路径单元测试；全量测试通过。

### V9 交付记录（2026-08-22）——PIT Unification

本轮审查核心："回测是 PIT 的，报告未必完全 PIT"。已实施：

| 审查项 | 落地 |
| :-- | :-- |
| P0-1 DSS 历史报告季度 PIT 泄漏 | `dss_report._row/_history` 与 `all_in_one._snapshot_table` 均改为 `WHERE available_date<=决策日`（不再只用 period_end） |
| P0-2 DSS PIT 自动测试 | 新增 `common/asof.pit_latest` 纯函数 + 单元测试（修改未来披露日不影响历史、提前披露会改变结果）+ integration 测试（01951 @ 2026-07-10 必须用 2026Q1） |
| P1-3 条件回归 HAC | `conditional_regression` 对 beta 时间序列做 Newey-West HAC（Fama-MacBeth 风格），新增 `t_hac`；实测 F t_hac 1.23/1.42（普通 t 2.10 → HAC 修正后未达 2，如实呈现） |
| P1-4 验证门升级为结果有效性 | 06 OOS Sharpe 中位数>0、07 同参率≥80%（60~80 WARN，<60 FAIL）+ 平台占比、08 \|HAC t\|≥2 或条件回归显著、09 Full MTF 超额>0、10 risk_on/neutral 年化为正 |
| P1-5 参数稳定性门槛 50%→80% | 已生效（当前 3/4=75% → WARN 边界，如实标记） |
| P1-6 All-in-One 统一 run_id | 产物清单只绑定同一 `report_{run_id}_{stock}.html`，报告头与产物清单标注 run_id/决策日/模型版本 |
| 四层结论结构 | All-in-One 新增"研究结论与限制"：证据（OOS/HAC/条件回归）→ 判断（强/中/弱）→ 结论（C/F/P 增量是否支持）→ 限制（PIT 估计/流动性/样本/行业中性） |

**验证结果（2026-08-22 实测）**：

- DSS PIT：01951 @ 2026-07-10 使用披露日 2026-05-15 的季度（2026Q1），不再使用未披露的 2026Q2；
- 质量门升级后：PASS 6 / WARN 4 / FAIL 0——WARN 均为有效性口径（PIT 数据未配、流动性未开、同参率 75%、Full MTF 超额≤0）；
- 条件回归 HAC：F t_hac=1.23（13w）/1.42（26w）、C t_hac≈0.5~0.6、P t_hac=-1.84/-4.37、增量 R²≈0.12~0.14；
- 42 个测试模块全部通过。

**研究状态**：PIT 已统一（生产 DSS / 回测 / 历史报告 / All-in-One 共用 available_date 规则），验证门已从"文件存在"升级为"结果有效"。当前证据：F 因子在 HAC 修正后仍为边际（t_hac 1.2~1.4），C 无独立增量，组合绝对 alpha 弱——结论仍是"研究级框架（A-），投资有效性尚待真实披露日历 + 更长样本验证"。

### V10 交付记录（2026-08-24）——方案 B 温和试多 + 催化剂质量评分（CQS）

**目标**：在空头季度结构下以"战略看空、战术试多"方式捕捉 2024 年 01951 类的中短期反弹，同时避免方案 A（激进恢复路径）的翻多风险。

**实现（不破坏"层级不可越权"）**：

| 模块 | 改动 |
| :-- | :-- |
| `decision/catalyst_quality.py`（新增） | CQS = F 持续性（+2/+1）＋趋势质量（±2）＋CBI 稳定性（±1），范围 -3~+3；映射 35%/20%/5% 观察仓与"不限/4 周/2 周"时间止损 |
| `fusion/mtf_alignment.py` | `align_mtf(..., tactical_override, position_52w, max_52w_position, min_trigger)`：空头族＋周线触发＋52W<0.15 → `BULLISH_WARNING`（method=`tactical_override`），结构状态本身不变；`min_trigger=[]` 表示任意触发 |
| `decision/position_sizing.py` | `effective_position_cqs`：override 时取 `min(CQS 观察仓, Risk 上限)`，常规路径行为不变 |
| `backtest/data_pipeline.py` | 从 structural/monthly 取 `q_trend_score/q_position_52w/cbi_state`，计算 `prev_f_state/catalyst_score/catalyst_type/is_override/time_stop_weeks/override_run_weeks`；时间止损在"周信号中断或新季度结构披露"时重置（季报更新即允许重新试多） |
| `scripts/mtf_fusion_engine.py` | 生产融合同样计算 CQS 与 override；写库新增 `catalyst_score/catalyst_type/align_method` 三列 |
| `scripts/dss_report.py` | 决策摘要显示 CQS；override 行的仓位建议按 CQS 观察仓显示；风险节按 3 类催化剂提示观察仓与时间止损 |
| `scripts/trigger_sensitivity.py`（新增） | 触发器宽度敏感性工具（OFF / Breakout / +Pullback / +Consolidation / ANY） |
| 修复 | `backtest_runner/calibration/cross_sectional/incremental_alpha/research_validation/sensitivity` 的 structural/monthly 查询补齐 `q_trend_score/q_position_52w/cbi_state`（此前时间线构建会报缺列）；`align_method` 迁移加入 `init_db.py` |

**配置（`Config/qcfp_settings.yaml` → `decision.tactical_override`）**：

```yaml
tactical_override:
  enabled: true                # false = 完全关闭方案 B（等价 OFF 基线）
  max_52w_position: 0.15       # 仅 52 周位置 < 15% 才允许试多
  min_trigger: [Breakout, Pullback, Consolidation]  # [] = 任意触发
catalyst_quality:
  position_high: 0.35          # CQS ≥ +2 高质量反转
  position_mid: 0.20           # CQS 0~+1 中性偏强
  position_low: 0.05           # CQS < 0 纯脉冲/噪音
  time_stop_high: null         # 高质量反转不限时间止损
  time_stop_mid: 4             # 中性偏强 4 周后评估
  time_stop_low: 2             # 纯脉冲 2 周内必须离场
```

**敏感性回测（2021-01-01 ~ 2026-08-21，等权全组合；01951 波段 2024-02-02~10-31，买入持有 +61.61%）**：

| 变体 | 组合年化 | Sharpe | 最大回撤 | 年化换手 | 试多行/股 | 01951 波段收益 | 波段持仓周 |
| :-- | --: | --: | --: | --: | --: | --: | --: |
| OFF（禁用方案 B） | -0.58% | -0.022 | -23.97% | 1.05 | 0 | 0.00% | 0/39 |
| Breakout（最保守） | -0.63% | -0.027 | -23.98% | 1.06 | 7/5 | 0.00% | 0/39 |
| Breakout+Pullback | -0.68% | -0.034 | -24.00% | 1.12 | 63/11 | -3.28% | 3/39 |
| **Breakout+Pullback+Consolidation（默认）** | -0.78% | -0.042 | -24.83% | 1.30 | 1058/12 | **+2.47%** | 9/39 |
| ANY（含 Breakdown） | -0.81% | -0.047 | -24.94% | 1.23 | 1129/12 | +1.11% | 8/39 |

**结论（如实呈现）**：

- 方案 B 实现完整可用：空头结构不翻多（层级铁律未破），仅以 `BULLISH_WARNING` 预警＋5%~35% 观察仓轻仓试错；
- **01951 波段从 OFF 的 0% 提升到 B+P+C 的 +2.47%（持有 9/39 周）**，验证了"空头结构下轻仓试多"能部分捕捉反弹；但远小于买入持有 +61.61%，原因有三：① 该股 CQS 全程 0~1（中性偏强→20% 仓＋4 周时间止损），未达高质量反转（≥+2）的 35% 无止损档；② 52W 位置升破 0.15 后试多自动退出（不追高）；③ 披露滞后使新季度数据 45 天后才可用；
- **组合层面代价有限但真实**：B+P+C 的 Sharpe -0.042 vs OFF -0.022、回撤 -23.97%→-24.83%、换手 +0.25——即方案 B 的"期权费"属性（熊市小额磨损换反弹捕捉）；1058 试多行中 696 行被时间止损归零，印证了方案分析中"慢性失血"的警告；
- **默认取 B+P+C**（用户目标为捕捉反弹）；若账户厌恶磨损，改 `min_trigger: [Breakout]` 或 `enabled: false` 即可回到保守/原系统行为。

### V11 交付记录（2026-08-24）——移动止损 + CQS 权重微调 + 回测重绑

采纳系统审查的最后 3 点行动建议：

**行动 1：用当前代码重跑 01951 历史回测并更新报告绑定**

- `backtest_runner.py --stock 01951` 新 run_id=`bt_20260824`：2024 年化 **0.00% → +4.64%**（Sharpe 0.85，回撤 -2.18%）；
- All-in-One 自动绑定新 run_id（`01951_all_in_one_2026-08-21.md` 回测汇总为 bt_20260824），消除"当前决策 vs 旧回测"的误导。

**行动 2：CQS 趋势质量权重 +2 → +1（负向 -2 → -1）**

- `decision/catalyst_quality.py`：趋势质量分支从 ±2 降为 ±1，避免对困境反转股因 Trend Score 未达标而过度压制；
- **实测修正**：01951 在 2024 波段 F 全程 F→、CBI 仅 2~5 月稳定、Trend Score 未过 60，CQS 真实值为 0~1（评审预估的 CQS=2 未在真实数据中出现），因此该调整不改变 01951 档位，主要效果是压缩高分分布、降低对趋势单因子的依赖。

**行动 3：固定周数止损 → 移动止损（Trailing Stop）**

- 新增 `backtest/engine._apply_trailing_stop`：试多持仓只要**收盘不跌破建仓周 K 线最低价×(1-2%)** 即可无限期持有；跌破即离场，且同段试多内不再自动重进（周信号中断或新季度披露才允许重新试多）；
- 配置 `decision.trailing_stop {enabled: true, buffer_pct: 0.02}`；`catalyst_quality.time_stop_mid` 由 4 → null（中性偏强改用移动止损），纯脉冲（CQS<0）保留 2 周强制止损；
- 止损/重进切换的成本在引擎内重算（含止损交易成本）。

**V11 敏感性实测（2026-08-24，全市场；01951 波段买入持有 +61.61%）**：

| 变体 | 组合年化 | Sharpe | 最大回撤 | 01951 波段收益 | 波段持仓周 |
| :-- | --: | --: | --: | --: | --: |
| OFF（禁用方案 B） | -0.58% | -0.022 | -23.97% | 0.00% | 0/39 |
| Breakout | -0.65% | -0.030 | -23.98% | 0.00% | 0/39 |
| Breakout+Pullback | -0.71% | -0.036 | -24.00% | -3.28% | 3/39 |
| **B+P+Consolidation（默认）** | -0.24% | **+0.020** | -24.77% | **+7.31%** | 19/39 |
| ANY | +0.16% | +0.063 | -23.17% | +7.31% | 19/39 |

**结论（如实呈现）**：

- 移动止损是本次最大增益点：01951 波段从 V10 的 +2.47%（9/39 周）提升到 **+7.31%（19/39 周）**，组合 Sharpe 由负转正（-0.022 → +0.020），年化 -0.58% → -0.24%；
- 代价：回撤 -23.97% → -24.77%（+0.8pp）、年化换手 1.05 → 1.39（移动止损延长持仓带来更多风险暴露与交易）；
- 仍未达到评审预估的 +30%：根因是 01951 CQS 实际为 0~1（20% 仓 + 移动止损），未达高质量反转的 35% 无止损档，且 52W 升破 0.15 后系统自动退出（不追高）——这是方案 B 的纪律性代价，而非缺陷；
- 行动标签优化：DSS/All-in-One 中试多行显示"试多（TEST_BUY）"，数据库 action_signal 仍为 REDUCE（驱动回测），消除"空仓减仓"语义歧义。

### V12 交付记录（2026-08-24）——移动止损缓冲调参 + 换手监控

按审查"3 点行动建议"执行（重点：不追求重仓吃满 90%，保持低回撤哲学）：

**行动 1：`buffer_pct` 2% → 5%**

- `Config/qcfp_settings.yaml` 与 `settings.py` 默认改为 0.05（收盘跌破建仓周最低价×(1-5%) 离场）；
- **敏感性实测（buffer×触发器网格，2026-08-24）**：

| 变体 | buf | 组合年化 | Sharpe | 最大回撤 | 年化换手 | 01951 波段 | 波段持仓周 |
| :-- | --: | --: | --: | --: | --: | --: | --: |
| OFF | 任一 | -0.58% | -0.022 | -23.97% | 1.05 | 0.00% | 0/39 |
| Breakout | 任一 | -0.65% | -0.030 | -23.98% | 1.13 | 0.00% | 0/39 |
| B+Pullback | 任一 | -0.71% | -0.036 | -24.00% | 1.18 | -3.28% | 3/39 |
| **B+P+C** | 2% | -0.24% | +0.020 | -24.77% | 1.39 | **+7.31%** | 19/39 |
| **B+P+C** | **5%（默认）** | -0.25% | +0.019 | -24.95% | 1.37 | +6.17% | 20/39 |
| B+P+C | 8% | -0.31% | +0.013 | -24.98% | 1.36 | +5.97% | 23/39 |
| ANY | 2% | +0.16% | +0.063 | -23.17% | 1.32 | +7.31% | 19/39 |
| ANY | 5% | +0.15% | +0.063 | -23.34% | 1.31 | +6.17% | 20/39 |
| ANY | 8% | +0.05% | +0.051 | -23.58% | 1.30 | +5.97% | 23/39 |

- **如实结论**：放宽缓冲**没有**带来评审预期的"2024 收益 10%+"。01951 波段反而从 7.31% 微降至 6.17%（5%）、5.97%（8%），组合 Sharpe 0.020→0.019→0.013，2024 单股年化 4.64%→3.53%。原因：01951 的反弹中后期伴随明显回调（8 月后 52W 位置已升破 0.15 系统退出），更宽的缓冲让系统在回调中多扛了几周、回吐部分利润——移动止损缓冲不是 01951 波段的瓶颈；瓶颈仍是 CQS=1（20% 仓）与 52W 过滤器；
- 保留 5% 为默认：与 2% 组合级差异在噪声范围内，但 5% 对底部暴力洗盘更稳健（评审的鲁棒性观点），且不牺牲换手。

**行动 2：换手率监控**

- 全市场年化换手最高 1.39（B+P+C@2%）/ 1.37（@5%），**均远低于 2.0 阈值** → 无需收紧 `min_trigger`，默认维持 `[Breakout, Pullback, Consolidation]`；
- 后续若换手 > 2.0，再收紧回 `[Breakout]`（过滤无效噪音）。

**行动 3：接受"低回撤下的小赚"哲学**

- 2024 年 01951 以 20% 观察仓 + 移动止损实现 +3.53%（年化，MDD 仅 -2.53%），组合 Sharpe 转正（+0.019~0.020）；
- 不因单一样本调高 CQS 档位或放开 52W 过滤器——那会重蹈激进恢复路径（V8）的覆辙（组合年化 -2.52%、回撤 -38%）。

### V13 交付记录（2026-08-24）——buffer 数据驱动寻优（20 组网格）

按"工程效率升级"审查的行动建议执行，核心结论：**数据否证了"放宽缓冲提升收益"的预期，buffer=0.02 全指标最优**。

**行动 1：一次性运行 buffer×触发器网格**

`trigger_sensitivity.py --buffers 0.02,0.05,0.08,0.12`（4 buffer × 5 变体 = 20 组）：

| 变体 | buf | 组合年化 | Sharpe | 最大回撤 | 年化换手 | 01951 波段 | 波段持仓周 |
| :-- | --: | --: | --: | --: | --: | --: | --: |
| OFF | 任一 | -0.58% | -0.022 | -23.97% | 1.05 | 0.00% | 0/39 |
| Breakout | 任一 | -0.65% | -0.030 | -23.98% | 1.13 | 0.00% | 0/39 |
| B+Pullback | 任一 | -0.71% | -0.036 | -24.00% | 1.18 | -3.28% | 3/39 |
| **B+P+C** | **2%** | -0.24% | **+0.020** | **-24.77%** | 1.39 | **+7.31%** | 19/39 |
| B+P+C | 5% | -0.25% | +0.019 | -24.95% | 1.37 | +6.17% | 20/39 |
| B+P+C | 8% | -0.31% | +0.013 | -24.98% | 1.36 | +5.97% | 23/39 |
| B+P+C | 12% | -0.32% | +0.012 | -25.02% | 1.35 | +5.97% | 23/39 |
| ANY | 2% | +0.16% | +0.063 | -23.17% | 1.32 | +7.31% | 19/39 |
| ANY | 5% | +0.15% | +0.063 | -23.34% | 1.31 | +6.17% | 20/39 |
| ANY | 8% | +0.05% | +0.051 | -23.58% | 1.30 | +5.97% | 23/39 |
| ANY | 12% | -0.07% | +0.039 | -24.04% | 1.30 | +5.97% | 23/39 |

**结论**：

- buffer 单调性：同一触发器内，0.02 的 Sharpe/波段收益/回撤全部最优，0.05→0.08→0.12 单调变差。原因：01951 反弹中后期（8 月后）出现显著回调，更宽的缓冲让系统多扛几周、回吐利润；且换手不升反降（1.39→1.35），说明瓶颈不是换手成本；
- 评审预测（0.05→+8~12%、0.08→+15~20%、0.12→接近买入持有）未被数据证实；
- 换手率最高 1.39 < 2.0，仍无需收紧触发器。

**行动 2：按数据选定 buffer=0.02**（`Config/qcfp_settings.yaml` + `settings.py`，含寻优注释）

**行动 3：重跑 01951 回测** → 新 run_id=`bt_20260824_3`：2024 年化 **+4.64%**（Sharpe 0.85，MDD -2.18%），恢复最优值。

**行动 4：重新生成 All-in-One** → `01951_all_in_one_2026-08-21.{md,html}` 绑定 `bt_20260824_3`，快照显示"试多（TEST_BUY）"。

**工程化附加**：

- `trigger_sensitivity.py` 输出新增自包含 **HTML 对比表**（按 Sharpe 降序，零依赖）与日志自动汇总（Top-3 Sharpe + 波段最优）；
- `qcfp_settings.yaml` 增加 CQS 评分规则与 buffer 寻优结论注释，防止日后遗忘。

### V14 交付记录（2026-08-24）——日线战术层（L4 · Tactical Timing）

按"将日线分析加入正式模型，但作为战术层而非第四个平权周期"的优化方案实施：

**架构**：Q/M/W 决定战略方向（Long/Neutral/Defensive），Daily 只决定时机。
Daily 权限：早入场（WAIT→ENTER）、战术加仓（ADD）、战术减仓（REDUCE）、持有不减（PULLBACK）；
Daily 无权改变 Q/M/W 状态、无权单独产生长期 BUY。

**实现**：

| 模块 | 说明 |
| :-- | :-- |
| `tactical/daily_tactical.py` | 日线因子（F：超大单+大单净额、60 日 PIT Z、改善斜率；P：均线/趋势分/量比/20 日 VWAP/前 20 日高低）+ 4 状态合成（BREAKOUT > DISTRIBUTION > PULLBACK > ACCUMULATION > NEUTRAL），全 PIT 无泄漏 |
| `scripts/daily_tactical_engine.py` | 全市场计算 → `qcfp_daily_tactical`（47,297 行，含状态/因子/质量）；已加入 `run_QCFP_MTF_workflow.py` |
| `fusion/daily_timing.py` | Model B 日线时机门：BREAKOUT/ACCUMULATION→早入场+战术加仓（×1.25 不超 Risk 上限）、DISTRIBUTION→战术减仓（×0.5）、PULLBACK→持有；默认 `daily.timing.enabled=false` |
| `scripts/wave_replay.py` | 2024 波段事件回放：26 周涨幅≥50% 波段的 T0/+20%/+50%/+90% 四层状态，判断"哪一层最先识别" |
| `scripts/daily_alpha_test.py` | Model A(QMW) vs Model B(QMWD)：收益/风险/换手 + MFE/MAE + 01951 波段 + 5 项验收（波段捕捉提升为必过项） |
| DSS/All-in-One | 决策摘要新增"战略 × 战术"行与"## 4.5 日线战术层"小节（日线状态+时机提示）；快照新增日线战术行 |

**诊断结论（如实呈现）**：

1. **2024 波段回放**（14 个 26 周涨幅≥50% 波段）：急突破波段（00268、03033）在 +20% 节点**日线层最先识别**（D=Y 而 Q/M/W=N），说明日线对"突破型"波段有增量；但 01951 的爬坡式反弹在 +20% 节点**四层全部未识别**（Q=DECLINE、M=Stable、W=Consolidation、D=NEUTRAL）；
2. **01951 波段日线状态**（2024-02~10）：NEUTRAL 122 / PULLBACK 35 / ACCUMULATION 23 / DISTRIBUTION 2 / BREAKOUT 0——日线层有 23 天吸筹信号但无突破；
3. **增量测试（Model A vs B）**：B 未提升 01951 波段（7.31%→7.15%），组合 Sharpe 0.020→-0.004、回撤 -24.77%→-25.55%；验收 **3/5**（波段捕捉提升 FAIL 为必过项）→ 按验收标准**日线层保持诊断层，不接入生产决策**；
4. **MFE/MAE 诊断**：两模型入场后平均 MFE 21.96%、但实现收益为负（捕捉率 -73%）——**真正瓶颈是退出/持仓机制（移动止损与减仓让利润回吐），不是入场识别**；这与"加日线≠解决问题"的判断一致。

**2D 决策**：报告层输出"战略定位（LONG/NEUTRAL/DEFENSIVE）× 战术动作（ENTER/ADD/HOLD/REDUCE/EXIT/WAIT）"，数据库 action_signal 不变。

**启用方法**：当新的日线规则（如更优的吸筹/派发阈值或日频退出机制）通过 `daily_alpha_test.py` 验收后，将 `qcfp_settings.yaml` 的 `daily.timing.enabled` 改为 `true` 即可正式接入（生产与回测共用同一门）。

### V15 交付记录（2026-08-24）——Correctness Hardening（P0）+ Backtest Credibility（P1）

按《融合审查与改进建议》的优先级执行：**先保证"数据 → 状态 → 决策 → 仓位 → 回测 → 报告"完全一致，再解决 Alpha**。

**P0-1 四概念决策语义统一**：不再让 TEST_BUY 直接充当 Action。DSS/All-in-One 摘要分列：
`MTF State` / `Action Signal` / `Tactical Override` / `Trade Intent` / `Target Position`；
数据库 `action_signal` 保持 REDUCE（驱动回测），`trade_intent`（TEST_BUY）仅报告层展示。

**P0-2 战术覆盖全链路自动化核查**：新增 `tests/test_decision/test_tactical_chain.py`——
用 01951 真实场景（DECLINE + Improving + Consolidation + 52W=0.0272）断言
`align_mtf → BULLISH_WARNING/tactical_override → generate_action=REDUCE → CQS 20% → 止损展示`，
并核对数据库 01951 最新行与代码规则一致（明确是 `min_trigger=[B+P+C]` 配置生效，非旧结果）。

**P0-3 止损单一来源（StopLossPolicy）**：新增 `decision/stop_loss.py`，
`decision.stop_loss_policy {type: entry_week_low, buffer_pct: 0.02}` 为唯一止损来源；
Backtest（`engine._apply_trailing_stop`）、DSS/All-in-One 的"止损触发"均从同一 Policy 读取，
报告不再自行解释（原"周线放量跌破季VWAP×0.95"文本已废弃）。

**P0-4 E2E 一致性测试**：新增 `tests/test_e2e/test_e2e_consistency.py`——
同一输入从 State → Action → Target → Backtest(position=target.shift(1)) → Report 全链断言，
强制 `Report MTF State == DSS MTF State / Report Action == DSS Action / Report Target == Backtest Target / Report Stop == Backtest Stop`。

**P1 回测可信度**：

- **RUN STATUS 门**（`backtest/run_status.py`）：回测 summary 与 All-in-One 顶部显示
  `PASS / PASS_WITH_WARNING / FAILED`（PIT disclosure=ESTIMATED → WARNING；PIT universe 缺失：
  production → FAILED、research → WARNING）；
- **成本语义**：区分年化毛换手 / 年化交易成本 / 成本占换手比 / 平均仓位 / 平均单笔换仓，写入 summary 与报告；
- **HTML 报告新增两图**：回撤曲线（水下周期）与滚动 12M Sharpe（`html_report.py`）。

**P2 实验（Market Regime Gate）**：`regime_gate_test.py`（risk_off → target×0.25）实测：
MDD -24.77% → **-21.51%**（改善 3.3pp）、risk_off 年化 -9.37% → -6.97%；
但 Sharpe 0.020 → -0.030、换手 1.39 → 2.74（每次 risk_off 来回降/升杠杆产生大量交易）。
结论：简单降杠杆门以换手翻倍换回撤改善，**暂不部署**；后续可试"仅禁止 risk_off 新增买入"的平滑变体。

**分级定位（按审查口径）**：工程架构 8.0~8.5、研究框架 7.0~7.5、策略有效性 4.0~5.0、
整体研究成熟度约 6.5~7.0（Level 2 Research Framework）——策略 Alpha 尚未证明，重点继续 Correctness/PIT/Liquidity。

**遗留（后续阶段）**：真实披露日历（qcfp_disclosure_dates.csv 已有加载器，需数据源）、
ADV/参与率/滑点流动性模型、严格统一口径的 P/P+C/P+F/P+C+F 增量实验（incremental_alpha_test 已有雏形）、
参数校准自动化门、行业中性化与组合风险约束。

### V16 交付记录（2026-08-24）——PIT/回测口径修正 + 层级消融验证

按《融合审查与改进建议》第二轮清单执行（重点：把 PIT、Universe、回测口径与增量验证做严）：

**P0-3 修复横截面换手语义 bug**：`cross_sectional.py` 的 `agg["turnover"] = agg["cost"]` 修正为
`turnover = gross_turnover`（成本独立成列），修复年化换手/成本分析被污染的统计口径。

**P0-2 统一 Chip/Structural 披露日**：`build_signal_timeline` 与 `mtf_fusion_engine` 的 chip
available_date 改为优先使用结构表同一季度的 available_date（含真实披露覆盖），无匹配才回退
quarter_end + lag——消除"C 与 F/P 可用时间口径不同"的不一致。

**P0-4 止损命名与执行语义**：`_apply_trailing_stop` 更名 `_apply_entry_week_low_stop`；
报告止损文本注明"**周线收盘确认，不做盘中触发**"（实际执行语义与展示一致）。

**P0-1 PIT 分级（PIT-A/PIT-C）**：`run_status` 输出 `pit_grade`（真实披露覆盖=A、固定滞后估算=C）；
回测 summary 增加研究注册表雏形：`config_hash` / `pit_grade` / `cost_model_version`。

**P1-1/P1-3 层级消融实验**（`layer_ablation_test.py`，增量贡献矩阵 + 试多专项统计）：

| 模型 | 年化 | Sharpe | MDD | PF | 换手 | IC13 | 01951 波段 |
| :-- | --: | --: | --: | --: | --: | --: | --: |
| Q（仅季度结构） | -1.31% | -0.041 | -32.67% | 0.984 | 0.33 | +0.026 | 0.00% |
| QM（+月线门） | -2.29% | -0.239 | -25.87% | 0.913 | 1.20 | +0.020 | 0.00% |
| QMW（完整管道，无覆盖） | -0.58% | -0.022 | -23.97% | 0.992 | 1.05 | **+0.037** | 0.00% |
| **Full（+战术覆盖）** | **-0.24%** | **+0.020** | -24.77% | **1.008** | 1.39 | +0.035 | **+7.31%** |

**结论（如实）**：

- **月线阶段门（QM）当前是负贡献**（Sharpe -0.239，明显差于 Q）——月度行为作为"门"的设计需重新评估；
- QMW 管道 Rank IC 最高（0.037），说明 MTF 状态有横截面信息量，但绝对收益仍弱；
- **战术覆盖（Full）是唯一让 Sharpe 转正（+0.020）、PF>1、并捕捉 01951 波段的层**；
- 试多专项：1,058 试多周 / 12 股，平均目标仓位 12.2%，试多周均 pnl **+0.105%**（机制本身温和为正）；
- C/F 独立增量仍弱（IC13 0.02~0.04；条件回归 F 边际、C 不显著）——与 QCFP 名称能否成立直接相关，留待真实 PIT/更长样本复验。

**五类金融不变量测试**（`tests/test_backtest/test_invariants.py`）：PIT 不变量（披露日≤决策日）、
Position ∈ [0,1]、成本守恒（pnl=position×ret−cost 精确）、基准独立性。

**报告决策卡**：DSS 顶部新增 `## 0. 决策卡`（Strategic Regime / Structural / Behavioral /
Tactical Trigger / Tactical Opportunity / Risk / Position + WHY / INVALIDATION / CONFIDENCE）；
`Strategic Regime` 由季度结构推导（LONG/BEARISH/NEUTRAL），01951 显示
"**BEARISH × 试多（TEST_BUY）**"——战略偏空、战术试多的语义不再让用户自行推断。

### V17 交付记录（2026-08-24）——Entry-Week-Low Stop 回测完整性修复 + 模型诊断页

按《融合审查与改进建议》第三轮清单执行（P0 回测完整性 > P1 因子消融 > P2 Override 单独验证）：

**P0（最高优先级）止损周收益处理修复**：

- 旧实现：止损周把整周 position 直接改为 0 → 该周价格损失不进 pnl（**回测被高估**）；
- 新实现（`engine._apply_entry_week_low_stop`）：止损周按"**止损价成交**"——承担
  周初到止损价的损失（effective_return = stop/prev_close−1），随后退出；
- 引擎输出新增 `position_start`（周初仓位）与 `effective_return`（止损周=止损价收益，其余=周收益）；
  pnl = position_start × effective_return − cost，成本守恒可验证（不变量测试已更新）；
- **如实影响（全市场 + 01951）**：

| 指标 | 修复前 | 修复后 |
| :-- | --: | --: |
| Full Sharpe | +0.020 | **+0.014** |
| 01951 2024-02~10 波段 | +7.31% | **+4.34%** |
| 01951 2024 年化 | +4.64% | **+1.74%** |
| 试多周均 pnl | +0.105% | **+0.098%** |

结论：旧实现确实高估（止损周"免费"）；修复后方向结论不变（覆盖仍为正贡献、整体 Alpha 仍未证明），口径更严格可信。

**P1 因子消融补充（上下行捕获）**：`layer_ablation_test.py` 新增 upside/downside capture：

| 模型 | 上行捕获 | 下行捕获 | 01951 波段 |
| :-- | --: | --: | --: |
| Q | 0.348 | 0.353 | 0.00% |
| QM | 0.222 | 0.244 | 0.00% |
| QMW | 0.251 | 0.253 | 0.00% |
| Full | 0.272 | 0.270 | +4.34% |

解读：各模型上下行捕获基本对称（≈0.25~0.35），属于低暴露策略，**未见"抓涨避跌"的不对称优势**；
Full 的 Sharpe 转正主要来自试多机制的正贡献（周均 pnl +0.098%），而非组合层的方向不对称。

**P2 Override 单独验证**：消融矩阵并列 QMW（无覆盖）vs Full（有覆盖）——Full 是唯一 Sharpe>0、
PF>1、捕捉 01951 波段的层，且试多周均 pnl 为正；Override 机制本身值得保留并单独研究。

**P3 Daily 保持诊断层（按建议不变）**；**P4 参数优化最后做（按建议不变）**。

**报告**：All-in-One 新增 `## 3.5 模型诊断（Layer Ablation）` 页，自动嵌入最新消融矩阵
（年化/Sharpe/MDD/PF/换手/IC13/上下行捕获/波段）。

### V18 交付记录（2026-08-24）——Dynamic Risk Exit（下行风险层）

基于 00371 北控水务 2026-05~08 逐日回放（价格 -28.7% 而系统全程 HOLD）实施"下行风险层"，
目标：**长期结构未确认转空时，也能根据中短期风险证据主动降仓/退出**（Downside Risk 权限高于 HOLD）。

**P0-A MTF 兜底修复**（`fusion/mtf_alignment.py`）：BULLISH 族 + **任意阶段** + 周线 Breakdown
→ `BULLISH_WARNING`（REDUCE），不再被兜底成 BULLISH_STABLE/HOLD。

**P0-B 下行风险层**（`decision/downside_risk.py`）：

- **Downside Evidence Score（DES）**：周线破位(+2)/连续破位(+1)/close<MA20(+1)/MA5<MA10(+1)/
  MA20 斜率<0(+1)/flow_z<0(+1)/flow_z<-1(+1)/DAILY_DECLINE(+2)/CQS<0(+1)/5W<-5%(+1)/
  13W<-10%(+1)/距 52W 峰>-15%(+1)；0-2 NORMAL / 3-4 WATCH / 5-6 REDUCE / 7+ DE-RISK；
- **风险下限（Risk Floor）**：破位且 close<MA20 → risk = max(risk, **Extreme**)，禁止因
  "无背离/dq 改善/市场中性"降回 Low（修复 8/21 risk=Low/target=0.75 漏洞）；
- **滞后解除**：站回 MA20 且连续 2 周无破位才解除（进入风险容易、解除困难）；
- **仓位单调性**：风险下限生效期间目标仓位不得上升（DES≥7 → EXIT/0）。

**P1-C 日线持续下降状态**：新增 `DAILY_DECLINE`（close<MA20 且 MA5<MA10，有资金流时要求
flow_z<0）+ `qcfp_daily_tactical.d_decline` 列；日线状态/资金流作为下行证据进入 DES
（`daily.risk` 生效；`daily.timing` 买入时机仍默认关闭）。

**P1-D CQS 负值**：作为 DES 的一项证据（需与其他下行证据叠加才触发减仓，避免单点噪音）。

**生产链路**：`decision_engine.py` 应用下行风险层并回写 `des_score/des_band`；
DSS 决策卡新增 `DOWNTREND EVIDENCE`（DES + 档位 + 风险下限标记）。

**00371 金标准回归**（`tests/test_decision/test_00371_downtrend_exit.py`）：

| 检查点 | 修复前 | 修复后 |
| :-- | :-- | :-- |
| 6/19 首次周线 Breakdown | HOLD / High / 0.5 | **EXIT / Extreme / DES=8** |
| 6/26 连续 Breakdown | HOLD / High / 0.5 | **EXIT / Extreme / DES=9** |
| 8/21 持续下跌（dq 改善/市场中性） | HOLD / Low / 0.75 | **EXIT / Extreme / DES=12** |

风险下限全程保持、仓位单调不反弹；50 个测试模块全部通过。

**E（季度披露滞后）**：按审查定性为"非 bug"——季度数据披露前本就不能用（PIT），
正确分工为 Quarterly=战略 / Weekly=结构预警 / Daily=战术风险。

### V19 交付记录（2026-08-24）——Research Integrity（研究可信度基础设施）

按《融合审查与改进建议》第四轮清单执行（目标：QCFP-MTF 2.2 Research Integrity，先修 P0 再谈因子）：

**P0-1 横截面 target 语义修复**（`backtest/cross_sectional.py`）：

- 组合权重从 `target/sum(target)`（错误归一化到 100%）改为 **`target/N`**——target 是"单股票目标暴露"，
  组合总暴露 = 入选股 target 均值（N=5、target=0.2 → 每只 4%、总暴露 20%）；
- 完整 stock×交易周 网格改为来自**周 K 日历**（而非 signal∩return），显式统计
  `n_signal_missing / n_return_missing`；任一持仓股 return 缺失 → 该周绩效标记缺失，
  **不再用 fillna(0) 把缺数据变成 0 收益**。

**P0-2 止损执行假设修复**（`backtest/engine.py`，方案 A）：

- 不再假设"周收盘确认 → 本周按止损价成交"（含未来信息）；改为 **周收盘确认 → 该周完整承受周收益 → 次周离场**；
- `effective_return` 恒等于周收益（取消 stop_ret 替换）；测试与不变量同步更新；
- 报告文本："周线收盘确认 → 次周离场；不做盘中触发"。

**P0-3 研究验证门去"假 PASS"**（`scripts/research_validation.py`）：

| 门槛 | 修复前 | 修复后 |
| :-- | :-- | :-- |
| 03 Signal/Return | 硬编码 PASS | 真校验：signal 唯一率 / return 覆盖率 / 跨周 shift 违规（position==target.shift(1)，排除文档化止损覆盖） |
| 07 Parameter Plateau | 只查同参率 | 同参率≥80% **且** 平台占比≥50% 才 PASS（60%/30% WARN） |
| 08 HAC/Bootstrap | any(\|t\|≥2) | **BH-FDR 多重检验校正**后显著才 PASS |
| 09 Factor Ablation | Full 超额>0 | Full 超额 > 0.5% **且** 相对基准增量 > 0.5% 才 PASS |
| 10 Regime Robustness | risk_on/neutral>0 | + risk_off ≥ -25% 护栏 + 环境集中度 < 80% |

实测（研究模式）：**PASS 6 / WARN 4 / FAIL 0（Conditional）**——07 同参率 75%→WARN、
09 Full 超额 -2.12%→WARN，不再虚报 PASS。

**P0-4 All-in-One Scope 分离**：报告头部新增 `Scope / Provenance`（Analysis/Backtest/Research 三口径 +
PIT + Universe + Execution）；回测汇总拆分 **Engineering Status**（管道）/ **Research Status**
（OOS 中位数>0 才 VALIDATED）/ **Economic Evidence**（Sharpe 符号）；模型诊断节标注
"Scope：Full Universe（焦点股票 01951）——与上方个股回测不同口径"。

**P1 其他**：

- PIT Universe 重叠检查（`pit_universe.validate_universe`：overlap>0 → 01 门槛 FAIL）；
- 不变量测试改为**纯合成数据**（脱离 SQLite，`tests/test_backtest/test_invariants.py`）；
- 新增 `pytest.ini`（注册 integration marker）；
- 基准 `hsi_returns` 防御性排序（修复 unique() 无序导致的 merge_asof 报错）；
- HTML 报告补 viewport + 中文字体栈；qcfp 核心表新增 `(stock_code, period, model_version)` 复合唯一索引
  （支持多模型版本并存）。

**当前定位（按审查口径）**：工程 8/10、回测工程 6.5→7、研究方法 5.5→6（验证门已严格化，
但 PIT-C/Universe/流动性仍缺）、报告 7→7.5；整体仍为 **Research NOT VALIDATED**（OOS 中位数<0、
Full 超额为负）——诚实结论保留在报告最顶部，不再与工程状态混淆。

### V20 交付记录（2026-08-24）——回测可信度（Missing/缺失语义 + 组合账本 + 压力测试）

按第五轮审查清单继续加固"回测可信度"（P0-3/P0-4/P0-1 + P1 项）：

**P0-3 缺失收益语义修复**（`backtest/engine.py`）：持仓周 return 缺失 → `pnl=NaN` 并标记
`return_missing`，**不再 fillna(0) 把 NO_DATA 变成 ZERO_RETURN**；组合层跳过缺失周而非当 0。

**P0-4 组合账本（Portfolio Ledger）**（`portfolio_returns`）：每周输出
`avg_exposure / cash_weight / n_stocks / n_missing_return`——"平均暴露 36.3%"从此有明确
经济含义（= 周均 position_start，现金 = 1 - 暴露）。

**P0-1 三档 PIT Universe 模式**：`research_exploration`（缺 universe→WARN）/
`research_validation`（缺 universe→**FAILED**）/ `production`（FAILED），由
`backtest.mode` 控制；同一 Sharpe 在"无 PIT"与"有 PIT"下不再同等级可信度。

**P1 OOS 多条件门槛**（研究验证 06 门）：median OOS Sharpe>0.3 且正窗≥60% 才 PASS
（0.2~0.3 边界 WARN，否则 FAIL）——实测 OOS 中位数 1.048 但正窗 50% → **FAIL**（诚实拦截）。

**P1 成本压力测试**（`cost_stress_test.py`，成本×0.5/1/2/3/4）：

| 成本乘数 | 年化 | Sharpe | MDD | PF | 年化成本 |
| :-- | --: | --: | --: | --: | --: |
| ×0.5 | -1.40% | -0.22 | -20.4% | 0.91 | 0.62% |
| ×1 | -1.98% | -0.33 | -22.1% | 0.87 | 1.19% |
| ×2 | -3.11% | -0.53 | -25.4% | 0.80 | 2.35% |
| ×4 | -5.35% | -0.93 | -33.7% | 0.68 | 4.66% |

→ 策略对成本高度敏感（×1→×4 Sharpe -0.33→-0.93），验证门 12 WARN。

**P1 Decision Trace**：DSS 决策卡新增 `Tactical Risk Override: ACTIVE/INACTIVE`；
`QCFP 评分` 更名 `State Score`（状态编码，非连续预测分数/非收益概率）。

**P1 Golden Dataset**（`tests/golden/`）：00371 下行（BULLISH+Breakdown+DES≥7→EXIT/Extreme/0）
与 01951 恢复（DECLINE+52W 极低→TEST_BUY/20%）两个金标准案例 + `test_golden_cases.py`，
锁定输入→输出防规则漂移。

**All-in-One 口径修正**：Layer Ablation 默认**无焦点股票**（universe 级），
报告标注"Scope：Full Universe（无焦点股票）"。

**验证门扩至 12 门**：新增 11 Delisting/CA（周 K >21 天缺口检查，实测 3 行→WARN）、
12 Capacity/Liquidity Stress（成本压力产物）。实测：
**PASS 5 / WARN 6 / FAIL 1（Conditional）**——06 OOS 正窗不足、12 成本敏感被如实拦截。

**如实说明**：下行风险层显著改善回撤（Full MDD -24.77%→-22.11%）但以换手上升
（1.39→2.92）与 Sharpe 下降（+0.014→-0.326）为代价——"敏感度升级"在全市场口径代价明显，
DES 权重/风险下限/退出阈值均可在 `qcfp_settings.yaml` 校准（Phase 4 参数调优前不硬调）。

### V21 交付记录（2026-08-24）——止损 PnL 暴露修复 + 研究清单 + 预测/交易双轨

按第六轮审查 P0（回测正确性）执行：

**P0-1 止损后 PnL 暴露修复**（`backtest/engine.py`）：

- 旧缺陷：`position_start = orig_positions` 使止损退出后的后续周仍保留原 target 仓位，
  PnL 继续按残留仓位计收益（**退出后仍有暴露**）；
- 修复：止损确认周 `position_start=原仓位`（完整承担当周收益），之后逐周
  `position_start=0`（FLAT，无未来 PnL）；测试新增 `position_start==0` 与 `pnl==-cost` 断言。

**P0-2 缺失收益语义修复**：`_apply_entry_week_low_stop` 移除 `effective_return.fillna(0)`，
缺失收益保持 NaN → `return_missing` 标记真实有效；组合层计数 `n_missing_return` 而非当 0。

**P0-3 金融不变量测试**（`tests/test_backtest/test_financial_invariants.py`）：
止损后无未来暴露 / 缺失收益不变成 0 / 缺失收益不改变组合分母 /
PIT Universe 重叠检测 / research_validation 模式缺 universe → FAILED。

**P1 预测能力 vs 交易能力双轨**（`layer_ablation_test.py`）：

- 新增 **IC 衰减曲线**（4W/13W/26W）与 **ICIR**；
- 实测（Full，universe 级）：IC4 **0.007** → IC13 **0.025** → IC26 **0.054**（单调上升，
  信号更偏结构/长周期），ICIR13 **0.079**（弱但为正）；
- 与交易层（Sharpe -0.32、换手 2.92、成本敏感）对照：预测信息为正但微弱，
  **交易损耗主导组合表现**——支持"因子有微弱信号、交易规则吃掉 alpha"的判断方向。

**P3 Research Manifest**（`backtest_runner`）：每次回测输出
`research_manifest_{run_id}_{stock}.json`——run_id / model_version / config_hash /
code_hash / data_snapshot（各表行数）/ pit_mode / pit_grade / universe_version /
区间 / cost_model_version——`Sharpe=-0.3582` 从此可追溯到确切代码、配置、数据与口径。

**全量测试 52 模块通过**；00371 单股回测在止损修复后 2026 年仍为 -1.08%（风险层 EXIT 路径
无持仓，修复主要影响试多段的退出周）。研究状态维持 **RESEARCH NOT VALIDATED**（如实）。

### V22 交付记录（2026-08-24）——PIT 硬门 + 基准同口径 + 超额定义 + 决策字段标准化

按第七轮审查 P0（回测口径）执行：

**P0-1 PIT 硬门**（`backtest/run_status.py`）：`research_validation` 模式只允许 PIT-A/B，
**PIT-C → FAILED**（不再是 PASS_WITH_WARNING）；PIT-C 只能用于 research_exploration。

**P0-2 基准同口径**（`backtest/pit_universe.py::filter_price_universe`）：Buy&Hold 与
Momentum 基准在 PIT Universe 存在时，**与策略共用同一历史股票池过滤**——不再出现
"策略过滤、基准不过滤"的口径错配。

**P0-3 超额收益定义修正**（`backtest/benchmark.py::excess_stats`）：不再把
`compound(strategy - benchmark)` 单独称为 alpha；同时输出
**strategy CAGR / benchmark CAGR / CAGR spread / 算术主动收益（mean×52）/ IR**；
`excess_annualized` 保留为 CAGR spread（严格口径）。

**P0-4 缺失收益机制**（`backtest/cross_sectional.py`）：缺失收益的持仓股**仅从该周剔除**，
不再整周删除（保留其余股票与周），并统计 `n_missing_stock_weeks`；整周无有效收益才标记缺失。

**P1-5 决策字段标准化**（`qcfp_mtf_decision` 新增列 + `decision_engine` 生产回写 + DSS）：

- `base_action / final_action / base_target / final_target / risk_override_active / alignment_override`；
- DSS 摘要重命名 `Tactical Override` → **Alignment Override**，新增 **Base → Final** 行；
- 00371 实测：`REDUCE → EXIT`、base_target 0.5 → final_target 0、risk_override_active=1、
  alignment_override=0（对齐层未覆盖、风险层覆盖）。

**P1-6 绩效口径标准化**（`backtest/performance.py`）：

- Sortino 改为标准 downside deviation = `sqrt(mean(min(r - target, 0)^2))`；
- 新增 `positive_week_rate`（无持仓信息时 win_rate 实为"正收益周占比"，两者并列输出）。

**全量测试 52 模块通过**；数据字典已同步。遗留：真实披露日历与 PIT Universe 数据（外部数据源）、
ADV/参与率成交模型、iterrows 向量化——已在研究清单（manifest）与 12 门验证中留好接口。

### V23 交付记录（2026-08-24）——散户波段决策系统（Retail Execution Layer）

按第八轮方案将 QCFP-MTF 正式定位为「机构状态识别 + 散户择时/空仓系统」：
机构研究层（C/F/P、IC、回归、OOS）全部保留在后台，前台只回答四个问题：
**Risk → Regime → Trigger → Position**。

**新增 `decision/retail.py`（散户执行层）**：

- **红黄绿灯**：🔴 RED（BEARISH_CONFIRMED / Extreme / DES≥5 / 破位+High）＝"我不参与"（非看空做空）；
  🟢 GREEN（BULLISH 族 + Low/Medium + DES<5）；🟡 YELLOW（观察/试错）；
- **六态交易阶梯**：WAIT(0) / TEST(10~20%) / BUILD(30~60%) / HOLD(50~80%) /
  REDUCE(20~40%) / EXIT(0)——映射自 MTF + Risk + DES + 周线触发；
- **散户仓位建议**（`retail.position_bands`）：Extreme 0%、High 0~20%、Low+Recovery 30~50%、
  BULLISH_STABLE 50~70%、BULLISH_CONFIRMED 60~80%、**100% 仅限极强+risk_on 特例**；
- **A/B 股票池**：A 池（趋势持仓：结构多头+月线改善/稳定+周线突破/盘整+Risk≤Medium+筹码≥Medium）、
  B 池（反转观察：结构空头/底部候选+52W<0.15+月线改善+周线突破+Risk≤Medium——**非立即买**）；
- 哲学：**Bottom ≠ Buy**；Risk Reduction + Structural Improvement + Price Confirmation = Buy Permission。

**报告**：DSS/All-in-One 新增 `## 0.1 散户决策卡（Retail Execution）`——红黄绿灯/交易状态/
建议仓位/趋势/风险 + 红灯"禁止抄底/补仓/提前下注"与"重新观察条件"。

**工具**：`scripts/stock_pool_report.py` 输出 A/B 池（MD/CSV/JSON，每只含 MTF/交易状态/风险/DES/52W）。

**实测（00371 2026-08-21）**：🔴 RED / EXIT / 0% / 禁止抄底——与机构层
（BULLISH_WARNING → REDUCE → EXIT，DES=12）一致但语言更贴近散户执行。

**测试**：`tests/test_decision/test_retail.py`（红黄绿灯、六态阶梯、仓位不带默认 100%、A/B 池判定）；
全量 53 模块通过。

### V24 交付记录（2026-08-24）——Institutional Permission Engine + Retail Position FSM

按第九轮方案实施 QCFP-MTF 3.0 的两个核心中间层（机构过滤器 + 散户仓位状态机），
**不推翻现有代码**：Structural FSM / MTF / DES / Daily Tactical / Retail 六态全部保留。

**P0-1 Institutional Permission Engine**（`decision/institutional_filter.py`）：

- `institutional_state`：ACCUMULATION / ACCUMULATION_WEAK / NEUTRAL / RECOVERY /
  DISTRIBUTION / DISTRIBUTION_STRONG / CAPITULATION / UNKNOWN（由 C/F/P 状态判定）；
- `institutional_pressure`：+2 强吸筹 ~ -2 强派发；
- `institutional_persistence`：连续 F↑ 季度数（0~4）；
- `institutional_permission` 五档：**BLOCK / WATCH / TEST / ALLOW / STRONG_ALLOW**
  （ACCUMULATION+持续性≥2+压力+2+无背离 → STRONG_ALLOW）；
- 定位变化：**C/F 从"Alpha 评分器"转为"交易权限过滤器"**——P/M/W 负责机会，
  Risk 负责 kill switch。

**P0-2 Retail Position FSM**（`decision/retail_fsm.py`）：

- 状态：FLAT → TESTING → BUILDING → HOLDING → TRIMMING → EXITING → **COOLDOWN**；
- **Hard Exit > 结构看多**：DES≥7 / Extreme / 破位+BLOCK → EXITING（不再被 BULLISH 族挡住）；
- **Cooldown**：EXIT → COOLDOWN（默认 2 周）→ 必须重新满足权限 + 日线突破/回踩才允许 TEST，
  消除"刚止损又买回"的震荡损耗；
- **Chase Filter**：日线突破但 52W 位置 > 0.6 → 禁止 BUILD（等回踩），
  突破 ≠ 一定追进去；
- 仓位状态感知：TEST 10~20%、加仓 +10~20%、已有仓位不再追（替代 `target×1.25` 的粗糙加仓）。

**P0-3 Hard Exit 架构澄清**：`action_generator` 的"BULLISH 族禁止 EXIT"仅约束**结构本身**；
Hard Risk Gate（DES≥7 等）拥有更高 EXIT 权限——已由 `test_hard_exit_overrides_bullish` 固化。

**报告**：散户决策卡新增 **机构状态/压力→权限** 与 **仓位状态(FSM)** 行
（00371：NEUTRAL(+0) → WATCH，FSM=COOLDOWN）。

**股票池升级为四池**（`stock_pool_report.py`）：
A 池 Institutional Trend（权限 ALLOW/STRONG_ALLOW）/ B 池 Recovery（RECOVERY+52W 低位+周线突破）/
C 池 Swing Watch（WATCH+日线 Setup+Risk≤Medium）/ D 池 Risk（派发/破位/投降）。
实测（2026-08-21）：A 0 / B 0 / C 1 / D 6——市场整体处于风险池，符合 DES/风险层判断。

**测试**：`tests/test_decision/test_institutional_filter.py`（状态/权限/压力/持续性、
Hard Exit、FSM 生命周期含 Cooldown、Chase Filter）；全量 **54 模块通过**。

### V25 交付记录（2026-08-24）——QCFP-MTF 2.2 Design Freeze（正式接口 + 测试驱动重构）

按第十轮方案进入 **Architecture / Design Freeze → Unit Test → Implementation** 阶段：
把已有的 institutional_permission / retail_fsm 雏形**正式化、解耦、补齐规则**；
**先不动生产路径、不调参、不开 Daily Timing**（新增模块 → 双轨运行 → 测试 → Ablation → 替换）。

**1. Institutional Permission Engine（正式接口）**（`decision/institutional_permission.py`）：

- `evaluate_institutional_permission(state, pressure, persistence, divergence,
  confidence, data_quality, market_risk, settings)` → `{permission, state, pressure,
  persistence, confidence, reason_codes}`；
- 权限矩阵冻结：ACCUMULATION(压力≥+1,持续≥2)→ALLOW / (+2,≥2)→STRONG_ALLOW；
  NEUTRAL→WATCH；RECOVERY(≥+1,≥1)→TEST；DISTRIBUTION(≤-1,≥2)→BLOCK；
  DISTRIBUTION_STRONG(≤-2,≥2)→BLOCK；CAPITULATION→BLOCK；UNKNOWN→WATCH；
- **降级-only**：divergence / low_confidence → WATCH；poor_data_quality(D) → BLOCK；
  market_risk_off → TEST；**BLOCK 不能被 Daily Breakout 升级**（权限是交易上限）；
- Permission ≠ Signal ≠ Action ≠ Position（四态分离）。

**2. Retail Position FSM（冻结版）**（`decision/retail_position_fsm.py`）：

- `RetailDecisionContext` dataclass 统一输入（institutional_permission/state、MTF、
  weekly/daily、risk/DES、current_position、chase_filter、stop_triggered、hard_exit、
  cooldown_remaining）；
- 状态转移冻结：FLAT→TESTING→BUILDING→HOLDING→TRIMMING→EXITING→COOLDOWN，
  **禁止状态跳跃**（FLAT 不得直接 HOLDING）；
- **HARD_EXIT > ALL**：DES≥7 / Extreme / stop → 无条件 EXITING/COOLDOWN，
  不能被 BULLISH/ALLOW/BREAKOUT 覆盖；
- 权限≠FSM：ALLOW + DAILY_NEUTRAL + FLAT → FLAT（有资格≠有机会）。

**3. 配置正式化**：`institutional.permission`（persistence_min_quarters、降级开关）、
`retail.fsm.position`（test 0.10 / build_step 0.10 / max_position 0.70）、
`risk.hard_exit`（des_threshold 7）——第一版不放过多可调参数。

**4. 测试（先于实现验收）**：

- `test_institutional_permission.py`：权限矩阵 8 例 + 降级 5 例 +
  **BLOCK 不可被 DAILY_BREAKOUT 升级** + ALLOW 无 Setup 保持 FLAT；
- `test_retail_position_fsm.py`：全生命周期 + 禁止跳跃 + HARD_EXIT 最高优先级 +
  BLOCK/COOLDOWN 边界；
- 全量 **56 模块通过**。

**5. 轻量 Permission Ablation**（股票池报告）：机构权限分布实测
`{WATCH: 15, TEST: 1}`（当前市场无 ALLOW/STRONG_ALLOW）——机构层目前以“观察/试错”为主，
与 DES/风险层判断一致。完整 A/B/C/D 四池回测 Ablation（Model A~D）留待下一阶段（Phase 7）。

### V26 交付记录（2026-08-24）——QCFP-MTF 2.2 Contract Freeze + 正式领域层

按第十一轮设计文档执行 **Contract Freeze → 正式接口 → 测试 → Shadow Mode**（先不动生产路径）：

**1. 架构冻结**（`Core/QCFP_MTF/ARCHITECTURE.md`）：

- 五边界：Institutional State ≠ Permission ≠ Setup ≠ Position State；Risk 可覆盖所有普通逻辑；
- **十条规则**：Permission 是交易上限（RULE 01）；Daily 不能升级 Permission（RULE 02）、
  不能直接决定仓位（RULE 03）；FSM 拥有仓位生命周期（RULE 04）；Sizing 拥有数值仓位（RULE 05）；
  Hard Exit 覆盖所有看多（RULE 06）；PIT-invalid 不产生 Research-valid 信号（RULE 09）；
  新架构必须过 Shadow Mode 才替换 Legacy（RULE 10）；
- 优先级：Hard Exit > Stop > Cooldown > Permission > Risk > Weekly > Daily > Position。

**2. Institutional 领域包**（`institutional/`）：state_engine / pressure / persistence /
divergence / confidence / permission 拆分；`evaluate_institutional_permission` 返回
冻结 `InstitutionalPermission` dataclass（含 reason_codes / downgraded）；旧
`decision/institutional_*` 改为薄转发（兼容既有调用）。

**3. Hard Risk Gate**（`decision/hard_exit.py`）：DES≥threshold / Extreme / stop /
周线破位（仅持仓时）→ hard_exit，FSM 最高优先级处理。

**4. Swing Setup 层**（`setup/swing_setup.py`）：weekly/daily/monthly/permission →
setup_type（NONE/BREAKOUT/PULLBACK/ACCUMULATION/RECOVERY），FSM 不再自行推导 Setup。

**5. Position Sizing 解耦**（`decision/retail_position_sizing.py`）：加法阶梯
TESTING→10%、BUILDING→+10%、TRIMMING→-15%、上限 70%（**废除乘法加仓 0.75×1.25**）；
FSM 只决定状态，Sizing 决定数值。

**6. Shadow Mode**（`scripts/shadow_mode.py`）：同屏输出 Legacy（DB action/target）与
New（Permission→Setup→FSM→target），**不写库不改交易**；实测 16 只全部显示差异
（New 当前以 WATCH→FLAT/COOLDOWN 0% 为主，与权限分布 {WATCH:15, TEST:1} 一致），
报告落盘 `Report/QCFP_MTF/shadow/shadow_mode_*.{csv,json}`。

**7. 测试**：新增 `test_2dot2_engines.py`（hard_exit / swing_setup / 加法仓位 /
四集成用例：BLOCK+Breakout→FLAT、TEST+Pullback→TESTING、ALLOW+Breakout+10%→BUILDING、
STRONG_ALLOW+Breakout+DES8→EXITING）；全量 **57 模块通过**。

**边界（按设计文档）**：不开 Daily Timing、不调参、不扩大仓位上限、不宣称有效；
Permission/FSM Ablation（Sprint 6）与 PIT/OOS/Robustness（Sprint 7）通过前不替换 Legacy。

### V27 交付记录（2026-08-25）——Code Consolidation + Permission/FSM Ablation

按第十二轮审查进入"收口阶段"（消除旧/新重复、冻结接口、验证因果链）：

**P0 FSM 单一事实源**：`decision/retail_fsm.py` 改为**薄转发**到
`decision/retail_position_fsm.py`（唯一正式 FSM），旧 next_state 逻辑删除；
`chase_filter` 迁入正式模块；旧测试全部改走新引擎（Setup 语义按冻结矩阵：BREAKOUT 需周线确认）。

**P1 Permission 降级联动 FSM**：

- HOLDING/BUILDING + Permission=BLOCK 且持仓>0 → **TRIMMING**（停止加仓并减仓，不立即 EXIT）；
- HOLDING + WATCH + High/Distribution → TRIMMING；
- 机构过滤器控制的是 **Exposure**（敢不敢暴露风险），不是 Direction（预测涨跌）。

**P1 不可越权矩阵测试**：BLOCK × {Breakout/Pullback/Consolidation} × {Low/Medium/High} → FLAT；
STRONG_ALLOW × Breakout × DES∈{7,8} → EXITING（无任何普通信号能绕过 BLOCK 或 Hard Exit）。

**P2 Permission + FSM Ablation**（`scripts/permission_fsm_ablation.py`，A/B/C/D 四模型）：

| 模型 | 年化 | Sharpe | MDD | PF | 换手 | 暴露 | 下行捕获 |
| :-- | --: | --: | --: | --: | --: | --: | --: |
| A Legacy | -2.10% | -0.346 | -21.87% | 0.87 | 2.93 | 14.5% | 0.150 |
| B Legacy+PermGate | -0.37% | -0.381 | **-2.95%** | 0.68 | **0.23** | 0.9% | 0.009 |
| C FSM（ALLOW） | +0.34% | **+0.502** | -0.31% | **2.71** | 0.34 | 0.4% | 0.002 |
| D Perm+FSM | 0.00% | — | 0.00% | — | 0.00 | 0.0% | — |

**研究结论（符合假设）**：

- **Permission 的价值 = Risk Filtering**：B 把 MDD -21.87%→-2.95%、换手 2.93→0.23、
  暴露 14.5%→0.9%（代价是几乎空仓、Sharpe 转负）——机构过滤器正确地在风险环境"关掉交易"；
- **FSM 的价值 = 入场/退出质量**：C（假设 ALLOW）在少数 Setup 上给出 **Sharpe +0.50、PF 2.71、
  MDD -0.31%**（加法阶梯 + 追高过滤 + 冷却期），但暴露仅 0.4%（Setup 需周线确认，稀有）；
- **D 在当前市场正确空仓**：权限分布 {WATCH:15, TEST:1} 无 ALLOW → FSM 保持 FLAT（空仓即正义）；
- 数字口径为 2021-08~2026-08、PIT-C，**不构成有效 alpha 证据**；MAE/MFE 与 PIT/OOS 验证待后续。

**全量 57 模块通过**；ARCHITECTURE.md 十条规则保持不变。

### V28 交付记录（2026-08-25）——架构收口（Permission×FSM 矩阵 + 暴露效率）

按第十三轮审查执行"架构收口 + 决策链验证"：

**1. Permission × FSM 状态矩阵冻结**（`retail_position_fsm.PERMISSION_FSM_MATRIX`）：

| Permission | FLAT | TESTING | BUILDING | HOLDING |
| :-- | :-- | :-- | :-- | :-- |
| BLOCK | FLAT（禁止开仓） | TRIMMING（停止加仓） | TRIMMING | TRIMMING |
| WATCH | FLAT（等待） | TESTING | BUILDING | HOLDING |
| TEST | TESTING | TESTING | BUILDING | HOLDING |
| ALLOW | TESTING | BUILDING | BUILDING | HOLDING |
| STRONG_ALLOW | TESTING | BUILDING | BUILDING | HOLDING |

- 补上 BLOCK×TESTING → TRIMMING 分支（原实现漏掉）；
- Hard Exit 完全独立于矩阵，优先级最高；
- **穷举矩阵测试**（5 权限 × 4 状态 = 20 例）全部通过。

**2. FSM Timeline 跨股票隔离**：`build_fsm_timeline` 改为按 stock_code 分组维护各自
FLAT/Cooldown 状态（原实现单状态串行，多股票会互相污染）；新增双股票交错测试。

**3. Hard Exit 覆盖扩展**：BUILDING/HOLDING/TRIMMING × {Extreme, Stop 触发} → EXITING 全通过。

**4. Ablation 新增暴露效率指标**（`permission_fsm_ablation.py`）：

| 模型 | 暴露效率 | 坏暴露比 |
| :-- | --: | --: |
| A Legacy | -0.145 | 0.662 |
| B Legacy+PermGate | -0.409 | **0.312** |
| C FSM | **+0.862** | 1.057 |
| D Perm+FSM | — | — |

**研究结论（强化假设）**：

- **Permission 把坏暴露比 0.66→0.31**（机构过滤器正确压低高风险阶段暴露）——Risk Filtering 假设成立；
- **FSM 暴露效率 +0.86**（每单位暴露的正收益贡献）——Entry/Exit 质量假设成立；
- D 在当前市场（权限全 WATCH/TEST）正确空仓；
- 口径 PIT-C、2021-08~2026-08，**不构成有效 alpha 证据**。

### V29 交付记录（2026-08-25）——唯一决策链收口（DecisionSnapshot + Stateful Shadow + A0~A4）

按第十四轮审查执行"唯一决策链收口"（消除 Legacy/FSM/Retail 三套平行决策源）：

**1. Canonical Decision Snapshot**（`decision/decision_snapshot.py`）：

- `DecisionSnapshot` 不可变对象：decision_id / inst_state / permission / permission_cap /
  exit_event(kind+reason) / setup_type / prev_fsm / next_fsm / prev_position /
  target_position / decision_path / rule_version / model_version；
- `build_decision_snapshot()` 运行唯一决策链（Institutional → Exit Events → Setup →
  FSM → Sizing），所有 action/card/report/shadow 从该对象派生；
- **ExitEvent 统一**（`hard_exit.evaluate_exit_events`）：HARD_EXIT / STOP_EXIT /
  FORCED_DELEVERAGE / NONE——FSM 不再自行重新解释 DES/Extreme/Stop（可审计"这次 EXIT 是谁触发"）。

**2. Permission Ceiling**（`retail_position_fsm.PERMISSION_CAP`）：

- BLOCK→FLAT、WATCH→TESTING、TEST→TESTING、ALLOW→BUILDING、STRONG_ALLOW→HOLDING；
- `permission_cap_exceeded()` 诊断 + `assert_permission_bound()` 审计断言；
- HOLDING（维持既有仓位）不算新增风险；BLOCK 只允许 FLAT/TRIMMING/EXITING/COOLDOWN。

**3. Stateful Shadow Mode**（`scripts/shadow_mode.py` 重写）：

- 从"每只股票单步 FLAT 计算"升级为**全历史滚动重放**（按 stock_code×decision_date 顺序，
  prev_state/prev_position 持续演化），输出 prev/candidate/final/transition_reason/
  permission_cap/exit_event/decision_id；
- 00371 全历史 868 个决策快照已落盘 `Report/QCFP_MTF/shadow/shadow_stateful_*.{csv,json}`。

**4. Ablation 升级 A0~A4**（`permission_fsm_ablation.py`）：

| 模型 | 年化 | Sharpe | MDD | PF | 换手 | 暴露效率 | 坏暴露比 | 越权 | 跳跃 |
| :-- | --: | --: | --: | --: | --: | --: | --: | --: | --: |
| A0 Legacy | -2.10% | -0.346 | -21.87% | 0.87 | 2.93 | -0.145 | 0.662 | — | — |
| A1 Legacy+PermCap | -0.96% | -0.304 | **-11.32%** | 0.89 | 1.59 | -0.115 | 0.814 | — | — |
| A2 FSM | +0.34% | **+0.502** | -0.31% | **2.71** | 0.34 | **+0.862** | 1.057 | 0 | 0 |
| A3 Perm+FSM（无 Hard Exit） | 0.00% | — | 0.00% | — | 0.00 | — | — | 0 | 0 |
| A4 +Hard Exit | 0.00% | — | 0.00% | — | 0.00 | — | — | 0 | 0 |

- A1 用 Permission **Cap**（非二值门）把 MDD -21.87%→-11.32%、换手 2.93→1.59；
- A2/A3/A4 决策链**零越权、零非法跳跃**（状态机收口有效）；
- A3/A4 当前市场权限全 WATCH/TEST → 正确空仓（暴露 0）；
- 口径 PIT-C、2021-08~2026-08，**不构成有效 alpha 证据**。

**5. 测试新增**：exit_event 种类 / permission cap 与 assert / 单调性 / FSM≠Sizing（所有权）/
DecisionSnapshot 确定性（同一输入两次构建完全一致）；全量 **57 模块通过**。

**M0 验证结果（实测）**：

- 全量工作流 `run_QCFP_MTF_workflow.py` 三步全部通过；
- 覆盖度：10 张源表、15 只有行情股票；发现 `00579`/`02602` 完全无数据、`03033`（ETF）缺机构持股；
- 质量：全量 135 项快照，A:76 / B:24 / C:35 / D:0；主要降级原因是早期历史负价格占位数据（如 01093 有 442 条）与资金流辅助列缺失；
- 单股票验证：`--stock 00700` 输出 10 类数据质量标签（daily_kline C 级：负价格 4 条）。

**下一步（P1 前置说明）**：季度结构引擎可直接读取 `qcfp_data_quality_audit` 与 `hk_quarterly_institutional_holdings_analysis`/`hk_quarterly_chip_analysis`；`available_date` 仍为推算模式（披露滞后 45 天），P6 回测前建议补充真实披露日历。
