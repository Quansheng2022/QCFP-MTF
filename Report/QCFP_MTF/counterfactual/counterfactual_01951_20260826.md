# Counterfactual Decision Replay　01951　2026-08-21

> 数据源：NON_CANONICAL|point-in-time 推算（无 Ledger/Shadow 匹配，按 FLAT/0 起算）　|　run_id：counterfactual
> 基线：FLAT @ 0%

| 变体 | 目标仓位 | FSM | 主因 | Action | 相对 Actual Δ仓位 |
| --- | --- | --- | --- | --- | --- |
| 全模块开启（Actual） | 0.0% | COOLDOWN | FORCED_DELEVERAGE | WAIT | +0.0% |
| 关闭 Institutional Permission | 0.0% | COOLDOWN | FORCED_DELEVERAGE | WAIT | +0.0% |
| 关闭 Wave/Setup 信号 | 0.0% | COOLDOWN | FORCED_DELEVERAGE | WAIT | +0.0% |
| 关闭 Risk 约束 | 2.5% | TESTING | POSITION_CAP | HOLD | +2.5% |
| 关闭 Portfolio 约束 | 0.0% | COOLDOWN | FORCED_DELEVERAGE | WAIT | +0.0% |
| 关闭日线战术层 | 0.0% | COOLDOWN | FORCED_DELEVERAGE | WAIT | +0.0% |
| 关闭 Hard Exit | 0.0% | FLAT | DAILY_TRIGGER_ABSENT | REDUCE | +0.0% |

## Unified Decision Object（11 号）

- decision_id：`01951_2026-08-21`
- version_hash：`574715db01280db3`
- decision_hash：`5a3d12b7c9cdec0f`
- consumers：REPLAY
- 一致性违规：无

## 结论

模块关闭导致 2/6 个变体改变决策：no_risk；no_hard_exit