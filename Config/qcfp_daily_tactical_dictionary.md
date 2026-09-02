# qcfp_daily_tactical 数据字典

- **表名**: `qcfp_daily_tactical`
- **生成时间**: 2026-08-24 22:03:30
- **总记录数**: 47313
- **股票数量**: 16

| 字段名 | 数据类型 | 描述 |
|--------|----------|------|
| id | INTEGER | 主键，自增ID |
| stock_code | TEXT | 股票代码（5位数字） |
| stock_name | TEXT | 股票名称 |
| trade_date | TEXT | 交易日（YYYY-MM-DD） |
| daily_state | TEXT | 日线战术状态（DAILY_BREAKOUT/ACCUMULATION/PULLBACK/DISTRIBUTION/NEUTRAL） |
| d_breakout | INTEGER | 日线突破标记（1/0）：收盘>前20日高+量比≥1.5+站上20日VWAP |
| d_distribution | INTEGER | 日线派发标记（1/0）：接近前高+放量滞涨+资金流出 |
| d_pullback | INTEGER | 日线回调标记（1/0）：中期趋势向上+短期回调 |
| d_accumulation | INTEGER | 日线吸筹标记（1/0）：资金改善+量结构改善+价格未突破 |
| d_trend_score | REAL | 日线趋势评分（0~100） |
| d_vol_ratio | REAL | 当日量 / 前 5 日均量 |
| d_near_high | REAL | 收盘 / 前 N 日最高（<1） |
| d_inst_flow | REAL | 日机构净流入代理（超大单+大单净额） |
| d_flow_z | REAL | 日资金流 PIT Z（60 日滚动） |
| d_flow_slope | REAL | 资金流改善斜率（5 日均-20 日均） |
| model_version | TEXT | 模型版本号 |
| data_quality | TEXT | 数据质量等级（A/B/C/D） |
| update_time | TEXT | 更新时间 |
| d_decline | INTEGER |  |

