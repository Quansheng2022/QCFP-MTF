# qcfp_weekly_tactical 数据字典

- **表名**: `qcfp_weekly_tactical`
- **生成时间**: 2026-08-24 22:03:30
- **总记录数**: 10046
- **股票数量**: 16

| 字段名 | 数据类型 | 描述 |
|--------|----------|------|
| id | INTEGER | 主键，自增ID |
| stock_code | TEXT | 股票代码（5位数字） |
| stock_name | TEXT | 股票名称 |
| week_end | TEXT | 周结束日期（YYYY-MM-DD） |
| w_turnover_deviation | REAL | 周换手偏离度（%） |
| w_turnover_spike | INTEGER | 是否极端换手（1/0） |
| w_volume_breakout | INTEGER | 是否放量突破（1/0） |
| w_vwap_deviation | REAL | 收盘价 vs 周 VWAP 偏离（%） |
| w_ma_slope | TEXT | 周均线斜率方向（5/10/20 周二阶差分） |
| w_breakout | INTEGER | 是否有效突破（1/0） |
| w_breakdown | INTEGER | 是否有效破位（1/0） |
| tactical_signal | TEXT | 战术信号（Breakout/Pullback/Consolidation/Breakdown） |
| model_version | TEXT | 模型版本号 |
| data_quality | TEXT | 数据质量等级（A/B/C/D） |
| update_time | TEXT | 更新时间 |
| w_volume_shrink | INTEGER |  |

