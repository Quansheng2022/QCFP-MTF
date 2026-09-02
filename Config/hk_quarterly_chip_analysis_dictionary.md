# hk_quarterly_chip_analysis 数据字典

- **表名**: `hk_quarterly_chip_analysis`
- **生成时间**: 2026-08-16 05:33:23
- **总记录数**: 944
- **股票数量**: 14

| 字段名 | 数据类型 | 描述 |
|--------|----------|------|
| id | INTEGER | 主键，自增ID |
| stock_code | TEXT | 股票代码（5位数字，如 00700） |
| stock_name | TEXT | 股票名称 |
| quarter | TEXT | 季度标识（如 2026/Q2） |
| quarter_end_date | TEXT | 季度结束日期（自然日，如 2026-06-30） |
| chip_structure_score | REAL | 筹码结构评分（0-100，来自TA4C） |
| chip_regime | TEXT | 筹码状态（极弱/弱/中性/强/极强） |
| chip_migration_status | TEXT | 筹码迁移状态（ACCUMULATION/DISTRIBUTION/DISPERSION/CONCENTRATION/NEUTRAL） |
| chip_migration_score | REAL | 筹码迁移评分（-1~+1） |
| institution_participation_score | REAL | 机构参与度评分（0-100） |
| institutional_concentration_score | REAL | 集中度代理评分（0-100） |
| holder_pct | REAL | 持股比例（%） |
| holder_pct_qoq_pp | REAL | 持股比例环比变化（百分点） |
| institution_quantity_qoq | INTEGER | 机构数量环比变化 |
| institutional_flow | REAL | 机构资金流（季度净额） |
| individual_flow | REAL | 散户资金流（季度净额） |
| idr | REAL | 机构主导比率 IDR |
| fbi | REAL | 资金流平衡指标 FBI |
| flow_bias | TEXT | 资金流偏向（机构净流入/机构净流出/均衡） |
| close | REAL | 季末收盘价 |
| change_percent | REAL | 季度涨跌幅（%） |
| macd_status | TEXT | MACD 状态（金叉/死叉/延续等） |
| ema5_10_status | TEXT | EMA5/10 状态（金叉/死叉/延续等） |
| rsi14 | REAL | RSI14 |
| price_trend | TEXT | 价格趋势（上行/下行/震荡） |
| chip_direction | INTEGER | 筹码方向（+1偏多/-1偏空/0中性） |
| flow_direction | INTEGER | 资金流方向（+1净流入/-1净流出/0均衡） |
| price_direction | INTEGER | 价格方向（+1上行/-1下行/0震荡） |
| chip_flow_alignment | TEXT | 筹码与资金流对齐（共振/背离/中性） |
| chip_price_alignment | TEXT | 筹码与价格对齐（共振/背离/中性） |
| flow_price_alignment | TEXT | 资金流与价格对齐（共振/背离/中性） |
| chip_flow_price_regime | TEXT | QCFP 状态（多头共振/空头共振/吸筹蓄势等） |
| integrated_score | REAL | 综合评分（0-100，筹码40%+资金流30%+价格30%） |
| signal_summary | TEXT | 信号摘要文本 |
| update_time | TEXT | 更新时间 |

