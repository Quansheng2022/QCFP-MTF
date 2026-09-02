# qcfp_quarterly_structural 数据字典

- **表名**: `qcfp_quarterly_structural`
- **生成时间**: 2026-08-24 22:03:28
- **总记录数**: 960
- **股票数量**: 15

| 字段名 | 数据类型 | 描述 |
|--------|----------|------|
| id | INTEGER | 主键，自增ID |
| stock_code | TEXT | 股票代码（5位数字，如 00700） |
| stock_name | TEXT | 股票名称 |
| period_end | TEXT | 季度结束日期（YYYY-MM-DD） |
| available_date | TEXT | 数据真实可用日期（推算时用季度末+披露滞后，data_quality 降级） |
| inst_ownership_pct_chg | REAL | 机构持股比例变化（百分点，来自 TA4C） |
| holder_quantity_chg_pct | REAL | 股东户数变化（%） |
| inst_participation_chg | REAL | 机构数量变化（%） |
| q_inst_flow_raw | REAL | 季度机构资金净流入（原始值，IDR/FBI 派生） |
| q_inst_flow_z | REAL | 季度机构资金净流入 Z-Score |
| q_ifa_zscore | REAL | 机构资金优势 Z-Score |
| q_return | REAL | 季度收益率（%） |
| q_trend_score | REAL | 季度趋势评分（0~100，季末快照窗口） |
| q_position_52w | REAL | 52 周价格位置（0~1，季末快照） |
| c_state | TEXT | 筹码方向状态（C↑/C→/C↓） |
| f_state | TEXT | 资金方向状态（F↑/F→/F↓） |
| p_state | TEXT | 价格方向状态（P↑/P→/P↓） |
| structural_regime | TEXT | 季度结构状态（6 种：STRUCTURAL_BULLISH 等） |
| core_score | REAL | 季度核心评分（0~100，State-First） |
| source_period | TEXT | 来源季度标识（如 2026/Q2） |
| model_version | TEXT | 模型版本号（QCFP-MTF-2.1.1） |
| data_quality | TEXT | 数据质量等级（A/B/C/D） |
| update_time | TEXT | 更新时间 |
| resolve_method | TEXT |  |

