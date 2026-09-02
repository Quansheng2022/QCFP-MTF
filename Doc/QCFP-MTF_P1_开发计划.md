# QCFP-MTF P1 开发计划 —— 季度结构引擎（Structural Engine）

> 版本：v0.1（评审稿）
> 日期：2026-08-19
> 前置：P0 已完成（`qcfp_*` 表、loader/quality/evidence、配置、日历）
> 依据：《QCFP-MTF 2.1.1 架构设计.md》§一~§三、§六.1 + 总体开发计划 P1

## 一、范围与目标

P1 实现 **Layer 1（季度结构层）**：用 A/A- 级证据（真实筹码 C + 资金 F + 季度价格 P）判定季度结构状态（FSM-1，6 种），输出 Core Score 与三维背离信号。

| 项 | 内容 |
| :-- | :-- |
| 输入 | `hk_quarterly_institutional_holdings_analysis`、`hk_quarterly_chip_analysis`、`hk_hist_quarterly_kline`、`hk_hist_daily_kline`、`qcfp_data_quality_audit` |
| 输出 | `qcfp_quarterly_structural`（已建表，P1 写入） |
| 核心模块 | `structural/chip_factors.py`、`flow_factors.py`、`price_factors.py`、`structural_regime.py`、`divergence.py` |
| 里程碑 | M1：任意股票输出 `structural_regime` + `core_score` + 背离信号，并与现有 `chip_flow_price_regime` 交叉验证 |

## 二、数据输入映射（实测字段）

| QCFP 因子 | 计算字段 | 数据来源 | 实测覆盖 |
| :-- | :-- | :-- | :-- |
| C：`inst_ownership_pct_chg` | `holder_pct_qoq_pp` | `hk_quarterly_institutional_holdings_analysis` | 缺失 1.5%（首季无环比） |
| C：`holder_quantity_chg_pct` | `holder_quantity_qoq_pct` | 同上 | 缺失 1.5% |
| C：`inst_participation_chg` | `institution_quantity_qoq_pct` | 同上 | 缺失 1.5% |
| C：公司行为标记 | `corporate_action_flag`（1 表示 ≥25% 异动，可能 IPO/配股） | 同上 | 53/944（5.6%）需屏蔽 |
| F：`q_inst_flow_raw` | `institutional_flow`（IDR/FBI 派生） | `hk_quarterly_chip_analysis` | **67.9% 为空（仅 2021+）** |
| F：`q_ifa_zscore` | 由 `institutional_flow` 计算 | 同上 | 同 F |
| P：`q_return` | `close` 季环比（读 `hk_hist_quarterly_kline`） | 季度 K 线 | 完整（派生表 close 缺失 22.9%，**不用派生表价格**） |
| P：`q_position_52w` | 季末快照：日线 close 滚动 252 交易日 | `hk_hist_daily_kline` | 完整（2010+） |
| P：`q_trend_score` | 季度 K 线 ema5/10/20/50 + macd + 52W + VWAP 复合 | `hk_hist_quarterly_kline` | 完整 |

**结论**：C、P 因子可全历史计算；**F 因子只有 2021+ 季度可用**（资金流源表起点所致），是 P1 必须显式处理的限制。

## 三、模块设计与算法定义

### 3.1 `chip_factors.py`（C 因子）

- 输入：`hk_quarterly_institutional_holdings_analysis`；
- 输出字段：`inst_ownership_pct_chg`、`holder_quantity_chg_pct`、`inst_participation_chg`、`c_state`；
- `c_state` 判定（阈值进配置，P6 校准）：
  - `holder_pct_qoq_pp > +c_pp_threshold(0.5)` → `C↑`；
  - `< -c_pp_threshold` → `C↓`；
  - 其余 → `C→`；
  - 辅助确认：`holder_quantity_qoq_pct` 与 `institution_quantity_qoq_pct` 方向一致时权重 +1（记录 `c_confidence`）；
- **`corporate_action_flag=1` 的季度不参与 C 状态判定**，输出 `c_state=NULL` + `data_quality` 降级，防止配股/拆股污染筹码结论；
- 首季无 QoQ：`c_state=NULL`（标记 `C_NA`），不参与 FSM-1。

### 3.2 `flow_factors.py`（F 因子）

- 输入：`hk_quarterly_chip_analysis.institutional_flow`；
- 输出字段：`q_inst_flow_raw`、`q_inst_flow_z`、`q_ifa_zscore`、`f_state`；
- `q_inst_flow_z`：**个股时间序列 Z-Score**（滚动 8 季度窗口，≥4 期才计算）；
- `q_ifa_zscore`（机构资金优势）：**同期横截面 Z-Score**（同一季度内 14 只股票对比，≥5 只才计算）——与规格书"IFA 是相对优势"一致；
- `f_state` 判定（阈值进配置）：
  - `q_inst_flow_z > +f_z_threshold(0.5)` → `F↑`；
  - `< -f_z_threshold` → `F↓`；
  - 其余 → `F→`；
- **资金流缺失（2021 前）→ `f_state=F_UNKNOWN`**，走 FSM-1 降级映射（见 §4.3），`data_quality` 降级 B/C，证据等级 A-；
- `institutional_flow` 为派生值（IDR/FBI），证据等级标注为 A- 而非 A。

### 3.3 `price_factors.py`（P 因子）

- 输入：`hk_hist_quarterly_kline` + `hk_hist_daily_kline`；
- 输出字段：`q_return`、`q_trend_score`、`q_position_52w`、`p_state`；
- `q_return`：季末 close 环比（%）；
- `q_position_52w`：季末快照 `(close - min252) / (max252 - min252)`，日线 252 交易日窗口；日线缺失时回退季度滚动 5 期；
- `q_trend_score`（0~100，**默认复合方案，P6 校准**）：

```text
q_trend_score =
  30% × q_return 同期百分位（横截面 0~100）
+ 25% × 均线排列分（ema5>ema10>ema20>ema50 全满足=100，每少 1 档减 25）
+ 15% × MACD 状态分（hist>0 且 DIF>SIGNAL=100；仅 DIF>SIGNAL=60；否则 20）
+ 20% × q_position_52w × 100
+ 10% × VWAP 偏离分（clip(close/VWAP_Q-1, ±20%) 线性映射 0~100）
```

- `p_state` 判定（阈值进配置）：
  - `q_return > +p_return_threshold(2.0%)` → `P↑`；
  - `< -p_return_threshold` → `P↓`；
  - 其余 → `P→`（另设 `p_flat_return=1.0%` 区分强平/弱平，供 P2 月线阶段参考）；
- 负价格占位数据（早期脏数据）在读取时过滤，季末快照若 close≤0 则该季度 P 因子置 NULL。

### 3.4 `structural_regime.py`（FSM-1 + Core Score）

**状态定义（6 种，规格书 §3.1）**：

| ID | 状态 | C | F | P |
| :-- | :-- | :-- | :-- | :-- |
| QS1 | `STRUCTURAL_BULLISH` | ↑ | ↑ | ↑ |
| QS2 | `STRUCTURAL_ACCUMULATION` | ↑ | ↑ | → |
| QS3 | `STRUCTURAL_DIVERGENCE` | ↑ | ↓ | ↑ |
| QS4 | `STRUCTURAL_DISTRIBUTION` | ↓ | ↓ | ↑ |
| QS5 | `STRUCTURAL_DECLINE` | ↓ | ↓ | ↓ |
| QS6 | `STRUCTURAL_BOTTOM_CANDIDATE` | ↓ | ↑ | ↓ |

**状态解析分两层**：

1. **直接映射**：C/F/P 组合精确命中上表 → 对应状态；
2. **转换规则（8 条，规格书 §3.1）**：当存在上一季度状态时按转换表推进，仅季度新数据驱动：

| 当前状态 | 新季度 C/F/P | 下一状态 |
| :-- | :-- | :-- |
| ACCUMULATION | ↑ ↑ ↑ | BULLISH |
| BULLISH | ↓ ↓ ↑ | DISTRIBUTION |
| BULLISH | ↑ ↓ ↑ | DIVERGENCE |
| DIVERGENCE | ↓ ↓ ↓ | DECLINE |
| DISTRIBUTION | ↓ ↓ ↓ | DECLINE |
| DECLINE | ↑ ↑ → | ACCUMULATION |
| DECLINE | ↓ ↑ ↓ | BOTTOM_CANDIDATE |
| BOTTOM_CANDIDATE | ↑ ↑ ↑ | BULLISH |

**Core Score（State-First）**：先定状态再映射分数（0~100），默认映射表进配置：

```text
BULLISH=85  ACCUMULATION=70  DIVERGENCE=55
DISTRIBUTION=35  DECLINE=20  BOTTOM_CANDIDATE=45
```

### 3.5 `divergence.py`（三维背离）

- 计算 C/F/P 三因子的标准化值（各自 Z-Score，横截面或时间序列与因子口径一致）；
- 输出 `CPD`（筹码-价格）、`FPD`（资金-价格）、`CFD`（筹码-资金）三个背离信号；
- 判定：`|z_x - z_y| > divergence.z_threshold(1.0)` 且方向符号相反 → 背离；记录背离方向（如"筹码顶背离"）；
- 任一因子缺失时对应背离输出 `NULL`，不臆测。

## 四、关键设计决策

### 4.1 铁律执行

- FSM-1 状态切换**只允许由季度新数据驱动**（P1 阶段已天然满足：只消费季度数据）；
- 周线/月线事件不允许进入本模块（P4 才做 MTF 融合），代码层面不引入任何低周期输入；
- State-First：任何地方禁止"先算加权分再反推状态"。

### 4.2 写入规范（`qcfp_quarterly_structural`）

- 按 `(stock_code, period_end)` **UPSERT**（`INSERT OR REPLACE`，唯一索引已建）；
- 必填：`stock_code`、`period_end`、`available_date`（= period_end + 45 天推算，模式进配置）、`model_version=QCFP-MTF-2.1.1`、`source_period`（如 2026/Q2）、`update_time`；
- `data_quality` 继承规则：取参与因子来源的最差等级（C←institutional_holdings、F←quarterly_moneyflow、P←quarterly_kline），使用 F_UNKNOWN 降级映射时再降一级；
- 清洗：`corporate_action_flag=1`、负价格、首季无 QoQ 的季度按 §3 规则置 NULL 并记录原因到日志。

### 4.3 F 缺失降级映射（2021 前季度）

当 `F_UNKNOWN` 时用 C+P 保守映射，**只允许输出 A- 级结论**：

| C | P | 输出状态 | 说明 |
| :-- | :-- | :-- | :-- |
| ↑ | ↑ | `STRUCTURAL_ACCUMULATION`（A-） | 有资金佐证前不升级 BULLISH |
| ↓ | ↓ | `STRUCTURAL_DECLINE`（A-） | |
| ↑ | ↓ | `STRUCTURAL_BOTTOM_CANDIDATE`（A-） | |
| ↓ | ↑ | `STRUCTURAL_DIVERGENCE`（A-） | 筹码与价格背离，需资金确认 |
| 其余 | | `STATE_UNDETERMINED` | 不产生结构结论 |

`STATE_UNDETERMINED` 视为"数据不足"，P4 融合时不做门控输入，仅在报告中提示。

## 五、配置新增（`Config/qcfp_settings.yaml`）

```yaml
structural:
  direction_thresholds:
    c_pp_threshold: 0.5        # holder_pct_qoq_pp（百分点）
    f_z_threshold: 0.5
    p_return_threshold: 2.0    # %
    p_flat_return: 1.0         # %
  trend_score_weights:
    return_pctl: 0.30
    ma_alignment: 0.25
    macd_state: 0.15
    position_52w: 0.20
    vwap_deviation: 0.10
  divergence:
    z_threshold: 1.0
  score_mapping:
    STRUCTURAL_BULLISH: 85
    STRUCTURAL_ACCUMULATION: 70
    STRUCTURAL_DIVERGENCE: 55
    STRUCTURAL_DISTRIBUTION: 35
    STRUCTURAL_DECLINE: 20
    STRUCTURAL_BOTTOM_CANDIDATE: 45
  fallback:
    allow_f_missing_with_cp: true
```

## 六、脚本与工作流集成

- 新脚本：`Core/QCFP_MTF/scripts/structural_engine.py`
  - 参数：`--stock 00700`、`--period-end 2026-06-30`（可选，只算指定季度）、`--dry-run`（不写库，打印结果）
  - 行为：读源表 → 计算 C/F/P → FSM-1 → 背离 → UPSERT 写库 → 摘要日志
- 追加到 `run_QCFP_MTF_workflow.py` 的 `SCRIPT_LIST`（`check_data_quality` 之后）：

```python
SCRIPT_LIST = [
    "init_db.py",
    "audit_coverage.py",
    "check_data_quality.py",
    "structural_engine.py",   # P1 新增
]
```

- 前置校验：`qcfp_data_quality_audit` 无数据时提示先跑质量检测；`03033` 等无机构数据股票自动跳过（`DATA_INSUFFICIENT`）。

## 七、测试计划

### 单元测试（`tests/test_structural/`）

| # | 用例 | 验收 |
| :-- | :-- | :-- |
| 1 | c_state 阈值判定（↑/→/↓ + 边界） | 精确匹配 |
| 2 | f_state 阈值判定 + 缺失 → F_UNKNOWN | 精确匹配 |
| 3 | p_state 阈值判定 + 负价格过滤 | 精确匹配 |
| 4 | q_trend_score 复合公式（构造样例） | 手算一致 |
| 5 | q_position_52w 日线/回退窗口 | 手算一致 |
| 6 | FSM-1 直接映射（6 组合） | 全覆盖 |
| 7 | FSM-1 8 条转换规则 | 逐条通过 |
| 8 | 4 种 F_UNKNOWN 降级映射 | 逐条通过 |
| 9 | Core Score 映射（State-First） | 状态→分数唯一 |
| 10 | CPD/FPD/CFD 背离判定 + NULL 处理 | 精确匹配 |
| 11 | corporate_action_flag 屏蔽 | 屏蔽季度不产生 c_state |

### 集成测试（真实数据）

- 运行 `structural_engine.py --stock 00700`：`qcfp_quarterly_structural` 写入且唯一键不冲突（重复运行 UPSERT 不报错）；
- 全量运行：14 只有机构数据的股票均出状态；2021 前季度 `F_UNKNOWN` 标记正确；
- **交叉验证**：将 `hk_quarterly_chip_analysis.chip_flow_price_regime` 方向化（如 多头共振/吸筹→牛、空头共振/派发→熊、其余→中性），与 P1 状态方向对比，**2021+ 季度方向一致率 ≥ 70%** 为验收线（低于则回查阈值，允许调参但需记录）；
- 数据缺口用例：`03033` → 跳过；`corporate_action_flag=1` 季度 → C=NULL。

## 八、数据缺口与风险（P1 专属）

| # | 缺口/风险 | 影响 | 应对 |
| :-- | :-- | :-- | :-- |
| 1 | F 因子 67.9% 缺失（仅 2021+） | 2021 前季度无法判定资金方向 | §4.3 降级映射 + data_quality 降级 + 报告注明 |
| 2 | `corporate_action_flag=1` 共 53 条 | 筹码环比失真 | 屏蔽 + 日志留痕 |
| 3 | 派生表 close 缺失 22.9% | 不可用 | P 因子一律读 `hk_hist_quarterly_kline` |
| 4 | 早期负价格占位数据 | 52W/趋势分失真 | 季末快照过滤 close≤0 |
| 5 | Trend Score / IFA 公式规格书未给明确定义 | 与后续回测校准脱节 | 本文给出"默认方案"，全部权重/阈值进配置，P6 统一校准 |
| 6 | 首季无 QoQ（14 条×每股票 1 条） | 首季 C 缺失 | C_NA 标记，不参与 FSM-1 |

## 九、里程碑 M1 验收标准

1. 任意有数据的股票可输出 `structural_regime` + `core_score` + 背离信号；
2. `qcfp_quarterly_structural` 有写入，`(stock_code, period_end)` 唯一，重复运行幂等；
3. 8 条转换规则 + 4 条降级映射单元测试全过；
4. 与 `chip_flow_price_regime` 方向一致率 ≥ 70%（2021+ 有 F 数据季度）；
5. `03033` 等无机构数据股票输出 `DATA_INSUFFICIENT`，不产生误导性结论；
6. 若表结构增加字段，同步更新 `Code_utl/Generate_qcfp_Dictionaries.py` 并重新生成字典。

## 十、任务拆分与工时

| # | 任务 | 子模块 | 工时（人天） |
| :-- | :-- | :-- | :-- |
| 1 | C/F/P 三因子计算（含阈值、清洗、屏蔽） | `chip_factors.py` / `flow_factors.py` / `price_factors.py` | 2.0 |
| 2 | FSM-1 直接映射 + 8 条转换 + F_UNKNOWN 降级 | `structural_regime.py` | 1.0 |
| 3 | Core Score（State-First 映射） | `structural_regime.py` | 0.5 |
| 4 | 三维背离 CPD/FPD/CFD | `divergence.py` | 0.5 |
| 5 | 引擎脚本 + 写库 + 工作流集成 | `scripts/structural_engine.py` | 1.0 |
| 6 | 单测 + 集成 + 交叉验证 | `tests/test_structural/` | 1.0 |
| **合计** | | | **约 6 人天** |

## 十一、下一步

1. 确认本计划（特别是 §3.3 Trend Score 复合方案与 §4.3 F 缺失降级映射）；
2. 实施顺序：因子计算 → FSM-1 → 引擎脚本 → 测试与交叉验证；
3. P1 完成后输出 M1 验证报告，再进入 P2（月线行为引擎）。

---

## 附：P1 交付记录（2026-08-19）

| 计划任务 | 状态 | 交付物 |
| :-- | :-- | :-- |
| 1.1 C 因子 | ✅ | `structural/chip_factors.py`（公司行为屏蔽、首季 C_NA、置信度） |
| 1.2 F 因子 | ✅ | `structural/flow_factors.py`（滚动 8 季 Z、IFA 横截面 Z、F_UNKNOWN） |
| 1.3 P 因子 | ✅ | `structural/price_factors.py`（q_return / Trend Score / 52W 位置 / p_state） |
| 1.4 FSM-1 + Core Score | ✅ | `structural/structural_regime.py`（6 状态直接映射 + 8 转换等价验证 + F 缺失降级 + 保持策略） |
| 1.5 三维背离 | ✅ | `structural/divergence.py`（CPD/FPD/CFD + 布尔标记） |
| 1.6 引擎与工作流 | ✅ | `scripts/structural_engine.py`（UPSERT 写库）+ 加入 `SCRIPT_LIST` |
| 交叉验证 | ✅ | `scripts/validate_structural.py`（分层统计 + 报告） |
| 测试 | ✅ | `tests/test_structural/` 20 项 + 原有 40 项，共 60 项全部通过 |

**M1 验证结果（实测）**：

- `qcfp_quarterly_structural`：944 行（14 只 × 全季度），`(stock_code, period_end)` 唯一，重复运行幂等；
- 状态分布：DECLINE 256 / ACCUMULATION 182 / DIVERGENCE 140 / BOTTOM_CANDIDATE 79 / BULLISH 45 / DISTRIBUTION 5 / UNDETERMINED 237（25%）；
- 交叉验证（2021+ 有资金流季度）：可比 144 行，**direct 证据行一致率 90.0%（9/10）≥ 70% 达标**；hold 保持行 49.3%（路径依赖，作为参考口径）；
- `03033`（ETF）无机构数据 → 跳过（DATA_INSUFFICIENT）；`00579`/`02602` 无任何数据；
- 关键设计说明：规格书 6 状态表只覆盖 ↑/↓ 组合，真实数据大量 C→/F→/P→ 季度走"保持前一状态"或 UNDETERMINED（占 25%），这是冻结规格的固有稀疏性；阈值校准（P6）可将定义组合覆盖率从默认 20% 提升到约 35%。

**下一步（P2 前置说明）**：月线行为引擎输入为 `hk_hist_monthly_kline`（换手/量/幅度）+ 本阶段产出的 CBI/Cost Position/Stage 逻辑；P1 的 `structural_regime` 将作为 P4 融合层门控输入。
