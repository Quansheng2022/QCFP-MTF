# qcfp_data_quality_audit 数据字典

- **表名**: `qcfp_data_quality_audit`
- **生成时间**: 2026-08-24 22:03:30
- **总记录数**: 154
- **股票数量**: 17

| 字段名 | 数据类型 | 描述 |
|--------|----------|------|
| id | INTEGER | 主键，自增ID |
| stock_code | TEXT | 股票代码（5位数字；IDX 表示大盘指数） |
| data_type | TEXT | 数据源类型（如 daily_kline / institutional_holdings） |
| grade | TEXT | 质量等级（A/B/C/D） |
| rows | INTEGER | 记录数 |
| first_date | TEXT | 首条日期 |
| last_date | TEXT | 末条日期 |
| core_missing_rate | REAL | 核心字段缺失率（0~1） |
| anomalies | INTEGER | 异常值数量 |
| reasons | TEXT | 降级原因说明 |
| model_version | TEXT | 模型版本号 |
| audit_date | TEXT | 审计日期（YYYY-MM-DD） |
| update_time | TEXT | 更新时间 |

