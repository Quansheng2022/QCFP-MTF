# hk_hist_quarterly_kline 数据字典

## 基本信息

- **表名**: `hk_hist_quarterly_kline`
- **生成时间**: 2026-08-15 19:31:54
- **数据库路径**: `C:\Users\Quansheng\Documents\projects\TA_Workflow\SQLiteDB\HK_Stock.db`
- **字段数量**: 24

## 统计信息

- **总记录数**: 0
- **股票数量**: 0

## 字段信息

| 字段名 | 数据类型 | 可空 | 主键 | 默认值 | 描述 | 空值比例 | 示例值 |
|--------|----------|------|------|--------|------|----------|--------|
| id | INTEGER | 是 | 是 |  | 主键，自增ID | 0.0% |  |
| stock_code | TEXT | 否 | 否 |  | 股票代码（如：00700） | 0.0% |  |
| stock_name | TEXT | 是 | 否 |  | 股票名称（如：腾讯控股） | 0.0% |  |
| date | TEXT | 否 | 否 |  | 交易日期（格式：YYYY-MM-DD，每季度最后一个交易日） | 0.0% |  |
| open | REAL | 是 | 否 |  | 开盘价（元） | 0.0% |  |
| high | REAL | 是 | 否 |  | 最高价（元） | 0.0% |  |
| low | REAL | 是 | 否 |  | 最低价（元） | 0.0% |  |
| close | REAL | 是 | 否 |  | 收盘价（元） | 0.0% |  |
| volume | REAL | 是 | 否 |  | 成交量（股） | 0.0% |  |
| amount | REAL | 是 | 否 |  | 成交金额（元） | 0.0% |  |
| turnover_rate | REAL | 是 | 否 |  | 换手率（%） | 0.0% |  |
| amplitude | REAL | 是 | 否 |  | 振幅（%） | 0.0% |  |
| change_percent | REAL | 是 | 否 |  | 涨跌幅（%） | 0.0% |  |
| change_amount | REAL | 是 | 否 |  | 涨跌额（元） | 0.0% |  |
| ema5 | REAL | 是 | 否 |  | 5季度指数移动平均线 | 0.0% |  |
| ema10 | REAL | 是 | 否 |  | 10季度指数移动平均线 | 0.0% |  |
| ema20 | REAL | 是 | 否 |  | 20季度指数移动平均线 | 0.0% |  |
| ema50 | REAL | 是 | 否 |  | 50季度指数移动平均线 | 0.0% |  |
| ema100 | REAL | 是 | 否 |  | 100季度指数移动平均线 | 0.0% |  |
| ema200 | REAL | 是 | 否 |  | 200季度指数移动平均线 | 0.0% |  |
| macd_dif | REAL | 是 | 否 |  | MACD指标-DIF线 | 0.0% |  |
| macd_signal | REAL | 是 | 否 |  | MACD指标-信号线（DEA） | 0.0% |  |
| macd_histogram | REAL | 是 | 否 |  | MACD指标-柱状线（MACD） | 0.0% |  |
| created_at | TIMESTAMP | 是 | 否 | CURRENT_TIMESTAMP |  | 0.0% |  |

## 字段详细统计

