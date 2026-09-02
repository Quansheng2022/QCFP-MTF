# qcfp_mtf_decision 数据字典

- **表名**: `qcfp_mtf_decision`
- **生成时间**: 2026-08-24 22:03:30
- **总记录数**: 10046
- **股票数量**: 16

| 字段名 | 数据类型 | 描述 |
|--------|----------|------|
| id | INTEGER | 主键，自增ID |
| stock_code | TEXT | 股票代码（5位数字） |
| stock_name | TEXT | 股票名称 |
| decision_date | TEXT | 决策日期（YYYY-MM-DD） |
| structural_regime | TEXT | 季度结构状态（继承 FSM-1） |
| monthly_behavior_state | TEXT | 月线阶段（继承） |
| tactical_signal | TEXT | 周线信号（继承） |
| cbi_score | REAL | CBI 筹码行为指数（0~100） |
| cost_position | TEXT | 成本位置（COST_ADVANTAGE/NEUTRAL/DISADVANTAGE） |
| chip_stability_confidence | TEXT | 筹码稳定置信度（High/Medium/Low） |
| mtf_regime | TEXT | MTF 状态（5 种：BULLISH_CONFIRMED 等） |
| qcfp_score | REAL | QCFP 综合评分（0~100，辅助参考） |
| action_signal | TEXT | 行动信号（BUY/ADD/HOLD/REDUCE/EXIT/WAIT） |
| risk_level | TEXT | 风险等级（Low/Medium/High/Extreme） |
| market_context | TEXT | 大盘环境上下文（来自 hk_idx_hist 派生） |
| evidence_summary | TEXT | 证据等级摘要 |
| model_version | TEXT | 模型版本号 |
| data_quality | TEXT | 数据质量等级（A/B/C/D） |
| update_time | TEXT | 更新时间 |
| structure_behavior_alignment | TEXT |  |
| catalyst_score | REAL |  |
| catalyst_type | TEXT |  |
| align_method | TEXT | 对齐方法（matrix/fallback/tactical_override/data_insufficient） |
| des_score | INTEGER | 下行证据评分（0~12+） |
| des_band | TEXT | 下行证据档位（NORMAL/WATCH/REDUCE/DE-RISK） |
| alignment_override | INTEGER | 对齐层覆盖标记（1=战术覆盖 TEST_BUY，0=否） |
| base_action | TEXT | 风险层干预前的基础动作（如 REDUCE） |
| final_action | TEXT | 风险层干预后的最终动作（如 EXIT） |
| base_target | REAL | 风险层干预前的基础目标仓位 |
| final_target | REAL | 风险层干预后的最终目标仓位（EXIT=0） |
| risk_override_active | INTEGER | 下行风险覆盖是否激活（DES≥5 或风险下限） |

