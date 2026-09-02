# hk_weekly_kline_analysis 数据字典

## 基本信息

- **表名**: `hk_weekly_kline_analysis`
- **生成时间**: 2026-07-15 17:26:18
- **数据库路径**: `C:\Users\Quansheng\Documents\projects\TA_Workflow\SQLiteDB\HK_Stock.db`
- **字段数量**: 48

## 统计信息

- **总记录数**: 0
- **股票数量**: 0

## 字段信息

| 字段名 | 数据类型 | 可空 | 主键 | 默认值 | 描述 | 空值比例 | 示例值 |
|--------|----------|------|------|--------|------|----------|--------|
| id | INTEGER | 是 | 是 |  | 主键，自增ID | 0.0% |  |
| stock_code | TEXT | 否 | 否 |  | 股票代码（如：00700） | 0.0% |  |
| stock_name | TEXT | 否 | 否 |  | 股票名称（如：腾讯控股） | 0.0% |  |
| date | TEXT | 否 | 否 |  | 周K线日期（格式：YYYY-MM-DD，每周最后一个交易日） | 0.0% |  |
| open | REAL | 是 | 否 |  | 周开盘价 | 0.0% |  |
| high | REAL | 是 | 否 |  | 周最高价 | 0.0% |  |
| low | REAL | 是 | 否 |  | 周最低价 | 0.0% |  |
| close | REAL | 是 | 否 |  | 周收盘价 | 0.0% |  |
| volume | REAL | 是 | 否 |  | 周成交量（股） | 0.0% |  |
| amount | REAL | 是 | 否 |  | 周成交额（元） | 0.0% |  |
| turnover_rate | REAL | 是 | 否 |  | 周换手率（%） | 0.0% |  |
| amplitude | REAL | 是 | 否 |  | 周振幅（%） | 0.0% |  |
| change_percent | REAL | 是 | 否 |  | 周涨跌幅（%） | 0.0% |  |
| change_amount | REAL | 是 | 否 |  | 周涨跌额（元） | 0.0% |  |
| ema5 | REAL | 是 | 否 |  | 5周指数移动平均线 | 0.0% |  |
| ema10 | REAL | 是 | 否 |  | 10周指数移动平均线 | 0.0% |  |
| ema20 | REAL | 是 | 否 |  | 20周指数移动平均线 | 0.0% |  |
| ema50 | REAL | 是 | 否 |  | 50周指数移动平均线 | 0.0% |  |
| ema100 | REAL | 是 | 否 |  | 100周指数移动平均线 | 0.0% |  |
| ema200 | REAL | 是 | 否 |  | 200周指数移动平均线 | 0.0% |  |
| macd_dif | REAL | 是 | 否 |  | MACD DIF线（差离值） | 0.0% |  |
| macd_signal | REAL | 是 | 否 |  | MACD Signal线（信号线） | 0.0% |  |
| macd_histogram | REAL | 是 | 否 |  | MACD 柱状图（DIF - Signal） | 0.0% |  |
| ema5_10_status | TEXT | 是 | 否 |  | EMA5与EMA10交叉状态（金叉/死叉/平行） | 0.0% |  |
| ema5_10_streak | INTEGER | 是 | 否 |  | EMA5与EMA10持续状态天数 | 0.0% |  |
| ema5_20_status | TEXT | 是 | 否 |  | EMA5与EMA20交叉状态（金叉/死叉/平行） | 0.0% |  |
| ema5_20_streak | INTEGER | 是 | 否 |  | EMA5与EMA20持续状态天数 | 0.0% |  |
| ema10_50_status | TEXT | 是 | 否 |  | EMA10与EMA50交叉状态（金叉/死叉/平行） | 0.0% |  |
| ema10_50_streak | INTEGER | 是 | 否 |  | EMA10与EMA50持续状态天数 | 0.0% |  |
| ema20_50_status | TEXT | 是 | 否 |  | EMA20与EMA50交叉状态（金叉/死叉/平行） | 0.0% |  |
| ema20_50_streak | INTEGER | 是 | 否 |  | EMA20与EMA50持续状态天数 | 0.0% |  |
| golden_triangle | INTEGER | 是 | 否 |  | 黄金三角形（1: 金叉形成, 0: 未形成） | 0.0% |  |
| death_triangle | INTEGER | 是 | 否 |  | 死亡三角形（1: 死叉形成, 0: 未形成） | 0.0% |  |
| macd_cross | REAL | 是 | 否 |  | MACD交叉信号（1: 金叉, -1: 死叉, 0: 无交叉） | 0.0% |  |
| macd_status | REAL | 是 | 否 |  | MACD状态（1: 多头, -1: 空头, 0: 震荡） | 0.0% |  |
| macd_golden_streak | REAL | 是 | 否 |  | MACD金叉持续周数 | 0.0% |  |
| macd_death_streak | REAL | 是 | 否 |  | MACD死叉持续周数 | 0.0% |  |
| kdj_k | REAL | 是 | 否 |  | KDJ指标K值 | 0.0% |  |
| kdj_d | REAL | 是 | 否 |  | KDJ指标D值 | 0.0% |  |
| kdj_j | REAL | 是 | 否 |  | KDJ指标J值 | 0.0% |  |
| vol_ema5 | REAL | 是 | 否 |  | 5周成交量指数移动平均线 | 0.0% |  |
| volume_ratio | REAL | 是 | 否 |  | 量比（成交量/5周均量） | 0.0% |  |
| gain | REAL | 是 | 否 |  | 本周涨幅（正数） | 0.0% |  |
| loss | REAL | 是 | 否 |  | 本周跌幅（负数） | 0.0% |  |
| avg_gain | REAL | 是 | 否 |  | 14周平均涨幅 | 0.0% |  |
| avg_loss | REAL | 是 | 否 |  | 14周平均跌幅 | 0.0% |  |
| rs | REAL | 是 | 否 |  | RS值（平均涨幅/平均跌幅） | 0.0% |  |
| rsi14 | REAL | 是 | 否 |  | 14周相对强弱指标 | 0.0% |  |

## 字段详细统计

