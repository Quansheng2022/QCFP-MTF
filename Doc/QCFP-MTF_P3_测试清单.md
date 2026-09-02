# QCFP-MTF P3 测试清单

> 适用范围：周线战术引擎（放量/缩量、换手偏离/极端、VWAP 偏离、均线斜率、4 种信号）
> 验收口径：A~G 全部勾选 = P3 完成
> 记录：2026-08-19 实测基线（当前全部通过）

## 运行环境

- 项目根目录 `C:\Users\Quansheng\Documents\projects\TA_Workflow`；
- 使用 `.venv\Scripts\python.exe`；中文乱码先执行 `$env:PYTHONIOENCODING="utf-8"; $env:PYTHONUTF8="1"`；
- 数据库：`SQLiteDB/HK_Stock.db`。

---

## A. 单元测试（自动化）

- [ ] A1 全量回归：`.venv\Scripts\python.exe Core\QCFP_MTF\tests\run_all_tests.py`
  → 共 97 项全部 PASS（P0 40 + P1 20 + P2 21 + P3 16），退出码 0
- [ ] A2 pytest：`.venv\Scripts\python.exe -m pytest Core\QCFP_MTF\tests -v`
  → 97 passed
- [ ] A3 P3 专项：`... python Core\QCFP_MTF\tests\test_tactical\test_weekly_signal.py`（其余 4 个 P3 模块同理）
  → 每模块"全部通过 ✅"

## B. 因子模块单测（合成数据）

- [ ] B1 周量：放量阈值（>MA20×1.8）、缩量阈值（<MA20×0.5）、窗口不足 → 0
- [ ] B2 周换手：季度周均偏离公式、极端换手（>MA8×2.0）
- [ ] B3 周 VWAP：偏离公式手算一致、零成交量 → NaN
- [ ] B4 信号合成：突破三确认（新高+放量+VWAP 上）、无放量不突破、破位、Pullback、Consolidation、均线加速

## C. 数据表验证（qcfp_weekly_tactical）

- [ ] C1 行数与股票：`SELECT COUNT(*), COUNT(DISTINCT stock_code) FROM qcfp_weekly_tactical`
  → 9827 行 / 15 只
- [ ] C2 时间范围：`SELECT MIN(week_end), MAX(week_end) ...`
  → 2010-01-08 ~ 2026-08-14
- [ ] C3 信号分布：`SELECT tactical_signal, COUNT(*) ... GROUP BY 1`
  → Consolidation 8233 / Pullback 1038 / Breakdown 472 / Breakout 84
- [ ] C4 突破/破位标记：`SELECT SUM(w_breakout), SUM(w_breakdown) FROM ...`
  → 84 / 472
- [ ] C5 量能标记：`SELECT SUM(w_volume_breakout), SUM(w_volume_shrink), SUM(w_turnover_spike) FROM ...`
  → 920 / 1418 / 501
- [ ] C6 均线斜率：`SELECT w_ma_slope, COUNT(*) ...`
  → 加速 4019 / 减速 3927 / 平稳 1851
- [ ] C7 数据质量：`SELECT data_quality, COUNT(*) ...`
  → A:6914 / C:2913（继承 weekly_kline 审计等级）
- [ ] C8 幂等性：重复运行 `weekly_tactical_engine.py` 两次
  → 行数不变（9827）、无唯一键冲突
- [ ] C9 唯一索引：`PRAGMA index_list(qcfp_weekly_tactical)`
  → 含 `idx_qcfp_wt_code_week`（UNIQUE）
- [ ] C10 新增列：`PRAGMA table_info(qcfp_weekly_tactical)`
  → 含 w_volume_shrink

## D. 引擎运行

- [ ] D1 单股：`... weekly_tactical_engine.py --stock 00700`
  → 日志显示"已 UPSERT 865 行"（00700 周线数），退出码 0
- [ ] D2 全量：不加参数 → "已 UPSERT 9827 行"
- [ ] D3 预演：`--dry-run` → 生成报告不写库
- [ ] D4 指定周：`--week-end 2026-08-14` → 仅该周
- [ ] D5 报告产物：`Report/QCFP_MTF/weekly/weekly_tactical_<时间戳>.{csv,json}`

## E. 合理性检查

- [ ] E1 00700 最新周（2026-08-14）：Consolidation、无放量/缩量/极端换手、VWAP -2.97%、slope=减速
- [ ] E2 Breakout 稀有（84/9827 ≈ 0.9%）符合三重确认设计；Breakdown 472（4.8%）
- [ ] E3 Pullback 月份应伴随 close < ema5 且 > ema20（抽样报告 CSV 验证）

## F. 工作流集成

- [ ] F1 全流程：`.venv\Scripts\python.exe run_QCFP_MTF_workflow.py`
  → 7 步全 ✅（…structural → monthly_behavior → **weekly_tactical** → validate），退出码 0
- [ ] F2 日志：`Log/weekly_tactical_engine.py.log` 存在且中文正常
- [ ] F3 幂等：连续两次全流程不报错

## G. 工程约定

- [ ] G1 字典同步：`Code_utl\Generate_qcfp_Dictionaries.py` 重跑后，
  `Config/qcfp_weekly_tactical_dictionary.json` 字段数 = PRAGMA 列数（含 w_volume_shrink）
- [ ] G2 源表只读：`hk_*` 表结构未被 P3 改动
- [ ] G3 无乱码：CSV 报告 utf-8-sig

---

## 验收标准

- 必备：A1、B1~B4、C1~C10、D1~D2、D5、E1~E3、F1~F3、G1~G3；
- 可选：A2~A3、D3~D4；
- 说明：E3 属抽样验证，可结合最新报告 CSV 抽查。
