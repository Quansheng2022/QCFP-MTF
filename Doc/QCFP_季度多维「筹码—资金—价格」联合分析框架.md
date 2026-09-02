---
title: QCFP_季度多维「筹码—资金—价格」联合分析框架
date: 2026-08-14
tags: [QS财富方舟 V7.3 决策操作系统版/Deep Research]
---

QCFP_季度多维「筹码—资金—价格」联合分析框架


# 季度多维「筹码—资金—价格」联合分析框架

**Quarterly Chip–Flow–Price Integrated Analysis Framework，简称 QCFP**

它不是把三个表简单 JOIN，而是建立一个**“存量 → 增量 → 定价 → 周期 → 决策”**的分析系统。

从市场结构角度，这样设计是合理的：机构持股、所有权集中度和自由流通股决定筹码结构；资金流反映边际变化；成交量、换手率和价格则反映二级市场最终形成的定价结果。OECD 的资本市场研究也将 free float、turnover、所有权集中度和机构参与度作为分析市场结构的重要变量。([OECD][1])

---

# 一、总体架构

```text
                         QCFP
              季度筹码—资金—价格联合分析
                              │
        ┌─────────────────────┼─────────────────────┐
        │                     │                     │
        ▼                     ▼                     ▼
   CHIP / 筹码             FLOW / 资金          PRICE / 价格
      存量                    增量                  结果
        │                     │                     │
        ├─ Holder             ├─ Institutional     ├─ OHLC
        ├─ Institution        ├─ Individual        ├─ Return
        ├─ Ownership          ├─ Large/Small       ├─ Volume
        ├─ Concentration      ├─ Capital Trend     ├─ Turnover
        ├─ Cost               ├─ Flow MA           └─ Trend
        └─ Migration          └─ Flow Momentum
        │                     │                     │
        └─────────────────────┼─────────────────────┘
                              ▼
                       三维交叉验证
                              │
              ┌───────────────┼───────────────┐
              ▼               ▼               ▼
            同步             背离             转折
              │               │               │
              └───────────────┼───────────────┘
                              ▼
                       Regime 状态识别
                              │
       ┌────────┬────────┬────┼────┬────────┬────────┐
       ▼        ▼        ▼         ▼        ▼        ▼
      分散     吸筹     蓄势       主升      派发     退潮
                              │
                              ▼
                     Quarterly Chip Score
                              │
                              ▼
                       投资委员会决策
```

---

# 二、第一原则：三个维度不能混为一谈

这是整个框架最重要的原则。

| 维度      | 本质   | 核心问题      |
| ------- | ---- | --------- |
| **筹码**  | 存量   | 谁手里有货？    |
| **资金流** | 增量   | 最近谁在买卖？   |
| **价格**  | 定价结果 | 市场最终怎么定价？ |

因此：

> **筹码是 Stock，资金是 Flow，价格是 Outcome。**

例如：

```text
机构持仓 ↑
机构资金流 ↑
价格 ↑
```

是三维共振。

而：

```text
机构持仓 ↑
机构资金流 ↓
价格 ↑
```

就不能简单判定为强势，而应该进入：

> **结构性背离观察区。**

---

# 三、数据层设计

我建议最终建立四张核心表。

## ① 季度K线

```text
hk_quarterly_kline_analysis
```

来源：

```text
hk_monthly_kline_analysis
```

---

## ② 季度资金流

```text
hk_quarterly_moneyflow_analysis
```

来源：

```text
hk_monthly_moneyflow_analysis
```

---

## ③ 季度筹码

```text
hk_quarterly_chip_analysis
```

来源：

```text
hk_hist_institutional_holdings
```

---

## ④ 综合分析表

```text
hk_quarterly_integrated_analysis
```

这是最终给 AI / DSS 使用的**事实层**。

---

# 四、季度K线层

你的月度K线数据已经非常完整。

季度OHLC应该从月度原始数据重新聚合：

```text
Q_Open  = 第一月 Open
Q_High  = MAX(三个月 High)
Q_Low   = MIN(三个月 Low)
Q_Close = 最后一月 Close
```

成交量：

```text
Q_Volume = SUM(monthly_volume)
```

成交额：

```text
Q_Amount = SUM(monthly_amount)
```

季度涨跌：

```text
Q_Return =
Q_Close / Previous_Q_Close - 1
```

---

# 五、一个非常重要的技术原则

**不要直接平均月度技术指标。**

例如不要：

```text
Quarter RSI = AVG(Monthly RSI)
```

也不要：

```text
Quarter MACD = AVG(Monthly MACD)
```

正确方式：

```text
月度OHLC
    ↓
季度OHLC
    ↓
重新计算
    ↓
Quarter EMA
Quarter MACD
Quarter RSI
Quarter KDJ
```

原因是季度EMA、MACD、RSI本质上是对**季度价格序列**计算，而不是对月度指标做平均。

---

# 六、季度价格因子

建议至少保留：

```text
quarter_open
quarter_high
quarter_low
quarter_close

quarter_return
quarter_amplitude

quarter_volume
quarter_amount
quarter_turnover

ema5
ema10
ema20
ema50
ema100
ema200

macd_dif
macd_signal
macd_histogram

rsi14
kdj_k
kdj_d
kdj_j

volume_ratio
```

进一步增加：

```text
quarter_high_52w
quarter_low_52w
distance_to_high
distance_to_low
```

这样可以判断：

> 当前季度价格位于历史趋势的什么位置。

---

# 七、季度趋势状态

建议不要只使用 MACD。

建立：

### Trend Score

```text
EMA Structure       25%
MACD                20%
Price Structure     20%
Volume Confirmation 15%
RSI                 10%
KDJ                 10%
```

最终：

```text
0–20    极弱
21–40   弱势
41–60   中性
61–80   强势
81–100  极强
```

---

# 八、资金流层

你现有：

```text
institutional_flow
individual_flow
extra_large
large
medium
small
capital_trend
inst_5ma
ind_5ma
idr
fbi
```

已经非常适合构建资金流分析。

但季度数据不能全部使用同一种聚合方法。

---

# 九、资金流的三种聚合方式

这是数据库设计中非常重要的一点。

## A. 流量型变量 → SUM

例如：

```text
institutional_flow
individual_flow
extra_large
large
medium
small
```

季度：

```text
Q_Inst_Flow = SUM(monthly_inst_flow)
```

因为它们属于**期间流量**。

---

## B. 状态型变量 → END

例如：

```text
capital_trend
idr
fbi
```

如果定义为某个时间点状态：

```text
Quarter_End_IDR
=
最后一个月 IDR
```

---

## C. 趋势型变量 → 重新计算

例如：

```text
inst_5ma
ind_5ma
```

不要简单平均。

可以重新计算：

```text
Quarter Institutional Flow Momentum
```

---

# 十、季度资金流核心指标

建议：

```text
quarter_institutional_flow
quarter_individual_flow

quarter_extra_large_flow
quarter_large_flow
quarter_medium_flow
quarter_small_flow

institutional_flow_ratio
institutional_flow_momentum
individual_flow_momentum

capital_trend
idr
fbi
```

---

# 十一、建立“机构资金优势”

建议定义：

```text
Institutional Flow Advantage
=
Institutional Flow
-
Individual Flow
```

进一步标准化：

```text
IFA_Z
=
Z(Institutional Flow - Individual Flow)
```

解释：

```text
IFA ↑↑
→ 机构资金明显占优

IFA ↑
→ 机构资金改善

IFA →
→ 机构/个人平衡

IFA ↓
→ 个人资金占优

IFA ↓↓
→ 机构资金明显流出
```

---

# 十二、筹码层

你现在的：

```text
institution_quantity
holder_quantity
holder_pct
```

作为第一版完全可以。

建立：

### Holder Trend

```text
HQ_QoQ
HQ_YoY
HQ_4Q_Change
```

### Holder Ownership Trend

```text
HP_QoQ
HP_YoY
HP_4Q_Change
```

### Institution Participation

```text
IP_QoQ
IP_YoY
```

---

# 十三、但这里必须严格区分三个概念

这是你的数据库未来最容易产生误判的地方。

### ① Institution Quantity

```text
机构有多少个
```

是：

> **参与广度**

---

### ② Institution Shares

```text
机构持有多少股票
```

是：

> **机构筹码存量**

---

### ③ Institution Ownership %

```text
机构持股比例
```

是：

> **机构控制/占有程度**

三者绝对不能混为：

> “机构数量增加 = 机构增持”。

你的锦欣生殖历史数据已经证明了这一点。

---

# 十四、筹码集中度

如果目前只能使用现有字段：

### Basic Chip Concentration

```text
Holder Trend
+
Holder %
+
Institution Participation
```

如果未来获得机构明细：

```text
Top 3 Institution %
Top 5 Institution %
Top 10 Institution %
HHI
```

再升级为真正的机构集中度。

所有权集中度本身就是一个独立的重要变量；OECD 也将最大股东/前三大股东持股比例作为衡量集中度的核心指标。([OECD][2])

---

# 十五、自由流通股必须纳入第二阶段

建议以后加入：

```text
total_shares
free_float_shares
free_float_pct
```

然后：

```text
institution_pct_float
=
institution_shares
/
free_float_shares
```

这会比简单的：

```text
institution_shares / total_shares
```

更适合二级市场筹码分析。

因为真正决定市场交易筹码的是自由流通部分。OECD 对 free float 的定义也是围绕可在市场交易的股份展开。([OECD][1])

---

# 十六、三维核心：Chip × Flow × Price

现在进入整个框架最重要的部分。

建立三个标准化变量：

```text
C = Chip Score
F = Flow Score
P = Price/Trend Score
```

分别：

```text
C ∈ [-100, +100]
F ∈ [-100, +100]
P ∈ [-100, +100]
```

---

# 十七、三维状态矩阵

### ① C↑ F↑ P↑

```text
筹码改善
资金流入
价格上涨
```

## 🟢 主升确认

这是最高质量结构。

---

### ② C↑ F↑ P→

```text
筹码集中
资金流入
价格横盘
```

## 🟢 吸筹 / 蓄势

这是非常重要的左侧结构。

---

### ③ C↑ F→ P↑

## 🟢 趋势强化

资金没有明显加速，但存量筹码改善。

---

### ④ C↑ F↓ P↑

## 🟡 结构背离

价格在涨，但新增资金没有确认。

---

### ⑤ C↓ F↓ P↑

## 🔴 上涨派发风险

这是非常重要的顶部预警。

---

### ⑥ C↓ F↓ P↓

## 🔴 退潮

三维共振恶化。

---

### ⑦ C↑ F↓ P↓

## 🟠 逆势吸筹候选

价格下降，但是筹码改善。

需要进一步检查：

* 基本面
* 行业
* 成交量
* 南向
* 大股东行为

不能直接定义为底部。

---

### ⑧ C↓ F↑ P↓

## 🟡 潜在底部

存量筹码还没有修复，但边际资金已经改善。

这是非常值得监控的状态。

---

# 十八、建立三个背离指标

## 1. Chip–Price Divergence

```text
CPD = Z(C) - Z(P)
```

---

## 2. Flow–Price Divergence

```text
FPD = Z(F) - Z(P)
```

---

## 3. Chip–Flow Divergence

```text
CFD = Z(C) - Z(F)
```

于是：

```text
CPD > threshold
→ 筹码明显强于价格

FPD > threshold
→ 资金明显强于价格

CFD > threshold
→ 筹码强于新增资金
```

这些指标特别适合**转折检测**。

---

# 十九、建立“领先—同步—滞后”模型

这是我建议你进一步加入的高级层。

因为三个变量并不是同时变化。

例如：

```text
资金流
 ↓
筹码
 ↓
价格
```

可能存在：

> **资金领先 → 筹码变化 → 价格确认**

因此计算：

```text
Flow_t-1 → Chip_t → Price_t
```

以及：

```text
Chip_t-1 → Price_t
```

甚至：

```text
Flow_t-2 → Price_t
```

---

# 二十、建立 Lead-Lag Score

例如：

```text
LLS =
Correlation(F_{t-1}, P_t)
+
Correlation(C_{t-1}, P_t)
```

再通过历史数据测试：

> 哪一个变量对未来 1～4 个季度的价格最有解释力。

这一步非常重要。

因为不要先假定：

> “机构筹码一定领先价格”。

应该让你的历史数据告诉你：

> **对于港股不同类型股票，什么变量真正具有领先性。**

---

# 二十一、季度周期状态机

最终把三维数据映射到：

```text
                 筑底
                   ↑
                   │
                 吸筹
                   ↓
                 蓄势
                   ↓
                 主升
                   ↓
                 加速
                   ↓
                 派发
                   ↓
                 退潮
                   ↓
                 超跌
                   │
                   └────→ 筑底
```

---

# 二十二、各阶段的量化特征

| 阶段 | Chip | Flow | Price | Volume |
| -- | ---- | ---- | ----- | ------ |
| 分散 | ↓    | ↓    | ↓/→   | 低      |
| 吸筹 | ↑    | ↑    | →     | ↑      |
| 蓄势 | ↑↑   | ↑    | →/↑   | ↑      |
| 主升 | ↑/→  | ↑↑   | ↑↑    | ↑↑     |
| 加速 | →/↓  | ↑/→  | ↑↑    | ↑↑     |
| 派发 | ↓    | ↓    | ↑/→   | ↑↑     |
| 退潮 | ↓↓   | ↓↓   | ↓↓    | ↑      |
| 筑底 | →/↑  | ↑    | →     | ↓→↑    |

---

# 二十三、建立季度评分系统

建议最终形成：

## QCFP Score = 100

| 模块                      |      权重 |
| ----------------------- | ------: |
| Chip Structure          |      25 |
| Institutional Flow      |      20 |
| Price Trend             |      20 |
| Volume/Turnover         |      10 |
| Chip–Flow relationship  |      10 |
| Chip–Price relationship |       5 |
| Flow–Price relationship |       5 |
| Regime transition       |       5 |
| **总计**                  | **100** |

这样：

```text
QCFP ≥ 85
→ 极强

75–84
→ 强

60–74
→ 偏强

45–59
→ 中性

30–44
→ 偏弱

<30
→ 极弱
```

---

# 二十四、但是不要把QCFP直接作为买卖信号

这是非常重要的风险控制。

应该：

```text
QCFP
   ↓
市场结构判断
   ↓
再与：
   ↓
宏观
行业
基本面
估值
技术
风险
   ↓
综合决策
```

也就是说：

> **QCFP 是“资金与筹码周期引擎”，不是完整的投资决策引擎。**

---

# 二十五、最终综合报告结构

你的个股报告可以固定输出：

```text
━━━━━━━━━━━━━━━━━━━━━━━━━━
QUARTERLY QCFP ANALYSIS
━━━━━━━━━━━━━━━━━━━━━━━━━━

一、筹码结构
   筹码集中度
   Holder Trend
   Institution Participation
   Institution Ownership
   Cost Structure

二、资金流
   Institutional Flow
   Individual Flow
   Large Flow
   Small Flow
   Institutional Advantage

三、价格趋势
   Quarterly Return
   EMA Structure
   MACD
   RSI
   Volume
   Turnover

四、三维关系
   Chip × Flow
   Chip × Price
   Flow × Price

五、背离
   CPD
   CFD
   FPD

六、领先关系
   Flow → Chip → Price
   Chip → Price

七、周期状态
   分散 / 吸筹 / 蓄势 / 主升 /
   加速 / 派发 / 退潮 / 筑底

八、QCFP Score
   XX / 100

九、关键证据
   Evidence 1
   Evidence 2
   Evidence 3

十、结论
   当前状态
   趋势方向
   机构状态
   风险状态
━━━━━━━━━━━━━━━━━━━━━━━━━━
```

---

# 二十六、数据库层我建议这样最终落地

不要把所有东西塞进一张表。

### Layer 1：Raw

```text
hk_monthly_kline_analysis
hk_monthly_moneyflow_analysis
hk_hist_institutional_holdings
```

### Layer 2：Quarterly Fact

```text
hk_quarterly_kline_analysis
hk_quarterly_moneyflow_analysis
hk_quarterly_chip_analysis
```

### Layer 3：Derived

```text
hk_quarterly_chip_factors
hk_quarterly_moneyflow_factors
hk_quarterly_trend_factors
```

### Layer 4：Integrated

```text
hk_quarterly_integrated_analysis
```

### Layer 5：Decision

```text
hk_quarterly_regime
hk_quarterly_score
```

---

# 二十七、最终形成你的数据分析金字塔

```text
                    ┌───────────────┐
                    │  DSS Decision │
                    └───────▲───────┘
                            │
                    ┌───────┴───────┐
                    │ QCFP Regime   │
                    │ Score/Signal  │
                    └───────▲───────┘
                            │
              ┌─────────────┴─────────────┐
              │   Chip × Flow × Price    │
              └─────────────▲─────────────┘
                            │
        ┌───────────────────┼───────────────────┐
        │                   │                   │
      CHIP                FLOW                PRICE
        │                   │                   │
  Ownership          Money Flow            Quarterly K
  Concentration      Institution           Trend
  Migration          Individual            Volume
  Cost               Large/Small            Turnover
        │                   │                   │
        └───────────────────┼───────────────────┘
                            │
                    Quarterly Fact
                            │
              ┌─────────────┼─────────────┐
              │             │             │
           Monthly          Daily       Ownership
```

---

# 二十八、对你当前项目，我建议的实施顺序

**第一阶段：先完成季度数据层**

```text
月度K线
   ↓
季度OHLCV
   ↓
重新计算季度技术指标
```

同时：

```text
月度资金流
   ↓
季度资金流
```

以及：

```text
机构持股季度数据
   ↓
Quarterly Chip
```

**第二阶段：建立三张因子表**

```text
Chip Factors
Flow Factors
Price Factors
```

**第三阶段：建立 QCFP Integrated**

```text
Chip
+
Flow
+
Price
+
Divergence
+
Lead-Lag
```

**第四阶段：建立 Regime Engine**

```text
分散
吸筹
蓄势
主升
加速
派发
退潮
筑底
```

**第五阶段：才接入 QS 财富方舟的投资委员会。**

---

## 最关键的三个设计原则

### ① 存量、增量、结果必须分开

> **Chip = 存量，Flow = 增量，Price = 结果。**

### ② 指标不要简单平均，要按照经济含义聚合

> OHLC → 重新构造；
> Flow → 通常累计；
> State → 期末；
> Trend → 重新计算。

### ③ 最终判断不能看单一变量，而要看“三维共振/背离”

> **筹码告诉你“谁有货”；资金告诉你“谁正在行动”；价格告诉你“市场是否认可这种行动”。**

这会比单纯增加更多 MACD、RSI、EMA 指标更有价值。尤其对于港股，所有权集中度、自由流通股和机构参与之间的关系本身就具有重要的市场结构含义。OECD 2026 年亚洲资本市场报告也指出，较高的所有权集中度往往与较低估值相关，而机构参与度与市场流动性之间存在明显关系。([OECD][3])

**因此，我建议把 QCFP 直接作为你现有 TA Workflow 的一个独立“季度周期引擎”，而不是把它当成普通的技术指标模块。**它最有价值的地方不是预测下一根K线，而是识别一只股票正在经历的**资金与筹码周期状态，以及这个状态是否已经得到价格确认**。

[1]: https://www.oecd.org/en/publications/methodology-for-assessing-the-implementation-of-the-g20-oecd-principles-of-corporate-governance-2025_80996ea9-en/full-report/the-corporate-governance-landscape_0e15ffbd.html?utm_source=chatgpt.com "The corporate governance landscape: Methodology for Assessing the Implementation of the G20/OECD Principles of Corporate Governance 2025 | OECD"
[2]: https://www.oecd.org/en/publications/corporate-ownership-and-concentration_bc3adca3-en.html?utm_source=chatgpt.com "Corporate ownership and concentration | OECD"
[3]: https://www.oecd.org/en/publications/asia-capital-markets-report-2026_08f87bed-en/full-report/creating-value-and-increasing-trust_48e57a3d.html?utm_source=chatgpt.com "Creating value and increasing trust: Asia Capital Markets Report 2026 | OECD"


