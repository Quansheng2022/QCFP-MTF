# hk_hist_daily_moneyflow 数据字典

## 基本信息

- **表名**: `hk_hist_daily_moneyflow`
- **生成时间**: 2026-07-14 16:26:12
- **数据库路径**: `C:\Users\Quansheng\Documents\projects\TA_Workflow\SQLiteDB\HK_Stock.db`
- **字段数量**: 18

## 统计信息

- **总记录数**: 15
- **股票数量**: 15
- **日期范围**: 2026-07-14 至 2026-07-14

## 字段信息

| 字段名 | 数据类型 | 可空 | 主键 | 默认值 | 描述 | 空值比例 | 示例值 |
|--------|----------|------|------|--------|------|----------|--------|
| id | INTEGER | 是 | 是 |  | 主键，自增ID | 0.0% | 22, 23 |
| stock_code | TEXT | 否 | 否 |  | 股票代码（如：00700） | 0.0% | 00020, 00268 |
| stock_name | TEXT | 否 | 否 |  | 股票名称 | 0.0% | ,  |
| date | TEXT | 否 | 否 |  | 交易日期（格式：YYYY-MM-DD） | 0.0% | 2026-07-14, 2026-07-14 |
| Price_ChgPct | REAL | 是 | 否 |  | 价格涨跌幅（百分比） | 100.0% |  |
| Capital_Trend | REAL | 是 | 否 |  | 资金趋势/净流入额 | 0.0% | 0.0, 0.0 |
| Extra_Large | REAL | 是 | 否 |  | 特大单净流入额 | 0.0% | 0.0, 0.0 |
| Large | REAL | 是 | 否 |  | 大单净流入额 | 0.0% | 0.0, 0.0 |
| Medium | REAL | 是 | 否 |  | 中单净流入额 | 0.0% | 0.0, 0.0 |
| Small | REAL | 是 | 否 |  | 小单净流入额 | 0.0% | 0.0, 0.0 |
| capital_in_super | REAL | 是 | 否 |  | 特大单买入额 | 100.0% |  |
| capital_in_big | REAL | 是 | 否 |  | 大单买入额 | 100.0% |  |
| capital_in_mid | REAL | 是 | 否 |  | 中单买入额 | 100.0% |  |
| capital_in_small | REAL | 是 | 否 |  | 小单买入额 | 100.0% |  |
| capital_out_super | REAL | 是 | 否 |  | 特大单卖出额 | 100.0% |  |
| capital_out_big | REAL | 是 | 否 |  | 大单卖出额 | 100.0% |  |
| capital_out_mid | REAL | 是 | 否 |  | 中单卖出额 | 100.0% |  |
| capital_out_small | REAL | 是 | 否 |  | 小单卖出额 | 100.0% |  |

## 字段详细统计

### id

- **最小值**: 16
- **最大值**: 30
- **平均值**: 23.0
- **不同值数量**: 15
- **空值数量**: 0
- **非空数量**: 15
- **空值比例**: 0.00%

### Capital_Trend

- **最小值**: 0.0
- **最大值**: 0.0
- **平均值**: 0.0
- **不同值数量**: 1
- **空值数量**: 0
- **非空数量**: 15
- **空值比例**: 0.00%

### Extra_Large

- **最小值**: 0.0
- **最大值**: 0.0
- **平均值**: 0.0
- **不同值数量**: 1
- **空值数量**: 0
- **非空数量**: 15
- **空值比例**: 0.00%

### Large

- **最小值**: 0.0
- **最大值**: 0.0
- **平均值**: 0.0
- **不同值数量**: 1
- **空值数量**: 0
- **非空数量**: 15
- **空值比例**: 0.00%

### Medium

- **最小值**: 0.0
- **最大值**: 0.0
- **平均值**: 0.0
- **不同值数量**: 1
- **空值数量**: 0
- **非空数量**: 15
- **空值比例**: 0.00%

### Small

- **最小值**: 0.0
- **最大值**: 0.0
- **平均值**: 0.0
- **不同值数量**: 1
- **空值数量**: 0
- **非空数量**: 15
- **空值比例**: 0.00%

## 示例数据

| id | stock_code | stock_name | date | Price_ChgPct | Capital_Trend | Extra_Large | Large | Medium | Small | capital_in_super | capital_in_big | capital_in_mid | capital_in_small | capital_out_super | capital_out_big | capital_out_mid | capital_out_small |
|--------|--------|--------|--------|--------|--------|--------|--------|--------|--------|--------|--------|--------|--------|--------|--------|--------|--------|
| 16 | 00788 |  | 2026-07-14 | None | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | None | None | None | None | None | None | None | None |
| 17 | 00371 |  | 2026-07-14 | None | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | None | None | None | None | None | None | None | None |
| 18 | 02202 |  | 2026-07-14 | None | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | None | None | None | None | None | None | None | None |
| 19 | 00354 |  | 2026-07-14 | None | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | None | None | None | None | None | None | None | None |
| 20 | 00357 |  | 2026-07-14 | None | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | None | None | None | None | None | None | None | None |

