# hk_quarterly_institutional_holdings_analysis 数据字典

- **表名**: `hk_quarterly_institutional_holdings_analysis`
- **生成时间**: 2026-08-16 05:33:22
- **总记录数**: 944
- **股票数量**: 14

| 字段名 | 数据类型 | 描述 |
|--------|----------|------|
| id | INTEGER | 主键，自增ID |
| stock_code | TEXT | 股票代码（5位数字，如 00700） |
| stock_name | TEXT | 股票名称 |
| quarter | TEXT | 季度标识（如 2026/Q2） |
| quarter_end_date | TEXT | 季度结束日期（自然日，如 2026-06-30） |
| institution_quantity | INTEGER | 机构持股账户/机构数量（原始值） |
| holder_quantity | INTEGER | 持股数量（原始值） |
| holder_pct | REAL | 持股比例（%，原始值） |
| quarter_end_price | REAL | 季末价格 |
| institution_quantity_qoq | INTEGER | 机构数量环比变化（绝对值） |
| institution_quantity_qoq_pct | REAL | 机构数量环比变化（%） |
| holder_quantity_qoq | INTEGER | 持股数量环比变化（绝对值） |
| holder_quantity_qoq_pct | REAL | 持股数量环比变化（%） |
| holder_pct_qoq_pp | REAL | 持股比例环比变化（百分点） |
| institution_quantity_yoy_pct | REAL | 机构数量同比变化（%） |
| holder_quantity_yoy_pct | REAL | 持股数量同比变化（%） |
| holder_pct_yoy_pp | REAL | 持股比例同比变化（百分点） |
| institution_quantity_4q_change | INTEGER | 机构数量过去4个季度累计变化（绝对值） |
| holder_quantity_4q_change | INTEGER | 持股数量过去4个季度累计变化（绝对值） |
| holder_pct_4q_change_pp | REAL | 持股比例过去4个季度累计变化（百分点） |
| institution_trend | INTEGER | 机构数量趋势编码（-2强降/-1降/0稳定/1升/2强升） |
| holder_trend | INTEGER | 持股数量趋势编码（-2强降/-1降/0稳定/1升/2强升） |
| holder_pct_trend | INTEGER | 持股比例趋势编码（-2强降/-1降/0稳定/1升/2强升） |
| chip_migration_score | REAL | 筹码迁移评分（-1~+1，正=向机构集中，负=向外扩散） |
| chip_migration_status | TEXT | 筹码迁移状态（ACCUMULATION吸筹/DISTRIBUTION派发/DISPERSION分散/CONCENTRATION集中/NEUTRAL中性） |
| institution_participation_score | REAL | 机构参与度评分（0-100） |
| institutional_concentration_score | REAL | 集中度代理评分（0-100，以holder_pct为代理，真实集中度需机构明细） |
| chip_structure_score | REAL | 筹码结构评分（0-100，六层加权合成） |
| chip_regime | TEXT | 筹码状态（极弱/弱/中性/强/极强） |
| data_quality_flag | INTEGER | 数据质量标记（1=原始字段完整，0=存在缺失） |
| corporate_action_flag | INTEGER | 公司行为提示（1=持股数量环比变动≥25%，可能受IPO/配股/拆分等影响） |
| source_period | TEXT | 原始季度标识（与 hk_hist_institutional_holdings.period_text 一致） |
| data_source | TEXT | 数据来源 |
| update_time | TEXT | 更新时间 |

