# hk_quarterly_kline_analysis 数据字典

## 基本信息

- **表名**: `hk_quarterly_kline_analysis`
- **生成时间**: 2026-08-15 19:31:57
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
| stock_name | TEXT | 是 | 否 |  | 股票名称（如：腾讯控股） | 0.0% |  |
| date | TEXT | 否 | 否 |  | 交易日期（格式：YYYY-MM-DD） | 0.0% |  |
| open | REAL | 是 | 否 |  | 开盘价（港元） | 0.0% |  |
| high | REAL | 是 | 否 |  | 最高价（港元） | 0.0% |  |
| low | REAL | 是 | 否 |  | 最低价（港元） | 0.0% |  |
| close | REAL | 是 | 否 |  | 收盘价（港元） | 0.0% |  |
| volume | REAL | 是 | 否 |  | 成交量（股） | 0.0% |  |
| amount | REAL | 是 | 否 |  | 成交金额（港元） | 0.0% |  |
| turnover_rate | REAL | 是 | 否 |  | 换手率（%） | 0.0% |  |
| amplitude | REAL | 是 | 否 |  | 振幅（%） | 0.0% |  |
| change_amount | REAL | 是 | 否 |  | 涨跌额（港元） | 0.0% |  |
| change_percent | REAL | 是 | 否 |  | 涨跌幅（%） | 0.0% |  |
| ema5 | REAL | 是 | 否 |  | 5期指数移动平均线 | 0.0% |  |
| ema10 | REAL | 是 | 否 |  | 10期指数移动平均线 | 0.0% |  |
| ema20 | REAL | 是 | 否 |  | 20期指数移动平均线 | 0.0% |  |
| ema50 | REAL | 是 | 否 |  | 50期指数移动平均线 | 0.0% |  |
| ema100 | REAL | 是 | 否 |  | 100期指数移动平均线 | 0.0% |  |
| ema200 | REAL | 是 | 否 |  | 200期指数移动平均线 | 0.0% |  |
| macd_dif | REAL | 是 | 否 |  | MACD DIF线（差离值） | 0.0% |  |
| macd_signal | REAL | 是 | 否 |  | MACD Signal线（信号线） | 0.0% |  |
| macd_histogram | REAL | 是 | 否 |  | MACD Histogram（柱状线） | 0.0% |  |
| ema5_10_status | TEXT | 是 | 否 |  | EMA5与EMA10状态（1:金叉, -1:死叉, 0:粘合） | 0.0% |  |
| ema5_10_streak | INTEGER | 是 | 否 |  | EMA5与EMA10连续状态季度数（正:金叉持续, 负:死叉持续） | 0.0% |  |
| ema5_20_status | TEXT | 是 | 否 |  | EMA5与EMA20状态（1:金叉, -1:死叉, 0:粘合） | 0.0% |  |
| ema5_20_streak | INTEGER | 是 | 否 |  | EMA5与EMA20连续状态季度数（正:金叉持续, 负:死叉持续） | 0.0% |  |
| ema10_50_status | TEXT | 是 | 否 |  | EMA10与EMA50状态（1:金叉, -1:死叉, 0:粘合） | 0.0% |  |
| ema10_50_streak | INTEGER | 是 | 否 |  | EMA10与EMA50连续状态季度数（正:金叉持续, 负:死叉持续） | 0.0% |  |
| ema20_50_status | TEXT | 是 | 否 |  | EMA20与EMA50状态（1:金叉, -1:死叉, 0:粘合） | 0.0% |  |
| ema20_50_streak | INTEGER | 是 | 否 |  | EMA20与EMA50连续状态季度数（正:金叉持续, 负:死叉持续） | 0.0% |  |
| golden_triangle | INTEGER | 是 | 否 |  | 黄金三角形态（1:形成, 0:未形成） | 0.0% |  |
| death_triangle | INTEGER | 是 | 否 |  | 死亡三角形态（1:形成, 0:未形成） | 0.0% |  |
| macd_cross | TEXT | 是 | 否 |  | MACD交叉状态（1:金叉, -1:死叉, 0:无交叉） | 0.0% |  |
| macd_status | TEXT | 是 | 否 |  | MACD状态（1:DIF>Signal, -1:DIF<Signal） | 0.0% |  |
| macd_golden_streak | INTEGER | 是 | 否 |  | MACD金叉持续天数 | 0.0% |  |
| macd_death_streak | INTEGER | 是 | 否 |  | MACD死叉持续天数 | 0.0% |  |
| kdj_k | REAL | 是 | 否 |  | KDJ指标K值 | 0.0% |  |
| kdj_d | REAL | 是 | 否 |  | KDJ指标D值 | 0.0% |  |
| kdj_j | REAL | 是 | 否 |  | KDJ指标J值 | 0.0% |  |
| vol_ema5 | REAL | 是 | 否 |  | 成交量5期指数移动平均线 | 0.0% |  |
| volume_ratio | REAL | 是 | 否 |  |  | 0.0% |  |
| gain | REAL | 是 | 否 |  | 当日上涨幅度（用于RSI计算） | 0.0% |  |
| loss | REAL | 是 | 否 |  | 当日下跌幅度（用于RSI计算） | 0.0% |  |
| avg_gain | REAL | 是 | 否 |  | 平均上涨幅度（14期） | 0.0% |  |
| avg_loss | REAL | 是 | 否 |  | 平均下跌幅度（14期） | 0.0% |  |
| rs | REAL | 是 | 否 |  | RS值（相对强度） | 0.0% |  |
| rsi14 | REAL | 是 | 否 |  | 14期相对强弱指标 | 0.0% |  |

## 字段详细统计

