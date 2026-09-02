# QCFP-MTF P6 用户使用手册（含实例）

> 适用版本：QCFP-MTF-2.1.1 / P6 回测与校准
> 环境：Windows + 项目虚拟环境 `.venv`（Python 3.13）
> 所有命令默认在项目根目录执行

## 一、环境准备

```powershell
cd C:\Users\Quansheng\Documents\projects\TA_Workflow
$env:PYTHONIOENCODING="utf-8"
$env:PYTHONUTF8="1"
```

## 二、实例 1：跑一次回测

```powershell
# 单股预演（不写库）
.venv\Scripts\python.exe Core\QCFP_MTF\scripts\backtest_runner.py --stock 00700 --dry-run

# 全量回测（写 qcfp_backtest_results，2021 起默认）
.venv\Scripts\python.exe Core\QCFP_MTF\scripts\backtest_runner.py --run-id bt_full_20260820

# 自定义区间
.venv\Scripts\python.exe Core\QCFP_MTF\scripts\backtest_runner.py --start 2023-01-01 --end 2025-12-31 --run-id bt_2023_2025
```

预期输出（全量，V2 Risk 上限 + 基准口径）：

```text
信号时间线 9827 行，Look-ahead 检查通过
累计 -4.37%  年化 -0.79%  Sharpe -0.0448  Sortino -0.0715  Calmar -0.0323
最大回撤 -24.32%  年化换手 1.11
risk_on: 年化 17.13%  Sharpe 1.7293
neutral: 年化 14.98%  Sharpe 2.2603
risk_off: 年化 -9.91%  Sharpe -1.1261
等权基准年化超额 -3.22%  IR -0.0018  恒指超额 -0.52%  IR 0.0094
已写入 qcfp_backtest_results 4321 行（run_id=bt_v2_risk_capped_20260820）
```

## 三、实例 2：查看回测结果

```powershell
# 报告文件
Get-ChildItem Report\QCFP_MTF\backtest | Sort-Object LastWriteTime -Descending | Select-Object -First 6 Name

# 数据库：某 run_id 的信号分布
sqlite3 SQLiteDB\HK_Stock.db "SELECT action_signal, COUNT(*) FROM qcfp_backtest_results WHERE run_id='bt_full_20260820' GROUP BY 1 ORDER BY 2 DESC;"

# 收益明细抽样
sqlite3 SQLiteDB\HK_Stock.db "SELECT stock_code, signal_date, action_signal, position, pnl FROM qcfp_backtest_results WHERE run_id='bt_full_20260820' AND pnl IS NOT NULL ORDER BY pnl DESC LIMIT 5;"
```

## 四、实例 3：参数校准

```powershell
# 网格校准（9 组合，约 20 秒）
.venv\Scripts\python.exe Core\QCFP_MTF\scripts\calibration.py --start 2021-01-01 --top 5

# 写入建议参数（不覆盖主配置）
.venv\Scripts\python.exe Core\QCFP_MTF\scripts\calibration.py --start 2021-01-01 --apply

# 查看校准结果
Get-Content (Get-ChildItem Report\QCFP_MTF\backtest\calibration_*.json | Sort-Object LastWriteTime -Descending | Select-Object -First 1).FullName
```

## 五、实例 4：解读回测指标

| 指标 | 含义 | 当前值（全量基线） |
| :-- | :-- | :-- |
| 累计收益 | 等权组合净值连乘 - 1 | -10.51% |
| 年化收益 | 周频年化 | -1.94% |
| Sharpe | (周均收益-无风险)/周标准差×√52 | -0.0916 |
| Sortino | 仅下行波动 | -0.144 |
| Calmar | 年化 / |最大回撤| | -0.0588 |
| 最大回撤 | 组合净值峰值到谷底 | -33.04% |
| 年化换手 | 平均周换手 × 52 | 0.79 |

分层结论：策略在 **risk_on/neutral 环境有效**（Sharpe 1.68/2.45），在 **risk_off 环境亏损**（-13.9%）——有效性集中于风险偏好正常/偏暖环境。

## 六、实例 5：运行测试

```powershell
# 全量 146 项
.venv\Scripts\python.exe Core\QCFP_MTF\tests\run_all_tests.py

# P6 专项
.venv\Scripts\python.exe Core\QCFP_MTF\tests\test_backtest\test_lookahead_filter.py
.venv\Scripts\python.exe Core\QCFP_MTF\tests\test_backtest\test_engine.py
```

## 七、实例 6：Python 直接调用（二次开发）

```powershell
$code = @'
import sys
sys.path.insert(0, "Core")
import pandas as pd
from QCFP_MTF.common.db import connect
from QCFP_MTF.config.settings import load_qcfp_settings
from QCFP_MTF.backtest.data_pipeline import build_signal_timeline
from QCFP_MTF.backtest.engine import run_backtest
from QCFP_MTF.backtest.performance import evaluate
from QCFP_MTF.backtest.lookahead_filter import assert_no_lookahead
from QCFP_MTF.data.loader import load_derived, load_idx_hist, load_kline

s = load_qcfp_settings()
structural = pd.read_sql_query("SELECT stock_code, period_end, available_date, structural_regime, c_state, data_quality FROM qcfp_quarterly_structural", connect())
monthly = pd.read_sql_query("SELECT stock_code, month_end, monthly_behavior_state, cbi_score, cost_position, data_quality FROM qcfp_monthly_behavior", connect())
weekly = pd.read_sql_query("SELECT stock_code, stock_name, week_end, tactical_signal, data_quality FROM qcfp_weekly_tactical", connect())
chip = load_derived("quarterly_chip_analysis")[["stock_code","quarter_end_date","chip_structure_score"]]
idx = load_idx_hist(); weekly_kl = load_kline("weekly")

signals = build_signal_timeline(structural, monthly, weekly, chip, idx, s, stocks=["00700"])
assert_no_lookahead(signals)
bt = run_backtest(signals, weekly_kl, s)
print(evaluate(bt["pnl"], bt["position"]))
'@
$code | .venv\Scripts\python.exe -
```

## 八、实例 7：日常维护

```powershell
# 表结构变更后重生成字典
.venv\Scripts\python.exe Code_utl\Generate_qcfp_Dictionaries.py

# 清理 WAL
sqlite3 SQLiteDB\HK_Stock.db "PRAGMA wal_checkpoint(TRUNCATE);"

# 回测日志
Get-Content Log\backtest_runner.log -Tail 30
```

## 九、参数汇总

| 参数 | 入口 | 说明 |
| :-- | :-- | :-- |
| `--stock 00700` | backtest_runner / calibration | 只回测指定股票 |
| `--start / --end` | backtest_runner / calibration | 回测区间（默认 2021 起） |
| `--run-id` | backtest_runner | 回测标识（写入结果表） |
| `--dry-run` | backtest_runner | 不写库 |
| `--top N` / `--apply` | calibration | 输出前 N 组合 / 写建议参数文件 |

## 十、常见问题

| 现象 | 说明 |
| :-- | :-- |
| 为什么总体收益为负 | 默认阈值下策略在 risk_off 环境亏损；校准与分层显示 risk_on/neutral 环境正收益，说明需要结合市场环境使用 |
| 回测为什么从 2021 起 | 资金流 2021 起可用，季度 F 因子 2021 前缺失 |
| 最大回撤 -99.7% 是否异常 | 池化 15 只股票周 pnl 的累计结果，2022-2023 系统性下跌所致；单股回撤更小 |
| 校准的芯片权重为何无影响 | chip 权重只经置信度→风险→Extreme 门控影响动作，极端情形少；真正敏感的是 REDUCE 仓位 |
| 如何启用校准参数 | `calibration.py --apply` 写 `Config/qcfp_calibration.json`，人工评审后手工合入主配置 |
| 回测进不进每日工作流 | 不进。回测/校准按需运行，与 `run_QCFP_MTF_workflow.py` 解耦 |

### V1 加固后的新工具

```powershell
# 因子/状态信息量分析（Rank IC + 状态前向收益分层）
.venv\Scripts\python.exe Core\QCFP_MTF\scripts\ic_analysis.py

# Walk-forward OOS 校准（训练窗选参 → 测试窗评估）
.venv\Scripts\python.exe Core\QCFP_MTF\scripts\calibration.py --start 2021-01-01
```

关键变化：生产融合引擎与回测现在**统一按 available_date 对齐**（季度结构/筹码评分均含披露滞后），CBI 改为横截面 as-of 标准化（无未来泄漏），回测绩效按等权组合净值计算（含 Sortino/Calmar/换手），成本模型区分买卖方向。

### V2 加固后的新工具

```powershell
# 横截面 Top-N 组合回测（选股层验证）
.venv\Scripts\python.exe Core\QCFP_MTF\scripts\cross_sectional_backtest.py --top-n 3,5,10

# C×F×P 三维收益矩阵 + 因子 IC
.venv\Scripts\python.exe Core\QCFP_MTF\scripts\ic_analysis.py

# 纯单元测试（无需真实数据库）
.venv\Scripts\python.exe Core\QCFP_MTF\tests\run_all_tests.py --unit-only
```

V2 关键变化：**Risk→仓位联动**（目标仓位 = min(MTF 基础仓位, Risk 上限)，Risk 成为真正门控）、**基准对照**（等权买入持有 + 恒指 + 年化超额/IR）、**横截面选股回测**（Top-N）、**C×F×P 三维收益矩阵**、**Walk-forward 参数稳定性报告**。

### V3 加固后的新工具

```powershell
# 增量信息实验（Model 0~6：P → C+P → C+F+P → +Monthly → +Weekly → 完整 MTF）
.venv\Scripts\python.exe Core\QCFP_MTF\scripts\incremental_alpha_test.py --top-n 5

# 回测 HTML 可视化报告（净值曲线/分年度/市场分层）
.venv\Scripts\python.exe Core\QCFP_MTF\scripts\html_report.py --run-id bt_v3_20260820
```

V3 关键变化：**横截面回测修正为 T 周选股→T+1 周收益**（消除时间错位）、**证据等级与数据质量二维分离**（季度 A-/月线 B/周线 C/MTF D）、**非重叠 t 统计**、**PIT 股票池**（`Config/qcfp_universe.csv`）、**真实披露日覆盖**（`Config/qcfp_disclosure_dates.csv`）、**组合层风险**（VaR95/波动/暴露/现金占比）、**参数平台分析**。

### V4 加固后的新工具

```powershell
# 研究质量门（产出绩效前最后一道检查）
.venv\Scripts\python.exe Core\QCFP_MTF\scripts\research_validation.py

# 正式回测强制 PIT 股票池（缺 qcfp_universe.csv 即报错）
.venv\Scripts\python.exe Core\QCFP_MTF\scripts\backtest_runner.py --run-id bt_v4_20260820 --require-universe
```

V4 关键变化：**股票代码进入全部报告/日志文件名**、**横截面完整 stock×week 网格 + 真实方向成本**、**DSS JSON 证据/质量彻底分离**、**HAC t + 块自助法 CI**、**Walk-forward 术语严谨化**（Rolling OOS vs 参数 Walk-forward）、**增量实验补 M0~M2 基准与单因子**、**研究质量门（Grade A/B/C/D）**。

### V5 加固后的新工具

```powershell
# 10 门槛验证协议（01~10，10/10 PASS 才 Research Validated）
.venv\Scripts\python.exe Core\QCFP_MTF\scripts\research_validation.py --run-id bt_20260821

# 正式模式强制 PIT（在 qcfp_settings.yaml 设 backtest.mode: production）
.venv\Scripts\python.exe Core\QCFP_MTF\scripts\backtest_runner.py
```

V5 关键变化：**文件/日志名只含日期**（如 `summary_bt_20260821.json`）、**production 模式强制 PIT**、**Factor Ablation（Model 0~10）**、**条件回归**（控制 P 后 C/F 的 β/t/增量 R²）、**最低佣金**、**动量基准对照**、**10 门槛验证协议**。

### V6 新增工具（All-in-One 报告 + HTML 自动匹配）

```powershell
# 个股一体化 MD 报告（文件名含股票代码）
.venv\Scripts\python.exe Core\QCFP_MTF\scripts\all_in_one_report.py --stock 01951
# → Report\QCFP_MTF\all_in_one\01951_all_in_one_2026-08-21.md

# HTML 回测报告：无需 --run-id，自动匹配该股票最新回测（文件名含股票代码）
.venv\Scripts\python.exe Core\QCFP_MTF\scripts\html_report.py --stock 01951
# → Report\QCFP_MTF\backtest\report_bt_20260822_01951.html
```

All-in-One 报告聚合：① 最新状态快照（季度/月线/周线/MTF 最新行）；② DSS 详细决策报告（10 节全文）；③ 回测汇总（总体/分年/市场分层/Rolling OOS/基准超额/组合风险）；④ 产物清单。

### V7 更新（2026-08-22）

- **All-in-One 支持 MD + HTML 双格式**：`all_in_one_report.py --stock 01951` 同时生成
  `Report\QCFP_MTF\all_in_one\01951_all_in_one_2026-08-21.{md,html}`（文件名均含股票代码）；
- **已接入 `test_QCFP-MTF.py`**：新增第 9 步 "P7 All-in-One 一体化报告"（`--single P7` 可单独运行，`--skip-reports` 时跳过）。

### V8 新工具：敏感性回测

```powershell
# 放宽 C 阈值 × 恢复路径敏感性（默认聚焦 01951 的 2024-02~10 波段）
.venv\Scripts\python.exe Core\QCFP_MTF\scripts\sensitivity_backtest.py
```

输出：`Report\QCFP_MTF\backtest\sensitivity_YYYYMMDD.{json,csv}`，比较各变体组合绩效与聚焦股票波段收益。结论：激进恢复路径可把 01951 波段收益从 0 提升到 +33.4%，但组合年化恶化至 -2.52%、回撤扩至 -38%，不建议直接启用；瓶颈是披露滞后而非 C 阈值。

### V9 更新（PIT Unification，2026-08-22）

- **DSS/历史报告全面 PIT 化**：季度数据查询统一为 `available_date<=决策日`（`_row`/`_history`/快照）；
- **验证门升级为结果有效性**：OOS Sharpe 中位数、同参率≥80%、\|HAC t\|≥2、Full MTF 超额、risk_on/neutral 年化为正均进入 PASS/WARN/FAIL；
- **All-in-One 增加"研究结论与限制"四层结构**，且产物按同一 run_id 精确绑定。

### V10 更新（2026-08-24）——方案 B 温和试多 + 催化剂质量评分（CQS）

**新增工具：触发器宽度敏感性**

```powershell
# 默认 5 个变体：OFF / Breakout / B+Pullback / B+P+C / ANY
.venv\Scripts\python.exe Core\QCFP_MTF\scripts\trigger_sensitivity.py

# 只比 B+P+C 与 ANY
.venv\Scripts\python.exe Core\QCFP_MTF\scripts\trigger_sensitivity.py --variants "B+P+C;ANY"

# 指定重点股票与波段（默认 01951，2024-02-02~2024-10-31）
.venv\Scripts\python.exe Core\QCFP_MTF\scripts\trigger_sensitivity.py --focus 01951
```

输出：`Report\QCFP_MTF\backtest\trigger_sensitivity_YYYYMMDD.{json,csv}`，每行一个变体，含组合绩效（年化/Sharpe/回撤/换手/暴露）、试多统计（行数/股票数/时间止损归零数/平均目标仓位）与重点股票波段收益/持仓周数。

**方案 B 行为与配置**：

| 配置键（`decision.tactical_override`） | 默认 | 说明 |
| :-- | :-- | :-- |
| `enabled` | `true` | `false` = 完全关闭方案 B（等价 OFF 基线） |
| `max_52w_position` | `0.15` | 仅 52 周位置 < 15% 允许试多（防追高） |
| `min_trigger` | `[Breakout, Pullback, Consolidation]` | 空头结构下允许试多的周线触发器；`[]` = 任意触发；`[Breakout]` = 最保守 |

| 配置键（`decision.catalyst_quality`） | 默认 | 说明 |
| :-- | :-- | :-- |
| `position_high / mid / low` | 0.35 / 0.20 / 0.05 | CQS ≥+2（高质量反转）/ 0~+1（中性偏强）/ <0（纯脉冲）观察仓 |
| `time_stop_high / mid / low` | null / 4 / 2 | 高质量不限时间止损；中性 4 周后评估；纯脉冲 2 周内必须离场 |

**时间止损语义**：试多持仓周数超过 CQS 对应上限后目标仓位归零；计数器在"周信号中断"或"新季度结构披露"时重置——即季报更新后允许依据新 CQS 重新试多（避免一次止损后整个季度被锁死）。

**敏感性实测（2021-01-01 ~ 2026-08-21，01951 波段买入持有 +61.61%）**：

| 变体 | 组合年化 | Sharpe | 最大回撤 | 01951 波段收益 | 波段持仓周 |
| :-- | --: | --: | --: | --: | --: |
| OFF（禁用方案 B） | -0.58% | -0.022 | -23.97% | 0.00% | 0/39 |
| Breakout | -0.63% | -0.027 | -23.98% | 0.00% | 0/39 |
| Breakout+Pullback | -0.68% | -0.034 | -24.00% | -3.28% | 3/39 |
| **B+P+Consolidation（默认）** | -0.78% | -0.042 | -24.83% | **+2.47%** | 9/39 |
| ANY | -0.81% | -0.047 | -24.94% | +1.11% | 8/39 |

**使用建议**：默认 `B+P+C` 能在 01951 类波段拿到正贡献（0% → +2.47%），代价是组合 Sharpe 约 -0.02、回撤约 +0.9pp、换手 +0.25（方案 B 的"期权费"）。追求绝对防御的账户可改 `min_trigger: [Breakout]` 或 `enabled: false`。

**修复记录**：`backtest_runner/calibration/cross_sectional_backtest/incremental_alpha_test/research_validation/sensitivity_backtest` 的 structural/monthly 查询补齐 `q_trend_score/q_position_52w/cbi_state`（V10 前时间线构建缺列会报错）；`qcfp_mtf_decision` 新增 `catalyst_score/catalyst_type/align_method`（`init_db.py` 自动迁移）；`mtf_fusion_engine` 写库时持久化 `align_method`，DSS 报告对试多行显示 CQS 观察仓。

### V11 更新（2026-08-24）——移动止损 + CQS 权重微调

**1. 移动止损（替换"中性偏强固定 4 周"）**

```yaml
decision:
  trailing_stop:
    enabled: true        # false = 关闭移动止损（回到 V10 固定周数止损）
    buffer_pct: 0.02     # 收盘跌破建仓周 K 线最低价×(1-2%) 即离场
  catalyst_quality:
    time_stop_mid: null  # 中性偏强（CQS 0~1）改用移动止损
    time_stop_low: 2     # 纯脉冲（CQS<0）仍强制 2 周离场
```

规则：试多持仓只要收盘不跌破建仓周最低价×(1-buffer) 即可无限期持有；跌破即离场，同段试多内不再自动重进；周信号中断或新季度结构披露后允许重新试多。

**2. CQS 趋势质量权重微调**

`decision/catalyst_quality.py` 的趋势质量分支由 ±2 降为 ±1（避免对困境反转股过度压制）；实际数据显示 01951 2024 波段 CQS 为 0~1，此调整不改变其档位，主要压缩高分分布。

**3. 重跑回测 + 报告绑定**

```powershell
# 用新代码重跑 01951（生成新 run_id，All-in-One 自动绑定最新）
.venv\Scripts\python.exe Core\QCFP_MTF\scripts\backtest_runner.py --stock 01951 --dry-run
.venv\Scripts\python.exe Core\QCFP_MTF\scripts\all_in_one_report.py --stock 01951
```

实测：01951 2024 年化 **0.00% → +4.64%**（Sharpe 0.85）；全市场敏感性见 `Report\QCFP_MTF\backtest\trigger_sensitivity_20260824.json`。

**V11 敏感性实测（01951 波段买入持有 +61.61%）**：

| 变体 | 组合年化 | Sharpe | 最大回撤 | 01951 波段 | 波段持仓周 |
| :-- | --: | --: | --: | --: | --: |
| OFF | -0.58% | -0.022 | -23.97% | 0.00% | 0/39 |
| Breakout | -0.65% | -0.030 | -23.98% | 0.00% | 0/39 |
| B+Pullback | -0.71% | -0.036 | -24.00% | -3.28% | 3/39 |
| **B+P+C（默认）** | -0.24% | **+0.020** | -24.77% | **+7.31%** | 19/39 |
| ANY | +0.16% | +0.063 | -23.17% | +7.31% | 19/39 |

**4. 行动标签优化**：DSS/All-in-One 中试多行显示"试多（TEST_BUY）"，数据库 `action_signal` 仍为 `REDUCE`（驱动回测），报告层仅改显示。

### V12 更新（2026-08-24）——移动止损缓冲 5% + 换手监控

**1. 参数调整**

```yaml
decision:
  trailing_stop:
    enabled: true
    buffer_pct: 0.05   # 2% → 5%：对底部暴力洗盘更稳健
```

**2. 实证**（`trigger_sensitivity_20260824.json`，buffer×触发器网格）：

- 01951 波段：2% 缓冲 +7.31%（19/39 周）→ 5% 缓冲 +6.17%（20/39 周）→ 8% 缓冲 +5.97%（23/39 周）——放宽缓冲并未提升收益，**移动止损缓冲不是波段瓶颈**；
- 组合：B+P+C@5% 年化 -0.25%、Sharpe +0.019、回撤 -24.95%、换手 1.37；
- 换手监控：全市场最高年化换手 **1.39 < 2.0** → 不收紧触发器，默认维持 `[Breakout, Pullback, Consolidation]`；
- 01951 单股 2024：5% 缓冲下年化 +3.53%（Sharpe 0.64，MDD -2.53%）。

**3. 调参工具**：`trigger_sensitivity.py --buffers 0.02,0.05,0.08 --variants "B+P+C;ANY"` 可随时复测。

### V13 更新（2026-08-24）——buffer 数据驱动寻优

**1. 20 组网格结论**（`trigger_sensitivity.py --buffers 0.02,0.05,0.08,0.12`）：

- **buffer=0.02 全指标最优**（Sharpe、01951 波段、回撤）；0.05/0.08/0.12 单调变差——放宽缓冲让系统在反弹后期回调中多扛几周、回吐利润；
- 换手 1.39→1.35 不升反降，说明瓶颈不是交易成本；全市场换手始终 < 2.0，无需收紧触发器；
- 01951 波段：2% +7.31%（19/39 周）＞ 5% +6.17% ＞ 8%/12% +5.97%。

**2. 默认配置**：`buffer_pct: 0.02`（已回写 `qcfp_settings.yaml`，含寻优注释）。

**3. 产物**：`trigger_sensitivity_YYYYMMDD.{json,csv,html}`（HTML 自包含对比表，按 Sharpe 降序）；01951 回测 `bt_20260824_3`（2024 +4.64%、Sharpe 0.85、MDD -2.18%），All-in-One 已重绑。

```powershell
# 一行命令复测任意 buffer 网格
.venv\Scripts\python.exe Core\QCFP_MTF\scripts\trigger_sensitivity.py --buffers 0.02,0.05,0.08,0.12
```

### V14 更新（2026-08-24）——日线战术层（L4）与增量价值验证

**1. 新工具**

```powershell
# 日线战术状态引擎（全市场，写 qcfp_daily_tactical）
.venv\Scripts\python.exe Core\QCFP_MTF\scripts\daily_tactical_engine.py

# 2024 波段事件回放：哪一层最先识别波段
.venv\Scripts\python.exe Core\QCFP_MTF\scripts\wave_replay.py --year 2024 --min-gain 0.5

# 日线增量价值测试（Model A=QMW vs Model B=QMWD + MFE/MAE + 验收）
.venv\Scripts\python.exe Core\QCFP_MTF\scripts\daily_alpha_test.py
```

产物：`Report/QCFP_MTF/daily_tactical/`、`wave_replay/wave_replay_YYYYMMDD.{json,csv}`、`backtest/daily_alpha_YYYYMMDD.{json,csv}`。

**2. 日线状态（4 种 + 中性）**：`DAILY_ACCUMULATION`（资金改善+量结构改善+未突破）、`DAILY_BREAKOUT`（突破+放量+资金确认）、`DAILY_PULLBACK`（中期向上+短期回调）、`DAILY_DISTRIBUTION`（高位+滞涨+资金流出）。

**3. 增量价值实测结论**：Model B（日线时机门：吸筹/突破→早入场+加仓、派发→减仓、回调→持有）**未通过验收**——01951 波段 7.31%→7.15%、Sharpe 0.020→-0.004，验收 3/5（必过项"波段捕捉提升"FAIL）。MFE 均值 21.96% 但实现收益为负（捕捉率 -73%），说明瓶颈在退出机制而非入场识别。因此 `daily.timing.enabled` **默认 false**（诊断层），规则改进并通过 `daily_alpha_test.py` 验收后再正式接入。

**4. 报告展示**：DSS/All-in-One 决策摘要新增"战略 × 战术"（LONG/NEUTRAL/DEFENSIVE × 动作）与"## 4.5 日线战术层"（日线状态+时机提示）；All-in-One 快照新增日线战术行。

### V15 更新（2026-08-24）——Correctness Hardening + Run Status

**1. 决策四概念**：DSS/All-in-One 摘要分列 `MTF State` / `Action Signal` / `Tactical Override` / `Trade Intent`（试多行=TEST_BUY）/ `Target`，数据库 `action_signal` 不变（REDUCE 驱动回测）。

**2. 止损单一来源**：`decision.stop_loss_policy`（type=entry_week_low, buffer_pct=0.02）为唯一止损来源；回测与报告"止损触发"同源显示"移动止损：收盘跌破建仓周最低价×(1-2%)"。改止损只改这一处。

**3. RUN STATUS**：回测 summary / All-in-One 顶部显示 PASS / PASS_WITH_WARNING / FAILED（披露模式、PIT universe、一致性检查）。

**4. 成本口径**：回测新增年化毛换手 / 年化交易成本 / 成本占换手比 / 平均仓位；HTML 报告新增回撤曲线与滚动 12M Sharpe。

**5. 新实验工具**：

```powershell
# Market Regime Gate（risk_off 降杠杆）
.venv\Scripts\python.exe Core\QCFP_MTF\scripts\regime_gate_test.py --factor 0.25
```

实测：MDD -24.77%→-21.51%，但换手 1.39→2.74、Sharpe 转负 → 暂不部署。

### V16 更新（2026-08-24）——PIT/口径修正 + 层级消融

**1. 新工具：层级消融实验（增量贡献矩阵）**

```powershell
.venv\Scripts\python.exe Core\QCFP_MTF\scripts\layer_ablation_test.py
```

输出 `backtest/layer_ablation_YYYYMMDD.{json,csv}`：Q / QM / QMW / Full 四模型
的年化/Sharpe/MDD/PF/换手/IC13/01951 波段 + Full 试多专项统计。实测结论：
月线门当前为负贡献（QM Sharpe -0.239）；Full（含战术覆盖）唯一 Sharpe 转正并捕捉波段
（+7.31%），试多周均 pnl +0.105%。

**2. 回测口径修正**

- `cross_sectional.py` turnover=cost 语义 bug 已修复（turnover 现为毛换手，成本独立）；
- Chip 与 Structural 披露日统一（优先真实/覆盖披露日，回退 +45 天）；
- 止损函数更名 `_apply_entry_week_low_stop`，报告注明"周线收盘确认，不做盘中触发"；
- 回测 summary 增加 `pit_grade`（PIT-A/PIT-C）、`config_hash`、`cost_model_version`（研究注册表雏形）。

**3. 金融不变量测试**：`tests/test_backtest/test_invariants.py`（PIT/Position/Cost/Benchmark 四类），
已注册全量回归（49 模块）。

**4. 决策卡**：DSS 顶部新增 `## 0. 决策卡`；`Strategic Regime` 由季度结构推导
（LONG/BEARISH/NEUTRAL），01951 显示 "BEARISH × 试多（TEST_BUY）"。

### V17 更新（2026-08-24）——回测完整性修复 + 模型诊断页

**1. Entry-Week-Low Stop 周收益修复（回测完整性）**：

- 止损周按"止损价成交"（承担周初到止损价损失，不再整周清零）；引擎输出 `position_start` 与 `effective_return`；
- 实测影响：Full Sharpe +0.020→+0.014、01951 波段 +7.31%→+4.34%、2024 年化 +4.64%→+1.74%——旧实现高估，现口径更严格；
- 不变量测试更新：`pnl = position_start × effective_return − cost` 精确守恒。

**2. 模型诊断页**：All-in-One 新增 `## 3.5 模型诊断（Layer Ablation）`（自动读取最新
`layer_ablation_*.json`），含上下行捕获；`layer_ablation_test.py` 输出矩阵含
upside/downside capture。

**3. 结论**：各模型上下行捕获对称（≈0.25~0.35）——低暴露策略，无"抓涨避跌"不对称；
Full（+Override）仍为唯一 Sharpe>0/PF>1/捕捉波段的层；试多周均 pnl +0.098%（修复后口径）。

### V18 更新（2026-08-24）——Dynamic Risk Exit（下行风险层）

**1. 新机制**（`decision/downside_risk.py`，默认开启）：

```yaml
decision:
  downside_risk:
    enabled: true
    breakdown_risk_floor: Extreme   # 破位+close<MA20 → 风险下限 Extreme
    release_weeks: 2                # 站回 MA20 且连续 2 周无破位才解除
    exit_at_score: 7                # DES≥7 → 清仓
    weights: {...}                  # 各项下行证据权重（可校准）
```

- **DES 档位**：0-2 NORMAL / 3-4 WATCH / 5-6 REDUCE / 7+ DE-RISK；
- **滞后解除**：进入风险容易、解除困难；
- **仓位单调性**：下跌未恢复前目标仓位不得上升；
- 日线新增 `DAILY_DECLINE` 状态（`qcfp_daily_tactical.d_decline`），日线状态/资金流进入 DES。

**2. 查看 DES**：DSS 决策卡新增 `DOWNTREND EVIDENCE`；数据库 `qcfp_mtf_decision` 新增
`des_score/des_band`。

**3. 00371 验证**：6/19 首次破位即 EXIT/Extreme（DES=8，原 HOLD/0.5）；8/21 DES=12 → EXIT/Extreme
（原 HOLD/Low/0.75）；风险下限与单调性防止"跌得越深仓位越高"。

**4. 回归测试**：`tests/test_decision/test_00371_downtrend_exit.py`（3 项金标准断言），
全量 50 模块通过。
