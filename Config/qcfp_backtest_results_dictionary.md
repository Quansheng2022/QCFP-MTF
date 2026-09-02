# qcfp_backtest_results 数据字典

- **表名**: `qcfp_backtest_results`
- **生成时间**: 2026-08-24 22:03:30
- **总记录数**: 0
- **股票数量**: 0

| 字段名 | 数据类型 | 描述 |
|--------|----------|------|
| id | INTEGER | 主键，自增ID |
| stock_code | TEXT | 股票代码（5位数字） |
| signal_date | TEXT | 信号日期 |
| action_signal | TEXT | 行动信号 |
| position | REAL | 仓位（0~1） |
| pnl | REAL | 收益（%） |
| mtf_regime | TEXT | 当时 MTF 状态 |
| market_regime | TEXT | 市场环境（牛/熊/震荡） |
| model_version | TEXT | 模型版本号 |
| run_id | TEXT | 回测运行标识 |
| update_time | TEXT | 更新时间 |

