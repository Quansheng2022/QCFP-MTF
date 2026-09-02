# QCFP-MTF P3 开发计划 —— 周线战术引擎（Tactical Engine）

> 版本：v0.1（实施稿）
> 日期：2026-08-19
> 前置：P0/P1/P2 已完成
> 依据：《QCFP-MTF 2.1.1 架构设计.md》§4 周线战术引擎 + 总体开发计划 P3

## 一、范围与目标

P3 实现 **Layer 3（周线触发层）**：用 C 级证据（短周期量价-换手信号）判定战术触发，输出 Breakout / Pullback / Consolidation / Breakdown。

| 项 | 内容 |
| :-- | :-- |
| 输入 | `hk_hist_weekly_kline`（含 ema5/10/20、volume、amount、turnover_rate）、`qcfp_data_quality_audit` |
| 输出 | `qcfp_weekly_tactical`（P0 已建表，P3 写入并新增 w_volume_shrink 列） |
| 核心模块 | `tactical/weekly_volume.py`、`weekly_turnover.py`、`weekly_vwap.py`、`weekly_signal.py` |
| 里程碑 | M3：任意股票输出 tactical_signal（4 种）+ w_breakout / w_breakdown 布尔标记 |

## 二、数据输入映射（实测）

| 字段 | 计算方式 | 来源 | 覆盖 |
| :-- | :-- | :-- | :-- |
| 周量 | `volume` | 周 K 线 | 完整（0% 缺失/零值） |
| 周成交额 | `amount` | 周 K 线 | 完整 |
| 周换手 | `turnover_rate` | 周 K 线 | 完整 |
| 周均线 | `ema5 / ema10 / ema20` | 周 K 线（已算） | 完整 |
| 周高低价 | `high / low` | 周 K 线 | 完整 |
| 周 VWAP | `amount / volume` | 周 K 线 | 完整 |

## 三、模块设计与算法定义

### 3.1 `weekly_volume.py`（周量检测）

- `w_volume_breakout`：`volume > MA20(volume) × 1.8` → 1（放量突破候选）；
- `w_volume_shrink`：`volume < MA20(volume) × 0.5` → 1（极度缩量）；
- 阈值进配置（`tactical.volume.*`）。

### 3.2 `weekly_turnover.py`（周换手检测）

- `w_turnover_deviation`：`turnover / MA13(turnover) - 1`（13 周 ≈ 季度周均）；
- `w_turnover_spike`：`turnover > MA8(turnover) × 2.0` → 1（极端换手）。

### 3.3 `weekly_vwap.py`（周 VWAP 偏离）

- `w_vwap_deviation`：`close / VWAP_W - 1`，`VWAP_W = amount / volume`。

### 3.4 `weekly_signal.py`（均线斜率 + 信号合成）

- `w_ma_slope`：取 ema5/10/20 的二阶差分（加速/减速代理），
  `Δ² = ema[t] - 2·ema[t-1] + ema[t-2]`；相对收盘价阈值 `> +0.5% → 加速`、`< -0.5% → 减速`、其余 `平稳`；
- `w_breakout`（有效突破，三确认）：
  `close > 前 20 周最高 high`（不含当期）且 `w_volume_breakout=1` 且 `close > VWAP_W`；
- `w_breakdown`（有效破位）：
  `close < 前 20 周最低 low`（不含当期）且 `close < VWAP_W`；
- `tactical_signal` 合成：

```text
w_breakdown=1                 → Breakdown（破位）
w_breakout=1                  → Breakout（突破）
close < ema5 且 close > ema20  → Pullback（上升趋势回调）
其余                          → Consolidation（盘整）
```

## 四、关键设计决策

1. **证据等级 C**：本层只做 Timing，不参与结构判定；不引用季度/月线数据；
2. **突破/破位三确认**：价格创新高/新低 + 量能 + VWAP 位置三重过滤，降低假突破；
3. **均线用既有 ema 列**：与周线 TA2B 口径一致，避免重复计算；
4. **写入规范**：`(stock_code, week_end)` UPSERT，`model_version` / `data_quality` / `update_time` 必填；
5. **表结构扩展**：增加 `w_volume_shrink INTEGER`（字段可增加，字典同步）。

## 五、配置新增（`Config/qcfp_settings.yaml`）

```yaml
tactical:
  volume:
    ma_window: 20
    breakout_ratio: 1.8
    shrink_ratio: 0.5
  turnover:
    quarter_window: 13
    spike_ma_window: 8
    spike_ratio: 2.0
  ma:
    slope_lag: 2
    slope_threshold_pct: 0.5
  breakout:
    lookback: 20
```

## 六、脚本与工作流集成

- 新脚本：`Core/QCFP_MTF/scripts/weekly_tactical_engine.py`
  - 参数：`--stock`、`--week-end`、`--dry-run`
- 追加到 `run_QCFP_MTF_workflow.py` `SCRIPT_LIST`（monthly_behavior_engine 之后）：

```python
SCRIPT_LIST = [
    "init_db.py",
    "audit_coverage.py",
    "check_data_quality.py",
    "structural_engine.py",
    "monthly_behavior_engine.py",
    "weekly_tactical_engine.py",   # P3 新增
    "validate_structural.py",
]
```

## 七、测试计划

### 单元测试（`tests/test_tactical/`）

| # | 用例 | 验收 |
| :-- | :-- | :-- |
| 1 | 放量/缩量阈值（1.8 / 0.5） | 精确匹配 |
| 2 | 换手偏离 + 极端换手（MA8×2.0） | 精确匹配 |
| 3 | VWAP 偏离公式 | 手算一致 |
| 4 | 均线二阶差分斜率（加速/减速/平稳） | 精确匹配 |
| 5 | 突破三确认（新高+放量+VWAP 上） | 全覆盖 |
| 6 | 破位判定（新低+VWAP 下） | 全覆盖 |
| 7 | 4 种信号合成 | 全覆盖 |

### 集成测试（真实数据）

- `weekly_tactical_engine.py --stock 00700`：写库 + 报告，幂等；
- 全量 15 只：行数 = 各股票周线行数（9827）；
- 合理性：Breakdown/Breakout 分布不过度稀疏；Pullback 应伴随短期回调（close < ema5）。

## 八、数据缺口与风险

| # | 风险 | 应对 |
| :-- | :-- | :-- |
| 1 | 前 20 周窗口期无历史 | lookback 不足时 w_breakout/breakdown 置 0，不误报 |
| 2 | MA 窗口初期无 MA20 | 量比/缩量标记 NaN→0 |
| 3 | 停牌周数据缺失 | 因子置 NaN，不参与信号合成 |
| 4 | 突破阈值可能过严/过松 | 全部配置化，P6 回测校准 |

## 九、里程碑 M3 验收标准

1. 任意有数据股票输出 `tactical_signal`（4 种）+ `w_breakout` / `w_breakdown`；
2. `qcfp_weekly_tactical` 有写入，`(stock_code, week_end)` 唯一，幂等；
3. P3 新增单元测试 ≥ 15 项，全套通过；
4. 4 种信号均出现且分布合理；
5. 数据质量继承 `weekly_kline` 审计等级。

## 十、任务拆分与工时

| # | 任务 | 模块 | 工时（人天） |
| :-- | :-- | :-- | :-- |
| 1 | 周量/换手/VWAP 因子 | weekly_volume / weekly_turnover / weekly_vwap | 1.5 |
| 2 | 均线斜率 + 信号合成 | weekly_signal | 1.0 |
| 3 | 引擎脚本 + 工作流 | weekly_tactical_engine | 1.0 |
| 4 | 测试 + 集成验证 | tests/test_tactical/ | 1.0 |
| **合计** | | | **约 4.5 人天** |

## 十一、下一步

实施顺序：因子模块 → 信号合成 → 引擎 → 测试 → 全量运行；完成后输出 M3 验证结果与测试清单/使用手册，再进入 P4（多周期融合层）。

---

## 附：P3 交付记录（2026-08-19）

| 计划任务 | 状态 | 交付物 |
| :-- | :-- | :-- |
| 周量/换手/VWAP 因子 | ✅ | `tactical/weekly_volume.py`（放量 1.8 / 缩量 0.5）、`weekly_turnover.py`（季度周均偏离 + MA8×2 极端）、`weekly_vwap.py`（amount/volume） |
| 均线斜率 + 信号合成 | ✅ | `tactical/weekly_signal.py`（ema5 二阶差分 + 突破三确认 + 4 种信号） |
| 引擎与工作流 | ✅ | `scripts/weekly_tactical_engine.py`（UPSERT 写库）+ 加入 `SCRIPT_LIST` |
| 测试与集成 | ✅ | `tests/test_tactical/` 16 项，全套 97 项通过；工作流 7 步端到端 ✅ |
| 表结构扩展 | ✅ | `qcfp_weekly_tactical` 增加 w_volume_shrink 列（字典已同步） |

**M3 验证结果（实测）**：

- `qcfp_weekly_tactical`：9827 行 / 15 只 / 2010-01-08 ~ 2026-08-14，`(stock_code, week_end)` 唯一，幂等；
- 信号：Consolidation 8233 / Pullback 1038 / Breakdown 472 / Breakout 84；w_breakout=84、w_breakdown=472；
- 量能：放量 920 / 缩量 1418 / 极端换手 501；斜率：加速 4019 / 减速 3927 / 平稳 1851；
- 数据质量：A 6914 / C 2913（继承 weekly_kline 审计等级）；
- 00700 最新周（2026-08-14）：Consolidation，VWAP -2.97%，斜率减速。

**下一步（P4 前置说明）**：多周期融合层输入 = P1 `structural_regime` + P2 `monthly_behavior_state` + P3 `tactical_signal`，按规格书 12 条映射矩阵输出 MTF_Regime；同时实现 Chip Stability Confidence 与 Anti-Inference 过滤。
