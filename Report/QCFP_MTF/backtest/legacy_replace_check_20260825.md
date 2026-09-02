# QCFP-MTF Legacy → New 验收替换检查

- 焦点：01951　时间：2026-08-25 23:09:23

## 结论：**PASS（可切换默认 engine_source=canonical）**

| 检查 | 状态 | 证据 |
| :-- | :-- | :-- |
| C1 Consistency（重放确定性） | PASS | 两次 canonical_replay target 完全一致 |
| C2 OOS（Rolling OOS Sharpe 中位数） | PASS | median=0.4521 |
| C3 Ablation（Governance 层有效） | PASS | New 捕获比=0.0012，Legacy=-0.1068 |
| C4 Governance（版本身份/越权） | PASS | QCFP-MTF-2.5.0/GOV-2.5.0/DECISION-1.1；引擎内断言越权=0 |

## 绩效对照

| 口径 | 年化 | MDD | 波段捕获比 |
| :-- | --: | --: | --: |
| Legacy | -9.83% | -45.03% | -0.1068 |
| New（canonical） | 0.02% | -0.02% | 0.0012 |