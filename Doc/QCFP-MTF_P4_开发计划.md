# QCFP-MTF P4 开发计划 —— 多周期融合层（Fusion Layer）

> 版本：v0.1（实施稿）
> 日期：2026-08-19
> 前置：P0~P3 已完成（qcfp_quarterly_structural / qcfp_monthly_behavior / qcfp_weekly_tactical 均有数据）
> 依据：《QCFP-MTF 2.1.1 架构设计.md》§三.2、§五.3、§2.3 + 总体开发计划 P4

## 一、范围与目标

P4 实现 **Layer 4（多周期融合层）**：把三层引擎输出融合为 5 种 MTF_Regime，产出 Chip Stability Confidence，并内置"层级不可越权"硬规则与 Anti-Inference 过滤器。

| 项 | 内容 |
| :-- | :-- |
| 输入 | `qcfp_quarterly_structural`、`qcfp_monthly_behavior`、`qcfp_weekly_tactical`、`hk_quarterly_chip_analysis`（chip_structure_score）、`hk_idx_hist`（市场环境） |
| 输出 | `qcfp_mtf_decision`（P0 已建表，P4 写入） |
| 核心模块 | `fusion/chip_confidence.py`、`mtf_alignment.py`、`mtf_fsm.py`、`anti_inference.py` |
| 里程碑 | M4：任意日期输出 mtf_regime + chip_stability_confidence 并通过禁止推断检查 |

## 二、融合逻辑

### 2.1 对齐矩阵（规格书 12 条 + 兜底）

规格书 12 条精确映射：

| Structural | Stage | Trigger | MTF_State |
| :-- | :-- | :-- | :-- |
| BULLISH | Improving | Breakout | BULLISH_CONFIRMED |
| BULLISH | Improving | Consolidation | BULLISH_STABLE |
| BULLISH | Stable | Breakout | BULLISH_STABLE |
| BULLISH | Stable | Consolidation | BULLISH_STABLE |
| BULLISH | Deteriorating | Breakdown | BULLISH_WARNING |
| ACCUMULATION | Improving | Breakout | BULLISH_CONFIRMED |
| ACCUMULATION | Improving | Consolidation | BULLISH_STABLE |
| ACCUMULATION | Deteriorating | Breakdown | BULLISH_WARNING |
| DIVERGENCE | Deteriorating | Breakdown | BULLISH_WARNING |
| DISTRIBUTION | Deteriorating | Breakdown | BEARISH_CONFIRMED |
| DECLINE | Deteriorating | Breakdown | BEARISH_CONFIRMED |
| BOTTOM_CANDIDATE | Improving | Breakout | BEARISH_RECOVERY_CANDIDATE |

**兜底规则（非矩阵组合，文档化）**：

- 结构多头族（BULLISH/ACCUMULATION）：Improving+Breakout → CONFIRMED；Deteriorating+Breakdown → WARNING；其余 → STABLE；
- DIVERGENCE：一律 BULLISH_WARNING（结构背离即警戒）；
- 结构空头族（DECLINE/DISTRIBUTION）：Improving+Breakout → BEARISH_RECOVERY_CANDIDATE（反弹候选，不构成反转）；其余 → BEARISH_CONFIRMED；
- BOTTOM_CANDIDATE：Improving+Breakout → RECOVERY_CANDIDATE；其余 → BULLISH_WARNING（候选未确认，警惕）。

### 2.2 层级不可越权（硬规则，代码断言）

- 结构多头族 永远 不得输出 BEARISH_CONFIRMED；
- 结构空头族 永远 不得输出 BULLISH_CONFIRMED / BULLISH_STABLE / BULLISH_WARNING；
- 违反即抛错（单元测试覆盖）。

### 2.3 Chip Stability Confidence（权重可配置）

```text
Confidence = 60% × Quarterly_Chip_Score + 40% × CBI_Normalized
Quarterly_Chip_Score = hk_quarterly_chip_analysis.chip_structure_score（0~100，复用 TA4C）
CBI_Normalized = qcfp_monthly_behavior.cbi_score（0~100）
≥70 → High；50~70 → Medium；<50 → Low
强制规则：c_state=C↓（季度筹码走弱）→ 一律 Low（"低流动性/关注度下降"，禁锁仓结论）
```

### 2.4 FSM-2（mtf_fsm）

`State(t+1) = Align(Structural, Stage, Trigger)`，与 2.1 同一矩阵；对给定当前状态 + 新事件返回下一状态，并再次校验不越权。

### 2.5 Anti-Inference（禁止推断表，14 条）

规则表 JSON 化（触发短语 → 禁止表述 → 允许表述），两种模式：

- `warn`（默认）：扫描结论文本，命中禁止表述则追加警告，不删除原文；
- `replace`：把禁止表述替换为允许表述。

### 2.6 结构-行为背离

- 结构多头族 + 月线 Deteriorating → `Divergence`；
- 结构空头族 + 月线 Improving → `Divergence`；
- 其余 → `Aligned` / `Unknown`（缺数据）。

## 三、输出（qcfp_mtf_decision）

决策粒度：**每股票 × 每周**（周线是触发层，每周为一个决策点，用截至该周的最近季度/月线数据对齐，天然支持 P6 回测）。

| 字段 | 来源 |
| :-- | :-- |
| decision_date | 周线 week_end |
| structural_regime / monthly_behavior_state / tactical_signal | 三层继承（≤ 决策日最近值） |
| cbi_score / cost_position | 最近月线 |
| chip_stability_confidence | 2.3 |
| mtf_regime | 2.1 |
| qcfp_score | State-First 映射（P5 评分表，先落列） |
| market_context | hk_idx_hist：HSI 60 日收益 + VHSI 分层（risk_on/risk_off/neutral） |
| evidence_summary | 证据等级摘要文本 |
| data_quality | 三层最差；结构为 UNDETERMINED/D → 整行 DATA_INSUFFICIENT |

action_signal / risk_level 留空（P5 填充）。

## 四、配置新增（`Config/qcfp_settings.yaml`）

```yaml
fusion:
  chip_confidence:
    quarterly_chip_weight: 0.60
    cbi_weight: 0.40
    high_threshold: 70
    medium_threshold: 50
  anti_inference:
    mode: warn
  market_context:
    hsi_return_window: 60
    vhsi_risk_off: 25
```

## 五、脚本与工作流集成

- 新脚本：`Core/QCFP_MTF/scripts/mtf_fusion_engine.py`
  - 参数：`--stock`、`--date`（决策日，默认最新周）、`--dry-run`
- 追加到 `run_QCFP_MTF_workflow.py` `SCRIPT_LIST`（weekly_tactical_engine 之后、validate 之前）：

```python
SCRIPT_LIST = [
    "init_db.py", "audit_coverage.py", "check_data_quality.py",
    "structural_engine.py", "monthly_behavior_engine.py",
    "weekly_tactical_engine.py", "mtf_fusion_engine.py",   # P4 新增
    "validate_structural.py",
]
```

## 六、测试计划

### 单元测试（`tests/test_fusion/`）

| # | 用例 | 验收 |
| :-- | :-- | :-- |
| 1 | 12 条矩阵精确映射 | 全覆盖 |
| 2 | 兜底规则（多头族/空头族/DIVERGENCE/BOTTOM） | 全覆盖 |
| 3 | 不越权断言（多头族禁 BEARISH_CONFIRMED 等） | 抛错测试 |
| 4 | Chip Confidence 权重公式 + 阈值 + C↓ 强制 Low | 手算一致 |
| 5 | FSM-2 状态转换 | 全覆盖 |
| 6 | Anti-Inference 14 条规则 warn/replace | 全覆盖 |
| 7 | 结构-行为背离标记 | 全覆盖 |

### 集成测试（真实数据）

- `mtf_fusion_engine.py --stock 00700`：写库 + 报告，幂等；
- 全量：每股票每周一行；5 种 MTF 状态均出现（或含 DATA_INSUFFICIENT）；
- 抽样验证：结构多头族的行不出现 BEARISH_CONFIRMED。

## 七、数据缺口与风险

| # | 风险 | 应对 |
| :-- | :-- | :-- |
| 1 | 结构 UNDETERMINED 占 25% | 输出 DATA_INSUFFICIENT，不产生决策 |
| 2 | chip_structure_score 与 C 因子口径差异 | 仅用于置信度（非状态判定），文档注明 |
| 3 | 决策行数大（15×865） | 全量 UPSERT 一次约 1.3 万行，可接受 |
| 4 | 兜底规则主观性 | 全部文档化 + 单测锁定，P6 回测校验 |

## 八、里程碑 M4 验收标准

1. 任意日期输出 mtf_regime + chip_stability_confidence，通过 anti-inference 检查；
2. `qcfp_mtf_decision` 有写入，`(stock_code, decision_date)` 唯一，幂等；
3. 12 条矩阵 + 兜底 + 不越权断言单测全过；
4. 结构多头族行不含 BEARISH_CONFIRMED（全量 SQL 验证）；
5. 数据质量 D/UNDETERMINED → DATA_INSUFFICIENT。

## 九、任务拆分与工时

| # | 任务 | 模块 | 工时（人天） |
| :-- | :-- | :-- | :-- |
| 1 | Chip Confidence | chip_confidence | 1.0 |
| 2 | 对齐矩阵 + 兜底 + 不越权 | mtf_alignment | 1.5 |
| 3 | FSM-2 + 结构-行为背离 | mtf_fsm | 0.5 |
| 4 | Anti-Inference | anti_inference | 1.0 |
| 5 | 引擎 + 工作流 | mtf_fusion_engine | 1.5 |
| 6 | 测试 + 集成 | tests/test_fusion/ | 1.0 |
| **合计** | | | **约 6.5 人天** |

## 十、下一步

实施顺序：融合模块 → 引擎 → 测试 → 全量运行；完成后输出 M4 验证结果与测试清单/使用手册，再进入 P5（DSS 决策层：Action/风险/输出协议）。

---

## 附：P4 交付记录（2026-08-19）

| 计划任务 | 状态 | 交付物 |
| :-- | :-- | :-- |
| Chip Confidence | ✅ | `fusion/chip_confidence.py`（60/40 加权 + 阈值 + C↓ 强制 Low） |
| MTF 对齐 + 兜底 + 不越权 | ✅ | `fusion/mtf_alignment.py`（12 条矩阵 + `_fallback` + `_assert_no_overrule`） |
| FSM-2 + 结构-行为背离 | ✅ | `fusion/mtf_fsm.py` + `structure_behavior_alignment` |
| Anti-Inference | ✅ | `fusion/anti_inference.py`（13 条规则，warn/replace 双模式） |
| 引擎与工作流 | ✅ | `scripts/mtf_fusion_engine.py`（每股票×每周决策点）+ 加入 `SCRIPT_LIST` |
| 测试与集成 | ✅ | `tests/test_fusion/` 21 项，全套 118 项通过；工作流 8 步端到端 ✅ |

**M4 验证结果（实测）**：

- `qcfp_mtf_decision`：9827 行 / 15 只 / 2010-01-08 ~ 2026-08-14，`(stock_code, decision_date)` 唯一，幂等；
- MTF 分布：BEARISH_CONFIRMED 3364 / BULLISH_WARNING 2872 / BULLISH_STABLE 2840 / DATA_INSUFFICIENT 730 / RECOVERY_CANDIDATE 12 / BULLISH_CONFIRMED 9；
- 置信度：Low 6707 / Medium 3063 / High 57；市场环境：risk_off 4124 / neutral 3194 / risk_on 2509；
- **不越权全量验证：多头结构 BEARISH_CONFIRMED 0 行、空头结构多头状态 0 行**；Anti-Inference 摘要全 PASSED；
- 00700 最新（2026-08-14）：BEARISH_CONFIRMED（结构 DECLINE）、conf=Low、market=risk_off。

**下一步（P5 前置说明）**：DSS 决策层将基于 `qcfp_mtf_decision` 填充 action_signal（BUY/ADD/HOLD/REDUCE/EXIT/WAIT，受单向门控约束）、risk_level 与 DSS JSON 输出协议。
