# Continuous Validation Report

**安全状态：HALTED**

## 触发项

- ledger_failure

## 劣化指标

- wave_capture_trend：1.0
- false_entry_rate：0.0
- slippage_ratio：1.0
- mfe_bias：0.0
- mae_bias：0.0
- permission_flip_rate：0.0
- liquidity_flag：LIQUIDITY_OK

## 建议

- HALTED：禁止产生任何新交易决策，先人工排查
- 台账完整性异常：立即审计 qcfp_decision_ledger
