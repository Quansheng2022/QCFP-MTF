# QCFP-MTF P2 开发计划 —— 月线行为引擎（Behavioral Engine）

> 版本：v0.1（实施稿）
> 日期：2026-08-19
> 前置：P0/P1 已完成
> 依据：《QCFP-MTF 2.1.1 架构设计.md》§四、§五 + 总体开发计划 P2

## 一、范围与目标

P2 实现 **Layer 2（月线阶段层）**：用 B 级证据（量价-换手行为代理）判定月线行为状态，输出 T1~T5、9 种 VP_Regime、CBI、Cost Position、Monthly Stage。

| 项 | 内容 |
| :-- | :-- |
| 输入 | `hk_hist_monthly_kline`、`hk_hist_weekly_kline`、`hk_hist_quarterly_kline`、`qcfp_data_quality_audit` |
| 输出 | `qcfp_monthly_behavior`（P0 已建表，P2 写入并新增 Cost/CBI 列） |
| 核心模块 | `behavioral/turnover_factors.py`、`volume_factors.py`、`vp_matrix.py`、`cbi.py`、`cost_position.py`、`monthly_stage.py` |
| 里程碑 | M2：任意股票输出 CBI_Score、Cost_Position、Monthly_Stage 三组核心字段 |

## 二、数据输入映射（实测）

| 字段 | 计算方式 | 来源 | 覆盖 |
| :-- | :-- | :-- | :-- |
| 月换手率 | `turnover_rate` | 月 K 线 | 完整（3.4% 为 0，停牌月） |
| 月成交量 | `volume` | 月 K 线 | 完整 |
| 月成交额 | `amount` | 月 K 线 | 8.2% 为 0（清洗为 NaN） |
| 月振幅 | `amplitude` | 月 K 线 | 完整 |
| 月收益 | `change_percent` / close 环比 | 月 K 线 | 完整（0.3% NaN） |
| VWAP 周/月/季 | `amount/volume` 周期聚合 | 周/月/季 K 线 | 完整 |

## 三、模块设计与算法定义

### 3.1 `turnover_factors.py`（换手-流动性 T1~T5）

- `m_turnover_zscore`：个股滚动 12 月 Z-Score（不含当前，历史 ≥5 期）；
- `m_turnover_pctl`：滚动 12 月百分位（0~1，历史 ≥6 期）；
- `m_turnover_ma_ratio`：`turnover / MA6`；
- `turnover_liquidity_regime`：

```text
Z < -1.5        → T1 极低交换（pctl < 10%）
-1.5 ~ -0.5     → T2 低交换（10%~30%）
-0.5 ~ +0.5     → T3 正常交换（30%~70%）
+0.5 ~ +1.5     → T4 高交换（70%~90%）
> +1.5          → T5 极端交换（> 90%）
```

主判据用 Z 区间，百分位做交叉校验（相差超过 1 档时记录提示，仍以 Z 为准）。

### 3.2 `volume_factors.py`（量因子）

- `m_volume_ma_ratio`：`volume / MA6`；
- `m_volume_accel`：`vol_t / vol_{t-3} - 1`（3 期滞后加速度）；
- 量方向（供 VP 矩阵）：`ratio > 1.10 → ↑`、`< 0.90 → ↓`、`> 1.50 → ↑↑`（强放量），其余 →；
- 换手方向同规则（基于 `m_turnover_ma_ratio`）。

### 3.3 `vp_matrix.py`（9 种量价结构）

| Price | Volume | Turnover | VP_Regime |
| :-- | :-- | :-- | :-- |
| ↑ | ↑ | ↑ | `VP_EXPANSION`（趋势扩张） |
| ↑ | → | → | `VP_STABLE_ASCENT`（稳步上涨） |
| ↑ | ↓ | ↓ | `VP_LOCKED_CANDIDATE`（缩量上涨） |
| ↑ | ↑↑ | ↑↑ | `VP_OVERHEAT`（加速/博弈） |
| → | ↓ | ↓ | `VP_SHRINK`（缩量整理） |
| → | ↑ | ↑ | `VP_DIVERGENCE_HIGH`（高换手分歧） |
| ↓ | ↓ | ↓ | `VP_DECLINE_SILENT`（缓慢退潮） |
| ↓ | ↑ | ↑ | `VP_SELLING_ACTIVE`（主动抛售） |
| ↓ | ↑↑ | ↑↑ | `VP_PANIC`（恐慌） |

判定顺序：先强信号（↑↑ 类 OVERHEAT/PANIC）→ 常规组合 → 其余输出 `VP_NEUTRAL`（价格/量/换手均平）。价格方向阈值：月收益 > +1.5% → ↑，< -1.5% → ↓（可配置）。

### 3.4 `cbi.py`（Chip Behavior Index）

严格按规格书流程：**Winsorize(1%~99%) → Z-Score → 0~100 缩放 → 加权**：

```text
CBI = 30% × N(1/Turnover_Std12) + 30% × N(1 - Turnover_Pctl12)
    + 25% × N(1/Volume_Std12) + 15% × N(1/Amplitude_MA6)
```

状态映射：`>70 CBI_LOCKED_CANDIDATE / 50~70 CBI_STABLE / 30~50 CBI_ACTIVE / <30 CBI_TURBULENT`。

### 3.5 `cost_position.py`（成本位置，VWAP 剥离）

- VWAP = 周期 `amount/volume`（周/月/季各自聚合）；
- `cost_vs_weekly_vwap`：月末 close / 该月最后一周 VWAP - 1；
- `cost_vs_monthly_vwap`：月末 close / 当月 VWAP - 1（即 `m_vwap_deviation`）；
- `cost_vs_quarterly_vwap`：月末 close / 最近已披露季度 VWAP - 1（非季末月用上一季度）；
- 状态：`COST_ADVANTAGE`（> 月 VWAP 且 > 季 VWAP）/ `COST_DISADVANTAGE`（< 两者）/ `COST_NEUTRAL`（其余，含 ±2% 月 VWAP 附近）。

### 3.6 `monthly_stage.py`（月线阶段）

| 状态 | 触发条件 |
| :-- | :-- |
| `Improving` | VP ∈ {EXPANSION, LOCKED_CANDIDATE, STABLE_ASCENT} 且 T ∉ {T4, T5} |
| `Stable` | VP = SHRINK 或 T = T3（VP_NEUTRAL 且 T 非极端的按平稳处理） |
| `Deteriorating` | VP ∈ {OVERHEAT, DIVERGENCE_HIGH, SELLING_ACTIVE, PANIC, DECLINE_SILENT} |

## 四、关键设计决策

1. **CBI 与 Cost Position 分离**：CBI 只描述筹码交换行为，VWAP 成本单独成模块，二者互不混用；
2. **标准化严格**：CBI 每个子项先 Winsorize→Z→0~100 再加权，权重进配置（P6 校准）；
3. **缺失处理**：`amount=0`、`volume=0`、停牌月 → VWAP/比率置 NaN，不参与状态判定；
4. **数据质量**：取 `monthly_kline / weekly_kline / quarterly_kline` 三源最差等级（从 `qcfp_data_quality_audit` 读取）；
5. **写入规范**：`(stock_code, month_end)` UPSERT，`model_version` + `data_quality` + `update_time` 必填；
6. **表结构扩展**：`qcfp_monthly_behavior` 增加 `cbi_score / cbi_state / cost_position / cost_vs_weekly_vwap / cost_vs_monthly_vwap / cost_vs_quarterly_vwap`（规格书允许字段增加，字典同步更新）。

## 五、配置新增（`Config/qcfp_settings.yaml`）

```yaml
behavioral:
  turnover:
    window: 12
    min_history: 5
    pctl_min_history: 6
    z_bands: [-1.5, -0.5, 0.5, 1.5]
    pctl_bands: [0.10, 0.30, 0.70, 0.90]
  volume:
    ma_window: 6
    accel_lag: 3
    up_ratio: 1.10
    down_ratio: 0.90
    strong_ratio: 1.50
  price_direction:
    up_threshold: 1.5
    down_threshold: 1.5
  cost_position:
    neutral_pct: 2.0
```

（CBI 权重复用顶层 `cbi_weights`，CBI 状态阈值复用 `thresholds.cbi`。）

## 六、脚本与工作流集成

- 新脚本：`Core/QCFP_MTF/scripts/monthly_behavior_engine.py`
  - 参数：`--stock`、`--month-end`、`--dry-run`
- 追加到 `run_QCFP_MTF_workflow.py` `SCRIPT_LIST`（structural_engine 之后）：

```python
SCRIPT_LIST = [
    "init_db.py",
    "audit_coverage.py",
    "check_data_quality.py",
    "structural_engine.py",
    "monthly_behavior_engine.py",   # P2 新增
    "validate_structural.py",
]
```

## 七、测试计划

### 单元测试（`tests/test_behavioral/`）

| # | 用例 | 验收 |
| :-- | :-- | :-- |
| 1 | T1~T5 边界（Z 区间 + 百分位交叉） | 精确匹配 |
| 2 | 量比/量加速度公式 | 手算一致 |
| 3 | 9 种 VP 判定（含 ↑↑ 强信号优先） | 全覆盖 |
| 4 | CBI 标准化流程（Winsorize→Z→0~100→加权） | 手算一致，0~100 |
| 5 | Cost Position 三周期 VWAP + 状态 | 手算一致 |
| 6 | Monthly Stage 组合判定 | 全覆盖 |
| 7 | 缺失/停牌月处理（amount=0 → NaN） | 不产生错误状态 |

### 集成测试（真实数据）

- `monthly_behavior_engine.py --stock 00700`：写库 + 报告，重复运行幂等；
- 全量：15 只股票，行数 = 各股票月线行数；
- 合理性检查：CBI 分布 0~100；T 状态分布符合直觉；COST_ADVANTAGE 时月收益多正。

## 八、数据缺口与风险

| # | 风险 | 应对 |
| :-- | :-- | :-- |
| 1 | 月线 amount 8.2% 为零 | 置 NaN，不参与 VWAP |
| 2 | 停牌月 turnover=0 | 置 NaN，不参与 Z/百分位 |
| 3 | 滚动窗口初期（2010-2011）因子缺失 | min_history 控制，缺失行不判 T/VP，标注 |
| 4 | CBI 权重未经验证 | 配置化 + P6 回测校准 |
| 5 | 季度 VWAP 对非季末月的口径 | 用"最近已披露季度"，文档注明 |

## 九、里程碑 M2 验收标准

1. 任意有数据股票输出 `cbi_score`、`cost_position`、`monthly_behavior_state`；
2. `qcfp_monthly_behavior` 有写入，`(stock_code, month_end)` 唯一，重复运行幂等；
3. 单元测试全过（P2 新增 ≥ 20 项）；
4. CBI 全部落在 0~100，T/VP/Stage 状态覆盖规格书全部类型；
5. 数据质量继承正确（三源最差）。

## 十、任务拆分与工时

| # | 任务 | 模块 | 工时（人天） |
| :-- | :-- | :-- | :-- |
| 1 | 换手/量/VP 因子 | turnover/volume/vp_matrix | 1.5 |
| 2 | CBI + Cost Position | cbi/cost_position | 1.5 |
| 3 | Stage 判定 + 引擎脚本 | monthly_stage + engine | 1.0 |
| 4 | 测试 + 集成验证 | tests/test_behavioral/ | 1.0 |
| **合计** | | | **约 5 人天** |

## 十一、下一步

实施顺序：因子模块 → 引擎 → 测试 → 全量运行；完成后输出 M2 验证结果与测试清单/使用手册，再进入 P3（周线战术引擎）。

---

## 附：P2 交付记录（2026-08-19）

| 计划任务 | 状态 | 交付物 |
| :-- | :-- | :-- |
| 换手/量/VP 因子 | ✅ | `behavioral/turnover_factors.py`（T1~T5）、`volume_factors.py`（量比/加速度/方向）、`vp_matrix.py`（9+1 种） |
| CBI + Cost Position | ✅ | `behavioral/cbi.py`（Winsorize→Z→0~100→加权）、`cost_position.py`（周/月/季 VWAP 剥离） |
| Stage + 引擎 | ✅ | `behavioral/monthly_stage.py` + `scripts/monthly_behavior_engine.py`（UPSERT 写库） |
| 测试与集成 | ✅ | `tests/test_behavioral/` 21 项，全套 81 项通过；工作流 6 步端到端 ✅ |
| 表结构扩展 | ✅ | `qcfp_monthly_behavior` 增加 cbi_score/cbi_state/cost_position/cost_vs_* 6 列（字典已同步） |

**M2 验证结果（实测）**：

- `qcfp_monthly_behavior`：2267 行 / 15 只 / 2010-01-31 ~ 2026-07-31，`(stock_code, month_end)` 唯一，幂等；
- Stage：Deteriorating 945 / Stable 739 / Improving 583；T：T2 733 / T3 684 / T4 312 / T5 294 / T1 90；
- VP：规格书 9 种 + VP_NEUTRAL 全覆盖；CBI：1.9~100.0；Cost：DISADVANTAGE 1253 / NEUTRAL 638 / ADVANTAGE 169；
- 数据质量：C 1860 / A 407（继承月/周/季 K 线审计等级）。

**下一步（P3 前置说明）**：周线战术引擎输入为 `hk_hist_weekly_kline`（放量/缩量、换手偏离、VWAP 偏离、均线斜率），输出 `qcfp_weekly_tactical`；P2 的 `monthly_behavior_state` 将作为 P4 融合层 Stage 输入。
