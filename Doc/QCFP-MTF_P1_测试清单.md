# QCFP-MTF P1 测试清单

> 适用范围：季度结构引擎（C/F/P 因子 + FSM-1 + Core Score + 三维背离）
> 验收口径：A~H 全部勾选 = P1 完成
> 记录：2026-08-19 实测基线（当前全部通过）

## 运行环境

- 项目根目录 `C:\Users\Quansheng\Documents\projects\TA_Workflow`；
- 使用 `.venv\Scripts\python.exe`；中文乱码先执行 `$env:PYTHONIOENCODING="utf-8"; $env:PYTHONUTF8="1"`；
- 数据库：`SQLiteDB/HK_Stock.db`。

---

## A. 单元测试（自动化）

- [ ] A1 全量回归：`.venv\Scripts\python.exe Core\QCFP_MTF\tests\run_all_tests.py`
  → 共 60 项全部 PASS（P0 40 项 + P1 20 项），退出码 0
- [ ] A2 pytest：`.venv\Scripts\python.exe -m pytest Core\QCFP_MTF\tests -v`
  → 60 passed
- [ ] A3 P1 专项：`... python Core\QCFP_MTF\tests\test_structural\test_structural_regime.py`（其余 5 个 P1 模块同理）
  → 每模块"全部通过 ✅"

## B. 因子模块单测（合成数据）

- [ ] B1 C 因子：↑/↓/→ 阈值判定、公司行为屏蔽（corporate_action_flag=1 → c_state 为空）、首季 C_NA、置信度 0~2
- [ ] B2 F 因子：滚动 Z-Score 方向、资金流缺失 → F_UNKNOWN、IFA 横截面 Z、period_end 格式
- [ ] B3 P 因子：q_return 环比、p_state 阈值、52W 位置（0~1）、Trend Score 落在 0~100、负价格清洗
- [ ] B4 背离：CPD/FPD/CFD 顶/底背离、NaN 处理、布尔标记

## C. 状态机规则

- [ ] C1 直接映射：6 种 C/F/P 组合 → 6 状态，方法 = direct
- [ ] C2 转换规则：规格书 8 条转换的目标状态与直接映射一致（`test_all_transitions_equivalent_to_direct_map`）
- [ ] C3 F 缺失降级：4 条 C+P 映射（如 C↑P↑ → ACCUMULATION）；未定义组合 → STATE_UNDETERMINED
- [ ] C4 保持策略：未定义组合/因子缺失时保持上一状态；无历史 → UNDETERMINED
- [ ] C5 State-First：core_score 由状态映射（BULLISH=85…DECLINE=20），UNDETERMINED → None

## D. 数据表验证（qcfp_quarterly_structural）

- [ ] D1 行数与股票：`SELECT COUNT(*), COUNT(DISTINCT stock_code) FROM qcfp_quarterly_structural`
  → 944 行 / 14 只
- [ ] D2 时间范围：`SELECT MIN(period_end), MAX(period_end) ...`
  → 2004-03-31 ~ 2026-06-30
- [ ] D3 状态分布：`SELECT structural_regime, COUNT(*) ... GROUP BY structural_regime`
  → DECLINE 256 / UNDETERMINED 237 / ACCUMULATION 182 / DIVERGENCE 140 / BOTTOM_CANDIDATE 79 / BULLISH 45 / DISTRIBUTION 5
- [ ] D4 解析方法分布：`SELECT resolve_method, COUNT(*) ...`
  → fallback_f_missing 496 / hold_unmapped 249 / hold_missing_factor 145 / direct 50 / unmapped 4
- [ ] D5 数据质量分布：`SELECT data_quality, COUNT(*) ...`
  → A:26 / B:80 / C:838 / D:0（无矛盾性 D 级）
- [ ] D6 幂等性：重复运行 `structural_engine.py` 两次
  → 行数不变（944）、无唯一键冲突、状态分布稳定
- [ ] D7 样本抽查：00700 最新季度
  → 2026-06-30：STRUCTURAL_DECLINE / core_score 20 / hold_unmapped / data_quality B
- [ ] D8 索引：`PRAGMA index_list(qcfp_quarterly_structural)`
  → 含 `idx_qcfp_qs_code_period`（UNIQUE）

## E. 引擎运行

- [ ] E1 单股写库：`.venv\Scripts\python.exe Core\QCFP_MTF\scripts\structural_engine.py --stock 00700`
  → 日志显示"已 UPSERT 89 行"，退出码 0
- [ ] E2 全量运行：不加参数
  → "已 UPSERT 944 行"；`03033` 显示跳过（DATA_INSUFFICIENT）
- [ ] E3 预演：`--dry-run`
  → 生成报告但不写库，日志标注"未写库"
- [ ] E4 指定季度：`--period-end 2026-06-30`
  → 仅输出该季度
- [ ] E5 报告产物：`Report/QCFP_MTF/structural/structural_<时间戳>.{csv,json}`
  → 含 stock_code / period_end / structural_regime / core_score / resolve_method / cpd/fpd/cfd 等列

## F. 交叉验证（M1 验收）

- [ ] F1 运行：`.venv\Scripts\python.exe Core\QCFP_MTF\scripts\validate_structural.py`
- [ ] F2 验收线：`direct 证据行一致率 ≥ 70%`
  → 当前 9/10 = 90.0% ✅（对比对象：hk_quarterly_chip_analysis.chip_flow_price_regime 方向化）
- [ ] F3 参考口径：整体一致率（含 hold 保持行）当前 75/144 = 52.1%，作为路径依赖参考
- [ ] F4 报告：`Report/QCFP_MTF/structural/validate_<时间戳>.{csv,json}`
  → JSON 含 direct_agreement_rate

## G. 工作流集成

- [ ] G1 全流程：`.venv\Scripts\python.exe run_QCFP_MTF_workflow.py`
  → 5 步全 ✅：init_db → audit_coverage → check_data_quality → structural_engine → validate_structural，退出码 0
- [ ] G2 日志：`Log/{structural_engine,validate_structural}.py.log`
  → 存在且中文正常
- [ ] G3 幂等：连续跑两次全流程不报错

## H. 工程约定

- [ ] H1 字典同步：`Code_utl\Generate_qcfp_Dictionaries.py` 重跑后，
  `Config/qcfp_quarterly_structural_dictionary.json` 字段数 = PRAGMA 列数（含新增 resolve_method）
- [ ] H2 源表只读：`hk_*` 表结构未被 P1 改动
- [ ] H3 无乱码：CSV 报告 utf-8-sig，Excel 直接打开正常

---

## 验收标准

- 必备：A1、B1~B4、C1~C5、D1~D8、E1~E2、E5、F1~F2、F4、G1~G3、H1~H3；
- 可选：A2~A3、E3~E4（抽查类）；
- 说明：D5 的"D:0"是修复"F 缺失降级产生矛盾性 D"后的基线；若未来调整降级规则需同步更新预期。
