
# 解释FSM

FSM 是 **Finite State Machine，有限状态机**。

在 QCFP_MTF 中，它不是用来“预测涨跌”的，而是用来管理**散户仓位从空仓到建仓、持有、减仓、退出、冷却的生命周期**。

你的架构定义得很明确：

> **Retail Position FSM → 仓位生命周期**
> **Position Sizing → 数值仓位**

也就是说：

> **FSM 决定“我现在处于什么交易阶段”；Position Sizing 决定“这个阶段到底持有多少仓位”。** 

---

# 1. 为什么需要 FSM？

如果没有 FSM，策略通常是这样的：

```text
信号好 → 买
信号更好 → 加仓
信号差 → 卖
```

问题是：**每一期决策都是孤立的。**

例如：

| 本周 | 信号       |
| -- | -------- |
| W1 | Breakout |
| W2 | Neutral  |
| W3 | Breakout |
| W4 | Neutral  |
| W5 | Breakout |

如果直接按信号交易，可能变成：

```text
买 → 卖 → 买 → 卖 → 买
```

产生大量噪音交易和换手。

FSM 的思想是：

> **本周的决策不仅取决于本周信号，还取决于“上周我已经处于什么状态”。**

所以它会问：

```text
我现在是空仓？
已经试仓？
正在加仓？
正在持有？
正在减仓？
刚退出？
处于冷却期？
```

这就是“状态”。

---

# 2. QCFP 中的 FSM 状态

从你目前系统的设计看，可以理解成：

```text
FLAT
 ↓
TESTING
 ↓
BUILDING
 ↓
HOLDING
 ↓
TRIMMING
 ↓
EXITING
 ↓
COOLDOWN
 ↓
FLAT
```

## FLAT：空仓

```text
仓位 = 0
```

意思：

> 目前没有持仓，等待机会。

只有机构 Permission 允许、Setup 成立时，才可能：

```text
FLAT → TESTING
```

而不是一出现信号就直接满仓。

---

## TESTING：试仓

```text
小仓位测试
```

意思：

> 我认为可能有机会，但还没有足够证据确认。

例如：

```text
Institutional Permission = TEST
Weekly Setup = PULLBACK
Risk = Normal
```

那么：

```text
FLAT → TESTING
```

例如仓位：

```text
0% → 10%
```

注意：

**10% 不是 FSM 决定的。**

FSM 只决定：

```text
FLAT → TESTING
```

Position Sizing 才决定：

```text
TESTING = 10%
```

---

# 3. BUILDING：逐步建立仓位

如果试仓后情况继续改善：

```text
TESTING
    +
Institutional Permission = ALLOW
    +
Setup = BREAKOUT
    ↓
BUILDING
```

意思：

> 初步判断正确，可以增加风险暴露。

例如：

```text
10% → 30%
```

---

# 4. HOLDING：正常持有

如果趋势和机构行为继续支持：

```text
BUILDING
    +
Permission = STRONG_ALLOW
    +
Setup = CONFIRMED
    ↓
HOLDING
```

意思：

> 不再频繁交易，让利润继续运行。

例如：

```text
30% → 60%
```

FSM 最大的价值之一就在这里。

没有 FSM：

```text
本周 Breakout → 买
下周 Neutral → 卖
```

有 FSM：

```text
BUILDING → HOLDING
```

即使某个短周期信号暂时消失，也不一定立刻退出。

因为：

> **持有状态具有路径依赖。**

---

# 5. TRIMMING：减仓

例如机构 Permission 从：

```text
ALLOW
```

下降到：

```text
WATCH
```

系统不一定应该：

```text
100% → 0%
```

而可能：

```text
HOLDING → TRIMMING
```

例如：

```text
60% → 30%
```

含义是：

> 机构条件恶化，但尚未达到 Hard Exit。

所以 FSM 可以避免“不是满仓就是空仓”的二元交易。

---

# 6. EXITING：退出

出现明确退出条件：

```text
Hard Exit
Stop
严重 Risk Event
```

例如：

```text
HOLDING → EXITING
```

然后仓位：

```text
60% → 0%
```

你的架构已经规定：

> **Hard Exit 覆盖所有普通看多信号。** 

所以：

```text
Institutional Permission = STRONG_ALLOW
Weekly = Breakout
Daily = Very Bullish
```

如果：

```text
Hard Exit = True
```

仍然应该：

```text
ANY STATE → EXITING
```

这叫做 **Kill Switch**。

---

# 7. COOLDOWN：冷却期

退出后，不允许马上重新买入。

例如：

```text
EXITING
   ↓
COOLDOWN
```

然后即使出现短期 Breakout：

```text
COOLDOWN + Breakout
```

也可能：

```text
继续 COOLDOWN
```

目的：

> 防止刚止损就被短期噪音重新吸引进去。

只有满足重新入场条件后：

```text
COOLDOWN → FLAT → TESTING
```

---

# 8. FSM 最核心的东西：状态转移

FSM 不是简单的状态列表。

真正的 FSM 是：

```text
当前状态
    +
新信息
    ↓
状态转移规则
    ↓
下一个状态
```

数学上可以写成：

```text
S(t+1) = Transition(
    S(t),
    Permission(t),
    Setup(t),
    Risk(t),
    ExitEvent(t)
)
```

在 QCFP 中：

```text
Previous FSM State
        +
Institutional Permission
        +
Trading Setup
        +
Risk / Hard Exit
        ↓
    Next FSM State
```

例如：

```text
Previous = TESTING
Permission = ALLOW
Setup = BREAKOUT
Risk = NORMAL

→ BUILDING
```

---

# 9. 为什么 Institutional Permission 和 FSM 必须分开？

这是你这个系统最重要的概念之一。

## Institutional Permission 回答：

> **最多允许我承担多大的风险？**

例如：

```text
BLOCK
WATCH
TEST
ALLOW
STRONG_ALLOW
```

它是：

> **Upper Bound Gate，交易上限。** 

---

## Retail FSM 回答：

> **根据我现在的持仓生命周期，我下一步处于什么阶段？**

例如：

```text
FLAT → TESTING → BUILDING → HOLDING
```

---

所以不能写成：

```text
Permission = ALLOW
→ 直接买 50%
```

正确逻辑应该是：

```text
Permission = ALLOW
        ↓
允许 BUILDING，但不强迫 BUILDING
        ↓
FSM 根据当前状态和 Setup 决定
        ↓
TESTING → BUILDING
        ↓
Position Sizing
        ↓
10% → 30%
```

---

# 10. QCFP 的完整决策链

我建议你把整个系统理解成这条链：

```text
                    C / F / P
                        │
                        ▼
              Institutional State
                        │
                        ▼
             Institutional Permission
                        │
              「决定风险上限」
                        │
                        ▼
              Hard Exit / Risk
                        │
                  「可强制覆盖」
                        │
                        ▼
                  Trading Setup
                 Q / M / W / D
                        │
                        ▼
                 Retail FSM
                        │
              「决定生命周期」
                        │
                        ▼
                Position Sizing
                        │
               「决定具体仓位」
                        │
                        ▼
                  Execution
```

这与项目的设计冻结架构一致：Institutional Permission 是上限，Retail FSM 管理仓位生命周期，而 Position Sizing 管理数值仓位。

---

# 11. 一个完整例子

假设某股票：

### 第 1 周

```text
Institution = WATCH
Setup = NONE
Previous FSM = FLAT
```

结果：

```text
FLAT → FLAT
Position = 0%
```

---

### 第 2 周

```text
Institution = TEST
Weekly Setup = PULLBACK
Previous FSM = FLAT
```

结果：

```text
FLAT → TESTING
Position = 10%
```

---

### 第 3 周

```text
Institution = ALLOW
Weekly Setup = BREAKOUT
Previous FSM = TESTING
```

结果：

```text
TESTING → BUILDING
Position = 30%
```

---

### 第 4 周

```text
Institution = STRONG_ALLOW
Trend = CONFIRMED
Previous FSM = BUILDING
```

结果：

```text
BUILDING → HOLDING
Position = 60%
```

---

### 第 5 周

```text
Institution = WATCH
Risk = ELEVATED
Previous FSM = HOLDING
```

结果：

```text
HOLDING → TRIMMING
Position = 30%
```

---

### 第 6 周

```text
Hard Exit = True
```

不管其他信号：

```text
TRIMMING → EXITING
Position → 0%
```

---

### 第 7 周

```text
Previous = EXITING
```

结果：

```text
EXITING → COOLDOWN
Position = 0%
```

---

这就是 FSM。

**它不是“买卖信号生成器”，而是一个交易生命周期控制器。**

对于 QCFP_MTF 来说，最关键的 FSM 原则可以浓缩成一句：

> **Institutional Permission 决定“最多可以走到哪里”，Retail FSM 决定“现在走到哪一步”，Position Sizing 决定“这一步实际投入多少钱”。**

---

# 解释DES  
根据目前已审查到的项目代码与报告，**文件中没有明确给出 DES 的全称定义**。

从已见代码只能确认它作为一个：

> **下行风险/恶化评分（risk deterioration score）**

参与退出逻辑，例如：

```python
ctx.des_score >= 7
```

会触发 `EXITING` 或 `COOLDOWN`。

因此，我前面把 DES 扩展解释为 **Downside / Deterioration / Exit Score** 是基于功能的推断，**不是文件中已经明确写出的官方全称**。

如果 QCFP_MTF 要正式化，我建议不要继续保留这个歧义缩写。可以明确命名为：

### 推荐

**DES = Downside Exit Score**

含义最直接：

> **下行退出评分**

或者如果强调“恶化过程”：

**DES = Deterioration Exit Score**

> **恶化退出评分**

在你的架构中，我更推荐 **Downside Exit Score**，因为它清楚表达：

```text
DES
= 下行风险评分
= 达到阈值时触发退出层
```

而不会和 Institutional Permission 或 Retail FSM 的职责混淆。


---
# 解释周 VWAP 偏离  
**周 VWAP 偏离**，通常是指：

> **当前价格相对于“周周期成交量加权平均价格（Weekly VWAP）”的距离。**

它用来判断当前价格相对本周期资金平均成本是处于：

* 上方：浮盈区、偏强；
* 附近：成本平衡区；
* 下方：浮亏区、偏弱。

---

## 1. 什么是 VWAP？

VWAP 全称：

> **Volume Weighted Average Price**
>
> **成交量加权平均价格**

基本公式：

[
VWAP=\frac{\sum(Price_i\times Volume_i)}{\sum Volume_i}
]

与普通均价不同，VWAP 给**成交量大的价格更多权重**。

例如：

| 价格   |    成交量 |
| ---- | -----: |
| 10 元 |  1,000 |
| 12 元 | 10,000 |

普通平均价：

[
(10+12)/2=11
]

但 VWAP 会更接近 **12 元**，因为大部分成交发生在 12 元附近。

所以可以把 VWAP 理解为：

> **市场参与者在某个周期内的平均成交成本中心。**

---

# 2. 什么是“周 VWAP”？

“周 VWAP”指使用**周周期的数据**计算 VWAP。

概念上：

```text
一周内的价格 × 对应成交量
            ↓
        加权平均
            ↓
       Weekly VWAP
```

例如：

```text
本周 VWAP = 100
当前价格 = 105
```

说明：

> 当前价格比本周成交量加权平均成本高 5%。

---

# 3. 什么是 VWAP 偏离？

通常可以定义为：

[
VWAP\ Deviation
===============

\frac{Close-VWAP}{VWAP}
]

也可以写成百分比：

[
VWAP\ 偏离率
=========

\frac{Close-VWAP}{VWAP}\times100%
]

例如：

```text
Weekly VWAP = 100
Close       = 105
```

则：

[
\frac{105-100}{100}=5%
]

所以：

```text
周 VWAP 偏离 = +5%
```

---

## 负偏离

例如：

```text
Weekly VWAP = 100
Close       = 95
```

则：

[
\frac{95-100}{100}=-5%
]

即：

```text
周 VWAP 偏离 = -5%
```

---

# 4. 在量化模型中怎么理解？

可以把周 VWAP 看成：

> **本周主要交易资金的平均成本参考线。**

因此：

### 正偏离

```text
Price > Weekly VWAP
Deviation > 0
```

说明价格位于平均成交成本之上。

例如：

```text
+1%
+3%
+5%
```

一般代表：

> 当前价格相对本周成交成本偏强。

---

### 接近 0

```text
Price ≈ Weekly VWAP
Deviation ≈ 0
```

说明：

> 当前价格接近平均成交成本。

可能处于：

```text
成本平衡
整理
方向选择
```

区域。

---

### 负偏离

```text
Price < Weekly VWAP
Deviation < 0
```

说明价格跌破平均成交成本。

例如：

```text
-2%
-5%
-8%
```

通常代表：

> 本周在 VWAP 附近成交的资金整体处于浮亏。

---

# 5. 对 QCFP_MTF 的意义

如果放入你现在的：

```text
Institutional Permission
×
Retail FSM
```

架构中，我建议周 VWAP 偏离**不要单独成为买卖规则**。

更适合把它作为：

> **周线价格位置 / Trend Extension / Mean Reversion 风险特征。**

例如：

```text
周 VWAP 偏离
        ↓
价格相对成本中心的位置
        ↓
判断趋势是否健康 / 是否过度延伸
        ↓
影响 Setup 或 Risk
        ↓
FSM 决定状态转移
```

而不是：

```text
VWAP 偏离 > 3%
→ 直接买入
```

---

# 6. 对 Retail FSM 的典型作用

假设：

```text
Institutional Permission = ALLOW
FSM = TESTING
```

再看周 VWAP 偏离。

### 情况 A：+1%

```text
价格略高于 VWAP
```

可能属于健康的确认状态：

```text
TESTING
   +
BREAKOUT
   +
VWAP Deviation = +1%
   ↓
BUILDING
```

---

### 情况 B：+15%

价格已经远离周 VWAP：

```text
TESTING
   +
VWAP Deviation = +15%
```

这时未必应该追高加仓。

更合理的逻辑可能是：

```text
ALLOW
+
过度 VWAP 偏离
↓
不禁止持有
但禁止进一步加仓
```

也就是说：

> **过度正偏离更适合限制追涨，而不是自动看空。**

---

### 情况 C：-5%

```text
Price < Weekly VWAP
```

如果同时：

```text
Institutional Permission = WATCH
```

那么：

```text
HOLDING
↓
TRIMMING
```

可能比继续 BUILDING 更合理。

---

# 7. 一个重要区别：VWAP 偏离 ≠ 涨跌幅

例如：

### 股票 A

```text
本周涨幅 = +5%
VWAP 偏离 = +1%
```

说明：

> 虽然上涨，但成交成本中心也在向上移动，价格没有过度偏离。

---

### 股票 B

```text
本周涨幅 = +5%
VWAP 偏离 = +8%
```

说明：

> 当前价格可能已经快速脱离成交成本中心。

所以 VWAP 偏离回答的不是：

> “涨了多少？”

而是：

> **“当前价格距离主要成交成本中心有多远？”**

---

# 8. 在 QCFP 中更好的标准化方式

建议统一定义：

```python
weekly_vwap_deviation = (
    weekly_close - weekly_vwap
) / weekly_vwap
```

然后转换成状态，而不是直接使用裸数值：

```text
≤ -X%      BELOW_VWAP
-X% ~ +X%  NEAR_VWAP
+X% ~ +Y%  HEALTHY_EXTENSION
> +Y%      OVEREXTENDED
```

最终进入决策链：

```text
Weekly VWAP Deviation
          ↓
Weekly Price Structure
          ↓
Setup / Extension Risk
          ↓
Retail FSM
          ↓
Position Sizing
```

**核心理解：周 VWAP 偏离衡量的是“当前价格距离本周成交量加权平均成本有多远”，它更适合作为趋势健康度和过度延伸的输入，而不是独立买卖按钮。**

如果你愿意，我也可以创建一张图，把“价格—周 VWAP—正负偏离—FSM 状态转移”的关系可视化。

---

# 不同层级的状态/决策字段
你列出的四个字段属于 **不同层级的状态/决策字段**。最重要的是不要把它们当成同一件事。

| 字段                  | 核心问题                | 所属层级    |
| ------------------- | ------------------- | ------- |
| `structural_regime` | **长期结构是什么？**        | 结构层     |
| `mtf_regime`        | **多周期综合后，当前状态是什么？** | MTF 融合层 |
| `market_regime`     | **大盘环境如何？**         | 市场环境层   |
| `action_signal`     | **旧决策链建议做什么？**      | 动作层     |

代码中 `qcfp_mtf_decision` 将它们作为不同字段保存，说明它们本来就不是同义词。

---

## 1. `structural_regime`：长期结构状态

它回答：

> **这只股票的中长期基本结构处于什么阶段？**

可以理解为系统的**高层结构约束**。

根据当前代码，明确出现的状态包括：

| 值                             | 含义     |
| ----------------------------- | ------ |
| `STRUCTURAL_BULLISH`          | 结构性多头  |
| `STRUCTURAL_ACCUMULATION`     | 结构性吸筹  |
| `STRUCTURAL_DIVERGENCE`       | 结构背离   |
| `STRUCTURAL_DISTRIBUTION`     | 结构性派发  |
| `STRUCTURAL_DECLINE`          | 结构性下行  |
| `STRUCTURAL_BOTTOM_CANDIDATE` | 底部候选   |
| `STATE_UNDETERMINED`          | 结构无法确定 |

其中代码明确把：

```text
STRUCTURAL_BULLISH
STRUCTURAL_ACCUMULATION
```

归为 Bullish Family；把：

```text
STRUCTURAL_DECLINE
STRUCTURAL_DISTRIBUTION
```

归为 Bearish Family。

#### 核心理解

```text
structural_regime
= 长期结构方向
= 系统的上层边界
```

例如：

```text
STRUCTURAL_BULLISH
```

意味着长期结构偏多。

但不代表：

```text
今天必须 BUY
```

因为短期可能正在调整。

---

## 2. `mtf_regime`：多周期融合状态

MTF = **Multi-Timeframe**，即多周期。

它回答：

> **把结构、月度行为阶段、周线触发条件综合以后，现在处于什么交易状态？**

当前主要列表为：

| 值                            | 含义          |
| ---------------------------- | ----------- |
| `BULLISH_CONFIRMED`          | 多头确认        |
| `BULLISH_STABLE`             | 多头稳定        |
| `BULLISH_WARNING`            | 多头预警        |
| `BEARISH_RECOVERY_CANDIDATE` | 空头后的修复/反转候选 |
| `BEARISH_CONFIRMED`          | 空头确认        |
| `DATA_INSUFFICIENT`          | 数据不足        |

代码中明确存在这些状态及对应分数映射。

它的生成逻辑本质上是：

```text
Structural Regime
        +
Monthly Behavior Stage
        +
Weekly Tactical Trigger
        ↓
MTF Regime
```

例如：

```text
STRUCTURAL_BULLISH
+
Improving
+
Breakout
↓
BULLISH_CONFIRMED
```

而：

```text
STRUCTURAL_BULLISH
+
Deteriorating
+
Breakdown
↓
BULLISH_WARNING
```

这些映射在代码中是显式定义的。

#### 核心理解

```text
structural_regime
= 长期结构

mtf_regime
= 当前多周期综合状态
```

所以：

```text
STRUCTURAL_BULLISH
+
BULLISH_WARNING
```

完全可能同时存在。

意思是：

> 长期结构仍然偏多，但当前多周期状态已经出现警告。

---

## 3. `market_regime`：市场环境状态

它回答：

> **现在整个市场是风险偏好环境，还是风险规避环境？**

当前代码中的主要列表是：

| 值          | 含义     |
| ---------- | ------ |
| `risk_on`  | 风险偏好环境 |
| `neutral`  | 中性环境   |
| `risk_off` | 风险规避环境 |

回测稳健性模块明确按照这三种市场环境分组。

可以理解为：

```text
risk_on
→ 市场整体更愿意承担风险

neutral
→ 市场环境中性

risk_off
→ 市场整体偏避险
```

#### 重要区别

`market_regime` 不是这只股票本身的状态。

例如：

```text
Stock A:
STRUCTURAL_BULLISH
BULLISH_CONFIRMED

Market:
risk_off
```

这是可能的。

意思是：

> 个股本身很好，但整体市场环境不利。

因此它更适合作为：

> **外部环境过滤器 / 风险调整变量**

而不是替代个股结构判断。

---

## 4. `action_signal`：旧决策链的动作信号

它回答：

> **根据旧 MTF 决策映射，建议执行什么动作？**

当前代码映射为：

| `mtf_regime`                 | `action_signal` |
| ---------------------------- | --------------- |
| `BULLISH_CONFIRMED`          | `BUY`           |
| `BULLISH_STABLE`             | `HOLD`          |
| `BULLISH_WARNING`            | `REDUCE`        |
| `BEARISH_RECOVERY_CANDIDATE` | `WAIT`          |
| `BEARISH_CONFIRMED`          | `EXIT`          |
| `DATA_INSUFFICIENT`          | `WAIT`          |

代码中明确配置了这个映射。

所以：

```text
action_signal
```

本质上是：

> **把 `mtf_regime` 翻译成一个传统交易动作。**

---

## 5. 四者之间的关系

完整关系应该这样理解：

```text
                    ┌──────────────────┐
                    │ market_regime    │
                    │ 市场外部环境     │
                    │ risk_on/off      │
                    └────────┬─────────┘
                             │
                             ▼
┌──────────────────┐   ┌──────────────────┐
│ structural_regime│ → │    mtf_regime    │
│ 长期结构         │   │ 多周期综合状态   │
└────────┬─────────┘   └────────┬─────────┘
         │                      │
         │                      ▼
         │               ┌───────────────┐
         └──────────────→│ action_signal │
                         │ BUY/HOLD/...  │
                         └───────────────┘
```

更准确地说：

```text
长期结构
    ↓
structural_regime
    +
月度行为
    +
周线触发
    ↓
mtf_regime
    ↓
旧 Action Mapping
    ↓
action_signal

与此同时：

市场指数 + 波动环境
    ↓
market_regime
    ↓
风险调整 / 环境过滤
```

---

## 6. 用一个实例理解

假设：

```text
structural_regime = STRUCTURAL_BULLISH
mtf_regime        = BULLISH_WARNING
market_regime     = risk_off
action_signal     = REDUCE
```

应该读成：

#### 第一步：长期

```text
STRUCTURAL_BULLISH
```

长期结构仍偏多。

#### 第二步：当前多周期状态

```text
BULLISH_WARNING
```

但当前周期已经出现风险警告。

#### 第三步：市场

```text
risk_off
```

整体市场环境也不支持积极承担风险。

#### 第四步：旧动作

```text
REDUCE
```

因此旧系统建议减仓。

---

## 7. 这四个字段在新架构中的问题

这是与你现在 QCFP_MTF 升级最相关的地方。

当前：

```text
action_signal
```

属于旧的：

```text
MTF Regime
    ↓
Action Mapping
    ↓
BUY / HOLD / REDUCE / EXIT
```

而你正在建设的新架构是：

```text
Institutional State
    ↓
Institutional Permission
    ↓
Exit Event
    ↓
Swing Setup
    ↓
Retail FSM
    ↓
Position Sizing
    ↓
DecisionSnapshot
```

因此未来建议明确区分：

| 字段                         | 建议定位            |
| -------------------------- | --------------- |
| `structural_regime`        | 原始/上游结构证据       |
| `mtf_regime`               | Legacy MTF 综合状态 |
| `market_regime`            | 外部市场环境          |
| `action_signal`            | Legacy 动作基线     |
| `institutional_permission` | 新架构风险授权         |
| `next_fsm_state`           | 新架构仓位生命周期       |
| `target_position`          | 新架构正式目标仓位       |

也就是说：

> **不要让 `action_signal` 和新的 FSM Action 同时充当“正式决策”。**

当前代码测试仍明确把 `action_signal` 作为 `BUY / HOLD / REDUCE / WAIT / EXIT` 的传统动作输出。

---

### 最简总结

```text
structural_regime
= 这只股票长期结构是什么？

mtf_regime
= 多周期综合后，目前状态是什么？

market_regime
= 整个市场环境怎么样？

action_signal
= 旧 MTF 系统建议采取什么动作？
```

而对于你正在建设的 **Institutional Permission × Retail FSM** 新系统，最终正式决策应该逐步从：

```text
action_signal
```

迁移到：

```text
DecisionSnapshot
├── institutional_permission
├── exit_event
├── setup
├── previous_fsm_state
├── next_fsm_state
└── target_position
```

这样才能避免旧 `action_signal` 与新 FSM 决策同时成为两个“最终答案”。

我也可以创建一张图，把这四个字段与新的 `Institutional Permission → Retail FSM → Position Sizing` 决策链放在同一张架构图里。


---

# 解释Ablation -- 消融实验
当然。结合你这个 **QCFP-MTF** 系统来解释，Ablation 可以简单理解成：

> **把系统里的某一个模块“拿掉”，其他条件全部保持不变，然后观察结果发生了什么变化。**

它不是普通的“回测比较”，而是用来回答：

> **“这个模块到底有没有用？它到底贡献了什么？”**

---

## 1. 用一个最简单的例子理解

假设你的完整 QCFP-MTF 是：

```text
机构行为
   ↓
Permission
   ↓
Participation Budget
   ↓
Swing Setup
   ↓
FSM
   ↓
Position Sizing
   ↓
Risk Exit
   ↓
Final Target
```

完整模型叫：

```text
FULL
```

现在你想知道：

> **Institutional Permission 到底有没有价值？**

就做两个实验。

#### 实验 A：完整模型

```text
Institutional Permission = ON

机构状态
   ↓
Permission
   ↓
FSM
   ↓
仓位
   ↓
回测
```

得到：

```text
Annual Return = 18%
MDD           = -12%
Wave Capture  = 61%
```

#### 实验 B：拿掉 Permission

```text
Institutional Permission = OFF

机构状态
   ↓
FSM
   ↓
仓位
   ↓
回测
```

得到：

```text
Annual Return = 21%
MDD           = -25%
Wave Capture  = 68%
```

那么：

```text
Permission 的影响：

收益       -3%
MDD        +13%
Wave       -7%
```

这时候你就知道：

> Permission 可能降低了一部分收益，但明显降低了风险。

这就是 **Ablation**。

---

## 2. Ablation 不是简单的“两个策略比较”

这是最重要的一点。

普通策略比较：

```text
Strategy A
vs
Strategy B
```

可能两个策略同时改变了很多东西。

例如：

```text
A:
EMA + RSI + Permission + FSM

B:
MACD + Volume + No Permission + Different Stop
```

最后发现：

```text
A Sharpe = 1.2
B Sharpe = 1.0
```

你不知道：

> 到底是 EMA 有用？

还是：

> Permission 有用？

还是：

> Stop 有用？

所以这种比较**不能证明某个模块有贡献**。

---

## 3. Ablation 的核心原则：只改变一个东西

例如你的完整模型：

```text
FULL

Institutional Permission = ON
FSM                     = ON
Hard Exit               = ON
Daily Timing            = ON
Participation Budget    = ON
Position Sizing         = ON
```

做：

```text
Ablation-Permission

Institutional Permission = OFF
FSM                     = ON
Hard Exit               = ON
Daily Timing            = ON
Participation Budget    = ON
Position Sizing         = ON
```

唯一变化：

```text
Permission
```

这才有意义。

---

## 4. 为什么 QCFP-MTF 特别需要 Ablation？

因为你的系统不是一个简单的：

```text
BUY / SELL
```

而是一条复杂决策链：

```text
Evidence
 ↓
Institutional State
 ↓
Permission
 ↓
Participation
 ↓
Setup
 ↓
FSM
 ↓
Risk
 ↓
Sizing
 ↓
Final Target
```

模块非常多。

如果最后发现：

```text
Sharpe = 1.45
```

你不能因此说：

> “QCFP-MTF 很厉害。”

你还需要知道：

```text
为什么 1.45？
```

可能：

```text
Institutional Filter    +0.25
FSM                     +0.12
Hard Exit               +0.31
Position Sizing         +0.18
Daily Timing            -0.04
```

这样才知道系统真正的价值在哪里。

---

## 5. 你现在代码中的 Ablation

你上传的代码已经设计了不少 Ablation，例如：

```text
A0
A1
A2
...
A13
```

其中包括 Permission、FSM、Soft Exit、Hard Exit、Daily、Budget、Market Scale、Stop、Observation 等模块。

这说明你的设计思路已经是对的。

但是我上一条回答里特别指出：

> **现在应该把 Ablation 从“性能比较”升级成“机制比较”。**

这很重要。

---

## 6. 什么叫“机制 Ablation”？

假设：

```text
FULL
Sharpe = 1.40
```

Permission Ablation：

```text
NO_PERMISSION
Sharpe = 1.20
```

普通 Ablation 只能告诉你：

```text
Permission
Sharpe +0.20
```

但这还不够。

你真正应该继续问：

> Permission 做了什么？

于是继续统计：

```text
Permission ON

BLOCK      18%
WATCH      25%
TEST       32%
ALLOW      25%
```

以及：

```text
被 Permission 阻止的交易 = 143
```

其中：

```text
后来上涨 > 20% = 21
后来上涨 > 50% = 6
后来下跌 > 20% = 47
```

这时候你就知道：

> Permission 不是简单“减少交易”。

它实际上：

> **过滤掉了大量高风险参与机会，同时也错过了一小部分真正的大行情。**

这才是有研究价值的结果。

---

## 7. 对 QCFP-MTF 来说，Ablation 应该回答 5 个问题

### 问题一：这个模块是否提高收益？

例如：

```text
Annual Return
Sharpe
Profit Factor
```

---

### 问题二：这个模块是否降低风险？

例如：

```text
MDD
MAE
Volatility
Tail Loss
```

---

### 问题三：这个模块改变了什么交易行为？

例如：

```text
交易次数
平均仓位
平均持仓时间
Entry Delay
Exit Delay
Turnover
```

---

### 问题四：这个模块改变了什么波段能力？

这对你的系统非常重要。

例如：

```text
Wave Capture
MFE
MAE
Opportunity Miss
False Participation
Capital Efficiency
```

你的代码本身已经有这些 Retail Utility 指标。

---

### 问题五：这个模块是否违反 Governance？

这是你的 QCFP-MTF 与普通量化系统最大的区别之一。

例如 Permission Ablation：

```text
BLOCK + Target > 0
```

应该被检测。

FSM Ablation：

```text
FLAT → HOLDING
```

是否出现非法跳跃？

Hard Exit Ablation：

```text
Hard Exit
但 Target > 0
```

是否出现？

因此 Ablation 不只是：

```text
Performance
```

还应该检查：

```text
Governance
```

---

## 8. 一个完整的 QCFP-MTF Ablation 例子

假设完整模型：

```text
FULL
```

结果：

| 指标                  | FULL |
| ------------------- | ---: |
| 年化收益                |  18% |
| Sharpe              | 1.35 |
| MDD                 | -14% |
| Wave Capture        |  63% |
| False Participation |  18% |
| Capital Efficiency  | 0.82 |

现在去掉 Institutional Permission：

```text
A-PERM-OFF
```

结果：

| 指标                  | FULL | PERM OFF | Delta |
| ------------------- | ---: | -------: | ----: |
| 年化收益                |  18% |      21% |   +3% |
| Sharpe              | 1.35 |     1.18 | -0.17 |
| MDD                 | -14% |     -27% |  -13% |
| Wave Capture        |  63% |      68% |   +5% |
| False Participation |  18% |      31% |  +13% |
| Capital Efficiency  | 0.82 |     0.61 | -0.21 |

这个结果非常有意思。

它告诉你：

> Permission **不是提高收益的模块**。

而是：

> **风险过滤器 / 资金效率模块。**

所以如果只看 Annual Return：

```text
Permission 不好
```

但如果看整个系统：

```text
Permission 很有价值
```

这就是为什么你的 QCFP-MTF **不能只用 Sharpe / Return 做 Ablation**。

---

## 9. 再看 FSM Ablation

完整：

```text
Permission
 ↓
FSM
 ↓
Position
```

FSM OFF：

```text
Permission
 ↓
Position
```

假设：

```text
FULL:

Annual Return       18%
MDD                 -14%
Turnover             3.2
False Participation 18%
```

FSM OFF：

```text
Annual Return       19%
MDD                 -21%
Turnover             6.8
False Participation 29%
```

那么 FSM 的真正价值可能不是：

> “赚钱更多。”

而是：

> **让交易节奏更有纪律。**

特别适合你的：

```text
TESTING
BUILDING
HOLDING
TRIMMING
EXITING
COOLDOWN
```

这就是 FSM 的机制价值。

---

## 10. Hard Exit Ablation 更容易理解

完整：

```text
Hard Exit = ON
```

然后：

```text
Hard Exit = OFF
```

如果：

```text
ON:
MDD = -15%

OFF:
MDD = -31%
```

同时：

```text
Annual Return
ON  = 18%
OFF = 20%
```

你就能非常明确地说：

> Hard Exit 牺牲约 2% 收益，换取约 16 个百分点的 MDD 改善。

这比简单说：

> “Hard Exit 很重要。”

强得多。

---

## 11. Ablation 最容易犯的错误

### 错误 1：一次关掉多个模块

例如：

```text
Permission OFF
FSM OFF
Hard Exit OFF
```

然后说：

> “三个模块合起来没用。”

不成立。

因为你不知道是哪一个造成变化。

---

### 错误 2：Ablation 时改变数据

比如：

```text
FULL
使用 2018-2026

ABLATION
使用 2020-2026
```

不能比较。

---

### 错误 3：Ablation 时改变成本

比如：

```text
FULL:
Cost = 0.3%

ABLATION:
Cost = 0.1%
```

也不能比较。

---

### 错误 4：Ablation 时重新优化参数

这个非常危险。

例如：

```text
FULL:
EMA = 20

Permission OFF:
重新搜索最优 EMA
→ EMA = 13
```

那么你已经不是在测试：

> Permission 有没有用。

而是在测试：

> 两个不同优化后的系统谁更好。

---

## 12. 你这个系统最理想的 Ablation 结构

我建议最终做成：

```text
A0 = FULL
```

然后：

```text
A1 = Permission OFF
A2 = Participation Budget OFF
A3 = FSM OFF
A4 = Hard Exit OFF
A5 = Soft Exit OFF
A6 = Daily Timing OFF
A7 = Position Sizing OFF
A8 = Market Scale OFF
A9 = Stop OFF
A10 = Cooldown OFF
```

然后每一个都必须：

```text
Same Data
Same PIT
Same Universe
Same Cost
Same Execution
Same Benchmark
Same Initial Capital
Same Random Seed
Same Evaluation Window
```

唯一变化：

```text
One module
```

---

## 13. 更进一步：做 Ablation Matrix

最终不要只得到：

```text
A1
A2
A3
...
```

而是形成一张表：

| 模块           | Return Δ | Sharpe Δ | MDD Δ | Wave Δ | MAE Δ | Capital Efficiency Δ |
| ------------ | -------: | -------: | ----: | -----: | ----: | -------------------: |
| Permission   |       +? |       +? |    +? |     +? |    +? |                   +? |
| Budget       |       +? |       +? |    +? |     +? |    +? |                   +? |
| FSM          |       +? |       +? |    +? |     +? |    +? |                   +? |
| Hard Exit    |       +? |       +? |    +? |     +? |    +? |                   +? |
| Soft Exit    |       +? |       +? |    +? |     +? |    +? |                   +? |
| Daily Timing |       +? |       +? |    +? |     +? |    +? |                   +? |
| Sizing       |       +? |       +? |    +? |     +? |    +? |                   +? |

这样你一眼就知道：

> **QCFP-MTF 到底是哪些模块创造价值。**

---

## 14. 对你这个项目，我会把 Ablation 定义成一句话

> **Ablation = 在完全相同的历史信息、数据、成本、执行和测试条件下，只移除 QCFP-MTF 决策链中的一个机制，然后测量它对“收益、风险、交易行为、波段能力、资金效率、治理约束”的独立贡献。**

所以你的五个目标里面：

```text
不可越权
      ↓
可审计
      ↓
可回测
      ↓
可 Ablation
      ↓
牛散实战
```

实际上是层层递进的。

**没有“可审计”的 DecisionSnapshot，就很难做严谨 Ablation；没有统一 Canonical Decision，又很难保证 Ablation 比较的是同一个决策系统。**

这也是为什么我上一条把 **“Canonical 唯一化”列为 P0**。

---

# 解释Canonical Decision  
可以。结合你这个 **QCFP-MTF**，我把 **Canonical Decision** 说得尽量直白。

## 1. 一句话解释

**Canonical Decision = “唯一正式版本的最终决策”。**

也就是说：

> 对某一只股票、某一个交易日、某一套模型版本、某一份输入数据，**系统只能有一个被认可的正式交易决策结果**。

这个结果以后：

* 回测用它
* 报告用它
* Shadow 用它
* Ablation 用它
* 审计用它

而不是每个模块自己重新算一次。

---

## 2. 为什么需要 Canonical Decision？

假设今天：

```text
01951
2026-08-26
```

系统算出来：

```text
Institutional State = WATCH
Permission            = TEST
FSM                   = TESTING
Target Position       = 10%
```

这是一个决策。

但如果出现：

```text
报告模块：
Target = 10%

回测模块：
Target = 20%

Shadow：
Target = 0%

Ablation：
Target = 15%
```

那么问题来了：

> **到底哪个才是 QCFP-MTF 的真实决策？**

这就是 Canonical Decision 要解决的问题。

---

## 3. Canonical 的核心不是“一个函数”

这是最容易误解的地方。

Canonical Decision **不是简单地指一个 `canonical_decision()` 函数**。

它真正代表的是：

> **唯一的 Decision Authority（决策权威来源）。**

你的系统应该是：

```text
                    Evidence
                       ↓
                Canonical Engine
                       ↓
                DecisionSnapshot
                       ↓
                Canonical Decision
                       ↓
        ┌──────────────┼──────────────┐
        ↓              ↓              ↓
      Report         Backtest       Ablation
```

而不是：

```text
Evidence
   ├── Report 自己算一次
   ├── Backtest 自己算一次
   ├── Ablation 自己算一次
   └── Shadow 自己算一次
```

---

## 4. 在 QCFP-MTF 里，Canonical Decision 到底是什么？

根据你代码里的设计，它已经比较明确：

```text
Evidence
 ↓
Institutional State
 ↓
Institutional Permission
 ↓
Exit Event
 ↓
Setup
 ↓
Participation Budget
 ↓
FSM
 ↓
Position Sizing
 ↓
Permission Constraint
 ↓
Trade Quality
 ↓
Governance
 ↓
Final Target
```

最终产生：

```text
DecisionSnapshot
```

你代码里已经把这些信息放进 Snapshot，例如：

* `run_id`
* `institutional_state`
* `institutional_permission`
* `permission_cap`
* `exit_event`
* `setup_type`
* `base_fsm_state`
* `prev_fsm_state`
* `next_fsm_state`
* `raw_target_position`
* `target_position`
* `permission_constraint_applied`
* `primary_reason`
* `secondary_reasons`
* `participation_mode`
* `participation_cap`
* `position_class`
* `trade_quality`
* `feature_manifest_hash`
* `override_rule_ids`
* `input_fingerprint`
* `settings_hash`

这些字段已经说明：

> **DecisionSnapshot 实际上就是你 Canonical Decision 的载体。** 

---

## 5. 最关键的一点：Canonical Decision ≠ Signal

这是你这个系统特别需要区分的。

例如：

```text
MACD 金叉
```

只是：

```text
Signal
```

甚至：

```text
Setup = BREAKOUT
```

也只是：

```text
Setup
```

而：

```text
Institutional Permission = TEST
FSM = TESTING
Target = 10%
```

才是：

```text
Decision
```

所以：

```text
Signal
   ↓
Setup
   ↓
Permission
   ↓
FSM
   ↓
Sizing
   ↓
Decision
```

**Canonical Decision 是整条决策链的最终结果，不是某个指标。**

---

## 6. 为什么叫 Canonical？

`Canonical` 可以理解成：

> **标准的、规范的、唯一认可的版本。**

比如一本书有很多翻印版本：

```text
版本 A
版本 B
版本 C
```

你需要指定一个：

> **Canonical Edition**

作为正式版本。

QCFP-MTF 同样：

```text
Legacy Decision
Shadow Decision
Research Decision
Backtest Decision
Report Decision
```

这些都可能存在。

但必须指定：

```text
Canonical Decision
```

作为：

> **唯一事实源。**

---

## 7. 这和你之前问的 Ablation 有直接关系

例如你要测试：

> Permission 有没有用？

Canonical：

```text
FULL
 ↓
DecisionSnapshot
 ↓
Target = 20%
```

Ablation：

```text
Permission OFF
 ↓
DecisionSnapshot
 ↓
Target = 40%
```

然后比较。

重点来了：

**Ablation 也必须产生一个自己的 Canonical Decision。**

不能：

```text
FULL
   ↓
Canonical Engine

Permission OFF
   ↓
另一个临时算法
```

否则比较不公平。

应该是：

```text
                    Same Evidence
                         │
              ┌──────────┴──────────┐
              ↓                     ↓
        Canonical FULL       Canonical Ablation
              ↓                     ↓
       DecisionSnapshot       DecisionSnapshot
              ↓                     ↓
            Target                Target
              └──────────┬──────────┘
                         ↓
                    Compare
```

这才是真正严谨的 Ablation。

---

## 8. Canonical Decision 和 Ledger 的关系

可以把它们理解成：

```text
Canonical Decision
      │
      │ “我决定什么？”
      ↓
DecisionSnapshot
      │
      │ “把这个决定完整记录下来”
      ↓
Decision Ledger
      │
      │ “以后证明当时到底决定了什么”
      ↓
Audit
```

所以：

#### DecisionSnapshot

是：

> **这个时点的完整决策对象。**

#### Decision Ledger

是：

> **这个决策对象的正式、可追溯记录。**

---

## 9. 为什么你代码里强调 Ledger ONLY？

你上传的代码已经明确规定：

正式模式：

```text
RESEARCH_VALIDATION
PRODUCTION
AUDIT
```

要求：

> **Ledger ONLY**

如果 Ledger 找不到对应决策，就不能偷偷重新计算一个：

```text
FLAT / 0
```

作为正式结果。代码明确会抛出 `LedgerRequiredError`，而探索模式才允许 Shadow / NON_CANONICAL fallback。

这个设计非常重要。

因为否则：

```text
当时没有决策
        ↓
今天重新计算
        ↓
得到一个新结果
        ↓
假装这是历史决策
```

这就破坏了：

> **可审计 + 可回测。**

---

## 10. 一个非常直观的例子

假设：

```text
股票：01951
日期：2026-08-20
```

当时系统真正产生：

```text
Institutional State = COLD
Permission = WATCH
FSM = TESTING
Target = 0%
Reason = institutional pressure weak
```

那么 Canonical Decision 就是：

```text
Decision ID = D20260820-01951-xxxx

Permission = WATCH
FSM = TESTING
Target = 0%
```

两个月以后你改了参数：

```text
Permission Rule v2.6
```

重新运行：

```text
Permission = TEST
Target = 10%
```

**这个新结果不能覆盖原来的 Canonical Decision。**

因为：

```text
2026-08-20 当时的决策
≠
今天重新计算出来的结果
```

这就是 Canonical + Ledger 的意义。

---

## 11. Canonical Decision 对“不可越权”尤其重要

这是 QCFP-MTF 和普通量化策略非常不同的地方。

例如：

```text
Institutional Permission = WATCH
```

那么：

```text
FSM 说 BUY
```

不能直接：

```text
Target = 30%
```

Canonical Engine 必须执行：

```text
FSM raw target = 30%
          ↓
Permission cap = 10%
          ↓
Final target = 10%
```

所以：

```text
Raw Decision
      ↓
Governance
      ↓
Canonical Decision
```

**Canonical Decision 是已经经过权限约束的最终结果。**

不是：

```text
Raw Signal
```

---

## 12. 你可以把它理解成“法院最终判决”

这个类比非常简单：

```text
Evidence
    ↓
证据
    ↓
Institutional Analysis
    ↓
分析
    ↓
FSM / Risk / Sizing
    ↓
各种意见
    ↓
Governance
    ↓
最终裁决
```

最终裁决：

> **Canonical Decision**

后面的：

```text
Report
Backtest
Ablation
Audit
```

都不能再重新“判一次”。

只能读取这个最终裁决。

---

## 13. 所以我对你这个项目的核心要求可以浓缩成一句话

> **QCFP-MTF 必须做到“一次决策，多处消费”，而不是“多处计算，同一个名字”。**

即：

```text
                  ONE
             Decision Engine
                    ↓
             ONE DecisionSnapshot
                    ↓
               ONE Ledger
                    ↓
       ┌────────────┼────────────┐
       ↓            ↓            ↓
    Backtest      Report       Ablation
```

这就是 **Canonical Decision**。

---

## 14. 最后区分 5 个概念

你后面做 QCFP-MTF 时，建议始终把这几个词分开：

| 概念                     | 人话                 |
| ---------------------- | ------------------ |
| **Evidence**           | 我看到了什么             |
| **Signal / Setup**     | 市场可能在发生什么          |
| **Raw Target**         | 如果不考虑权限，我想买多少      |
| **Canonical Decision** | 综合所有规则后，正式决定怎么做    |
| **Ledger**             | 把这个正式决定永久、可审计地记录下来 |

所以最终链条应该是：

```text
Evidence
   ↓
Signal / Setup
   ↓
Institutional Permission
   ↓
FSM
   ↓
Risk
   ↓
Sizing
   ↓
Governance
   ↓
★ Canonical Decision ★
   ↓
Decision Ledger
   ↓
Backtest / Report / Ablation / Audit
```

**对你的 QCFP-MTF 来说，Canonical Decision 是整个系统的“决策单一事实源（Single Source of Truth）”。**

这也是为什么我之前把“Canonical 唯一化”列为 P0：目前源码已经有这个设计，但还存在 Legacy 路径；真正完成后，你的“不可越权 + 可审计 + 可回测 + 可 Ablation”才会形成一个闭环。

---
# 解释shadow
可以。结合你这个 **QCFP-MTF**，`Shadow` 可以理解成：

> **“影子运行”：系统把一个新的/实验中的决策模型在旁边跑一遍，但暂时不让它真正控制交易。**

它和 **Backtest、Ablation、Canonical Decision** 都不一样。

---

## 1. 最简单的例子

假设现在生产系统正在运行：

```text
生产模型
01951
Permission = WATCH
Target = 0%
```

你准备测试新版本：

```text
QCFP-MTF 2.6
Permission = TEST
Target = 10%
```

但你还不敢让 2.6 真正交易。

于是：

```text
真实市场数据
       │
       ├──────────────→ Production
       │                   ↓
       │              Target = 0%
       │
       └──────────────→ Shadow 2.6
                           ↓
                       Target = 10%
```

Shadow 的意思就是：

> **2.6 可以“发表意见”，但没有交易权。**

---

## 2. Shadow 和 Production 的区别

可以把它理解成：

| 模式         | 会计算？ |   会产生正式决策？ | 会下单？ |
| ---------- | ---: | ---------: | ---: |
| Production |    ✅ |          ✅ |    ✅ |
| Shadow     |    ✅ | ⚠️ 实验/影子决策 |    ❌ |
| Backtest   |    ✅ |       历史模拟 |    ❌ |
| Ablation   |    ✅ |       实验决策 |    ❌ |
| Report     | ❌/读取 |         读取 |    ❌ |

所以：

> **Shadow 不是 Backtest。**

Shadow 是：

> **“现在真的发生了什么市场数据，我的新模型如果当时运行，会怎么决策？”**

---

## 3. 为什么需要 Shadow？

这是你的 QCFP-MTF 非常重要的一层。

假设你修改了：

```text
Institutional Permission
```

从：

```text
WATCH → TEST
```

你当然不能直接：

```text
代码改完
 ↓
上线
 ↓
真钱交易
```

风险太大。

可以先：

```text
Production
    ↓
继续正常交易

Shadow 2.6
    ↓
同步计算
    ↓
记录它想做什么
```

运行一段时间后比较：

```text
Production vs Shadow
```

例如：

| 日期   | Production | Shadow |
| ---- | ---------- | ------ |
| 8/20 | 0%         | 10%    |
| 8/21 | 0%         | 10%    |
| 8/22 | 10%        | 20%    |
| 8/25 | 0%         | 0%     |

然后你可以研究：

> Shadow 为什么和 Production 不一样？

---

## 4. Shadow 最重要的价值：验证“新模型到底改变了什么”

例如你改了 Permission。

Shadow 运行 3 个月后：

```text
Shadow 新增交易：153
```

再看：

```text
153 次新增交易
 ↓
盈利：92
亏损：61
```

进一步：

```text
平均收益：+8.2%
平均 MAE：-4.1%
Wave Capture：67%
```

你就可以判断：

> 新 Permission 是不是改善了参与机会。

而且**没有冒真实资金风险**。

---

## 5. Shadow 和 Ablation 的区别

这两个特别容易混。

### Ablation

回答：

> **“如果我把某个模块拿掉，会发生什么？”**

例如：

```text
FULL
Permission ON
```

vs

```text
ABLATION
Permission OFF
```

通常是：

```text
历史数据
 ↓
反复实验
 ↓
比较性能
```

---

### Shadow

回答：

> **“如果我现在让新模型运行，它实际上会怎么做？”**

例如：

```text
实时/当前数据
       ↓
Production
       ↓
Shadow
```

所以：

```text
Ablation = 实验室实验
Shadow   = 影子运行
```

---

## 6. Shadow 和 Canonical Decision 的关系

这点对你的系统非常重要。

**Shadow 不应该绕开 Canonical Engine。**

正确方式：

```text
当前 Evidence
      │
      ├───────────────┐
      ↓               ↓
Production 2.5    Shadow 2.6
      ↓               ↓
Canonical Engine  Canonical Engine
      ↓               ↓
DecisionSnapshot  DecisionSnapshot
      ↓               ↓
Target 0%         Target 10%
```

也就是说：

> **Shadow 只是另一套实验配置/版本，但仍然必须经过同一套 Canonical Decision Governance。**

否则 Shadow 没有意义。

---

## 7. 这正好对应你的“五个目标”

Shadow 对五个目标都有帮助。

#### ① 不可越权

Shadow 也必须检查：

```text
BLOCK + Target > 0
WATCH + Increase
Hard Exit + Target > 0
非法 FSM transition
```

所以：

> Shadow 不能因为是实验模式就绕过 Governance。

---

#### ② 可审计

Shadow 应该记录：

```text
run_id
decision_id
model_version
rule_version
settings_hash
input_fingerprint
target_position
permission
FSM
reason
```

这样以后可以问：

> 2026-08-20 Shadow 2.6 为什么想买 10%？

可以完整回答。

---

#### ③ 可回测

Shadow 结果以后可以拿真实发生的行情验证：

```text
Shadow Decision
       ↓
未来实际价格
       ↓
MFE
MAE
Wave Capture
```

---

#### ④ 可 Ablation

甚至可以同时跑：

```text
Production
Shadow Full
Shadow Permission-Off
Shadow FSM-Off
```

然后观察它们的决策差异。

---

#### ⑤ 牛散实战

Shadow 最有价值的是：

> **不急着上线，但先看看新规则在真实市场环境下到底会做出什么交易。**

这比单纯看历史回测更接近实战。

---

## 8. 你代码里的 Shadow 是什么含义？

你上传的代码中已经有明确的 Shadow fallback 机制。

例如在加载正式决策时：

```text
Ledger
   ↓
找不到
   ↓
Shadow
   ↓
匹配 stock_code
decision_date
settings_hash
model_version
rule_version
```

如果匹配成功，会返回：

```text
shadow:<filename>
```

作为决策来源。

而正式模式：

```text
research_validation
production
audit
```

如果 Ledger 中没有正式决策，会直接：

```text
LedgerRequiredError
```

禁止偷偷使用 Shadow 或重新计算。

这个设计我认为是**正确的**。

---

## 9. 为什么正式模式不能随便用 Shadow？

因为 Shadow 是：

> **影子决策**

而不是：

> **正式历史事实。**

举个例子。

8 月 20 日：

```text
Production:
Target = 0%
```

Shadow：

```text
New Model:
Target = 20%
```

8 月 30 日你发现：

```text
股票涨了 30%
```

不能说：

> “QCFP-MTF 当时买了 20%。”

因为实际上：

> **Production 当时没有买。**

只能说：

> **Shadow 模型当时给出了 20% 的目标仓位。**

这个区别对于你的“可审计”非常重要。

---

## 10. Shadow 应该保存什么？

我建议你的 Shadow Snapshot 至少保存：

```text
Shadow Decision
├── run_id
├── decision_id
├── decision_date
├── stock_code
│
├── model_version
├── rule_version
├── schema_version
├── settings_hash
├── input_fingerprint
├── feature_manifest_hash
│
├── institutional_state
├── institutional_permission
├── participation_mode
├── setup_type
│
├── prev_fsm_state
├── next_fsm_state
│
├── raw_target_position
├── permission_cap
├── target_position
│
├── exit_event
├── primary_reason
├── secondary_reasons
│
└── governance_status
```

这样 Shadow 才真正有研究价值。

---

## 11. 我尤其建议增加一个东西：Shadow Diff

不要只保存：

```text
Shadow Target = 20%
```

应该自动生成：

```text
Production vs Shadow
```

例如：

```text
┌──────────────────────────────┐
│ 01951 2026-08-26             │
├──────────────────────────────┤
│ Production                   │
│ Permission = WATCH           │
│ FSM        = TESTING         │
│ Target     = 0%              │
│                              │
│ Shadow 2.6                   │
│ Permission = TEST             │
│ FSM        = TESTING         │
│ Target     = 10%             │
│                              │
│ Difference                   │
│ Permission: WATCH → TEST     │
│ Target:       0% → 10%       │
│ Reason: Institutional F ↑   │
└──────────────────────────────┘
```

这个东西对于调模型非常有价值。

---

## 12. Shadow 最终应该形成一条“晋级链”

我建议 QCFP-MTF 以后采用：

```text
开发
 ↓
Unit Test
 ↓
Backtest
 ↓
Ablation
 ↓
OOS
 ↓
Shadow
 ↓
Production
```

尤其：

```text
Shadow
```

应该成为 **Production 前最后一道验证门**。

例如：

#### 阶段 1

```text
Shadow 运行 1 个月
```

#### 阶段 2

检查：

```text
Decision Mismatch
Governance Violation
PIT Violation
Target Drift
```

#### 阶段 3

检查实战指标：

```text
Wave Capture
MAE
MFE
False Participation
Capital Efficiency
```

#### 阶段 4

全部通过：

```text
Shadow → Production
```

---

## 13. 一句话区分你现在几个核心概念

你可以把它们记成：

```text
Canonical Decision
= 正式决定“应该怎么做”

Ledger
= 把这个决定记录下来

Backtest
= 如果过去这样做，会发生什么？

Ablation
= 如果拿掉某个机制，会发生什么？

Shadow
= 如果现在让新模型运行，它会怎么做，但暂时不给它交易权？
```

所以整个 QCFP-MTF 可以理解成：

```text
                 新模型
                   │
        ┌──────────┴──────────┐
        ↓                     ↓
     Backtest              Shadow
        ↓                     ↓
   历史上怎么样？          现在会怎么样？
        │                     │
        └──────────┬──────────┘
                   ↓
               Production
                   ↓
                真交易
```

**最重要的一点：Shadow 不是“偷偷交易”，而是“只产生决策、不产生交易权”。**

对于你的 **“不可越权 + 可审计 + 可回测 + 可 Ablation + 牛散实战”** 五个目标，Shadow 的定位就是：

> **在不承担真实交易风险的情况下，让新版本接受真实市场环境的实战考核。**

---
# shadow 是模拟盘交易吗？
不完全是。

在你这个 **QCFP-MTF / 量化研究系统**的语境里，`Shadow` 更准确地理解为：

> **影子运行（Shadow Mode / Shadow Trading）**，可以是模拟盘交易的一种形式，但重点不是“模拟下单”，而是**跟踪系统如果真实执行，会产生什么交易行为，而不真正下单**。

可以这样区分：

| 模式                  | 是否真实下单 | 是否产生模拟持仓 | 是否使用实时/最新数据 | 目的           |
| ------------------- | -----: | -------: | ----------: | ------------ |
| Backtest            |      ❌ |        ✅ |        历史数据 | 验证历史表现       |
| Paper / Sim Trading |      ❌ |        ✅ |     实时/最新数据 | 模拟真实交易       |
| **Shadow Trading**  |      ❌ |    通常是 ✅ |  通常是实时/最新数据 | 观察真实运行中的策略行为 |
| Live Trading        |      ✅ |        ✅ |        实时数据 | 真正交易         |

### 对你的项目，我建议把 Shadow 定义得更严格

```text
Research
   ↓
Backtest
   ↓
Walk-forward / OOS
   ↓
Shadow
   ↓
Live
```

Shadow 阶段每天正常运行：

```text
真实数据
  ↓
PIT / Universe
  ↓
QCFP
  ↓
MTF
  ↓
Risk Gate
  ↓
Target Position
  ↓
模拟成交
```

但是：

```text
Target Position
      ↓
   ❌ 不提交券商订单
```

同时记录：

```text
signal_time
decision_time
target_position
simulated_entry
simulated_exit
simulated_cost
slippage
turnover
P&L
drawdown
```

这样 Shadow 最有价值，因为它可以回答：

> **这个模型在真正面对每天的新数据时，是否按照我们设计的方式稳定地产生信号？**

---

### 对你现在这个项目尤其重要

你前面代码审查里有几个问题——**PIT、Signal→Return Alignment、止损执行价格、交易成本、Liquidity**——其实非常适合在 Shadow 阶段继续验证。

例如：

```text
Backtest:
2021–2026 历史回测
        ↓
Shadow:
2026-08-01 开始
        ↓
每天记录：
“如果今天真实执行，我会做什么？”
        ↓
几个月后比较：
Shadow simulated P&L
vs
Backtest expectations
```

所以我会建议你把它定义成：

> **Shadow = 不真实下单的生产级策略运行 + 模拟交易账本。**

而不是简单理解成“模拟盘”。

如果你的系统以后真的要接券商/API，我还建议把 **Shadow 和 Paper Trading 分成两个状态**：`SHADOW_SIGNAL` 只验证信号和决策链，`PAPER_EXECUTION` 才验证订单、成交、滑点和持仓管理。


---

# 解释证书哈希逻辑  
可以。结合你当前 QCFP-MTF 的 `DecisionCertificate` 设计，**证书哈希不是“给交易打一个编号”这么简单，而是给一次完整决策建立一个可验证的数字指纹**。

核心目的：

> **证明“当时系统究竟基于什么输入、什么规则、什么状态，产生了什么决策”，并且以后可以验证它有没有被偷偷修改。**

---

## 1. 先理解整个逻辑

一次决策大致是：

```text
市场数据
   ↓
PIT Evidence
   ↓
Institutional State
   ↓
Permission
   ↓
Setup / TQS
   ↓
Risk
   ↓
FSM
   ↓
Sizing
   ↓
Governance
   ↓
Final Target
```

然后系统生成：

```text
DecisionCertificate
```

例如：

```text
DecisionCertificate
{
    symbol: "00371",
    decision_time: "2026-08-21 15:00",

    institutional_state: "DISTRIBUTION",
    permission: "WATCH",

    fsm_from: "HOLDING",
    fsm_to: "EXITING",

    previous_position: 0.40,
    raw_target: 0.00,
    final_target: 0.00,

    hard_exit: true,

    reason_codes: [
        "INST_DISTRIBUTION",
        "WEEKLY_BREAKDOWN",
        "RISK_EXTREME",
        "HARD_EXIT"
    ],

    model_version: "...",
    rule_version: "...",
    schema_version: "...",

    input_fingerprint: "...",
    settings_hash: "..."
}
```

然后对**标准化后的证书内容**计算：

```text
SHA-256
```

得到：

```text
certificate_hash
```

例如：

```text
8f6e4c7d...
```

---

## 2. 哈希到底是什么？

可以简单理解成：

```text
任意长度的数据
       ↓
    SHA-256
       ↓
固定长度指纹
```

例如：

```text
"HELLO"
```

得到一个固定长度的 hash。

如果变成：

```text
"HELLO!"
```

哪怕只增加一个字符，hash 也会发生巨大变化。

所以：

```text
Certificate A
      ↓
SHA256
      ↓
ABC123...

Certificate B
      ↓
SHA256
      ↓
9F72D...
```

两者不会因为“看起来差不多”而得到相同指纹。

---

## 3. 为什么 QCFP-MTF 需要这个？

因为你的目标之一是：

> **可审计**

假设 8 月 21 日系统产生：

```text
00371
Permission = WATCH
FSM = EXITING
Final Target = 0
```

一个月后有人打开数据库，看到：

```text
Permission = ALLOW
FSM = HOLDING
Final Target = 40%
```

那么问题来了：

> 是系统当时真的这样决定的，还是后来有人改过？

如果只有 JSON / 数据库记录：

```text
decision.json
```

你很难证明。

但如果当时已经有：

```text
certificate_hash = A7F82...
```

现在重新计算：

```text
当前证书 → SHA256 → B91C4...
```

发现：

```text
A7F82...
≠
B91C4...
```

就知道：

> **证书内容发生过变化。**

这就是哈希的审计价值。

---

## 4. 但是有一个非常重要的区别

#### 哈希可以证明：

> **内容有没有变化。**

#### 哈希不能单独证明：

> **原始内容一定是真的。**

这是非常重要的。

例如：

```text
原始证书
Permission = WATCH
```

攻击者如果把：

```text
Permission = ALLOW
```

改掉，然后重新计算 SHA-256：

```text
新的 certificate_hash
```

单看这个文件，它依然是“内部一致”的。

所以真正可靠的审计体系应该是：

```text
Certificate
     +
Hash
     +
Immutable Ledger
     +
Version Identity
     +
Input Fingerprint
     +
Timestamp
```

而不是：

```text
Certificate + Hash
```

就认为不可篡改。

---

## 5. 你现在的设计里，应该有 4 层 Hash

这是我建议你特别注意的地方。

### 第一层：Evidence Hash

证明：

> **输入数据是什么。**

例如：

```text
feature_manifest_hash
```

包含：

```text
Q
C
F
P
MTF features
PIT metadata
```

---

### 第二层：Settings Hash

证明：

> **当时用了什么参数。**

例如：

```text
settings_hash
```

包括：

```text
thresholds
weights
risk limits
permission rules
FSM parameters
sizing parameters
```

---

### 第三层：Decision / Certificate Hash

证明：

> **输入 + 参数 + 状态 → 最终产生了什么决策。**

例如：

```text
certificate_hash
```

---

### 第四层：Ledger Hash

证明：

> **这个 Certificate 在决策历史中的位置。**

例如：

```text
previous_ledger_hash
        ↓
current_certificate_hash
        ↓
ledger_entry_hash
```

这样就可以进一步形成：

```text
D1 → D2 → D3 → D4 → D5
```

一旦修改：

```text
D3
```

那么：

```text
D3 hash
   ↓
D4 previous hash
   ↓
D5 previous hash
```

后面的链都会断。

这就是 **Hash Chain**。

---

## 6. 推荐 QCFP-MTF 使用的结构

最终可以做成：

```text
                    Evidence
                       │
                       ↓
              feature_manifest_hash
                       │
                       ↓
                   Decision
                       │
          ┌────────────┴────────────┐
          ↓                         ↓
    settings_hash              input_hash
          │                         │
          └────────────┬────────────┘
                       ↓
              DecisionCertificate
                       │
                       ↓
              certificate_hash
                       │
                       ↓
                 DecisionLedger
                       │
                       ↓
              ledger_entry_hash
                       │
                       ↓
               next previous_hash
```

---

## 7. 最关键的问题：到底 Hash 哪些字段？

**不能简单地把 Python 对象直接 `hash()`。**

例如：

```python
hash(certificate)
```

不适合你的系统。

因为你需要：

> **跨机器、跨进程、跨时间确定性一致。**

应该：

```text
Certificate
    ↓
Canonical Serialization
    ↓
UTF-8 bytes
    ↓
SHA-256
    ↓
certificate_hash
```

---

## 8. 什么叫 Canonical Serialization？

例如原始 Python dict：

```python
{
    "symbol": "00371",
    "permission": "WATCH",
    "final_target": 0.0
}
```

必须转换成固定形式：

```json
{"final_target":0.0,"permission":"WATCH","symbol":"00371"}
```

要求：

```text
字段排序固定
浮点格式固定
日期格式固定
枚举格式固定
None/null 固定
Unicode 编码固定
```

然后：

```text
UTF-8
↓
SHA-256
```

---

## 9. 为什么字段排序非常重要？

例如同样的信息：

```json
{"symbol":"00371","permission":"WATCH"}
```

和：

```json
{"permission":"WATCH","symbol":"00371"}
```

语义一样。

但是字符串不同。

如果直接 hash：

```text
Hash(A) ≠ Hash(B)
```

这会导致 Replay 失败。

所以必须：

```python
json.dumps(
    data,
    sort_keys=True,
    separators=(",", ":"),
    ensure_ascii=False
)
```

形成 canonical representation。

---

## 10. 浮点数是更危险的问题

例如：

```text
0.3
```

在不同计算路径中可能出现：

```text
0.30000000000000004
```

那么：

```text
Hash("0.3")
```

和：

```text
Hash("0.30000000000000004")
```

完全不同。

因此你的 Certificate 里：

```text
position
target
risk
TQS
scores
```

最好规定统一精度。

例如：

```text
target → 6 decimals
risk → 6 decimals
score → 6 decimals
```

或者对需要审计的 Decimal 使用明确的字符串表示。

---

## 11. Hash 的输入不要包括 Hash 自己

这是一个经典问题。

不能：

```text
certificate
    ↓
加入 certificate_hash
    ↓
再 hash
```

否则：

```text
Hash(
    Certificate + Hash(Certificate)
)
```

会产生递归问题。

所以：

```text
CertificatePayload
       ↓
SHA256
       ↓
certificate_hash
```

最终保存：

```text
{
    ...payload,
    "certificate_hash": "..."
}
```

---

## 12. Certificate Hash 和 Input Hash 不应该混为一谈

这个区别对你的系统非常重要。

#### Input Hash

回答：

> **“当时喂给模型的东西是什么？”**

例如：

```text
input_hash = SHA256(
    PIT Evidence
    + feature snapshot
)
```

---

#### Settings Hash

回答：

> **“当时使用什么规则？”**

例如：

```text
settings_hash = SHA256(
    DecisionConfig
)
```

---

#### Certificate Hash

回答：

> **“在这些输入和规则下，系统最终做出了什么决定？”**

例如：

```text
certificate_hash = SHA256(
    canonical DecisionCertificate
)
```

---

## 13. 这样 Replay 就非常漂亮了

假设历史记录：

```text
Decision ID:
00371-20260821-001
```

数据库保存：

```text
input_hash
settings_hash
certificate_hash
```

现在重新运行：

```text
历史 Evidence
      ↓
同一个 Decision Engine
      ↓
同一个 Config
      ↓
重新生成 Certificate
      ↓
重新计算 hash
```

得到：

```text
old_certificate_hash
=
new_certificate_hash
```

那么：

> **这次决策被成功重放。**

---

## 14. 如果不一样怎么办？

不要直接说：

> 模型错了。

应该进入：

```text
REPLAY_MISMATCH
```

然后比较：

```text
Input
Settings
Version
Previous State
Decision
```

例如：

```text
Input Hash
    PASS

Settings Hash
    PASS

Model Version
    PASS

Previous State
    FAIL

Decision
    FAIL
```

那么原因很可能是：

> Stateful FSM 初始状态不同。

---

## 15. 这也是为什么 Previous State 必须进入 Certificate

你的系统是 Stateful 的。

例如：

```text
Day 1
FLAT → TESTING

Day 2
TESTING → BUILDING

Day 3
BUILDING → HOLDING
```

如果 Day 3 只记录：

```text
HOLDING
```

是不够的。

必须记录：

```text
previous_fsm = BUILDING
next_fsm = HOLDING
```

以及：

```text
previous_position
```

因为：

```text
同样的市场数据
+
不同 previous_state
```

可能产生不同决策。

所以：

> **State 是 Certificate 的一部分。**

---

## 16. 更进一步：Certificate 应该记录“决策证明”

我建议最终 Certificate 不只是：

```text
BUY / SELL / HOLD
```

而是：

```text
INPUT
STATE
PERMISSION
CONSTRAINTS
TRANSITION
SIZING
FINAL DECISION
```

例如：

```text
INPUT
C↓ F↓ P↓

↓
Institutional State
DISTRIBUTION_STRONG

↓
Permission
WATCH

↓
Setup
VALID

↓
Risk
EXTREME

↓
Hard Exit
TRUE

↓
Previous Position
40%

↓
Candidate Target
40%

↓
Governance
VETO

↓
Final Target
0%

↓
Action
EXIT
```

然后：

```text
certificate_hash
```

就是这整个过程的指纹。

这才符合你提出的：

> **不可越权 + 可审计。**

---

## 17. 最后一个非常重要的边界

**SHA-256 ≠ 数字签名。**

如果未来你真的要做到：

> “第三方可以验证这个决策确实由某个可信系统产生，而且系统方不能事后否认。”

那么下一层才是：

```text
Certificate
      ↓
SHA-256
      ↓
Digital Signature
      ↓
Private Key
```

验证方使用：

```text
Public Key
```

验证签名。

不过对于目前 QCFP-MTF 的研究/Shadow/回测阶段，**先把 Canonical Certificate + SHA-256 + Append-only Ledger + Replay 做扎实就够了**。

---

## 18. 我建议 QCFP-MTF 最终采用这个完整模型

```text
                 INPUT
                   │
                   ↓
              input_hash
                   │
                   ↓
          Decision Engine
                   │
       ┌───────────┼───────────┐
       ↓           ↓           ↓
   State       Settings      Version
       │           │           │
       ↓           ↓           ↓
 previous     settings_hash  rule/model
 state
       │           │           │
       └───────────┼───────────┘
                   ↓
          Decision Certificate
                   │
                   ↓
          canonical serialization
                   │
                   ↓
                SHA-256
                   │
                   ↓
          certificate_hash
                   │
                   ↓
          Append-only Ledger
                   │
                   ↓
          previous_ledger_hash
                   │
                   ↓
              next decision
```

这样以后你可以非常明确地回答五个问题：

| 问题         | 对应机制                            |
| ---------- | ------------------------------- |
| 当时输入是什么？   | `input_hash`                    |
| 当时规则是什么？   | `settings_hash` + version       |
| 当时状态是什么？   | Certificate                     |
| 最终为什么这样交易？ | Reason / Constraint Trace       |
| 后来有没有被修改？  | Certificate Hash + Ledger Chain |
| 今天能不能重现？   | Replay + Hash                   |

**这才是“证书哈希”在 QCFP-MTF 中真正应该发挥的作用：不是为了炫技，而是把一次交易决策变成一个可以被验证、重放和追责的不可变研究对象。**


---

# 解释Wave 效用

在你这套 **QCFP-MTF** 系统里，如果你说的 **“Wave 效用”** 是指 Wave（波段/波动阶段）在整个决策框架中的作用，那么它可以理解为：

> **Wave 不是用来直接预测涨跌的，而是用来描述“当前价格行为处于什么阶段”，从而帮助系统判断当前信号的持续性、风险和仓位。**

更直观地说：

```text
Structural = 长期处于什么状态？
Behavioral = 中期正在发生什么变化？
Wave       = 当前这轮价格运动走到哪一步？
Tactical   = 现在有没有明确的交易触发？
Risk       = 即使方向正确，现在能不能持仓？
```

---

## 1. Wave 最核心的效用：把“一个信号”变成“一个过程”

单看价格信号：

```text
Breakdown
```

信息其实不够。

因为同样是 Breakdown，可能是：

### 情形 A：第一次跌破

```text
上涨
 ↓
震荡
 ↓
第一次 Breakdown
```

这可能只是：

> 正常回调 / 假突破。

### 情形 B：连续 Breakdown

```text
Breakdown
 ↓
反弹失败
 ↓
再次 Breakdown
 ↓
继续创新低
```

这就更像：

> 下跌趋势正在形成。

因此 Wave 的价值就在于：

**把单点信号变成时间序列上的“演化过程”。**

---

# 2. 在你的系统里，它尤其适合解决“滞后问题”

你目前的 00371 案例非常典型：

```text
Quarterly
STRUCTURAL_BULLISH

Monthly
Improving

Weekly
Breakdown

Daily
DAILY_DECLINE

Risk
Extreme

Action
EXIT
```

这里存在明显的时间尺度冲突。

季度仍然是 Bullish，但周线和日线已经恶化。

如果只看 Quarterly：

```text
Bullish → HOLD
```

很容易过于迟钝。

Wave 的作用就是观察：

```text
Bullish
 ↓
第一次恶化
 ↓
Breakdown
 ↓
连续 Breakdown
 ↓
反弹失败
 ↓
下跌 Wave 确认
```

因此它是一个**中间层的动态状态描述器**。

---

# 3. Wave 与 State 的区别

这是最重要的一点。

### State

回答：

> **“现在是什么状态？”**

例如：

```text
STRUCTURAL_BULLISH
IMPROVING
BREAKDOWN
```

### Wave

回答：

> **“这个状态是刚刚出现，还是正在发展，还是已经衰竭？”**

例如：

```text
Breakdown #1
Breakdown #2
Breakdown #3
```

或者：

```text
Impulse
Correction
Recovery
Failure
Continuation
```

因此：

```text
State = 静态截面
Wave  = 动态路径
```

---

# 4. Wave 真正有价值的地方：判断“信号质量”

假设两个股票今天都是：

```text
Breakdown
```

### 股票 A

过去：

```text
BULLISH
BULLISH
BULLISH
BREAKDOWN
```

### 股票 B

过去：

```text
BREAKDOWN
BREAKDOWN
BREAKDOWN
BREAKDOWN
```

如果只看当前 State：

```text
A = Breakdown
B = Breakdown
```

完全一样。

但 Wave 信息告诉你：

```text
A = 新出现的风险
B = 已经持续的风险
```

这两个信号的交易意义完全不同。

---

# 5. 所以 Wave 可以产生一个非常有用的变量：Wave Age

例如：

```text
wave_age = 当前状态连续持续的周期数
```

那么：

```text
Breakdown age = 1
```

和：

```text
Breakdown age = 5
```

就可以区别对待。

进一步可以定义：

```text
Wave Strength
Wave Age
Wave Direction
Wave Acceleration
Wave Failure
Wave Recovery
```

例如：

```text
Wave:
    direction = DOWN
    age = 3
    strength = 0.82
    acceleration = +0.35
```

这比单纯：

```text
tactical_signal = Breakdown
```

的信息量大得多。

---

# 6. Wave 对仓位的价值尤其明显

我认为这是 Wave 在你这个系统里最值得发展的用途。

例如：

```text
Breakdown #1
→ target 75%

Breakdown #2
→ target 50%

Breakdown #3
→ target 25%

Breakdown + daily decline
→ target 0%
```

也就是说：

> **Wave 不一定负责决定“买还是卖”，而可以负责决定“这个风险正在变得多严重”。**

最终：

```text
State
 ↓
Wave
 ↓
Risk
 ↓
Position
```

这样比直接：

```text
Breakdown → EXIT
```

更加连续。

---

# 7. Wave 还能识别“假动作”

这是它非常重要的第二个效用。

例如：

```text
上涨
 ↓
Breakdown
 ↓
2周后重新站回 MA20
 ↓
Recovery
```

那么第一次 Breakdown 很可能属于：

```text
failed wave
```

而不是完整的 bearish wave。

反过来：

```text
Breakdown
 ↓
反弹
 ↓
无法突破前高
 ↓
再次 Breakdown
```

这就是：

```text
failed recovery
```

它的风险意义通常更强。

---

# 8. Wave 和你现有的 Downside Risk 很适合结合

你现在已经有：

```text
Downside Risk
```

并且代码明确要求：

> Downside Risk 的权限高于 HOLD。

所以可以进一步形成：

```text
Wave
 ↓
Wave Severity
 ↓
Downside Risk
 ↓
Action
```

例如：

| Wave 状态                      | Risk       | Action      |
| ---------------------------- | ---------- | ----------- |
| 第一次 Breakdown                | Medium     | HOLD/REDUCE |
| 连续 Breakdown                 | High       | REDUCE      |
| Breakdown + Recovery Failure | High       | REDUCE      |
| Breakdown + Daily Decline    | Extreme    | EXIT        |
| Recovery                     | Risk 开始下降  | 观察          |
| Confirmed Recovery           | Medium/Low | WAIT/ADD    |

这样 Wave 就不再是一个“装饰指标”，而成为**风险状态的时间维度**。

---

# 9. 但有一个非常重要的问题：Wave 不能只是“人为命名”

这是我审查你代码后特别想强调的。

如果 Wave 最终只是：

```text
if breakdown:
    wave = "BEARISH_WAVE"
```

那么它实际上没有增加多少信息。

真正有用的 Wave 必须有**独立的信息维度**。

至少应该回答：

```text
1. Wave 从什么时候开始？
2. 当前处于第几个阶段？
3. Wave 强度是否增加？
4. 是否出现加速？
5. 是否出现反弹？
6. 反弹是否失败？
7. Wave 是否已经结束？
```

否则：

```text
Wave = Breakdown
```

实际上只是：

```text
Wave ≈ Tactical Signal
```

那就属于重复建模。

---

# 10. 对你这个 QCFP-MTF，我建议 Wave 最终定义成这样

我会建议不要把 Wave 做成第 5 个独立预测因子。

而是把它定义成：

> **对 Q/M/W/D 状态序列进行时间连续性编码的“状态演化层”。**

架构：

```text
Q = Structural State
M = Behavioral State
W = Tactical State
D = Daily Trigger
       ↓
   Wave Engine
       ↓
 ┌───────────────┐
 │ Age           │
 │ Direction     │
 │ Strength      │
 │ Acceleration  │
 │ Failure       │
 │ Recovery      │
 └───────────────┘
       ↓
 Downside Risk
       ↓
 Action / Target
```

这会非常适合你目前的 State-First 架构。

---

# 11. 最关键的是：如何证明 Wave 有效？

不要问：

> “Wave 看起来是不是合理？”

应该直接做实验。

把策略拆成：

```text
M0 = Q/M/W/D，没有 Wave
M1 = Q/M/W/D + Wave
```

然后严格 OOS 比较：

```text
OOS Sharpe
OOS Return
Max Drawdown
Profit Factor
Turnover
Hit Rate
```

特别观察：

```text
Wave 加入后
↓
是否减少 Drawdown？
是否减少错误 HOLD？
是否减少 EXIT 延迟？
是否提高风险调整收益？
```

如果结果：

```text
Sharpe ↑
MDD ↓
Turnover ≈
```

那么 Wave 有真正的**增量效用**。

如果：

```text
Sharpe ≈
MDD ≈
IC ≈
```

那么 Wave 只是对现有 W/D 信号的重新包装。

---

## 一句话总结

**Wave 的真正效用不是“预测下一根 K 线”，而是回答：**

> **“当前这个上涨/下跌信号究竟是刚开始、正在发展、正在加速、已经衰竭，还是已经失败反转？”**

对于你现在的 QCFP-MTF，我认为 Wave **最适合放在 Tactical State 与 Downside Risk 之间**：

```text
Q/M/W/D
   ↓
Wave（状态演化）
   ↓
Risk（风险等级）
   ↓
Action
   ↓
Position
```

这样它才有独立价值；否则单纯再增加一个 Wave 指标，很容易造成**重复信息和过拟合**。



---
