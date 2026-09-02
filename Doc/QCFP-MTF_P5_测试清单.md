# QCFP-MTF P5 测试清单

> 适用范围：DSS 决策层（Score / Action / Risk / DSS 输出协议）
> 验收口径：A~G 全部勾选 = P5 完成
> 记录：2026-08-20 实测基线（当前全部通过）

## 运行环境

- 项目根目录 `C:\Users\Quansheng\Documents\projects\TA_Workflow`；
- 使用 `.venv\Scripts\python.exe`；中文乱码先执行 `$env:PYTHONIOENCODING="utf-8"; $env:PYTHONUTF8="1"`；
- 数据库：`SQLiteDB/HK_Stock.db`。

---

## A. 单元测试（自动化）

- [ ] A1 全量回归：`.venv\Scripts\python.exe Core\QCFP_MTF\tests\run_all_tests.py`
  → 共 133 项全部 PASS（P0 40 + P1 20 + P2 21 + P3 16 + P4 21 + P5 15），退出码 0
- [ ] A2 pytest：`.venv\Scripts\python.exe -m pytest Core\QCFP_MTF\tests -v`
  → 133 passed
- [ ] A3 P5 专项：`... python Core\QCFP_MTF\tests\test_decision\test_action_generator.py`（其余 4 个 P5 模块同理）
  → 每模块"全部通过 ✅"

## B. 决策模块单测（合成数据）

- [ ] B1 Score：State-First 映射（85/75/55/40/20）、DATA_INSUFFICIENT → None
- [ ] B2 Action：基础映射（BUY/HOLD/REDUCE/WAIT/EXIT）、空头族禁 BUY/ADD、多头族禁 EXIT（强制 REDUCE）、Extreme→WAIT、数据不足→WAIT
- [ ] B3 Risk：base+各项加成计分（Low/Medium/High/Extreme 边界）
- [ ] B4 DSS 输出：规格书第七章 7 大节结构完整、字段映射正确

## C. 数据表验证（qcfp_mtf_decision）

- [ ] C1 action 填充：`SELECT action_signal, COUNT(*) ... GROUP BY 1`
  → EXIT 3364 / REDUCE 2872 / HOLD 2840 / WAIT 742 / BUY 9
- [ ] C2 risk 填充：`SELECT risk_level, COUNT(*) ... GROUP BY 1`
  → Extreme 4645 / High 2498 / Medium 1732 / Low 952
- [ ] C3 全量门控验证（必须为 0）：
  `SELECT COUNT(*) FROM qcfp_mtf_decision WHERE structural_regime IN ('STRUCTURAL_DECLINE','STRUCTURAL_DISTRIBUTION') AND action_signal IN ('BUY','ADD')`
  → 0；反向（多头族 + EXIT）也为 0
- [ ] C4 幂等性：重复运行 `decision_engine.py` 两次 → 分布不变
- [ ] C5 qcfp_score 非空：9097 行（DATA_INSUFFICIENT 730 行为 NULL）
- [ ] C6 structure_behavior_alignment 列存在（P5 新增迁移）

## D. 引擎与报告

- [ ] D1 `decision_engine.py` 全量：日志"已回写 9827 行"，退出码 0
- [ ] D2 `dss_report.py --stock 00700`：
  → 生成 `Report/QCFP_MTF/dss/00700_2026-08-14.{json,md}`
- [ ] D3 00700 最新决策：BEARISH_CONFIRMED → EXIT / risk=Extreme / position 0%
- [ ] D4 DSS JSON 含 7 大节（structural/stage/cost_position/trigger/confidence/risk/decision）
- [ ] D5 `--dry-run` 不写库

## E. 合理性检查

- [ ] E1 Action 与 MTF 状态一致性：BULLISH_CONFIRMED→BUY、BULLISH_WARNING→REDUCE、BEARISH_CONFIRMED→EXIT
- [ ] E2 风险与市场环境：risk_off 行风险等级显著高于 risk_on 行（抽样）
- [ ] E3 EXIT 行均为空头结构（BEARISH_CONFIRMED）

## F. 工作流集成

- [ ] F1 全流程：`.venv\Scripts\python.exe run_QCFP_MTF_workflow.py`
  → 9 步全 ✅（…mtf_fusion → **decision_engine** → validate），退出码 0
- [ ] F2 日志：`Log/decision_engine.py.log` / `Log/dss_report.log` 存在且中文正常
- [ ] F3 幂等：连续两次全流程不报错

## G. 工程约定

- [ ] G1 字典同步：`Code_utl\Generate_qcfp_Dictionaries.py` 重跑后，
  `Config/qcfp_mtf_decision_dictionary.json` 字段数 = PRAGMA 列数（含 structure_behavior_alignment）
- [ ] G2 源表只读：`hk_*` 表结构未被 P5 改动
- [ ] G3 无乱码：DSS 报告 JSON/MD 为 UTF-8

---

## 验收标准

- 必备：A1、B1~B4、C1~C5、D1~D4、E1~E3、F1~F3、G1~G3；
- 可选：A2~A3、D5；
- 说明：C3 是全量门控验证（M5 核心验收项），必须为 0。
