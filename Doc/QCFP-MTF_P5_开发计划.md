# QCFP-MTF P5 开发计划 —— DSS 决策层

> 版本：v0.1（实施稿）
> 日期：2026-08-19
> 前置：P0~P4 已完成（qcfp_mtf_decision 9827 行）
> 依据：《QCFP-MTF 2.1.1 架构设计.md》§七 DSS 输出协议 + 总体开发计划 P5

## 一、范围与目标

P5 实现 **Layer 5（DSS 决策层）**：基于 MTF_Regime 生成 Action（BUY/ADD/HOLD/REDUCE/EXIT/WAIT）、风险等级（Low/Medium/High/Extreme），并输出规格书第七章的标准 JSON 报告。

| 项 | 内容 |
| :-- | :-- |
| 输入 | `qcfp_mtf_decision` + 三层 `qcfp_*` 表（DSS 报告需要补充字段） |
| 输出 | `qcfp_mtf_decision` 更新 action_signal / risk_level；`Report/QCFP_MTF/dss/*.json|md` |
| 核心模块 | `decision/score_calculator.py`、`action_generator.py`、`risk_evaluator.py`、`dss_output.py` |
| 里程碑 | M5：任意股票+日期生成完整 DSS JSON + 可读报告 |

## 二、算法定义

### 2.1 Score Calculator（State-First）

`qcfp_score = 分数映射表[mtf_regime]`（P4 已落列，P5 形式化为独立模块）：

```text
BULLISH_CONFIRMED=85  BULLISH_STABLE=75  BULLISH_WARNING=55
BEARISH_RECOVERY_CANDIDATE=40  BEARISH_CONFIRMED=20  DATA_INSUFFICIENT=None
```

严禁"先算分再推状态"。

### 2.2 Action Generator（单向门控）

基础映射：

| MTF 状态 | Action |
| :-- | :-- |
| BULLISH_CONFIRMED | BUY |
| BULLISH_STABLE | HOLD |
| BULLISH_WARNING | REDUCE |
| BEARISH_RECOVERY_CANDIDATE | WAIT |
| BEARISH_CONFIRMED | EXIT |
| DATA_INSUFFICIENT | WAIT |

硬门控（代码强制）：

- 季度结构空头族（DECLINE/DISTRIBUTION）→ Action 只能 ∈ {WAIT, EXIT}（禁 BUY/ADD）；
- 季度结构多头族（BULLISH/ACCUMULATION）→ Action 不得为 EXIT；
- risk_level = Extreme → 强制降为 WAIT（禁 BUY/ADD）；
- data_quality = D / DATA_INSUFFICIENT → WAIT。

### 2.3 Risk Evaluator

```text
基础分（按 MTF 状态 1~4）
+1 结构-行为背离（Divergence）
+1 市场 risk_off
+1 data_quality = C
+2 data_quality = D
+1 置信度 Low
≤2 → Low；3 → Medium；4 → High；≥5 → Extreme
```

### 2.4 DSS 输出（规格书第七章 JSON）

```json
{
  "stock_code": "00700", "decision_date": "2026-08-14", "model_version": "QCFP-MTF-2.1.1",
  "structural": {"regime", "core_score", "evidence_level", "data_quality", "key_drivers": [C/F/P]},
  "stage": {"monthly_state", "turnover_regime", "vp_regime", "cbi_score"},
  "cost_position": {"status", "vs_weekly_vwap", "vs_monthly_vwap", "vs_quarterly_vwap"},
  "trigger": {"signal", "breakout", "breakdown", "volume_spike"},
  "confidence": {"chip_stability_confidence", "structure_behavior_alignment", "evidence_summary"},
  "risk": {"risk_level", "divergence_detected", "key_risks", "anti_inference_check": "PASSED"},
  "decision": {"mtf_regime", "action", "action_detail", "position_advice", "stop_loss_trigger"}
}
```

## 三、配置新增（`Config/qcfp_settings.yaml`）

```yaml
decision:
  action_mapping: {BULLISH_CONFIRMED: BUY, BULLISH_STABLE: HOLD, BULLISH_WARNING: REDUCE,
                   BEARISH_RECOVERY_CANDIDATE: WAIT, BEARISH_CONFIRMED: EXIT,
                   DATA_INSUFFICIENT: WAIT}
  risk:
    base: {BULLISH_CONFIRMED: 1, BULLISH_STABLE: 1, BULLISH_WARNING: 2,
           BEARISH_RECOVERY_CANDIDATE: 3, BEARISH_CONFIRMED: 3, DATA_INSUFFICIENT: 4}
    add_divergence: 1
    add_risk_off: 1
    add_dq_c: 1
    add_dq_d: 2
    add_low_confidence: 1
  position_advice:
    BULLISH_CONFIRMED: 80%~100%
    BULLISH_STABLE: 50%~80%
    BULLISH_WARNING: 20%~50%
    BEARISH_RECOVERY_CANDIDATE: 0%~20%
    BEARISH_CONFIRMED: 0%
    DATA_INSUFFICIENT: 0%
  stop_loss:
    BULLISH_WARNING: 周线放量跌破季VWAP×0.95
    BEARISH_RECOVERY_CANDIDATE: 跌破建仓成本-5%
    BEARISH_CONFIRMED: 空仓观望
```

## 四、脚本与工作流集成

- `scripts/decision_engine.py`：读 `qcfp_mtf_decision` → 计算 score/action/risk → **UPDATE** 回写表（参数 `--stock`、`--dry-run`）；
- `scripts/dss_report.py`：`--stock 00700 [--date 2026-08-14]`（缺省取最新决策日）→ 生成 JSON + Markdown 报告；
- 加入 `SCRIPT_LIST`（mtf_fusion_engine 之后）：

```python
SCRIPT_LIST = [..., "mtf_fusion_engine.py", "decision_engine.py", "validate_structural.py"]
```

## 五、测试计划

### 单元测试（`tests/test_decision/`）

| # | 用例 | 验收 |
| :-- | :-- | :-- |
| 1 | Score 映射（State-First） | 全覆盖 |
| 2 | Action 基础映射 | 全覆盖 |
| 3 | 单向门控：空头族禁 BUY/ADD、多头族禁 EXIT、Extreme→WAIT | 全覆盖 |
| 4 | Risk 计分（base + 各项加成） | 手算一致 |
| 5 | DSS JSON 结构与字段 | 与规格书第七章一致 |

### 集成测试（真实数据）

- `decision_engine.py --stock 00700`：action/risk 回写且幂等；
- `dss_report.py --stock 00700`：生成 JSON + MD；
- 全量校验：空头族行无 BUY/ADD；多头族行无 EXIT（SQL）。

## 六、数据缺口与风险

| # | 风险 | 应对 |
| :-- | :-- | :-- |
| 1 | Action 语义偏主观 | 全部映射进配置，P6 回测校验 |
| 2 | 停牌/无周线日 | 不产生决策行（决策点=周线） |
| 3 | 报告字段依赖三层表 | dss_report 做 join，缺字段置 null 并标注 |

## 七、里程碑 M5 验收标准

1. 任意股票+日期生成完整 DSS JSON + Markdown；
2. `qcfp_mtf_decision` 的 action_signal / risk_level 全部填充（DATA_INSUFFICIENT 行 = WAIT/Extreme）；
3. 全量门控验证：空头族 0 行 BUY/ADD；多头族 0 行 EXIT；
4. P5 新增单测 ≥ 15 项，全套通过。

## 八、任务拆分与工时

| # | 任务 | 模块 | 工时（人天） |
| :-- | :-- | :-- | :-- |
| 1 | Score / Action / Risk | score_calculator / action_generator / risk_evaluator | 1.5 |
| 2 | DSS 输出 + 报告 | dss_output + dss_report | 1.5 |
| 3 | 决策引擎 + 工作流 | decision_engine | 1.0 |
| 4 | 测试 + 集成 | tests/test_decision/ | 1.0 |
| **合计** | | | **约 5 人天** |

## 九、下一步

实施顺序：决策模块 → 引擎 → 报告 → 测试 → 全量运行；完成后输出 M5 验证结果与测试清单/使用手册，再进入 P6（回测与校准，系统闭环）。

---

## 附：P5 交付记录（2026-08-20）

| 计划任务 | 状态 | 交付物 |
| :-- | :-- | :-- |
| Score / Action / Risk | ✅ | `decision/score_calculator.py`、`action_generator.py`（单向门控）、`risk_evaluator.py` |
| DSS 输出 + 报告 | ✅ | `decision/dss_output.py`（规格书第七章 JSON）+ `scripts/dss_report.py`（JSON/MD） |
| 决策引擎 + 工作流 | ✅ | `scripts/decision_engine.py`（回写 action/risk）+ 加入 `SCRIPT_LIST` |
| 测试与集成 | ✅ | `tests/test_decision/` 15 项，全套 133 项通过；工作流 9 步端到端 ✅ |
| 表结构扩展 | ✅ | `qcfp_mtf_decision` 增加 structure_behavior_alignment 列（字典已同步） |

**M5 验证结果（实测）**：

- `qcfp_mtf_decision` 9827 行全部回写：Action = EXIT 3364 / REDUCE 2872 / HOLD 2840 / WAIT 742 / BUY 9；Risk = Extreme 4645 / High 2498 / Medium 1732 / Low 952；
- 全量门控验证：空头族 BUY/ADD = 0、多头族 EXIT = 0；
- 00700 最新（2026-08-14）：BEARISH_CONFIRMED → EXIT / risk=Extreme / position 0%，DSS JSON 与 MD 已生成；
- 修复关键 bug：`decision_engine` UPDATE 参数顺序错误（stock_code/decision_date 与 update_time 错位）导致 WHERE 永不匹配，修正后写入正常。

**下一步（P6 前置说明）**：回测系统将基于 `qcfp_mtf_decision` 的 action 序列做防 Look-ahead 切片回测，用 `hk_idx_hist` 分市场环境评估，并校准权重/阈值闭环。
