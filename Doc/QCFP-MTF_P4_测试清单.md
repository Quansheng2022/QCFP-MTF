# QCFP-MTF P4 测试清单

> 适用范围：多周期融合层（Chip Confidence / MTF 对齐 / FSM-2 / Anti-Inference / 结构-行为背离）
> 验收口径：A~G 全部勾选 = P4 完成
> 记录：2026-08-19 实测基线（当前全部通过）

## 运行环境

- 项目根目录 `C:\Users\Quansheng\Documents\projects\TA_Workflow`；
- 使用 `.venv\Scripts\python.exe`；中文乱码先执行 `$env:PYTHONIOENCODING="utf-8"; $env:PYTHONUTF8="1"`；
- 数据库：`SQLiteDB/HK_Stock.db`。

---

## A. 单元测试（自动化）

- [ ] A1 全量回归：`.venv\Scripts\python.exe Core\QCFP_MTF\tests\run_all_tests.py`
  → 共 118 项全部 PASS（P0 40 + P1 20 + P2 21 + P3 16 + P4 21），退出码 0
- [ ] A2 pytest：`.venv\Scripts\python.exe -m pytest Core\QCFP_MTF\tests -v`
  → 118 passed
- [ ] A3 P4 专项：`... python Core\QCFP_MTF\tests\test_fusion\test_mtf_alignment.py`（其余 4 个 P4 模块同理）
  → 每模块"全部通过 ✅"

## B. 融合模块单测（合成数据）

- [ ] B1 Chip Confidence：60/40 加权公式、High/Medium/Low 阈值、C↓ 强制 Low、缺失输入 → None
- [ ] B2 MTF 对齐：12 条矩阵精确映射、兜底规则（多头族/空头族/DIVERGENCE/BOTTOM）、DATA_INSUFFICIENT
- [ ] B3 不越权：多头结构禁 BEARISH_CONFIRMED、空头结构禁多头状态（`_assert_no_overrule` 抛错）
- [ ] B4 FSM-2：状态转换、Breakdown 降级为 BULLISH_WARNING
- [ ] B5 Anti-Inference：13 条规则（规格书 2.3）、warn 保留原文、replace 替换、干净文本不误报
- [ ] B6 结构-行为背离：多头+恶化 / 空头+改善 → Divergence，其余 Aligned/Unknown

## C. 数据表验证（qcfp_mtf_decision）

- [ ] C1 行数与股票：`SELECT COUNT(*), COUNT(DISTINCT stock_code) FROM qcfp_mtf_decision`
  → 9827 行 / 15 只（每股票×每周一个决策点）
- [ ] C2 时间范围：`SELECT MIN(decision_date), MAX(decision_date) ...`
  → 2010-01-08 ~ 2026-08-14
- [ ] C3 MTF 状态分布：`SELECT mtf_regime, COUNT(*) ... GROUP BY 1`
  → BEARISH_CONFIRMED 3364 / BULLISH_WARNING 2872 / BULLISH_STABLE 2840 / DATA_INSUFFICIENT 730 / BEARISH_RECOVERY_CANDIDATE 12 / BULLISH_CONFIRMED 9
- [ ] C4 置信度分布：`SELECT chip_stability_confidence, COUNT(*) ...`
  → Low 6707 / Medium 3063 / High 57
- [ ] C5 市场环境：`SELECT market_context, COUNT(*) ...`
  → risk_off 4124 / neutral 3194 / risk_on 2509
- [ ] C6 不越权全量验证：
  `SELECT COUNT(*) FROM qcfp_mtf_decision WHERE structural_regime IN ('STRUCTURAL_BULLISH','STRUCTURAL_ACCUMULATION') AND mtf_regime='BEARISH_CONFIRMED'`
  → 0；反向（空头结构 + 多头状态）也为 0
- [ ] C7 数据质量：`SELECT data_quality, COUNT(*) ...`
  → C 8121 / B 1020 / A 333
- [ ] C8 幂等性：重复运行 `mtf_fusion_engine.py` 两次
  → 行数不变（9827）、无唯一键冲突
- [ ] C9 唯一索引：`PRAGMA index_list(qcfp_mtf_decision)`
  → 含 `idx_qcfp_mtf_code_date`（UNIQUE）
- [ ] C10 action_signal / risk_level 当前为 NULL（P5 填充）

## D. 引擎运行

- [ ] D1 单股：`... mtf_fusion_engine.py --stock 00700`
  → 日志显示"已 UPSERT 865 行"，退出码 0
- [ ] D2 全量：不加参数 → "已 UPSERT 9827 行"
- [ ] D3 预演：`--dry-run` → 生成报告不写库
- [ ] D4 指定决策日：`--date 2026-08-14` → 仅该日
- [ ] D5 报告产物：`Report/QCFP_MTF/fusion/mtf_decision_<时间戳>.{csv,json}`

## E. 合理性检查

- [ ] E1 00700 最新决策（2026-08-14）：BEARISH_CONFIRMED（结构 DECLINE）、conf=Low、market=risk_off
- [ ] E2 DATA_INSUFFICIENT 730 行均来自结构 UNDETERMINED/D（抽样验证）
- [ ] E3 置信度与状态一致性：BEARISH_CONFIRMED 行置信度以 Low 为主
- [ ] E4 摘要文本全部通过 Anti-Inference（`evidence_summary` 不含"Anti-Inference 警告"）

## F. 工作流集成

- [ ] F1 全流程：`.venv\Scripts\python.exe run_QCFP_MTF_workflow.py`
  → 8 步全 ✅（…weekly_tactical → **mtf_fusion** → validate），退出码 0
- [ ] F2 日志：`Log/mtf_fusion_engine.py.log` 存在且中文正常
- [ ] F3 幂等：连续两次全流程不报错

## G. 工程约定

- [ ] G1 字典同步：`Code_utl\Generate_qcfp_Dictionaries.py` 重跑后，
  `Config/qcfp_mtf_decision_dictionary.json` 字段数 = PRAGMA 列数
- [ ] G2 源表只读：`hk_*` 表结构未被 P4 改动
- [ ] G3 无乱码：CSV 报告 utf-8-sig

---

## 验收标准

- 必备：A1、B1~B6、C1~C10、D1~D2、D5、E1~E4、F1~F3、G1~G3；
- 可选：A2~A3、D3~D4；
- 说明：C6 是全量不越权验证（M4 核心验收项），必须为 0。
