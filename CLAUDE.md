# CLAUDE.md

完整项目规范见 **[AGENTS.md](AGENTS.md)**（内容以 AGENTS.md 为准），本文件仅为快速入口。

## 项目一句话

TA_Workflow 是港股个股技术分析自动化工作台：数据获取（Futu OpenD/moomoo、akshare）→ 技术指标计算（EMA/MACD/RSI/KDJ/筹码/资金流）→ PDF 报告生成 → 超级提示词生成（`Code_Prompt/` 模板 + 生成器）。

## 关键约定

1. **分层模块化**：入口 `run_*_workflow.py` 按 `SCRIPT_LIST` 顺序执行 `Core/{Daily,Weekly,Monthly,HK_Macro}` 步骤脚本；脚本间通过 `SQLiteDB/HK_Stock.db` 表传递数据，不直接 import。
2. **共享工具**：路径/配置/股票列表/数据库查询统一走 `Core/utl`（命名空间包，`from utl.xxx import ...`）。
3. **配置驱动**：路径、开关、股票池、API 凭据在 `Config/stock_data_analysis.par` 与 `Config/stock_list.json`，不要硬编码。
4. **数据字典联动**：改表结构/字段必须同步 `Config/*_dictionary.*` 与提示词生成器中的字段引用。
 5. **UTF-8**：所有读写 `encoding="utf-8"`；Windows 乱码时用 `PYTHONIOENCODING=utf-8` 或 `Core/utl/stock_analysis_utl.py`。
6. **运行位置**：所有入口脚本从项目根目录运行；子脚本日志在 `Log/<脚本名>.log`。

## 常见坑

- 旧脚本（如 `Daily_TA_report.py`）硬编码了 `TA_Workflow2` 路径，仅参考，勿复制。
- 个别文件带 `2Remove_` 前缀或拼写差异，以 `SCRIPT_LIST` 引用为准。
- SQLite WAL 残留用 `PRAGMA wal_checkpoint(TRUNCATE)` 清理。
- PDF 依赖 Windows 中文字体（simsun/msyh），缺失会退化为提示页。
