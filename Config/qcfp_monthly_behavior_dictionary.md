# qcfp_monthly_behavior 数据字典

- **表名**: `qcfp_monthly_behavior`
- **生成时间**: 2026-08-24 22:03:30
- **总记录数**: 2307
- **股票数量**: 16

| 字段名 | 数据类型 | 描述 |
|--------|----------|------|
| id | INTEGER | 主键，自增ID |
| stock_code | TEXT | 股票代码（5位数字） |
| stock_name | TEXT | 股票名称 |
| month_end | TEXT | 月份结束日期（YYYY-MM-DD） |
| m_turnover_zscore | REAL | 月换手率 Z-Score |
| m_turnover_pctl | REAL | 月换手率 52W 百分位（0~1） |
| m_turnover_ma_ratio | REAL | 月换手率 / MA6 |
| m_volume_ma_ratio | REAL | 月成交量 / MA6 |
| m_volume_accel | REAL | 成交量加速度（VE_t / VE_{t-3} - 1） |
| m_vwap_deviation | REAL | 收盘价 vs 月 VWAP 偏离（%） |
| m_turnover_efficiency | REAL | 换手效率 |
| m_vp_regime | TEXT | 量价矩阵状态（9 种，如 VP_EXPANSION） |
| turnover_liquidity_regime | TEXT | 换手-流动性状态（T1~T5） |
| monthly_behavior_state | TEXT | 月线阶段（Improving/Stable/Deteriorating） |
| model_version | TEXT | 模型版本号 |
| data_quality | TEXT | 数据质量等级（A/B/C/D） |
| update_time | TEXT | 更新时间 |
| cbi_score | REAL |  |
| cbi_state | TEXT |  |
| cost_position | TEXT |  |
| cost_vs_weekly_vwap | REAL |  |
| cost_vs_monthly_vwap | REAL |  |
| cost_vs_quarterly_vwap | REAL |  |

