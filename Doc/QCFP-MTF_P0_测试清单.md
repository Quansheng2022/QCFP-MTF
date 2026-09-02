# QCFP-MTF P0 测试清单

> 适用范围：`Core/QCFP_MTF` P0 阶段交付（基础设施与数据层）
> 验收口径：A~G 全部勾选 = P0 完成
> 记录：2026-08-19 实测基线（除标注"未实测"项外均已通过）

## 运行环境

- 所有命令在项目根目录 `C:\Users\Quansheng\Documents\projects\TA_Workflow` 执行；
- 使用项目虚拟环境：`.venv\Scripts\python.exe`；
- 控制台中文乱码时先执行：`$env:PYTHONIOENCODING="utf-8"; $env:PYTHONUTF8="1"`；
- 数据库：`SQLiteDB/HK_Stock.db`。

---

## A. 自动化单元测试（模块级）

- [ ] A1 全量回归（无需 pytest）：
  `.venv\Scripts\python.exe Core\QCFP_MTF\tests\run_all_tests.py`
  → 6 个模块共 36 项全部 PASS，退出码 0
- [ ] A2 pytest 方式回归：
  `.venv\Scripts\python.exe -m pytest Core\QCFP_MTF\tests -v`
  → 36 passed（venv 已装 pytest 9.1.1）
- [ ] A3 逐模块抽查：
  `.venv\Scripts\python.exe Core\QCFP_MTF\tests\test_calendar.py`（同理 test_normalization / test_settings / test_evidence / test_loader / test_quality）
  → 每模块打印"全部通过 ✅"
- [ ] A4 修改回归：改动 `common/` 或 `data/` 任一模块后重跑 A1
  → 无回归；重点覆盖：日历周/月/季切分、Winsorize→Z-Score→0~100 流水线、A/B/C/D 分级、证据降级

## B. 数据表验证（SQLiteDB/HK_Stock.db）

- [ ] B1 6 张表存在：
  `SELECT name FROM sqlite_master WHERE type='table' AND name LIKE 'qcfp_%'`
  → qcfp_quarterly_structural / qcfp_monthly_behavior / qcfp_weekly_tactical / qcfp_mtf_decision / qcfp_backtest_results / qcfp_data_quality_audit
- [ ] B2 列数符合设计：`PRAGMA table_info(<表名>)`
  → 23 / 17 / 15 / 19 / 11 / 13 列（对应上述顺序）
- [ ] B3 唯一索引生效：`PRAGMA index_list(qcfp_quarterly_structural)`
  → 含 `idx_qcfp_qs_code_period` 等 UNIQUE 索引
- [ ] B4 5 张结果表当前为空：
  `SELECT COUNT(*) FROM qcfp_quarterly_structural`（其余 4 张同理）
  → 均为 0 行（P1~P6 引擎填充）
- [ ] B5 审计表有历史快照：
  `SELECT COUNT(*), COUNT(DISTINCT audit_date) FROM qcfp_data_quality_audit`
  → 每次运行追加，当前 280 行 / 3 个审计日期
- [ ] B6 审计内容可读：
  `SELECT stock_code, data_type, grade, reasons FROM qcfp_data_quality_audit WHERE stock_code='00700'`
  → 10 类数据，daily_kline = C（负价格 4）
- [ ] B7 字段规范抽查：stock_code 为 5 位数字、日期为 YYYY-MM-DD
- [ ] B8 数据字典一致：对比 `Config/qcfp_*_dictionary.json` 的 `field_count` 与 PRAGMA 列数
  → 字段数一一对应（6 表 × json/md/xlsx 已生成）

## C. 配置验证

- [ ] C1 YAML 可加载（Core 加入 sys.path 后）：
  `from QCFP_MTF.config.settings import load_qcfp_settings; print(load_qcfp_settings()['model']['version'])`
  → 打印 `QCFP-MTF-2.1.1`
- [ ] C2 par 节覆盖生效：把 `stock_data_analysis.par` 的 `[QCFP_MTF] disclosure_lag_days` 改为 60 后重载
  → `institutional.disclosure_lag_days == 60`（验证后改回 45）
- [ ] C3 无 PyYAML 兜底解析器：
  `.venv\Scripts\python.exe Core\QCFP_MTF\tests\test_settings.py`
  → test_simple_yaml_parser / test_parser_matches_real_file 通过

## D. 覆盖度审计

- [ ] D1 运行：
  `.venv\Scripts\python.exe Core\QCFP_MTF\scripts\audit_coverage.py`
  → 退出码 0，日志显示 10 张表汇总
- [ ] D2 报告产物：
  → `Report/QCFP_MTF/audit/coverage_report_<时间戳>.{csv,json}` 生成
- [ ] D3 行数对照：
  daily_kline 46,312 / weekly_kline 9,827 / monthly_kline 2,267 / quarterly_kline 752 / idx_hist 2,860 / institutional_holdings 944
- [ ] D4 缺失发现：
  → `00579`、`02602` 完全无数据；`03033` 缺 institutional_holdings（共 19 项缺失）
- [ ] D5 单股模式：
  `.venv\Scripts\python.exe Core\QCFP_MTF\scripts\audit_coverage.py --stock 00700`
  → 只输出 00700 相关行

## E. 数据质量检测

- [ ] E1 运行：
  `.venv\Scripts\python.exe Core\QCFP_MTF\scripts\check_data_quality.py`
  → 写库快照 + 生成报告，退出码 0
- [ ] E2 全量快照行数：
  → 每次约 135 行（15 股 × 9 类 + IDX）；DB 总行数随运行次数递增
- [ ] E3 等级分布（首次全量基线）：
  → A:76 / B:24 / C:35 / D:0
- [ ] E4 降级原因可解释：
  → reasons 含分项，如"异常值 442 条（负价格 442）"
- [ ] E5 单股模式：
  `... check_data_quality.py --stock 00700`
  → 10 行；daily_kline=C（负价格 4）、institutional=B、其余 A/B
- [ ] E6 数据门禁可用：
  → D 级（无数据）股票在 P1 起不得进入决策流程（读取本表做门禁）

## F. 端到端工作流

- [ ] F1 全流程：
  `.venv\Scripts\python.exe run_QCFP_MTF_workflow.py`
  → 依次 init_db → audit_coverage → check_data_quality 全 ✅，退出码 0
- [ ] F2 日志产物：
  → `Log/run_qcfp_mtf_workflow.log` + `Log/{init_db,audit_coverage,check_data_quality}.py.log`
- [ ] F3 幂等性：
  → 连续运行两次不报错（init_db 幂等；审计/质量按时间戳追加）
- [ ] F4 参数透传（未实测）：
  `... run_QCFP_MTF_workflow.py --date 2026-08-19 --stock 00700`
  → 子脚本收到过滤参数并生效

## G. 工程约定

- [ ] G1 目录完整：
  → `Core/QCFP_MTF` 下 common/config/data/structural/behavioral/tactical/fusion/decision/backtest/scripts/tests/sql 齐全
- [ ] G2 源表未被改动：
  → 新系统只读 `hk_*` 表，数据库变更仅新增 `qcfp_*` 表
- [ ] G3 中文无乱码：
  → 日志与 CSV 报告 UTF-8 正常（CSV 为 utf-8-sig，Excel 打开不乱码）

---

## 验收标准

- 必备：A1、B1~B8、C1~C3、D1~D5、E1~E6、F1~F3、G1~G3；
- 可选补充：A2、A3、D5、E5（抽查类）；
- 待补测：C2（改配置重载）、F4（--date/--stock 透传）。

全部通过后，P0 阶段完成，可进入 P1（季度结构引擎）。
