---
title: QCFP-MTF 2.1.1 筹码-资金-价格 多时间框架 股票分析系统 架构设计
date: 2026-08-18
tags: [QS财富方舟]
---

# QCFP-MTF 2.1.1 架构设计（基线）

> **注意**：2.1.1 为基线架构；系统已演进至 **QCFP-MTF 2.2**（机构行为过滤器 + 散户波段决策）。
> 2.2 的架构冻结、开发计划、目录结构、使用手册与测试清单见同目录
> 《QCFP-MTF 2.2_架构设计.md》《QCFP-MTF 2.2_开发计划.md》《QCFP-MTF 2.2_目录与结构图.md》
> 《QCFP-MTF 2.2_使用手册.md》《QCFP-MTF 2.2_测试清单.md》。

# QCFP-MTF 简介
Quarter Chip-Flow-Price - Multi-Timeframe 
季度筹码-资金-价格 三维多时间周期框架 股票分析系统

在 **QCFP-MTF 2.1.1** 这个系统里，**MTF** 是 **Multi-Timeframe（多时间框架）** 的缩写。

但请注意：**它绝不只是“同时看三个周期的K线图”**。在这个系统里，MTF 是一种**严格的“层级决策架构”**——它把三个周期定义为三个不同权限的决策层，而不是三个平级的参考信号。

具体来说，在 QCFP-MTF 2.1.1 中，MTF 的核心含义可以拆解为 **3个层级 + 1个规则**：

---

## 一、MTF 的 3 个层级（核心定义）

系统强制区分季度、月线、周线的职责，互不混淆：

| 层级 | 周期 | 系统内的专业术语 | 回答的核心问题 | 决策权限 |
| :--- | :--- | :--- | :--- | :--- |
| **第一层（主引擎）** | **季度** | **Structural（结构层）** | **“这只股票的基本盘硬不硬？”**（谁在拿货？资金认不认可？） | **门控（Gate）**：决定 **能不能买**（值不值得重仓） |
| **第二层（辅助修正）** | **月线** | **Stage（阶段层）** | **“当前的季度结构演化到什么火候了？”**（是主升初期还是末期？） | **修正（Modifier）**：决定 **当前节奏**（结构是否正在被验证或破坏） |
| **第三层（执行触发器）** | **周线** | **Trigger（触发层）** | **“此时此刻要不要动手？”**（突破了吗？破位了吗？） | **时机（Timing）**：决定 **什么时候具体操作** |

---

## 二、为什么要搞这个 MTF（解决的核心痛点）？

在纯量价分析里，我们常看到“周线走坏了”就赶紧清仓，结果发现这只是季度大牛市的正常回调，踏空了主升浪。

**MTF 架构就是为了杜绝这种“低周期干扰高周期”的误判。**

1. **解决数据频率错配**：你的**机构筹码（C）**数据只有季度频（还滞后1个月），而**价格和资金（P&F）**是日频/周频。MTF 强制要求：**低频率的“真筹码”决定方向，高频率的“量价行为”只负责验证方向**。
2. **解决滞后性**：季度数据虽然准，但太慢。MTF 允许周线在季度结构没变坏的前提下，提前发出“战术撤退”信号（即减仓，而不是彻底看空）。

---

## 三、MTF 在这里的“硬规则”（禁止越权）

在你冻结的 2.1.1 规格书中，MTF 的核心体现就是这**两条铁律**（代码层面会写死）：

1. **周线破位（Trigger=Breakdown）绝对不允许推翻季度主升（Structural= Bullish）**。  
   → 结果只能是 **结构性强势下的战术回调（MTF状态 = BULLISH_WARNING）**，系统绝对不给出“清仓退场”的信号。
2. **只有季度新数据（C/F/P变化）才能推动季度结构状态机（FSM-1）切换**（比如从“Bullish”变成“Decline”）。  
   → 月线和周线的数据事件（Event）只能推动多周期战术状态机（FSM-2）切换（比如从“BULLISH_STABLE”变成“BULLISH_WARNING”）。


## 四、1个规则 -- **“层级不可越权”（Hierarchical Non-Overrule）**
这“1个规则”就是 **“层级不可越权”（Hierarchical Non-Overrule）**，也就是整个 MTF 架构的**最高宪法**。

在 QCFP-MTF 2.1.1 中，把它拆解为一句可直接落地的硬性逻辑，就是：

> **低周期（周线/月线）只能修正“战术动作”（加减仓/等待），绝对不能改变高周期（季度）的“结构性质”（看涨/看跌）。**

为了让程序严格执行，这个规则在系统里被固化为 **“单向门控逻辑”**：

### 1. 正向锁死（结构决定生死）
- **如果** 季度结构引擎判定为 `DECLINE`（退潮）或 `DISTRIBUTION`（派发），**那么** 无论月线行为多么“改善”、周线信号多么“强势突破”，DSS 最终输出 **绝对禁止** 给出 `BUY`（买入）或 `ADD`（加仓）指令。
- *系统逻辑*：只能输出 `WAIT`（等待）或 `EXIT`（离场）。

### 2. 反向降级（高频只改节奏）
- **如果** 季度结构引擎判定为 `BULLISH`（主升）或 `ACCUMULATION`（蓄势），**那么** 即使周线出现 `Breakdown`（破位下跌），DSS 也**绝对禁止**将结构状态推翻为“退潮”。
- *系统逻辑*：只能把最终状态从“强共振（`BULLISH_CONFIRMED`）”降级为“结构健康但战术预警（`BULLISH_WARNING`）”，输出信号只能是 `REDUCE`（减仓）或 `HOLD`（持有观察），**严禁输出 `EXIT`（清仓）**。

---

### 这个规则在代码里的强制执行方式
在你冻结的 2.1.1 规格书里，`P4（多周期融合层）` 中的 **`mtf_alignment.py`（多周期对齐协调器）** 会按照以下“硬编码判定表”执行这个规则：

| 季度结构（高周期） | 周线信号（低周期） | **系统允许的最终状态** | **禁止的错误输出** |
| :--- | :--- | :--- | :--- |
| `STRUCTURAL_BULLISH` | `BREAKDOWN` | ➡️ **`BULLISH_WARNING`**（高位预警，减仓观察） | ❌ 禁止输出 `BEARISH_CONFIRMED`（退潮） |
| `STRUCTURAL_DECLINE` | `BREAKOUT` | ➡️ **`BEARISH_RECOVERY_CANDIDATE`**（只是反弹候选，不构成反转） | ❌ 禁止输出 `BULLISH_CONFIRMED`（反转买入） |

---

**总结：** 
这“1个规则”确保了你的系统不会犯散户最常见的错误——**被周线的一根大阴线吓跑，从而错失季线级别的大牛股；也不会因为周线的脉冲反弹，就去抄季线级别大跌的底。** 这就是 **MTF（多时间框架）** 区别于“简单指标罗列”的核心护城河。

---

### 四、最精炼的一句总结

> **QCFP-MTF 中的 MTF，就是把“季度的战略判断、月线的战役阶段、周线的战术动作”封装成一个分层过滤网：用低频真数据定生死（结构），用高频行为数据定买卖（时机）。**

**简单说：MTF 不是看三个图，而是“大周期定方向，小周期找拐点”——且小周期永远服从大周期。** 这正是 QCFP-MTF 2.1.1 区别于普通指标堆砌系统的灵魂所在。

# QCFP-MTF 2.1.1 工程规格书（最终冻结版）

## 季度筹码—资金—价格多周期状态机决策系统

> **版本状态**：🔒 **正式冻结** — 完成全部架构评审，进入 P0 工程实现阶段。
> **版本路径**：`QCFP 1.0 → 1.x → MTF 2.0 → 2.1 → 2.1.1（当前）`
> **核心修订**：① 拆分 Quarterly FSM 与 MTF FSM；② 修正 CBI 数学标准化 + VWAP 剥离为 Cost Position；③ 增加 `model_version` / `data_quality` / 真实 `available_date`；④ 补充禁止推断表（Anti-Inference Rule）。

---

## 一、核心哲学与不可违背原则

### 1.1 系统总纲

> **季度真实筹码—资金—价格决定结构（Structural Anchor）；月线量价—换手行为识别阶段（Stage）；周线量价—换手行为确认交易触发（Trigger）。三层信息逐级收敛，绝不越级。**

### 1.2 四大铁律（工程固化版）

| # | 铁律 | 工程含义 |
| :--- | :--- | :--- |
| **①** | **真实筹码不可替代** | 季度的 `inst_ownership_pct_chg` / `holder_quantity_chg_pct` 是唯一能回答"谁持有"的 A 级证据；周/月换手率**永远不能**升级为筹码结构结论 |
| **②** | **代理变量 ≠ 事实变量** | CBI（Chip Behavior Index）是行为代理指数，不是真实筹码；所有基于 V/T 的推论必须与季度真实筹码联合验证 |
| **③** | **层级不可越权** | 周线 `Trigger` 不能推翻月线 `Stage`；月线 `Stage` 不能推翻季度 `Structural_Regime`；周线破位只能触发"战术减仓"，不能输出"结构翻转" |
| **④** | **State First, Score Second** | 先判定状态（State）→ 再输出 Regime → 最后映射 Score；**严禁**先算加权分再反推状态 |

### 1.3 三层权限体系

| 层级 | 周期 | 核心问题 | 数据 | 决策权限 | 证据等级 |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Structural** | 季度 | **这是什么股票？** | 真实 C + F + P | **门控** — 决定可不可以买 | A / A- |
| **Stage** | 月线 | **它现在处于什么阶段？** | V + T + P 行为代理 | **修正** — 决定结构在演化中的位置 | B |
| **Trigger** | 周线 | **现在是否到了行动时点？** | V + T + P 短期信号 | **时机** — 决定什么时候动手 | C |

---

## 二、证据等级与数据质量体系（新增核心模块）

### 2.1 五级证据等级（修订版）

| 等级 | 定义 | 指标举例 | 决策权限 |
| :--- | :--- | :--- | :--- |
| **A** | 事实/直接数据 | 机构持股比例变化、股东户数变化、季度机构资金净流入 | 可单独支撑结构性结论 |
| **A-** | 高可信派生事实 | 季度 Trend Score、IFA Z-Score、52周位置（季末快照） | 可支撑结论，需交叉验证 |
| **B** | 行为代理 | 月线换手率 Z-Score/百分位、月成交量趋势、量价矩阵状态 | 不能单独推出筹码结论，仅用于阶段修正 |
| **C** | 短周期交易信号 | 周线突破/破位、周换手偏离度、短期均线斜率 | 仅用于 Timing，不参与结构判定 |
| **D** | **模型推断/组合结果** | **CBI、Chip_Stability_Confidence、Final_Regime、QCFP_Score** | 不作为独立证据，仅供决策参考 |

### 2.2 数据质量等级（新增）

| 等级 | 定义 | 触发条件 |
| :--- | :--- | :--- |
| **A** | 完整 | 所有关键字段均有值，且来源可追溯 |
| **B** | 轻微缺失 | 个别辅助字段缺失，核心字段完整 |
| **C** | 重大缺失 | 核心字段（如机构持股）缺失或明显异常 |
| **D** | 数据不足 | 无法形成有效判断 |

> **联合规则**：`Confidence = f(Evidence_Level, Data_Quality)`，任一为 D 则整体判定为"数据不足，不产生决策信号"。

### 2.3 禁止推断表（Anti-Inference Rule）—— 新增核心模块

> **目的**：防止模型从代理变量跳跃到未经证实的主力行为叙事。此表将硬编码入 DSS 输出层，作为 AI 报告生成的前置过滤器。

| 数据现象 | **允许推断（上限）** | **禁止直接推断** |
| :--- | :--- | :--- |
| 换手率下降 | 市场筹码交换速度下降 | 机构锁仓 / 主力吸筹 |
| 成交量下降 | 市场活跃度降低 | 主力高度控盘 / 抛压耗尽 |
| 价格上涨 | 定价改善，买方占优 | 机构买入 / 主力拉升 |
| 价涨量增 | 趋势扩张，有增量资金参与 | 机构建仓 / 主力控盘 |
| 价涨量缩 | 上涨动能减弱，或浮筹减少 | 机构锁仓上涨 / 主力高度控盘 |
| 高换手滞涨 | 多空分歧加大 | 主力派发 / 出货确认 |
| 低换手上涨 | 筹码交换效率高，浮筹较少 | 机构锁仓 / 主力控盘 |
| 季度机构持股↑ | 机构投资者在该季度增持 | 未来股价一定上涨 / 机构看多 |
| 季度股东户数↓ | 户均持股上升，筹码呈集中趋势 | 一定是机构在收集 / 主力吸筹 |
| 价格跌破 VWAP | 短期平均持仓者亏损 | 趋势反转 / 主力出货 |
| 价格站上 VWAP | 短期平均持仓者盈利 | 趋势启动 / 主力入场 |
| CBI 处于低位 | 市场行为活跃，换手积极 | 筹码分散 / 主力离场 |
| CBI 处于高位 | 市场行为稳定，换手较低 | 机构高度锁仓 / 无风险 |

> **工程实现方式**：DSS 输出层的自然语言生成模块在形成任何结论前，必须扫描此表。若生成内容触犯"禁止推断"规则，则强制降级为允许推断的上限表述。

---

## 三、两级状态机（FSM）架构 —— 核心架构修订

> **核心变更**：原 2.1 版本将季度 Structural FSM 与 MTF Tactical FSM 混合在一起，现拆分为两个独立但协同的 FSM。

### 3.1 FSM-1：Quarterly Structural FSM（季度结构状态机）

**驱动力量**：仅由**季度新信息**（机构持股、股东户数、季度资金流、季度价格）推动转换。

**状态定义**（6 个结构性状态）：

| ID | 状态名称 | C | F | P | 证据等级 |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `QS1` | `STRUCTURAL_BULLISH` | ↑ | ↑ | ↑ | A |
| `QS2` | `STRUCTURAL_ACCUMULATION` | ↑ | ↑ | → | A |
| `QS3` | `STRUCTURAL_DIVERGENCE` | ↑ | ↓ | ↑ | A- |
| `QS4` | `STRUCTURAL_DISTRIBUTION` | ↓ | ↓ | ↑ | A |
| `QS5` | `STRUCTURAL_DECLINE` | ↓ | ↓ | ↓ | A |
| `QS6` | `STRUCTURAL_BOTTOM_CANDIDATE` | ↓ | ↑ | ↓ | A- |

> **命名说明**：原 `MARK_UP_CONFIRMED` 降级为 `STRUCTURAL_BULLISH`，因"确认"需要多周期验证，不应在季度层面断言。

**状态转换规则**（仅由季度数据驱动）：

| 当前状态 | 下一季度 C/F/P 变化 | 下一状态 |
| :--- | :--- | :--- |
| `STRUCTURAL_ACCUMULATION` | C↑ F↑ P↑ | `STRUCTURAL_BULLISH` |
| `STRUCTURAL_BULLISH` | C↓ F↓ P↑ | `STRUCTURAL_DISTRIBUTION` |
| `STRUCTURAL_BULLISH` | C↑ F↓ P↑ | `STRUCTURAL_DIVERGENCE` |
| `STRUCTURAL_DIVERGENCE` | C↓ F↓ P↓ | `STRUCTURAL_DECLINE` |
| `STRUCTURAL_DISTRIBUTION` | C↓ F↓ P↓ | `STRUCTURAL_DECLINE` |
| `STRUCTURAL_DECLINE` | C↑ F↑ P→ | `STRUCTURAL_ACCUMULATION` |
| `STRUCTURAL_DECLINE` | C↓ F↑ P↓ | `STRUCTURAL_BOTTOM_CANDIDATE` |
| `STRUCTURAL_BOTTOM_CANDIDATE` | C↑ F↑ P↑ | `STRUCTURAL_BULLISH` |

### 3.2 FSM-2：MTF Tactical FSM（多周期战术状态机）

**驱动力量**：`Structural_State + Monthly_Stage + Weekly_Event → MTF_State`

**状态定义**（5 个多周期综合状态）：

| ID | MTF 状态 | 含义 |
| :--- | :--- | :--- |
| `MTF1` | `BULLISH_CONFIRMED` | 结构强势 + 月线改善 + 周线突破 → 🟢 强共振 |
| `MTF2` | `BULLISH_STABLE` | 结构强势 + 月线稳定 + 周线盘整 → 🟢 趋势健康，等待时机 |
| `MTF3` | `BULLISH_WARNING` | 结构强势 + 月线恶化 + 周线破位预警 → 🟡 结构松动，战术警惕 |
| `MTF4` | `BEARISH_RECOVERY_CANDIDATE` | 结构底部候选 + 月线改善 + 周线突破 → 🟡 左侧试盘成功 |
| `MTF5` | `BEARISH_CONFIRMED` | 结构退潮 + 月线恶化 + 周线破位 → 🔴 多周期退潮，坚决回避 |

**合成规则**：

```
MTF_State = F(
  Structural_Regime（6种）,
  Monthly_Stage（Improving / Stable / Deteriorating）,
  Weekly_Trigger（Breakout / Pullback / Consolidation / Breakdown）
)
```

**完整映射矩阵**：

| Structural_Regime | Monthly_Stage | Weekly_Trigger | MTF_State |
| :--- | :--- | :--- | :--- |
| `STRUCTURAL_BULLISH` | Improving | Breakout | `BULLISH_CONFIRMED` |
| `STRUCTURAL_BULLISH` | Improving | Consolidation | `BULLISH_STABLE` |
| `STRUCTURAL_BULLISH` | Stable | Breakout | `BULLISH_STABLE` |
| `STRUCTURAL_BULLISH` | Stable | Consolidation | `BULLISH_STABLE` |
| `STRUCTURAL_BULLISH` | Deteriorating | Breakdown | `BULLISH_WARNING` |
| `STRUCTURAL_ACCUMULATION` | Improving | Breakout | `BULLISH_CONFIRMED` |
| `STRUCTURAL_ACCUMULATION` | Improving | Consolidation | `BULLISH_STABLE` |
| `STRUCTURAL_ACCUMULATION` | Deteriorating | Breakdown | `BULLISH_WARNING` |
| `STRUCTURAL_DIVERGENCE` | Deteriorating | Breakdown | `BULLISH_WARNING` |
| `STRUCTURAL_DISTRIBUTION` | Deteriorating | Breakdown | `BEARISH_CONFIRMED` |
| `STRUCTURAL_DECLINE` | Deteriorating | Breakdown | `BEARISH_CONFIRMED` |
| `STRUCTURAL_BOTTOM_CANDIDATE` | Improving | Breakout | `BEARISH_RECOVERY_CANDIDATE` |

> **关键原则**：周线 `Breakdown` 不能将 `STRUCTURAL_BULLISH` 直接变为 `BEARISH_CONFIRMED`，只能降为 `BULLISH_WARNING`。结构翻转必须由季度数据驱动。

---

## 四、月线行为引擎

### 4.1 换手—流动性状态（T1~T5）

| 状态 | 换手率 Z-Score 区间 | 换手率百分位 | 行为解释 |
| :--- | :--- | :--- | :--- |
| **T1 极低交换** | < -1.5 | < 10% | 筹码几乎不流动 |
| **T2 低交换** | -1.5 ~ -0.5 | 10%~30% | 筹码交换缓慢 |
| **T3 正常交换** | -0.5 ~ +0.5 | 30%~70% | 筹码正常流转 |
| **T4 高交换** | +0.5 ~ +1.5 | 70%~90% | 筹码加速换手 |
| **T5 极端交换** | > +1.5 | > 90% | 极度活跃/博弈 |

### 4.2 量价结构矩阵（修订版 — 增加第 9 种状态）

| Price | Volume | Turnover | VP_Regime | 行为含义 |
| :--- | :--- | :--- | :--- | :--- |
| ↑ | ↑ | ↑ | `VP_EXPANSION` | 趋势扩张（健康） |
| ↑ | → | → | `VP_STABLE_ASCENT` | **稳步上涨，量价正常（新增）** |
| ↑ | ↓ | ↓ | `VP_LOCKED_CANDIDATE` | 缩量上涨（锁定候选） |
| ↑ | ↑↑ | ↑↑ | `VP_OVERHEAT` | 加速/博弈升温 |
| → | ↓ | ↓ | `VP_SHRINK` | 缩量整理 |
| → | ↑ | ↑ | `VP_DIVERGENCE_HIGH` | 高换手分歧 |
| ↓ | ↓ | ↓ | `VP_DECLINE_SILENT` | 缓慢退潮/无人交易 |
| ↓ | ↑ | ↑ | `VP_SELLING_ACTIVE` | 主动抛售 |
| ↓ | ↑↑ | ↑↑ | `VP_PANIC` | 恐慌/剧烈分歧 |

### 4.3 月线行为状态

| 状态 | 核心特征 | 触发条件 |
| :--- | :--- | :--- |
| **Improving** | 行为改善 | VP_Regime ∈ {EXPANSION, LOCKED_CANDIDATE, STABLE_ASCENT} 且 T 状态不为 T4/T5 |
| **Stable** | 行为平稳 | VP_Regime ∈ {SHRINK} 或 T3 正常交换 |
| **Deteriorating** | 行为恶化 | VP_Regime ∈ {OVERHEAT, DIVERGENCE_HIGH, SELLING_ACTIVE, PANIC, DECLINE_SILENT} |

---

## 五、CBI（Chip Behavior Index）与 Cost Position 分离 —— 核心修订

> **核心变更**：原 2.1 版本将 VWAP 纳入 CBI，现**剥离 VWAP**，单独建立 **Cost Position** 模块。CBI 仅描述"筹码交换行为"，VWAP 描述"成本位置"，两者概念分离。

### 5.1 CBI（Chip Behavior Index）— 行为代理指数

**定义**：CBI 是一个 **B 级行为代理指数**，描述"市场筹码交换行为的活跃/稳定程度"。**它不是筹码结构本身，而是连接真实筹码与高频市场行为的桥梁。**

**标准化流程（工程级）**：

```
Raw Factor → Winsorize(1%~99%) → Z-Score Normalize → Scale to 0~100 → Weighted Sum
```

**最终公式**：

```
CBI = 
  30% × N(Turnover_Stability)      [1 / Turnover_Std_12M]
+ 30% × N(Turnover_Pctl_Inverse)   [100% - 52W Percentile]
+ 25% × N(Volume_Stability)        [1 / Volume_Std_12M]
+ 15% × N(Amplitude_Stability)     [1 / Amplitude_MA6]
```

> **注意**：所有子项必须先标准化为 0~100 分再进行加权。

**CBI 状态映射**：

| CBI 区间 | 状态 | 行为含义 |
| :--- | :--- | :--- |
| > 70 | `CBI_LOCKED_CANDIDATE` | 筹码交换极低，**锁定候选**（需季度 C 验证） |
| 50 ~ 70 | `CBI_STABLE` | 筹码交换正常，行为平稳 |
| 30 ~ 50 | `CBI_ACTIVE` | 筹码交换加速，市场活跃 |
| < 30 | `CBI_TURBULENT` | 筹码交换剧烈，高博弈/分歧 |

### 5.2 Cost Position（成本位置模块）— 从 CBI 剥离

**定义**：独立描述"当前价格相对于各周期平均成本的位置"。

| 指标 | 计算方式 | 含义 |
| :--- | :--- | :--- |
| `cost_vs_weekly_vwap` | Close / VWAP_W - 1 | 周内持仓者盈亏状态 |
| `cost_vs_monthly_vwap` | Close / VWAP_M - 1 | 月内持仓者盈亏状态 |
| `cost_vs_quarterly_vwap` | Close / VWAP_Q - 1 | 季内持仓者盈亏状态 |
| `cost_multi_period` | 三者综合 | 多周期成本优势/劣势 |

**Cost Position 状态**：

| 状态 | 条件 | 含义 |
| :--- | :--- | :--- |
| `COST_ADVANTAGE` | 价格 > 月 VWAP 且 > 季 VWAP | 多周期持仓者盈利，趋势健康 |
| `COST_NEUTRAL` | 价格在月 VWAP 附近 | 成本附近，方向选择 |
| `COST_DISADVANTAGE` | 价格 < 月 VWAP 且 < 季 VWAP | 多周期持仓者亏损，上方抛压 |

### 5.3 Chip Stability Confidence（筹码稳定置信度）— 联合指标

> 将**季度真实筹码（A 级）**与 **CBI（B 级代理）**联合推断的综合置信度。

**公式**（权重可配置）：

```
Chip_Stability_Confidence = 
  W_chip × Quarterly_Chip_Score + 
  W_cbi × CBI_Normalized
```

**初始权重**：`W_chip = 60%, W_cbi = 40%`（**待历史回测校准**）

> **工程约束**：权重应设计为可配置参数（`config.chip_confidence_weights`），而非硬编码。

**输出**：

| 置信度 | 触发条件 | 系统输出 |
| :--- | :--- | :--- |
| **High** | Q_Chip↑ + CBI_LOCKED_CANDIDATE | "机构锁仓/筹码高度稳定"（A+B 联合验证） |
| **Medium** | Q_Chip↑ + CBI_STABLE | "结构健康，筹码稳定待确认" |
| **Low** | Q_Chip↓ + 任意 CBI | **强制锁定为**"低流动性/关注度下降"，**严禁输出锁仓结论** |

---

## 六、数据库表结构（最终工程版）

### 6.1 季度结构表：`qcfp_quarterly_structural`

| 字段名 | 类型 | 说明 |
| :--- | :--- | :--- |
| `stock_code` | VARCHAR(20) | 股票代码 |
| `period_end` | DATE | 季度结束日期（如 2026-06-30） |
| **`available_date`** | DATE | **真实数据公开可用日期（来自实际披露日期，非推算）** |
| `inst_ownership_pct_chg` | DECIMAL(10,4) | 机构持股比例变化（%） |
| `holder_quantity_chg_pct` | DECIMAL(10,4) | 股东户数变化（%） |
| `inst_participation_chg` | DECIMAL(10,4) | 机构数量变化（%） |
| `q_inst_flow_raw` | DECIMAL(20,4) | 季度机构净流入（原始值） |
| `q_inst_flow_z` | DECIMAL(10,4) | 季度机构净流入 Z-Score |
| `q_ifa_zscore` | DECIMAL(10,4) | 机构资金优势 Z-Score |
| `q_return` | DECIMAL(10,4) | 季度收益率（%） |
| `q_trend_score` | DECIMAL(10,4) | 季度趋势评分（0~100，**窗口：季末快照**） |
| `q_position_52w` | DECIMAL(10,4) | 52 周位置（0~1，**季末快照**） |
| `c_state` | VARCHAR(10) | C↑ / C→ / C↓ |
| `f_state` | VARCHAR(10) | F↑ / F→ / F↓ |
| `p_state` | VARCHAR(10) | P↑ / P→ / P↓ |
| `structural_regime` | VARCHAR(30) | 6 种季度状态之一 |
| `core_score` | DECIMAL(10,4) | 季度核心评分（0~100） |
| **`model_version`** | VARCHAR(20) | **模型版本号（如 QCFP-MTF-2.1.1）** |
| **`data_quality`** | CHAR(1) | **A/B/C/D 数据质量等级** |

**索引**：`(stock_code, period_end)` **唯一**；`(available_date)`；`(model_version)`

### 6.2 月线行为表：`qcfp_monthly_behavior`

| 字段名 | 类型 | 说明 |
| :--- | :--- | :--- |
| `stock_code` | VARCHAR(20) | 股票代码 |
| `month_end` | DATE | 月份结束日期 |
| `m_turnover_zscore` | DECIMAL(10,4) | 换手率 Z-Score |
| `m_turnover_pctl` | DECIMAL(10,4) | 换手率 52W 分位数（0~1） |
| `m_turnover_ma_ratio` | DECIMAL(10,4) | 换手率 / MA6 |
| `m_volume_ma_ratio` | DECIMAL(10,4) | 成交量 / MA6 |
| `m_volume_accel` | DECIMAL(10,4) | 成交量加速度 |
| `m_vwap_deviation` | DECIMAL(10,4) | 价格 vs 月 VWAP 偏离（%） |
| `m_turnover_efficiency` | DECIMAL(10,4) | 换手效率 |
| `m_vp_regime` | VARCHAR(30) | 量价矩阵状态（9 种） |
| `turnover_liquidity_regime` | VARCHAR(10) | T1~T5 |
| `monthly_behavior_state` | VARCHAR(20) | Improving / Stable / Deteriorating |

### 6.3 周线战术表：`qcfp_weekly_tactical`

| 字段名 | 类型 | 说明 |
| :--- | :--- | :--- |
| `stock_code` | VARCHAR(20) | 股票代码 |
| `week_end` | DATE | 周结束日期 |
| `w_turnover_deviation` | DECIMAL(10,4) | 周换手偏离度（%） |
| `w_turnover_spike` | BOOLEAN | 是否触发极端换手 |
| `w_volume_breakout` | BOOLEAN | 是否触发放量突破 |
| `w_vwap_deviation` | DECIMAL(10,4) | 价格 vs 周 VWAP 偏离（%） |
| `w_ma_slope` | VARCHAR(10) | 均线斜率方向 |
| `w_breakout` | BOOLEAN | 是否有效突破 |
| `w_breakdown` | BOOLEAN | 是否有效破位 |
| `tactical_signal` | VARCHAR(20) | Breakout / Pullback / Consolidation / Breakdown |

### 6.4 整合决策表：`qcfp_mtf_decision`

| 字段名 | 类型 | 说明 |
| :--- | :--- | :--- |
| `stock_code` | VARCHAR(20) | 股票代码 |
| `decision_date` | DATE | 决策日期 |
| `structural_regime` | VARCHAR(30) | 季度状态（继承） |
| `monthly_behavior_state` | VARCHAR(20) | 月线状态（继承） |
| `tactical_signal` | VARCHAR(20) | 周线信号（继承） |
| `cbi_score` | DECIMAL(10,4) | CBI 指数（0~100） |
| `cost_position` | VARCHAR(20) | COST_ADVANTAGE / NEUTRAL / DISADVANTAGE |
| `chip_stability_confidence` | VARCHAR(10) | High / Medium / Low |
| `mtf_regime` | VARCHAR(30) | 5 种 MTF 状态之一 |
| `qcfp_score` | DECIMAL(10,4) | 综合评分（0~100，辅助参考） |
| `action_signal` | VARCHAR(20) | BUY / ADD / HOLD / REDUCE / EXIT / WAIT |
| `risk_level` | VARCHAR(10) | Low / Medium / High / Extreme |
| **`model_version`** | VARCHAR(20) | **模型版本号** |
| **`data_quality`** | CHAR(1) | **A/B/C/D 数据质量等级** |

---

## 七、DSS 输出协议（最终决策格式）

```json
{
  "stock_code": "00700.HK",
  "decision_date": "2026-08-19",
  "model_version": "QCFP-MTF-2.1.1",
  
  "structural": {
    "regime": "STRUCTURAL_BULLISH",
    "core_score": 82,
    "evidence_level": "A",
    "data_quality": "A",
    "key_drivers": ["inst_ownership_pct_chg: +2.3%", "q_inst_flow: +8.7亿"]
  },
  
  "stage": {
    "monthly_state": "Improving",
    "turnover_regime": "T2_LOW",
    "vp_regime": "VP_STABLE_ASCENT",
    "cbi_score": 68
  },
  
  "cost_position": {
    "status": "COST_ADVANTAGE",
    "vs_weekly_vwap": "+1.8%",
    "vs_monthly_vwap": "+3.2%",
    "vs_quarterly_vwap": "+5.1%"
  },
  
  "trigger": {
    "signal": "Consolidation",
    "breakout": false,
    "breakdown": false,
    "volume_spike": false
  },
  
  "confidence": {
    "chip_stability_confidence": "High",
    "structure_behavior_alignment": "Aligned",
    "evidence_summary": "A级季度强势 + B级月线改善 + C级周线盘整"
  },
  
  "risk": {
    "risk_level": "Low",
    "divergence_detected": false,
    "key_risks": ["周线尚未放量突破"],
    "anti_inference_check": "PASSED"
  },
  
  "decision": {
    "mtf_regime": "BULLISH_STABLE",
    "action": "HOLD",
    "action_detail": "季度结构强势，月线行为改善，持仓等待周线突破信号加仓",
    "position_advice": "80%~100%",
    "stop_loss_trigger": "周线放量跌破季VWAP × 0.95"
  }
}
```

---

## 八、版本冻结声明

**QCFP-MTF 2.1.1 已完成全部架构设计，即日起冻结。**

### 8.1 本版本包含的核心模块

- [x] 季度 Structural 引擎（C + F + P，6 状态）
- [x] 月线 Stage 引擎（V + T + P，含 T1~T5 及 9 种 VP 矩阵）
- [x] 周线 Trigger 引擎（V + T + P，4 种信号）
- [x] 两级 FSM：Quarterly Structural FSM + MTF Tactical FSM
- [x] CBI（标准化 + Winsorize，VWAP 已剥离）
- [x] Cost Position 独立模块
- [x] Chip Stability Confidence（权重可配置）
- [x] 5 级证据等级（A/A-/B/C/D）
- [x] 数据质量等级（A/B/C/D）
- [x] 禁止推断表（Anti-Inference Rule）
- [x] `available_date` 防 Look-ahead Bias
- [x] `model_version` 版本追踪
- [x] State-First, Score-Second
- [x] 回测防偏设计

### 8.2 后续迭代规则（硬约束）

**以下内容不再修改**（除非发现重大逻辑缺陷）：

- 总体架构（季度/月线/周线三层）
- 四大铁律
- 证据等级体系
- 两级 FSM 结构
- 数据库表结构（字段可增加，不删减不重命名）
- DSS 输出协议

**以下内容允许通过回测优化**：

- CBI 权重
- Chip Stability Confidence 权重
- 状态转换阈值（Z-Score 阈值、百分位阈值等）
- QCFP Score 映射

> **工程承诺**：所有后续优化必须**基于历史回测数据**驱动参数调整，**不得在无回测验证的情况下修改框架结构**。

---

**规格书结束 — 可进入 P0 工程实现阶段。**


---

# 制定开发计划，初步列出子模块及子路径。
# QCFP-MTF 2.1.1 开发计划

> **版本状态**：🔒 架构已冻结，正式进入 P0 工程实现阶段
> **目标**：将 QCFP-MTF 2.1.1 规格书转化为可运行、可回测、可对接 QS 财富方舟的生产级系统


## 一、项目目录结构

```
qcfp-mtf/
├── config/                          # 全局配置
│   ├── settings.yaml                # 数据库连接、API密钥、日志级别
│   ├── model_version.yaml           # 模型版本号（QCFP-MTF-2.1.1）
│   ├── weights.yaml                 # CBI权重、Chip Stability权重（可配置）
│   └── thresholds.yaml              # 各状态阈值（Z-Score、百分位等）
│
├── data/                            # 数据层
│   ├── raw/                         # L1 Raw（原始数据）
│   │   ├── kline/                   # 日线/周线/月线原始K线
│   │   ├── moneyflow/               # 原始资金流数据
│   │   └── institutional/           # 原始机构持股数据
│   ├── fact/                        # L2 Fact（事实层）
│   │   ├── quarterly_fact/          # 季度事实表
│   │   ├── monthly_fact/            # 月线事实表
│   │   └── weekly_fact/             # 周线事实表
│   ├── factors/                     # L3 Factor（因子层）
│   │   ├── structural_factors/      # 季度结构因子（C/F/P）
│   │   ├── monthly_behavior/        # 月线行为因子
│   │   └── weekly_tactical/         # 周线战术因子
│   ├── states/                      # L4 State（状态层）
│   │   ├── structural_regime/       # 季度6状态
│   │   ├── monthly_state/           # 月线Improving/Stable/Deteriorating
│   │   ├── turnover_liquidity/      # T1~T5
│   │   ├── chip_confidence/         # Chip Stability Confidence
│   │   └── weekly_signal/           # Breakout/Pullback/Consolidation/Breakdown
│   └── decision/                    # L5 Decision（决策层）
│       ├── mtf_alignment/           # MTF最终状态
│       ├── scores/                  # QCFP Score
│       └── dss_output/              # DSS最终输出
│
├── src/                             # 源代码
│   ├── core/                        # 核心引擎
│   │   ├── __init__.py
│   │   ├── data_loader.py           # 数据加载与预处理
│   │   ├── data_quality.py          # 数据质量检测（A/B/C/D）
│   │   └── evidence_level.py        # 证据等级标注（A/A-/B/C/D）
│   │
│   ├── structural/                  # 季度结构引擎（Layer 1）
│   │   ├── __init__.py
│   │   ├── chip_factors.py          # C因子：机构持股、股东户数
│   │   ├── flow_factors.py          # F因子：机构资金流、IFA
│   │   ├── price_factors.py         # P因子：季度收益、Trend Score、52W位置
│   │   ├── structural_regime.py     # 6状态判定（FSM-1）
│   │   └── divergence.py            # CPD/FPD/CFD背离检测
│   │
│   ├── behavioral/                  # 月线行为引擎（Layer 2）
│   │   ├── __init__.py
│   │   ├── turnover_factors.py      # 换手率Z-Score、百分位、T1~T5
│   │   ├── volume_factors.py        # 成交量加速度、量比
│   │   ├── vp_matrix.py             # 量价结构矩阵（9种状态）
│   │   ├── cbi.py                   # CBI（Chip Behavior Index）
│   │   ├── cost_position.py         # Cost Position（VWAP剥离）
│   │   └── monthly_stage.py         # 月线状态：Improving/Stable/Deteriorating
│   │
│   ├── tactical/                    # 周线战术引擎（Layer 3）
│   │   ├── __init__.py
│   │   ├── weekly_volume.py         # 周成交量突破/萎缩检测
│   │   ├── weekly_turnover.py       # 周换手偏离度、极端换手
│   │   ├── weekly_vwap.py           # 周VWAP偏离
│   │   └── weekly_signal.py         # 战术信号：Breakout/Pullback/Consolidation/Breakdown
│   │
│   ├── fusion/                      # 多周期融合（Layer 4）
│   │   ├── __init__.py
│   │   ├── chip_confidence.py       # Chip Stability Confidence（60/40可配置）
│   │   ├── mtf_alignment.py         # 多周期对齐协调器
│   │   ├── mtf_fsm.py               # MTF Tactical FSM（5状态）
│   │   └── anti_inference.py        # 禁止推断表过滤器
│   │
│   ├── decision/                    # DSS决策层（Layer 5）
│   │   ├── __init__.py
│   │   ├── score_calculator.py      # QCFP Score（State-First映射）
│   │   ├── action_generator.py      # Action：BUY/ADD/HOLD/REDUCE/EXIT/WAIT
│   │   ├── risk_evaluator.py        # Risk Level：Low/Medium/High/Extreme
│   │   └── dss_output.py            # 最终JSON输出
│   │
│   ├── backtest/                    # 回测模块
│   │   ├── __init__.py
│   │   ├── engine.py                # 回测引擎
│   │   ├── lookahead_filter.py      # available_date防偏过滤器
│   │   ├── performance.py           # 绩效评估（夏普、最大回撤、胜率）
│   │   └── calibration.py           # 参数校准（权重、阈值优化）
│   │
│   └── utils/                       # 工具函数
│       ├── __init__.py
│       ├── database.py              # 数据库连接与ORM
│       ├── logger.py                # 日志系统
│       ├── normalization.py         # Winsorize + Z-Score标准化
│       └── calendar.py              # 港股交易日历
│
├── tests/                           # 单元测试
│   ├── test_structural/
│   ├── test_behavioral/
│   ├── test_tactical/
│   ├── test_fusion/
│   └── test_backtest/
│
├── scripts/                         # 运维脚本
│   ├── fetch_data.py                # 数据采集脚本
│   ├── run_pipeline.py              # 全流程运行脚本
│   ├── generate_report.py           # 报告生成脚本
│   └── backtest_runner.py           # 回测运行脚本
│
├── reports/                         # 输出报告
│   ├── individual/                  # 个股QCFP报告
│   └── backtest/                    # 回测报告
│
├── docs/                            # 文档
│   ├── QCFP-MTF-2.1.1_Spec.md       # 架构规格书
│   ├── API_Reference.md             # API文档
│   └── User_Guide.md                # 使用指南
│
├── requirements.txt                 # Python依赖
├── setup.py                         # 安装脚本
├── docker-compose.yml               # Docker编排（数据库+应用）
└── README.md                        # 项目说明
```


## 二、子模块清单与依赖关系

### 2.1 模块依赖图（自上而下）

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                        Layer 5: DSS 决策层                                 │
│  decision/ ──► 依赖 fusion/ + structural/ + behavioral/ + tactical/        │
└─────────────────────────────────────────────────────────────────────────────┘
                                      ↑
┌─────────────────────────────────────────────────────────────────────────────┐
│                        Layer 4: 多周期融合层                               │
│  fusion/ ──► 依赖 structural/ + behavioral/ + tactical/                    │
└─────────────────────────────────────────────────────────────────────────────┘
                                      ↑
┌─────────────────────────────────────────────────────────────────────────────┐
│               Layer 2+3: 行为引擎 + 战术引擎（可并行）                      │
│  behavioral/ ──► 依赖 core/data_loader                                    │
│  tactical/   ──► 依赖 core/data_loader                                    │
└─────────────────────────────────────────────────────────────────────────────┘
                                      ↑
┌─────────────────────────────────────────────────────────────────────────────┐
│                        Layer 1: 季度结构引擎                                │
│  structural/ ──► 依赖 core/data_loader + core/evidence_level              │
└─────────────────────────────────────────────────────────────────────────────┘
                                      ↑
┌─────────────────────────────────────────────────────────────────────────────┐
│                         Core: 基础设施层                                   │
│  core/ ──► 无外部依赖（仅标准库 + pandas/numpy）                           │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 2.2 各模块详细说明

| 模块 | 路径 | 核心职责 | 输入 | 输出 | 预计工时 |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **数据加载** | `core/data_loader.py` | 从数据库/文件加载原始数据，处理 missing data | 股票代码、日期范围 | DataFrame（标准化格式） | 2天 |
| **数据质量** | `core/data_quality.py` | 检测数据完整性，输出 A/B/C/D 等级 | DataFrame | data_quality 标签 | 1天 |
| **证据等级** | `core/evidence_level.py` | 为每个因子标注 A/A-/B/C/D | 因子值 + 元数据 | 证据等级标签 | 1天 |
| **C因子** | `structural/chip_factors.py` | 机构持股变化、股东户数变化、机构数量变化 | 季度机构持仓数据 | c_state (↑/→/↓) | 2天 |
| **F因子** | `structural/flow_factors.py` | 机构资金流、IFA Z-Score | 季度资金流数据 | f_state (↑/→/↓) | 2天 |
| **P因子** | `structural/price_factors.py` | 季度收益、Trend Score、52W位置 | 季度K线 | p_state (↑/→/↓) | 2天 |
| **结构状态机** | `structural/structural_regime.py` | FSM-1：6状态判定 | C/F/P状态 | Structural_Regime | 2天 |
| **背离检测** | `structural/divergence.py` | CPD/FPD/CFD 计算 | C/F/P Z-Score | 背离信号 | 1天 |
| **换手因子** | `behavioral/turnover_factors.py` | 换手率Z-Score、百分位、T1~T5 | 月线换手率 | Turnover_Liquidity_Regime | 2天 |
| **量价矩阵** | `behavioral/vp_matrix.py` | 9种量价状态判定 | 月线 P/V/T | VP_Regime | 1.5天 |
| **CBI** | `behavioral/cbi.py` | CBI计算（Winsorize→标准化→加权） | 月线 V/T/P | CBI_Score (0~100) | 2天 |
| **Cost Position** | `behavioral/cost_position.py` | 多周期VWAP偏离 | 周/月/季VWAP | COST_ADVANTAGE/NEUTRAL/DISADVANTAGE | 1.5天 |
| **月线状态** | `behavioral/monthly_stage.py` | Improving/Stable/Deteriorating | VP_Regime + T状态 | Monthly_Stage | 1天 |
| **周线信号** | `tactical/weekly_signal.py` | Breakout/Pullback/Consolidation/Breakdown | 周线 V/T/P | Tactical_Signal | 2天 |
| **筹码置信度** | `fusion/chip_confidence.py` | Chip Stability Confidence（60/40可配置） | Q_Chip + CBI | High/Medium/Low | 1.5天 |
| **多周期对齐** | `fusion/mtf_alignment.py` | 结构+阶段+触发 → MTF状态 | Structural_Regime + Monthly_Stage + Tactical_Signal | MTF_Regime（5种） | 2天 |
| **MTF FSM** | `fusion/mtf_fsm.py` | FSM-2：状态转换引擎 | 当前MTF状态 + 事件 | 下一MTF状态 | 2天 |
| **禁止推断** | `fusion/anti_inference.py` | 扫描并过滤禁止推断 | 原始文本/结论 | 过滤后结论 | 1天 |
| **评分** | `decision/score_calculator.py` | State-First 评分映射 | MTF_Regime | QCFP_Score | 1天 |
| **Action生成** | `decision/action_generator.py` | BUY/ADD/HOLD/REDUCE/EXIT/WAIT | MTF_Regime + Risk | Action | 1天 |
| **风险评估** | `decision/risk_evaluator.py` | Low/Medium/High/Extreme | 背离信号 + 状态 | Risk_Level | 1天 |
| **DSS输出** | `decision/dss_output.py` | 最终JSON格式输出 | 所有状态 | DSS JSON | 1.5天 |
| **回测引擎** | `backtest/engine.py` | 历史回测主流程 | 历史数据 + 策略 | 交易记录 | 3天 |
| **防偏过滤** | `backtest/lookahead_filter.py` | available_date 过滤 | 原始数据 | 过滤后数据 | 1天 |
| **参数校准** | `backtest/calibration.py` | 权重/阈值优化 | 回测结果 | 最优参数 | 3天 |


## 三、分阶段开发计划

### Phase 0：基础设施（Week 1-2）

| # | 任务 | 子模块 | 产出 | 验收标准 |
| :--- | :--- | :--- | :--- | :--- |
| 0.1 | 项目初始化 | 目录结构 + `requirements.txt` | 可运行的Python项目骨架 | `pytest` 可通过 |
| 0.2 | 数据库设计与建表 | SQL脚本 + ORM模型 | 5张核心表（见规格书第六章） | 表结构符合规格书 |
| 0.3 | 数据加载器 | `core/data_loader.py` | 从CSV/数据库加载数据的统一接口 | 可加载港股日线/月线/季线 |
| 0.4 | 数据质量检测 | `core/data_quality.py` | A/B/C/D 等级输出 | 对缺失数据能正确分级 |
| 0.5 | 证据等级标注 | `core/evidence_level.py` | 因子→证据等级映射 | 映射表完整 |

**里程碑 M1**：数据基础设施就绪，可加载并质检任意港股数据 ✅

---

### Phase 1：季度结构引擎（Week 3-4）

| # | 任务 | 子模块 | 产出 | 验收标准 |
| :--- | :--- | :--- | :--- | :--- |
| 1.1 | C因子计算 | `structural/chip_factors.py` | `c_state` (↑/→/↓) | 与规格书阈值一致 |
| 1.2 | F因子计算 | `structural/flow_factors.py` | `f_state` (↑/→/↓) | 与规格书阈值一致 |
| 1.3 | P因子计算 | `structural/price_factors.py` | `p_state` (↑/→/↓) | 与规格书阈值一致 |
| 1.4 | 结构状态机（FSM-1） | `structural/structural_regime.py` | 6种Structural Regime | 转换规则与规格书3.1一致 |
| 1.5 | 背离检测 | `structural/divergence.py` | CPD/FPD/CFD | Z-Score计算正确 |
| 1.6 | 单元测试 | `tests/test_structural/` | 测试覆盖率 > 80% | 所有测试通过 |

**里程碑 M2**：季度结构引擎完成，可对任意港股输出6种Structural Regime + 背离信号 ✅

---

### Phase 2：月线行为引擎（Week 5-6）

| # | 任务 | 子模块 | 产出 | 验收标准 |
| :--- | :--- | :--- | :--- | :--- |
| 2.1 | 换手因子 | `behavioral/turnover_factors.py` | T1~T5 状态 | Z-Score + 百分位双条件 |
| 2.2 | 成交量因子 | `behavioral/volume_factors.py` | 成交量加速度、量比 | 计算正确 |
| 2.3 | 量价矩阵 | `behavioral/vp_matrix.py` | 9种VP_Regime | 覆盖所有9种状态 |
| 2.4 | CBI计算 | `behavioral/cbi.py` | CBI_Score (0~100) | Winsorize→标准化→加权流程正确 |
| 2.5 | Cost Position | `behavioral/cost_position.py` | 多周期成本位置 | 周/月/季VWAP偏离正确 |
| 2.6 | 月线状态 | `behavioral/monthly_stage.py` | Improving/Stable/Deteriorating | 与规格书4.3一致 |
| 2.7 | 单元测试 | `tests/test_behavioral/` | 测试覆盖率 > 80% | 所有测试通过 |

**里程碑 M3**：月线行为引擎完成，可输出CBI、Cost Position、Monthly Stage ✅

---

### Phase 3：周线战术引擎（Week 7）

| # | 任务 | 子模块 | 产出 | 验收标准 |
| :--- | :--- | :--- | :--- | :--- |
| 3.1 | 周成交量检测 | `tactical/weekly_volume.py` | 放量/缩量标记 | 阈值与规格书5.1一致 |
| 3.2 | 周换手检测 | `tactical/weekly_turnover.py` | 换手偏离度、极端换手标记 | 计算正确 |
| 3.3 | 周VWAP | `tactical/weekly_vwap.py` | 周VWAP偏离 | 计算正确 |
| 3.4 | 战术信号 | `tactical/weekly_signal.py` | Breakout/Pullback/Consolidation/Breakdown | 与规格书6.2一致 |
| 3.5 | 单元测试 | `tests/test_tactical/` | 测试覆盖率 > 80% | 所有测试通过 |

**里程碑 M4**：周线战术引擎完成，可输出4种Tactical Signal ✅

---

### Phase 4：多周期融合层（Week 8-9）

| # | 任务 | 子模块 | 产出 | 验收标准 |
| :--- | :--- | :--- | :--- | :--- |
| 4.1 | Chip Stability Confidence | `fusion/chip_confidence.py` | High/Medium/Low | 60/40权重可配置 |
| 4.2 | 多周期对齐 | `fusion/mtf_alignment.py` | 5种MTF_Regime | 映射矩阵与规格书3.2一致 |
| 4.3 | MTF FSM（FSM-2） | `fusion/mtf_fsm.py` | State(t)+Event(t)→State(t+1) | 转换规则完整 |
| 4.4 | 禁止推断过滤器 | `fusion/anti_inference.py` | 过滤后结论 | 与规格书2.3一致 |
| 4.5 | 集成测试 | `tests/test_fusion/` | 端到端状态流转 | 所有测试通过 |

**里程碑 M5**：多周期融合层完成，可输出最终MTF_Regime + Chip Stability Confidence ✅

---

### Phase 5：DSS决策层（Week 10）

| # | 任务 | 子模块 | 产出 | 验收标准 |
| :--- | :--- | :--- | :--- | :--- |
| 5.1 | 评分计算器 | `decision/score_calculator.py` | QCFP_Score | State-First映射正确 |
| 5.2 | Action生成器 | `decision/action_generator.py` | BUY/ADD/HOLD/REDUCE/EXIT/WAIT | 与Regime映射一致 |
| 5.3 | 风险评估 | `decision/risk_evaluator.py` | Low/Medium/High/Extreme | 综合背离+状态 |
| 5.4 | DSS输出 | `decision/dss_output.py` | 完整JSON报告 | 与规格书第七章一致 |
| 5.5 | 端到端测试 | `tests/` | 完整流程 | 从数据输入到DSS输出全流程通过 |

**里程碑 M6**：DSS决策层完成，可生成完整的个股QCFP分析报告 ✅

---

### Phase 6：回测系统（Week 11-13）

| # | 任务 | 子模块 | 产出 | 验收标准 |
| :--- | :--- | :--- | :--- | :--- |
| 6.1 | 防偏过滤器 | `backtest/lookahead_filter.py` | available_date过滤 | 杜绝Look-ahead Bias |
| 6.2 | 回测引擎 | `backtest/engine.py` | 历史回测主流程 | 可回测任意历史区间 |
| 6.3 | 绩效评估 | `backtest/performance.py` | 夏普、最大回撤、胜率、年化收益 | 指标计算正确 |
| 6.4 | 参数校准 | `backtest/calibration.py` | CBI权重、阈值优化 | 基于历史数据寻优 |
| 6.5 | 回测报告 | `reports/backtest/` | 可视化回测报告 | 含收益曲线、状态分布 |

**里程碑 M7**：回测系统完成，可验证QCFP-MTF策略的历史表现 ✅


## 四、技术栈建议

| 层级 | 技术选型 | 说明 |
| :--- | :--- | :--- |
| **语言** | Python 3.10+ | 主力开发语言 |
| **数据处理** | Pandas + NumPy | 数据清洗、因子计算 |
| **数据库** | PostgreSQL + SQLAlchemy | 关系型数据存储 |
| **数据获取** | AKShare + Longbridge API | 港股K线、机构持仓、资金流 |
| **回测** | VectorBT 或 Backtrader | 回测引擎 |
| **可视化** | Matplotlib + Plotly | 报告图表 |
| **配置管理** | PyYAML | 配置文件解析 |
| **日志** | Loguru | 结构化日志 |
| **测试** | Pytest + Coverage | 单元测试与覆盖率 |
| **依赖管理** | Poetry 或 pip + requirements.txt | 包管理 |
| **容器化** | Docker + Docker Compose | 环境隔离与部署 |


## 五、数据获取方案

### 5.1 数据源清单

| 数据类型 | 推荐数据源 | 频率 | 说明 |
| :--- | :--- | :--- | :--- |
| **港股日线/周线/月线K线** | AKShare / yfinance | 日频 | OHLCV完整 |
| **港股资金流** | AKShare | 日频/月频 | 机构/散户/大单/小单 |
| **机构持股（季度）** | Longbridge API `fund_holdings` | 季度 | 机构及基金持仓 |
| **股东户数** | AKShare `stock_hk_holder` | 季度 | 股东户数变化 |
| **经纪商持仓（CCASS）** | Longbridge API `broker_positions` | 日频 | 港股中央结算系统持仓 |
| **沪深港通持股** | AKShare 插件 | 日频 | 外资持仓代理 |

### 5.2 数据采集脚本

```python
# scripts/fetch_data.py 核心接口示例
from src.core.data_loader import DataLoader

# 采集某只港股的全部数据
loader = DataLoader(stock_code="00700.HK")
loader.fetch_kline(period="daily", start="2020-01-01")
loader.fetch_kline(period="weekly")
loader.fetch_kline(period="monthly")
loader.fetch_institutional_holdings()  # 季度
loader.fetch_moneyflow()               # 月频
loader.save_to_database()
```


## 六、关键风险与应对

| 风险 | 影响 | 应对措施 |
| :--- | :--- | :--- |
| **数据源不稳定** | 数据采集失败 | 多数据源备份（AKShare + Longbridge + yfinance） |
| **Look-ahead Bias** | 回测结果失真 | 所有回测强制使用 `available_date` 过滤 |
| **港股数据覆盖率不足** | 部分股票缺失机构持股 | 对缺失数据标注 `data_quality=C/D`，降级处理 |
| **CBI权重未经验证** | 置信度判断偏差 | 权重设计为可配置，通过回测校准 |
| **状态机状态爆炸** | 维护困难 | 两级FSM分离，状态数控制在 6+5=11 种 |


## 七、工时汇总

| Phase | 内容 | 工时（人天） |
| :--- | :--- | :--- |
| Phase 0 | 基础设施 | 7 |
| Phase 1 | 季度结构引擎 | 9 |
| Phase 2 | 月线行为引擎 | 9 |
| Phase 3 | 周线战术引擎 | 5 |
| Phase 4 | 多周期融合层 | 7 |
| Phase 5 | DSS决策层 | 5 |
| Phase 6 | 回测系统 | 9 |
| **合计** | | **51 人天（约 2.5 个月，1人全职）** |


## 八、下一步行动

1. **立即启动 Phase 0**：创建项目目录结构、初始化 Git 仓库、配置开发环境
2. **并行进行数据调研**：确认 AKShare + Longbridge API 对所需港股数据的覆盖情况
3. **Week 1 结束前**：完成数据库建表脚本 + 数据加载器原型

> **开发原则**：每个 Phase 完成后必须通过单元测试 + 集成测试，方可进入下一 Phase。所有参数阈值（Z-Score、百分位等）暂用规格书默认值，待 Phase 6 回测校准后统一调整。

---
# 列举P0~P6各开发阶段主要任务。
# QCFP-MTF 2.1.1 开发阶段任务清单（P0 ~ P6）

基于已冻结的架构规格书，将全部工程任务划分为 **7 个开发阶段（P0 ~ P6）** 。**P6 为本次新增阶段**，重点覆盖回测验证与参数校准的完整闭环。建议严格按顺序推进，每个阶段完成后必须通过单元测试与集成测试，方可进入下一阶段。


## P0：基础设施与数据层（Week 1-2）

> **目标**：建立项目骨架、数据底座和基础工具链，确保后续所有引擎可以“即插即用”。

| # | 核心任务 | 子模块/路径 | 关键产出 |
| :--- | :--- | :--- | :--- |
| 1 | **项目初始化** | 根目录 | 完成目录结构创建、Git 仓库初始化、`requirements.txt` / `setup.py` 配置 |
| 2 | **数据库设计与建表** | `config/settings.yaml` + SQL 脚本 | 5 张核心表（`qcfp_quarterly_structural`、`qcfp_monthly_behavior`、`qcfp_weekly_tactical`、`qcfp_mtf_decision`、`qcfp_backtest_results`）及索引 |
| 3 | **配置管理模块** | `config/` | 加载 YAML 配置（模型版本 `2.1.1`、CBI 权重、状态阈值、数据库连接） |
| 4 | **数据加载器** | `src/core/data_loader.py` | 统一数据接口：支持从 PostgreSQL / CSV / AKShare 加载日/周/月 K 线、机构持股、资金流 |
| 5 | **数据质量检测** | `src/core/data_quality.py` | 输出 `data_quality` 标签（A/B/C/D），检测缺失率与异常值 |
| 6 | **证据等级标注** | `src/core/evidence_level.py` | 为每个因子字段标注 A/A-/B/C/D（建立静态映射表 + 动态判定逻辑） |
| 7 | **港股交易日历工具** | `src/utils/calendar.py` | 生成港股交易日序列，用于自然周/月/季的切分对齐 |
| 8 | **日志系统** | `src/utils/logger.py` | 结构化日志（Loguru），支持分级输出与审计追踪 |

**里程碑 M0**：`SELECT * FROM qcfp_quarterly_structural LIMIT 1` 可正常返回结构化数据；任意股票的数据质量标签可自动生成。✅


## P1：季度结构引擎（Week 3-4）

> **目标**：复现并冻结原 QCFP 核心逻辑，完成 **A/A- 级证据**（真实筹码+资金+季度价格）的计算与状态机（FSM-1）。

| # | 核心任务 | 子模块/路径 | 关键产出 |
| :--- | :--- | :--- | :--- |
| 1 | **C 因子（筹码）** | `src/structural/chip_factors.py` | 计算 `inst_ownership_pct_chg`、`holder_quantity_chg_pct`、`inst_participation_chg`，输出 `c_state`（↑/→/↓） |
| 2 | **F 因子（资金）** | `src/structural/flow_factors.py` | 聚合季度机构净流入、计算 `IFA_ZScore`，输出 `f_state`（↑/→/↓） |
| 3 | **P 因子（价格）** | `src/structural/price_factors.py` | 计算季度收益、`Trend_Score`（窗口：季末快照）、`52W_Position`，输出 `p_state`（↑/→/↓） |
| 4 | **季度结构状态机（FSM-1）** | `src/structural/structural_regime.py` | 将 C/F/P 状态映射为 6 种 Structural Regime（`STRUCTURAL_BULLISH`、`ACCUMULATION`、`DIVERGENCE`、`DISTRIBUTION`、`DECLINE`、`BOTTOM_CANDIDATE`） |
| 5 | **三维背离检测** | `src/structural/divergence.py` | 计算 `CPD`、`FPD`、`CFD` 的 Z-Score 偏离值，输出背离预警信号 |
| 6 | **季度评分（Core Score）** | `src/structural/structural_regime.py` | 基于状态机映射基础分（0~100），作为后续评分的锚点 |
| 7 | **单元测试** | `tests/test_structural/` | 覆盖全部因子计算和状态转换逻辑，覆盖率 ≥ 80% |

**里程碑 M1**：输入任意港股历史季报数据，可稳定输出 `structural_regime` + `core_score` + 背离信号。✅


## P2：月线行为引擎（Week 5-6）

> **目标**：构建 **B 级证据**（量价—换手行为代理），完成 CBI 指数、Cost Position 和月线 Stage 判定。

| # | 核心任务 | 子模块/路径 | 关键产出 |
| :--- | :--- | :--- | :--- |
| 1 | **换手率因子** | `src/behavioral/turnover_factors.py` | 计算月换手率 Z-Score、52W 百分位、MA6 比值，输出 T1~T5（换手—流动性状态） |
| 2 | **成交量因子** | `src/behavioral/volume_factors.py` | 计算成交量加速度（`VE_t / VE_{t-3} - 1`）和量比（`Vol / MA6`） |
| 3 | **量价结构矩阵** | `src/behavioral/vp_matrix.py` | 依据 P/V/T 三态组合，输出 9 种 VP_Regime（含 `VP_STABLE_ASCENT`） |
| 4 | **CBI（筹码行为指数）** | `src/behavioral/cbi.py` | **严格按 Winsorize(1%~99%) → Z-Score 标准化 → 0~100 缩放 → 加权** 流程计算 CBI |
| 5 | **Cost Position（成本位置）** | `src/behavioral/cost_position.py` | 计算价格 vs 周/月/季 VWAP 偏离度，输出 `COST_ADVANTAGE` / `NEUTRAL` / `DISADVANTAGE` |
| 6 | **月线阶段判定** | `src/behavioral/monthly_stage.py` | 融合 VP_Regime + T 状态，输出 `Improving` / `Stable` / `Deteriorating` |
| 7 | **单元测试** | `tests/test_behavioral/` | 验证 CBI 标准化流程、VWAP 剥离逻辑、Stage 判定规则 |

**里程碑 M2**：输入月线数据，可稳定输出 `CBI_Score`、`Cost_Position`、`Monthly_Stage` 三组核心字段。✅


## P3：周线战术引擎（Week 7）

> **目标**：构建 **C 级证据**（短周期交易信号），完成战术触发判定（Timing）。

| # | 核心任务 | 子模块/路径 | 关键产出 |
| :--- | :--- | :--- | :--- |
| 1 | **周成交量检测** | `src/tactical/weekly_volume.py` | 标记放量突破（`Volume > MA20 × 1.8`）与极度缩量（`Volume < MA20 × 0.5`） |
| 2 | **周换手检测** | `src/tactical/weekly_turnover.py` | 计算周换手偏离度（vs 季度周均）及极端换手标记（`> MA8 × 2.0`） |
| 3 | **周 VWAP 偏离** | `src/tactical/weekly_vwap.py` | 计算收盘价与周 VWAP 偏离百分比 |
| 4 | **短期均线结构** | `src/tactical/weekly_signal.py` | 计算 5/10/20 周均线斜率（二阶差分），判断加速/减速 |
| 5 | **战术信号合成** | `src/tactical/weekly_signal.py` | 综合以上因子，输出 `Breakout` / `Pullback` / `Consolidation` / `Breakdown` |
| 6 | **单元测试** | `tests/test_tactical/` | 验证突破/破位阈值、信号合成逻辑，防止误触发 |

**里程碑 M3**：输入周线数据，可稳定输出 `tactical_signal`（4 种状态）及关键触发条件（`w_breakout` / `w_breakdown`）。✅


## P4：多周期融合层（Week 8-9）

> **目标**：连接季度/月线/周线，完成 **Chip Stability Confidence**、**MTF FSM（FSM-2）** 及 **禁止推断过滤**。

| # | 核心任务 | 子模块/路径 | 关键产出 |
| :--- | :--- | :--- | :--- |
| 1 | **筹码稳定置信度** | `src/fusion/chip_confidence.py` | 按 `60% × Quarterly_Chip_Score + 40% × CBI_Normalized`（**权重可配置**）计算 High/Medium/Low |
| 2 | **多周期对齐协调器** | `src/fusion/mtf_alignment.py` | 将 `Structural_Regime` + `Monthly_Stage` + `Tactical_Signal` 映射为 5 种 MTF 状态（`BULLISH_CONFIRMED`、`BULLISH_STABLE`、`BULLISH_WARNING`、`BEARISH_RECOVERY_CANDIDATE`、`BEARISH_CONFIRMED`） |
| 3 | **MTF 战术状态机（FSM-2）** | `src/fusion/mtf_fsm.py` | 实现 `State(t) + Event(t) → State(t+1)`，输入当前 MTF 状态和最新事件，输出下一状态 |
| 4 | **禁止推断过滤器** | `src/fusion/anti_inference.py` | **核心风控模块**：扫描 DSS 生成结论，若触碰“禁止推断表”（如“低换手→机构锁仓”），强制降级为允许表述 |
| 5 | **结构—行为背离检测** | `src/fusion/mtf_alignment.py` | 新增检测：季度强势 + 月线恶化 或 季度弱势 + 月线改善，输出“结构—行为背离”标记 |
| 6 | **集成测试** | `tests/test_fusion/` | 端到端验证 3 层输入 → MTF Regime → 置信度 → 防推断过滤的全链路 |

**里程碑 M4**：输入任意日期的三周期数据，可输出 `mtf_regime`、`chip_stability_confidence` 并通过“禁止推断”检查。✅


## P5：DSS 决策层（Week 10）

> **目标**：生成最终投资决策输出，完成从原始数据到标准化 JSON 报告的全链路。

| # | 核心任务 | 子模块/路径 | 关键产出 |
| :--- | :--- | :--- | :--- |
| 1 | **评分计算器（State-First）** | `src/decision/score_calculator.py` | 基于 MTF Regime 映射 QCFP_Score（0~100，**评分是状态的附属结果，非决策源头**） |
| 2 | **Action 生成器** | `src/decision/action_generator.py` | 输出 `BUY` / `ADD` / `HOLD` / `REDUCE` / `EXIT` / `WAIT`，受 Risk Level 约束 |
| 3 | **风险评估器** | `src/decision/risk_evaluator.py` | 综合背离信号、状态机位置、数据质量，输出 `Low` / `Medium` / `High` / `Extreme` |
| 4 | **DSS 输出格式化** | `src/decision/dss_output.py` | 生成标准 JSON 报告（含规格书全部字段：结构/阶段/触发/置信度/风险/行动） |
| 5 | **个股报告生成器** | `scripts/generate_report.py` | 将 JSON 渲染为可读的 Markdown/HTML 报告 |
| 6 | **端到端集成测试** | `tests/` | 从数据输入到 DSS 输出全流程通过 |

**里程碑 M5**：输入任意股票代码和日期，可生成完整的 QCFP 个股分析报告（JSON + 可读格式）。✅


## P6：回测与校准系统（Week 11-13）

> **目标**：通过历史回测验证系统有效性，完成参数校准闭环，确保策略在真实市场环境中可验证、可复现。

| # | 核心任务 | 子模块/路径 | 关键产出 |
| :--- | :--- | :--- | :--- |
| **回测基础设施（Week 11）** | | | |
| 1 | **防 Look-ahead 过滤器** | `src/backtest/lookahead_filter.py` | **强制约束**：所有历史回测必须使用 `available_date`（真实披露日期），严禁使用 `period_end` |
| 2 | **回测数据管道** | `src/backtest/data_pipeline.py` | 按 `available_date` 时序切片，逐日生成 QCFP 信号，确保无未来数据泄漏 |
| 3 | **回测引擎选型与集成** | `src/backtest/engine.py` | 基于 **VectorBT**（向量化回测，速度 100–1000x 优于事件驱动框架）或 Backtrader 构建 |
| 4 | **交易成本模型** | `src/backtest/cost_model.py` | 包含佣金、滑点、印花税（港股费率） |
| **策略验证（Week 12）** | | | |
| 5 | **策略执行器** | `src/backtest/strategy.py` | 将 QCFP Action 信号（BUY/ADD/HOLD/REDUCE/EXIT）转化为交易指令 |
| 6 | **绩效评估** | `src/backtest/performance.py` | 输出年化收益、夏普比率、最大回撤、胜率、盈亏比、收益曲线、分年度绩效 |
| 7 | **时间序列交叉验证** | `src/backtest/cross_validation.py` | 采用 **扩展窗口（Expanding Window）** 法，避免全历史单次回测过拟合 |
| **参数校准（Week 13）** | | | |
| 8 | **参数校准模块** | `src/backtest/calibration.py` | 对 CBI 权重、Chip Stability 权重、Z-Score 阈值进行**网格搜索**或**贝叶斯优化**，寻优后回写 `config/weights.yaml` |
| 9 | **稳健性测试** | `src/backtest/robustness.py` | 对不同市场环境（牛市/熊市/震荡市）分别回测，验证策略稳健性 |
| 10 | **回测报告生成** | `reports/backtest/` | 生成可视化回测报告（含收益曲线、状态分布、分年度绩效、参数敏感性分析） |
| 11 | **文档与交付** | `docs/` + `README.md` | 更新 API 文档、用户手册、回测验证报告 |

**里程碑 M6**：系统可对任意历史区间完成无偏回测，生成完整的回测报告，并通过校准模块输出优化后的参数组合。🎉


## 阶段依赖与并行策略

```
P0（基础设施）
 │
 ├──▶ P1（季度结构）─────────────────┐
 │                                   │
 ├──▶ P2（月线行为）─────────────────┼──▶ P4（多周期融合）──▶ P5（DSS）──▶ P6（回测+校准）
 │                                   │
 └──▶ P3（周线战术）─────────────────┘
```

- **P0 是唯一前置依赖**，必须最先完成。
- **P1、P2、P3 可并行开发**（分配不同人员，或顺序开发但互不阻塞），三者的输入数据源相互独立。
- **P4 必须等待 P1/P2/P3 全部完成**，因为 MTF 对齐需要三层输入。
- **P5 依赖 P4**，DSS 输出需要完整的 MTF 状态。
- **P6 必须最后进行**，且回测子阶段在 DSS 输出稳定后启动。


## 各阶段工时汇总

| Phase | 内容 | 工时（人天） |
| :--- | :--- | :--- |
| P0 | 基础设施与数据层 | 7 |
| P1 | 季度结构引擎 | 9 |
| P2 | 月线行为引擎 | 9 |
| P3 | 周线战术引擎 | 5 |
| P4 | 多周期融合层 | 7 |
| P5 | DSS 决策层 | 5 |
| P6 | 回测与校准系统 | 12 |
| **合计** | | **54 人天（约 2.5~3 个月，1人全职）** |


## 关键风险节点提示

| 阶段 | 关键风险 | 检查点 |
| :--- | :--- | :--- |
| **P0** | 港股数据源（机构持股、资金流）可用性不稳定 | 提前确认 AKShare / Longbridge API 覆盖范围，准备 CSV 备份数据 |
| **P1** | Trend Score 计算窗口定义模糊（季度快照 vs 滚动窗口） | 严格采用“季末快照”定义，并在因子表注释中明确 `window=end_of_quarter` |
| **P2** | CBI 跨股票不可比（量纲问题） | 强制执行 Winsorize → Z-Score 标准化流程，编写单元测试验证 |
| **P4** | “禁止推断表”过于严格导致报告空洞 | 初始版本采用“警告+降级”模式，不直接阻断输出，积累案例后迭代规则 |
| **P5** | DSS 输出与 QS 财富方舟接口不兼容 | 提前对齐接口协议，采用 JSON 标准格式输出 |
| **P6** | 回测过拟合（参数调优后失效） | 采用**时间序列交叉验证**（扩展窗口法），避免使用全历史单次回测优化 |
| **P6** | Look-ahead Bias 未被彻底清除 | 所有回测数据切片强制使用 `available_date`，编写自动化检测脚本验证 |


## 开发原则

1. **测试驱动**：每个 Phase 完成后必须通过单元测试 + 集成测试，方可进入下一 Phase
2. **配置驱动**：所有参数阈值（Z-Score、百分位等）和权重（CBI、Chip Stability）存放在 `config/` 目录，便于后续校准
3. **版本追踪**：所有核心结果表必须包含 `model_version` 字段，确保历史结果可复现
4. **防偏优先**：任何涉及历史数据的计算必须经过 `available_date` 过滤，杜绝 Look-ahead Bias
5. **文档同步**：代码变更必须同步更新 API 文档和用户手册

---
