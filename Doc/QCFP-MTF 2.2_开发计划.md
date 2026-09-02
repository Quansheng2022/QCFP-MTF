# QCFP-MTF 2.2 开发计划

> 版本：QCFP-MTF 2.2（Code Consolidation & Validation）
> 目标：把 2.1.1 的机构过滤器 + 散户波段雏形**正式化、收口、验证增量价值**

## 一、Sprint 计划

| Sprint | 内容 | 交付 | 状态 |
| :-- | :-- | :-- | :-- |
| S1 Contract Freeze | DecisionContext / Permission schema / FSM schema / 转移表 / 优先级 | `ARCHITECTURE.md`（十条规则） | ✅ V25/V26 |
| S2 Institutional Engine | state / pressure / persistence / divergence / confidence / permission | `institutional/` 领域包 + 正式接口 | ✅ V25/V26 |
| S3 Retail FSM | 七状态 + Cooldown + Chase Filter | `decision/retail_position_fsm.py` | ✅ V24 |
| S4 Risk Integration | Hard Exit / Stop / DES / 降级 | `decision/hard_exit.py` + FSM 联动 | ✅ V26/V27 |
| S5 Shadow Mode | legacy 与 new 双轨输出，不改交易 | `scripts/shadow_mode.py` | ✅ V26 |
| S6 Backtest / Ablation | A0~A4 五模型对比（含决策质量指标） | `scripts/permission_fsm_ablation.py` | ✅ V27/V29 |
| S7 Production Candidate | PIT / OOS / Robustness 全过才替换 Legacy | — | ⏳ 待外部数据 |

## 二、已完成（V10~V27 关键里程碑）

| 版本 | 内容 |
| :-- | :-- |
| V10 | 方案 B 温和试多 + CQS 催化剂质量评分 |
| V11 | 移动止损 + CQS 权重微调 + 回测重绑 |
| V12 | buffer 数据驱动寻优（0.02 最优） |
| V13 | buffer×触发器 20 组网格 + HTML |
| V14 | 日线战术层（L4，诊断层，未强行并入） |
| V15 | Correctness Hardening（四概念决策 + 止损单一来源 + E2E 一致性） |
| V16 | PIT/口径修正 + 层级消融 |
| V17 | Entry-Week-Low Stop 周收益完整性修复 |
| V18 | Dynamic Risk Exit（DES + 风险下限 + 滞后解除 + 仓位单调性） |
| V19 | Research Integrity（横截面 target 语义 / 缺失收益 / 超额定义 / Scope 分离） |
| V20 | 回测可信度（缺失收益 / 组合账本 / 三档 PIT / 成本压力 / Decision Trace） |
| V21 | 止损 PnL 暴露修复 + Research Manifest + 预测/交易双轨 |
| V22 | PIT 硬门 + 基准同口径 + 超额定义 + 决策字段标准化 |
| V23 | 散户波段决策系统（红黄绿灯 + 六态 + A/B 池） |
| V24 | Institutional Permission Engine + Retail Position FSM（雏形） |
| V25 | 2.2 Design Freeze（正式接口 + 测试驱动重构） |
| V26 | Contract Freeze + 正式领域层 + Shadow Mode |
| V27 | Code Consolidation + Permission/FSM Ablation |
| V28 | 架构收口：Permission×FSM 矩阵 + 暴露效率/坏暴露比 |
| V29 | 唯一决策链：DecisionSnapshot + Permission Ceiling + ExitEvent + Stateful Shadow + A0~A4 |

> **文档维护约定（2026-08-25）**：自 V28 起，版本演进记录统一维护在
> 《QCFP-MTF 2.2_开发计划.md》；2.1.1 文档冻结为历史基线，不再追加新版本记录。

## 三、Phase 边界

### 现在可以

```text
Architecture / Interfaces / Data Classes / State Machines / Permission Rules /
Unit & Integration Tests / Shadow Mode / Ablation
```

### 暂时不要

```text
参数优化 / 实盘权重优化 / 开启 Daily Timing / 扩大仓位上限 / 宣称模型有效
```

## 四、验收 Gate（G1~G7）

| Gate | 内容 |
| :-- | :-- |
| G1 Architecture | State/Permission/Setup/Position 分离；DecisionContext 完成；API 固定 |
| G2 Institutional | 五级 Permission；Persistence；Divergence/Confidence/DQ 降级 |
| G3 FSM | 七状态；合法/非法转换测试；Cooldown；Position boundary |
| G4 Risk | Hard Exit；DES；Stop；Hard Exit 不可被 Bullish/Breakout 覆盖 |
| G5 Daily | Daily 只产生 Timing Signal；不直接改 target；不绕过 Permission |
| G6 Research | PIT / OOS / Cost / Liquidity / Ablation / Plateau |
| G7 Production | Shadow Mode；Legacy/New 差异报告；Audit；可回滚 |

## 五、当前研究结论（如实）

- Ablation 实测：Permission = Risk Filtering（MDD -21.87%→-2.95%、换手 2.93→0.23）；
  FSM = 入场/退出质量（C 模型 Sharpe +0.50、PF 2.71）；当前市场 D 模型正确空仓；
- 数字口径 PIT-C、2021-08~2026-08，**不构成有效 alpha 证据**；
- 下一步：真实披露日历 + PIT Universe 数据接入 → PIT-A/B → 重跑 OOS/Robustness → 才考虑替换 Legacy。

## 六、2.2 架构收口进度（V28~V29）

| 项 | 状态 |
| :-- | :-- |
| Permission × FSM 状态矩阵（5×4=20 例穷举） | ✅ 已冻结并测试 |
| Permission Ceiling（交易上限 + assert） | ✅ V29 |
| ExitEvent 统一（HARD/STOP/FORCED_DELEVERAGE/NONE） | ✅ V29 |
| DecisionSnapshot（唯一决策链输出） | ✅ V29 |
| Stateful Shadow（全历史滚动重放） | ✅ V29（00371 868 快照） |
| Ablation A0~A4 + 决策质量指标（越权/跳跃/暴露效率/坏暴露比） | ✅ V29 |
| Hard Exit 覆盖（BUILDING/HOLDING/TRIMMING × Extreme/Stop） | ✅ V28 |
| FSM Timeline 跨股票隔离 | ✅ V28 |
