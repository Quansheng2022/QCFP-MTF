# QCFP-MTF 2.2 测试清单

> 验收口径：全量 57 模块通过（`run_all_tests.py`）；G1~G7 全部勾选 = 2.2 完成。

## A. 单元测试（自动化）

- [ ] A1 全量：`.venv\Scripts\python.exe Core\QCFP_MTF\tests\run_all_tests.py` → 57 模块 PASS
- [ ] A2 pytest：`-m pytest Core\QCFP_MTF\tests -v`（integration marker 已注册于 pytest.ini）

## B. 2.2 正式引擎

- [ ] B1 Institutional Permission：权限矩阵（ACCUMULATION→ALLOW/STRONG_ALLOW、NEUTRAL→WATCH、
      RECOVERY→TEST、DISTRIBUTION/CAPITULATION→BLOCK、UNKNOWN→WATCH）
- [ ] B2 降级：Divergence/LowConfidence→WATCH、DQ(D)→BLOCK、RiskOff→TEST；BLOCK 不可升级
- [ ] B3 FSM 全生命周期：FLAT→TESTING→BUILDING→HOLDING→TRIMMING→EXITING→COOLDOWN→TESTING
- [ ] B4 禁止状态跳跃：FLAT 不得直接 HOLDING
- [ ] B5 Hard Exit 最高优先级：STRONG_ALLOW+Breakout+DES8→EXITING
- [ ] B6 不可越权矩阵：BLOCK×{Breakout/Pullback/Consolidation}×{Low/Medium/High}→FLAT
- [ ] B7 追高过滤：DAILY_BREAKOUT + 52W>0.6 → 不 BUILD
- [ ] B8 仓位加法阶梯：TESTING 10% / BUILDING +10%（上限 70%）/ TRIMMING -15%
- [ ] B9 Permission 降级联动：HOLDING/BUILDING + BLOCK + 持仓>0 → TRIMMING
- [ ] B10 Setup Engine：weekly+daily → BREAKOUT/PULLBACK/ACCUMULATION/RECOVERY/NONE
- [ ] B11（V29）ExitEvent：HARD_EXIT（DES≥7）/ STOP_EXIT / FORCED_DELEVERAGE / NONE 分类正确
- [ ] B12（V29）Permission Ceiling：BLOCK→FLAT、WATCH→TESTING、TEST→TESTING、
      ALLOW→BUILDING、STRONG_ALLOW→HOLDING；`assert_permission_bound` 越权抛错；
      HOLDING（维持仓位）不算新增风险
- [ ] B13（V29）DecisionSnapshot 确定性：同一输入两次构建完全一致；
      00371（DES=12）→ HARD_EXIT / EXITING / target=0
- [ ] B14（V29）A0~A4 Ablation：A1 用 Cap（非二值门）；A2~A4 零越权、零非法跳跃；
      暴露效率/坏暴露比输出

## C. 金融不变量（纯合成，脱离 SQLite）

- [ ] C1 PIT：available_date ≤ decision_date
- [ ] C2 Position ∈ [0,1]；止损后无未来 PnL（position_start=0）
- [ ] C3 成本守恒：pnl = position_start × effective_return − cost
- [ ] C4 缺失收益不变成 0（return_missing / pnl=NaN）
- [ ] C5 PIT Universe 重叠检测；research_validation 缺 universe → FAILED
- [ ] C6 Benchmark 独立（只用价格）

## D. 金标准案例（tests/golden/）

- [ ] D1 00371 下行：BULLISH+Breakdown+DES≥7 → EXIT/Extreme/0
- [ ] D2 01951 恢复：DECLINE+52W 极低 → TEST_BUY/20%

## E. 回测正确性

- [ ] E1 Entry-Week-Low Stop：周收盘确认 → 次周离场；退出后无暴露
- [ ] E2 横截面 target 语义：target/N（总暴露=均值），不归一化到 100%
- [ ] E3 横截面缺失收益：仅剔该股周，不整周删除
- [ ] E4 超额收益定义：strategy/benchmark CAGR + spread + 算术主动收益 + IR
- [ ] E5 基准同口径：Buy&Hold/Momentum 与策略共用 PIT Universe

## F. 验证协议（research_validation，12 门）

- [ ] F1 01~12 门：PIT Universe / Available-date / Signal→Return / Cost / Liquidity /
      OOS（median>0.3 且正窗≥60%）/ Plateau（同参≥80% 且平台≥50%）/ HAC-BH / Ablation /
      Regime（risk_off 护栏 + 集中度）/ Delisting / Capacity
- [ ] F2 研究状态如实：PIT-C → research_exploration；research_validation 需 PIT-A/B

## G. Shadow / Ablation

- [ ] G1 shadow_mode.py：Legacy vs New 双轨输出，不写库不改交易
- [ ] G2 permission_fsm_ablation.py：A/B/C/D 四模型；Permission=Risk Filtering、
      FSM=Entry/Exit 质量假设可复现
- [ ] G3（V29）shadow_mode.py Stateful Replay：按 stock×date 全历史滚动，
      prev_state→next_state→target 演化；00371 产出 868 快照

## H. 报告

- [ ] H1 DSS/All-in-One 含散户决策卡（红黄绿灯/机构状态→权限/FSM/建议仓位）
- [ ] H2 Scope/Provenance 分离（个股回测 vs Full Universe 诊断）
- [ ] H3 Research Manifest（run_id→config/code/data/pit 可追溯）

## I. 全量回归

- [ ] I1 `run_all_tests.py` → 57 模块全 PASS
