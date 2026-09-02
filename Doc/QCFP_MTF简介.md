# 简要说明QCFP_MTF系统的功能。
### QCFP_MTF 系统功能简述

QCFP_MTF 是一个 **“机构行为状态过滤器 + 散户波段交易决策系统”**。

核心功能可以概括为：

1. **机构行为识别**

   * 从 Structural / Behavioral / Tactical 等多时间尺度判断股票所处状态。
   * 判断当前环境是否允许参与交易。

2. **机构风险过滤**

   * 通过 Permission、Risk Gate、Participation Budget 等机制限制风险。
   * 上层机构权限对下层交易决策形成**硬约束，不能越权**。

3. **牛散波段识别**

   * 通过 Wave、Setup、Trigger 和 Swing FSM 识别波段机会。
   * 支持 `TEST → BUILD → HOLD → REDUCE → EXIT` 的动态交易过程。

4. **仓位与风险管理**

   * 根据机会质量、机构权限、风险状态和资金预算计算最终仓位。
   * Hard Exit、Risk Cap 等规则可以强制降低或清零仓位。

5. **统一决策与审计**

   * 所有最终决策由统一 Decision Engine 产生。
   * Decision Snapshot / Certificate / Ledger 保存完整决策链，可以追溯“为什么买、为什么卖、为什么这个仓位”。

6. **回测与研究验证**

   * 支持 PIT、OOS、Walk-forward、交易成本等研究框架。
   * 可以评估收益、回撤、波段捕获率、MFE/MAE、进入延迟等。

7. **Ablation 实验**

   * 可以关闭 Permission、Wave、Daily、Risk、Budget 等模块，比较各模块的独立贡献。
   * 用于判断哪些模块真正有效，避免“复杂但无增益”。

### 一句话

> **QCFP_MTF 不是单纯预测股票涨跌，而是先判断“机构环境允不允许做”，再判断“有没有值得做的牛散波段”，最后在权限、风险和资金约束下决定“做不做、做多少、什么时候退出”，并让整个过程可审计、可回测、可 Ablation。**


---

# 简要说明系统的目标
### 系统目标

QCFP_MTF 的核心目标是：

> **构建一个“机构行为状态过滤器 + 散户波段交易决策系统”，在严格风险约束下提高牛散波段交易的实战参考价值。**

具体实现五个目标：

1. **不可越权** —— 机构权限、风险和资金约束高于交易信号。
2. **可审计** —— 每个决策都有完整、可追溯的决策链。
3. **可回测** —— 支持 PIT、OOS、成本和风险等规范化验证。
4. **可 Ablation** —— 能独立验证各模块是否真正产生增量价值。
5. **牛散实战** —— 重点提升波段机会捕获、进出场时机、风险控制和资金效率。

**最终不是追求“预测最准”，而是追求：在可控风险下，少做错误交易、抓住有价值的波段，并且每个决策都能解释和验证。**


---

# 如何评价系统的效用？
评价 QCFP_MTF 的**系统效用**，不能只看收益率或 Sharpe。按照你设定的目标，建议采用 **“五层效用评价体系”**。

| 层级          | 评价什么          | 核心指标                                             |
| ----------- | ------------- | ------------------------------------------------ |
| **1. 治理效用** | 是否真正不可越权      | 越权率、Invariant 通过率、Hard Exit 执行率                  |
| **2. 风险效用** | 是否减少错误风险      | MDD、MAE、尾部损失、False Entry                         |
| **3. 波段效用** | 是否抓住牛散真正关心的行情 | Wave Capture、MFE Capture、Entry Delay、Missed Wave |
| **4. 资金效用** | 是否有效利用资金      | Capital Efficiency、平均暴露、持仓时间、Turnover            |
| **5. 研究效用** | 结论是否可信        | OOS、PIT、Ablation、Replay 一致性                      |

### 最重要的是做“对照实验”

不能只评价：

> **QCFP_MTF 好不好？**

而要评价：

```text
A：无系统 / 基准策略
        ↓
B：只有散户波段系统
        ↓
C：机构过滤器 + 波段系统
        ↓
D：完整 QCFP_MTF + Risk Governance
```

然后比较每增加一层带来的**增量价值**。

例如：

```text
Institutional Filter
→ MDD ↓ 30%
→ False Entry ↓ 25%
→ Missed Wave ↑ 5%
```

说明它的价值是**降低错误参与，而不是提高收益**。

而：

```text
Wave Engine
→ Wave Capture ↑ 18%
→ Entry Delay ↓ 20%
→ Turnover ↑ 8%
```

说明 Wave 的价值是**提高波段捕获和时机**。

---

### 最终可以形成一个“效用矩阵”

```text
                收益/机会
                   ↑
                   │
          Wave     │
        Capture    │
                   │
                   └────────→ 风险控制
                  /
                 /
        资金效率
```

因此，我建议 QCFP_MTF 的最终评价不是单一的 **Utility Score**，而是：

> **治理效用 + 风险效用 + 波段效用 + 资金效用 + 研究可信度**

其中最核心的判断是：

> **系统是否在不增加不可接受风险的前提下，帮助交易者更少犯错、更早识别有效波段、更有效地配置资金。**

**只有当这些效用在 OOS、PIT 和 Ablation 中都能够稳定体现，才能认为 QCFP_MTF 具有真正的实战效用。**

---
# 提供系统架构图
下面给出一版适合作为**系统设计文档/汇报材料**的 QCFP_MTF 总体架构图：

```text
┌──────────────────────────────────────────────────────────────────────┐
│                         QCFP_MTF 系统                                │
│       机构行为状态过滤器 + 散户波段交易决策系统                      │
└──────────────────────────────────────────────────────────────────────┘
                                  │
                                  ▼
┌──────────────────────────────────────────────────────────────────────┐
│ ① 数据与研究基础层                                                   │
│                                                                      │
│  Market Data │ Financial Data │ Corporate/Disclosure │ Universe      │
│       │              │                │                 │             │
│       └──────────────┴────────────────┴─────────────────┘             │
│                              │                                       │
│                    PIT / Available Date / Data Quality               │
└──────────────────────────────┬───────────────────────────────────────┘
                               ▼
┌──────────────────────────────────────────────────────────────────────┐
│ ② 多时间尺度状态识别层 —— QCFP_MTF                                  │
│                                                                      │
│  Quarterly / Monthly / Weekly / Daily                                │
│             │                                                        │
│             ▼                                                        │
│   ┌─────────┬─────────┬─────────┐                                    │
│   │STRUCTURE│BEHAVIOR │TACTICAL │                                    │
│   │   Q     │    M    │    W    │                                    │
│   └─────────┴─────────┴─────────┘                                    │
│             │                                                        │
│             ▼                                                        │
│      Institutional State                                             │
└──────────────────────────────┬───────────────────────────────────────┘
                               ▼
┌──────────────────────────────────────────────────────────────────────┐
│ ③ 机构行为状态过滤器 —— Institutional Permission                    │
│                                                                      │
│       State → Permission → Participation Budget                      │
│                                                                      │
│       BLOCK ───────→ 0                                               │
│       WATCH ───────→ Observe Cap                                    │
│       TEST ────────→ Explore Cap                                    │
│       ALLOW ───────→ Trade Cap                                      │
│                                                                      │
│       ★ 这是第一道硬约束：下层不得突破机构权限                      │
└──────────────────────────────┬───────────────────────────────────────┘
                               │ Permission Cap
                               ▼
┌──────────────────────────────────────────────────────────────────────┐
│ ④ 散户波段交易层 —— Retail Swing Engine                              │
│                                                                      │
│       Wave / Setup / Trigger / Daily                                │
│                    │                                                 │
│                    ▼                                                 │
│             Swing FSM                                                │
│                                                                      │
│       TEST → BUILD → HOLD → REDUCE → EXIT                            │
│                    │                                                 │
│                    ▼                                                 │
│             Raw Target Position                                      │
└──────────────────────────────┬───────────────────────────────────────┘
                               │
                               ▼
┌──────────────────────────────────────────────────────────────────────┐
│ ⑤ 风险与仓位治理层 —— Risk Governance                                │
│                                                                      │
│  Permission Cap                                                      │
│       ∩                                                              │
│  Risk Cap                                                            │
│       ∩                                                              │
│  Participation Budget                                                │
│       ∩                                                              │
│  Hard Exit                                                           │
│                                                                      │
│                 ↓                                                    │
│          Final Target Position                                       │
│                                                                      │
│  核心不变量：                                                        │
│  Final Target ≤ Raw Target                                          │
│  Final Target ≤ Permission Cap                                      │
│  Final Target ≤ Risk Cap                                            │
│  Hard Exit → Final Target = 0                                       │
└──────────────────────────────┬───────────────────────────────────────┘
                               ▼
┌──────────────────────────────────────────────────────────────────────┐
│ ⑥ 统一决策引擎 —— Canonical Decision Engine                          │
│                                                                      │
│   State → Permission → Wave → FSM → Risk → Sizing → Final Decision  │
│                              │                                       │
│                              ▼                                       │
│                    Decision Snapshot                                 │
│                    Decision Certificate                              │
└──────────────────────────────┬───────────────────────────────────────┘
                               ▼
┌──────────────────────────────────────────────────────────────────────┐
│ ⑦ 决策事实与审计层                                                   │
│                                                                      │
│   Decision Ledger                                                    │
│       │                                                              │
│       ├── Decision ID                                                │
│       ├── Input Fingerprint                                         │
│       ├── Model / Rule / Schema Version                              │
│       ├── Permission / Risk / Target                                 │
│       ├── Reason Codes                                               │
│       ├── Decision Path                                              │
│       └── Hash / Replay Information                                  │
└──────────────────────────────┬───────────────────────────────────────┘
                               │
              ┌────────────────┼────────────────┐
              ▼                ▼                ▼
┌──────────────────┐ ┌──────────────────┐ ┌──────────────────┐
│ ⑧ Backtest       │ │ ⑨ Ablation      │ │ ⑩ Audit / Report │
│                  │ │                  │ │                  │
│ PIT / OOS        │ │ Module ON/OFF    │ │ Replay           │
│ Walk-forward     │ │ Alpha Ablation   │ │ Explainability   │
│ Cost / Slippage  │ │ Governance       │ │ Decision Trace   │
│ MFE / MAE        │ │ Wave Ablation    │ │ Certificate      │
└────────┬─────────┘ └────────┬─────────┘ └────────┬─────────┘
         │                    │                    │
         └────────────────────┴────────────────────┘
                              ▼
                 ┌─────────────────────────┐
                 │ ⑪ 系统效用评价          │
                 │                         │
                 │ 不可越权                │
                 │ 可审计                  │
                 │ 可回测                  │
                 │ 可 Ablation             │
                 │ 牛散实战价值            │
                 └─────────────────────────┘
```

### 核心控制关系

整个系统最重要的不是模块数量，而是这条**单向、不可逆的决策链**：

```text
数据
 ↓
多周期状态
 ↓
机构 Permission
 ↓
Wave / Swing
 ↓
Risk Governance
 ↓
Final Position
 ↓
Decision Ledger
 ↓
Backtest / Ablation / Audit
```

其中必须满足：

> **上层可以限制下层，下层不能突破上层。**

因此最终仓位可以抽象为：

```text
Final Position
=
min(
    Retail Raw Target,
    Institutional Permission Cap,
    Risk Cap,
    Participation Budget
)
```

而：

```text
Hard Exit → Final Position = 0
```

这就是 QCFP_MTF 实现**“不可越权 + 可审计 + 可回测 + 可 Ablation + 牛散实战”**的核心架构。


---

# 提供数据流程图
下面是 QCFP_MTF 的**数据流程图（Data Flow Diagram）**，重点展示数据从原始输入到最终交易决策、回测和审计的完整流转。

```text
┌────────────────────────────────────────────────────────────────────┐
│                         ① 原始数据源                               │
├────────────────────────────────────────────────────────────────────┤
│                                                                    │
│  行情数据          财务数据          公司事件/披露        股票池   │
│  OHLCV              F/S               Disclosure            Universe │
│    │                  │                    │                  │     │
└────┼──────────────────┼────────────────────┼──────────────────┼─────┘
     │                  │                    │                  │
     └──────────────────┴────────────────────┴──────────────────┘
                                │
                                ▼
┌────────────────────────────────────────────────────────────────────┐
│                    ② 数据治理 / PIT 层                             │
├────────────────────────────────────────────────────────────────────┤
│                                                                    │
│  Available Date        Disclosure Date       Data Quality          │
│       │                       │                    │                │
│       └───────────────────────┼────────────────────┘                │
│                               ▼                                    │
│                    Point-in-Time Dataset                            │
│                                                                    │
│              防止 Look-ahead / Survivorship Bias                    │
└────────────────────────────────┬───────────────────────────────────┘
                                 │
                                 ▼
┌────────────────────────────────────────────────────────────────────┐
│                    ③ 特征工程 / Feature Layer                     │
├────────────────────────────────────────────────────────────────────┤
│                                                                    │
│  Price Features       Fundamental Features       Behavioral        │
│       │                       │                     │               │
│       └───────────────────────┼─────────────────────┘               │
│                               ▼                                    │
│                     Canonical Features                             │
│                               │                                    │
│                    Feature Version / Hash                          │
└────────────────────────────────┬───────────────────────────────────┘
                                 │
             ┌───────────────────┼───────────────────┐
             ▼                   ▼                   ▼
┌──────────────────┐ ┌──────────────────┐ ┌────────────────────────┐
│ ④ Structural     │ │ ⑤ Behavioral     │ │ ⑥ Tactical             │
│                  │ │                  │ │                        │
│ Quarterly        │ │ Monthly         │ │ Weekly / Daily          │
│ 长周期状态        │ │ 中周期状态       │ │ 短周期状态              │
└────────┬─────────┘ └────────┬─────────┘ └──────────┬─────────────┘
         │                    │                       │
         └────────────────────┼───────────────────────┘
                              ▼
┌────────────────────────────────────────────────────────────────────┐
│                    ⑦ QCFP_MTF 状态融合层                          │
├────────────────────────────────────────────────────────────────────┤
│                                                                    │
│              Quarterly → Monthly → Weekly → Daily                 │
│                              │                                     │
│                              ▼                                     │
│                   Institutional State                              │
│                              │                                     │
│             State Transition / Persistence                         │
└────────────────────────────────┬───────────────────────────────────┘
                                 │
                                 ▼
┌────────────────────────────────────────────────────────────────────┐
│                    ⑧ Institutional Permission                      │
├────────────────────────────────────────────────────────────────────┤
│                                                                    │
│      Institutional State → Permission → Participation Budget       │
│                                                                    │
│      BLOCK / WATCH / TEST / ALLOW                                  │
│                         │                                          │
│                         ▼                                          │
│                  Permission Cap                                    │
└────────────────────────────────┬───────────────────────────────────┘
                                 │
                                 │ 硬约束
                                 ▼
┌────────────────────────────────────────────────────────────────────┐
│                    ⑨ Retail Swing Layer                            │
├────────────────────────────────────────────────────────────────────┤
│                                                                    │
│       Wave Signal ── Setup ── Trigger ── Daily Confirmation        │
│                              │                                     │
│                              ▼                                     │
│                         Swing FSM                                  │
│                                                                    │
│              TEST → BUILD → HOLD → REDUCE → EXIT                  │
│                              │                                     │
│                              ▼                                     │
│                       Raw Target Position                           │
└────────────────────────────────┬───────────────────────────────────┘
                                 │
                                 ▼
┌────────────────────────────────────────────────────────────────────┐
│                    ⑩ Risk / Position Governance                    │
├────────────────────────────────────────────────────────────────────┤
│                                                                    │
│  Raw Target                                                        │
│      │                                                             │
│      ├────────→ Permission Cap                                     │
│      ├────────→ Risk Cap                                            │
│      ├────────→ Participation Budget                               │
│      └────────→ Hard Exit                                           │
│                         │                                          │
│                         ▼                                          │
│                    Final Target                                    │
└────────────────────────────────┬───────────────────────────────────┘
                                 │
                                 ▼
┌────────────────────────────────────────────────────────────────────┐
│                    ⑪ Canonical Decision Engine                     │
├────────────────────────────────────────────────────────────────────┤
│                                                                    │
│  输入状态 + Permission + Wave + FSM + Risk + Sizing                │
│                              │                                     │
│                              ▼                                     │
│                    Decision Snapshot                               │
│                              │                                     │
│                              ▼                                     │
│                   Decision Certificate                             │
└────────────────────────────────┬───────────────────────────────────┘
                                 │
                                 ▼
┌────────────────────────────────────────────────────────────────────┐
│                    ⑫ Decision Ledger                              │
├────────────────────────────────────────────────────────────────────┤
│                                                                    │
│  Decision ID │ Input Fingerprint │ Config Hash │ Rule Version      │
│  State       │ Permission        │ Target      │ Reason Codes       │
│  Decision Path │ Certificate Hash │ PIT Grade                       │
└────────────────────────────────┬───────────────────────────────────┘
                                 │
             ┌───────────────────┼────────────────────┐
             ▼                   ▼                    ▼
┌──────────────────┐ ┌──────────────────┐ ┌────────────────────────┐
│ ⑬ Backtest       │ │ ⑭ Ablation      │ │ ⑮ Audit / Report       │
│                  │ │                  │ │                        │
│ PIT / OOS        │ │ Module ON/OFF    │ │ Replay                 │
│ Cost / Slippage  │ │ Alpha Ablation   │ │ Decision Trace         │
│ MFE / MAE        │ │ Governance       │ │ Certificate            │
│ Portfolio P&L    │ │ Wave Ablation    │ │ Explainability         │
└────────┬─────────┘ └────────┬─────────┘ └──────────┬─────────────┘
         │                    │                       │
         └────────────────────┼───────────────────────┘
                              ▼
┌────────────────────────────────────────────────────────────────────┐
│                    ⑯ 系统效用评价                                 │
├────────────────────────────────────────────────────────────────────┤
│                                                                    │
│  治理效用 │ 风险效用 │ 波段效用 │ 资金效用 │ 研究可信度            │
│                                                                    │
│  不可越权 │ 可审计 │ 可回测 │ 可 Ablation │ 牛散实战价值           │
└────────────────────────────────────────────────────────────────────┘
```

### 数据流的核心原则

整个系统实际上可以浓缩成一条主数据链：

```text
原始数据
  ↓
PIT / 数据治理
  ↓
Canonical Features
  ↓
Q / M / W / D 多周期状态
  ↓
Institutional State
  ↓
Permission
  ↓
Wave / Setup / Trigger
  ↓
Swing FSM
  ↓
Raw Position
  ↓
Permission / Risk / Budget 约束
  ↓
Final Position
  ↓
Decision Certificate
  ↓
Decision Ledger
  ↓
Backtest / Ablation / Audit
  ↓
System Utility
```

其中有两个必须严格隔离的数据流：

```text
未来数据
   ↓
Wave Label / Future Return / MFE / MAE
   ↓
只允许进入 Evaluation
```

而：

```text
As-of 数据
   ↓
Feature / State / Wave Signal
   ↓
允许进入 Decision Engine
```

这条边界是**防止 Look-ahead Bias、保证可回测性**的关键。

最终可以把整个数据流概括为：

> **数据 → 状态 → 权限 → 波段 → 风险 → 决策 → 事实记录 → 验证 → 效用评价。**


---
# 分析当前的数据完整性、数据质量及尚未提供的重要数据。
基于目前提供的 **QCFP_MTF 代码、报告和研究输出**，我对数据状况的判断是：

> **数据结构已经基本能够支撑“研究原型”，但还没有达到“严格 OOS / PIT 回测 + 牛散实战验证”的数据完整度。**
>
> 最大问题不是“没有数据”，而是**数据的时间可用性、股票池完整性、历史覆盖和部分核心行为数据的真实性/可追溯性**。

## 1. 当前数据完整性

| 数据类别               | 当前状态         | 评价                      |
| ------------------ | ------------ | ----------------------- |
| 日/周行情 OHLC         | 已有           | 🟢 基本可用                 |
| 高低价 / Close        | 已有           | 🟢 可用于 MFE/MAE          |
| 多周期行情              | 已有           | 🟢 Q/M/W/D 框架已形成        |
| 财务 C/F/P           | 已有派生数据       | 🟡 需要进一步验证历史 PIT        |
| 月度行为               | 有            | 🟡 属于行为代理               |
| 周期 Tactical 信号     | 有            | 🟡 可研究，但历史完整性需确认        |
| 成交量/换手/流动性         | 有            | 🟡 基本具备                 |
| Wave / MFE / MAE   | 已实现          | 🟢 评价体系完整               |
| Decision Ledger    | 有            | 🟢 审计基础较好               |
| PIT Available Date | 有机制          | 🟡 数据本身仍不完整             |
| PIT Universe       | **缺失/不足**    | 🔴 关键缺口                 |
| 历史退市股票             | 未充分证明        | 🔴 Survivorship Bias 风险 |
| 历史复权/公司行动          | 未充分证明        | 🟡 需要核验                 |
| 真实交易成本/滑点          | 有模型          | 🟡 仍需真实数据校准             |
| 机构真实持仓/资金流         | 主要为代理变量      | 🔴 机构行为真实性不足            |
| Level-2 / Tick     | 未见完整数据       | 🔴 尚缺                   |
| Corporate Actions  | 未见完整 PIT 数据链 | 🔴 需要补齐                 |

代码已经明确区分**证据等级**和**数据质量**：季度结构是 A-、月线 B、周线 C、MTF 结果 D；同时数据质量是另一套独立维度。

---

# 2. 当前最严重的问题：PIT Universe

这是目前最重要的数据缺口。

系统虽然已经考虑：

```text
Available Date
Disclosure Date
PIT
```

但目前**没有充分证明历史每一个决策日所使用的股票池，是当时真正存在且可交易的股票集合**。

这会产生：

```text
今天的股票池
        ↓
回看过去
        ↓
历史上已经知道哪些股票最终存活
        ↓
Survivorship Bias
```

对于牛散系统尤其危险。

因为它可能造成：

> **回测结果看起来知道“哪些股票后来成为牛股”，而真实交易者当时并不知道。**

因此 PIT Universe 是当前最优先需要补的数据。

---

# 3. 财务数据：有，但还不能直接认为“PIT 完整”

目前 C/F/P 已经进入季度结构：

```text
C / F / P
 ↓
Structural State
```

并且系统把季度结构标记为 **A-（派生事实）**。

问题在于：

### 必须同时有三个时间：

```text
period_end
filing_date
available_date
```

例如：

```text
2025-12-31
     ↓
2026-03-15 发布
     ↓
2026-03-16 才允许模型使用
```

不能仅仅记录：

```text
2025Q4 Revenue
```

否则回测可能在 2025-12-31 就使用了 2026-03 月份才披露的数据。

**建议把所有财务字段强制变成：**

```text
value
period_end
filing_date
available_date
source
revision_id
```

---

# 4. 机构行为数据目前更像“代理变量”

这是第二个重要问题。

系统目标是：

> **机构行为状态过滤器**

但从当前代码能看到的主要是：

* 成本位置
* VWAP
* 换手
* 成交量
* CBI
* VP Regime
* Chip Stability
* Structure/Behavior Alignment

例如当前 DSS 输出包含：

```text
turnover_liquidity_regime
m_vp_regime
cbi_score
cost_position
cost_vs_weekly_vwap
cost_vs_monthly_vwap
cost_vs_quarterly_vwap
chip_stability_confidence
```



这些对于研究**机构行为代理**是有价值的。

但需要明确：

> **它们不是机构真实交易行为本身。**

如果希望系统真正提高“牛散参考价值”，建议增加真实机构行为数据，例如：

* 机构持仓变化
* 基金季度持仓
* 北向/南向资金（适用市场）
* 大宗交易
* 龙虎榜机构席位
* 公司回购
* 增减持
* 融资融券
* 重要股东持股变化
* 机构调研
* 大额成交/Block Trade

并且全部必须带：

```text
event_date
announcement_date
available_date
```

---

# 5. Wave 数据：评价数据已经比较完整

这一块反而是当前系统比较成熟的部分。

回测已经能够计算：

* MFE
* MAE
* realized return
* capture
* holding weeks
* win rate



同时还有：

* Wave Capture Ratio
* Entry Delay
* Missed Wave Rate
* False Entry Rate



所以：

> **Wave Evaluation 数据框架已经基本成型。**

但仍需要补：

### Wave 的真实历史样本库

至少需要：

```text
股票
Wave ID
Wave Start
Wave End
Peak
Trough
Peak Gain
持续时间
最大回撤
行业
市场环境
```

最好覆盖完整牛熊周期，而不是只验证某一个年份/阶段。

---

# 6. 行情数据还需要补“公司行为调整链”

虽然目前已经有：

```text
date
high
low
close
```

并能够用于 MFE/MAE。

但正式回测必须进一步确认：

* 拆股
* 合股
* 配股
* 分红
* 配送
* 增发
* 停牌
* 复牌
* 特殊除权

否则可能出现：

```text
公司行为
 ↓
价格突然变化
 ↓
模型误认为巨大波动
```

因此需要一个独立的：

> **Corporate Action PIT Dataset**

---

# 7. 流动性数据还不够支持“真实可交易性”

当前系统已经考虑：

```text
turnover
liquidity regime
transaction cost
```

这说明框架正确。

但如果目标是**牛散实战**，还应该至少有：

```text
ADV
成交额
自由流通市值
换手率
Bid-Ask Spread
Amihud Illiquidity
涨跌停状态
停牌状态
可交易股数
```

进一步最好有：

```text
盘口 / Level-2
```

尤其是小盘股、波段突破、快速退出时：

> **Close-to-Close 回测可能严重高估实际可成交价格。**

---

# 8. 尚未提供的重要数据——我建议按优先级补

## P0：必须补

### ① PIT Universe

```text
date
stock_code
listed
tradable
in_universe
delisted_date
suspended
```

这是正式 OOS 验证的基础。

### ② 完整 Available Date

所有数据统一：

```text
value
event_date
available_date
source
```

### ③ Corporate Actions

```text
dividend
split
rights
bonus
suspension
resumption
```

### ④ 退市/停牌历史

避免 Survivorship Bias。

---

# 9. P1：决定“机构行为过滤器”有没有真实价值

建议补：

```text
机构持仓
基金持仓
重要股东增减持
大宗交易
机构席位
融资融券
回购
调研
资金流
```

并全部 PIT 化。

否则系统更准确的名称应该是：

> **“机构行为代理过滤器”**

而不是严格意义上的：

> **“机构行为过滤器”。**

---

# 10. P1：决定“牛散实战”是否可信

建议补：

### 交易层数据

```text
Bid
Ask
Spread
成交额
ADV
盘口深度
滑点
```

### 执行层数据

```text
开盘价
VWAP
收盘价
下一交易日价格
执行延迟
部分成交
```

因为系统最终不是只判断：

> “这只股票会不会涨。”

而是判断：

> **“现在能不能买、买多少、什么时候减、什么时候退出。”**

这必须有执行数据才能验证。

---

# 11. 当前数据质量的总体评级

如果按你自己的 **A~D 数据质量体系**来评价，我会给：

```text
                 当前        目标
──────────────────────────────────
行情              A/B         A
财务              B           A
PIT               B/C         A
PIT Universe      D           A
机构行为          B/C         A/B
Wave Label        A/B         A
交易执行          C           A/B
公司行为          B/C         A
退市/停牌         C/D         A
```

所以整体不是：

> **“数据很差。”**

而是：

> **“研究数据框架已经搭起来，但关键的历史可用性数据还没有完全闭环。”**

---

# 12. 对当前系统最重要的结论

目前最值得警惕的不是：

```text
Sharpe 不高
```

而是：

```text
数据 → PIT → Universe → 决策
```

这条链还没有完全达到生产级闭环。

特别是：

> **PIT Universe + 退市股票 + Available Date + Corporate Actions**

这四项没有彻底补齐之前，**不应该把回测结果作为“QCFP_MTF 已被验证具有牛散实战效用”的证据。**

另一方面，Wave 层的 MFE/MAE/Capture 等评价框架已经相对成熟，当前更适合继续作为**研究评价体系**使用。

### 建议的数据建设优先顺序

```text
P0
PIT Universe
   ↓
Available Date 全覆盖
   ↓
Corporate Actions
   ↓
Delisting / Suspension
   ↓
正式 OOS 回测
        │
        ▼
P1
真实机构行为数据
   ↓
真实流动性 / Spread / Execution
   ↓
牛散交易级回测
        │
        ▼
P2
Level-2 / Tick
   ↓
精细执行模型
```

**一句话总结：**

> **当前系统“计算数据”基本够用，“验证数据”还不够完整；最大的短板不是因子，而是 PIT Universe、历史可用性、退市/公司行为和真实机构/执行数据。**


---
