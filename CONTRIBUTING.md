# CONTRIBUTING.md — 开发与贡献指南

本项目的完整架构与约定见 [AGENTS.md](AGENTS.md)。本文聚焦**开发流程**：从环境准备、编码规范到新增功能与验证的完整路径。

## 环境准备

```powershell
# 项目根目录
cd C:\Users\Quansheng\Documents\projects\TA_Workflow

# 虚拟环境与依赖
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r Doc\requirements.txt
```

如无 Futu OpenD / 外网，涉及下载的步骤（TA1A/TA1B、周月 TA2A）可跳过，仅开发/调试计算与分析步骤。

## 编码规范

### 通用

- **编码**：所有源文件与读写一律 UTF-8；Windows 下输出中文乱码时设置 `PYTHONIOENCODING=utf-8`、`PYTHONUTF8=1`，或经 `Core/utl/stock_analysis_utl.py` 启动。
- **命名**：脚本按 `TA{n}[A/B/C]_<动作>.py` 命名；函数/变量/表字段用小写下划线；`stock_code` 统一为 5 位字符串（如 `00700`），`date` 统一 `YYYY-MM-DD`。
- **入口脚本**：新增步骤必须按依赖顺序加入对应 `run_*_workflow.py` 的 `SCRIPT_LIST`，让主控统一管理执行顺序与日志。

### 分层职责

- 步骤脚本只做一件事，通过 SQLite 表与上下游交互，**不要互相 import**。
- 路径、配置、股票列表、数据库查询等通用能力一律复用 `Core/utl`（命名空间包，`from utl.xxx import ...`）；不要在步骤脚本里重复实现。
- 配置项必须写入 `Config/stock_data_analysis.par`（INI）或 `Config/stock_list.json`，**禁止硬编码**路径、凭据、股票池。
- 多进程场景遵循 `Config/stock_data_analysis.par` 的 `[MULTI_PROCESSING]` 配置，脚本日志名保留 `_mproc` 后缀。

## 新增功能的标准流程

### 新增流程步骤

1. 在 `Core/<周期>/` 下新建 `TA{n}[A/B/C]_<动作>.py`，脚本头部用中文注释写明：步骤名、输入表 → 输出表、依赖说明；
2. 接入主控：把文件名加入对应 `run_*_TA_workflow.py` 的 `SCRIPT_LIST`；
3. 日志：沿用现有模式——主控自动将 stdout/stderr 写入 `Log/<脚本名>.log`，脚本内部也可自建 logger；
4. 验证：从根目录单跑该脚本，检查日志与输出表/文件。

### 新增技术指标

1. 在对应周期的 `TA2` 脚本中，按 `calculate_*` 系列函数风格添加指标列（注意向量化，避免逐行循环）；
2. 若写入分析表，同步表结构（`SQLiteDB/HK_Stock.db` 的 `hk_*_kline_analysis`）；
3. 重新生成数据字典：`python Code_utl\Generate_hk_*_analysis_Dictionary.py`，并检查 `Config/*_dictionary.{json,md,xlsx}` 更新；
4. 如提示词需要展示新字段，同步 `Code_Prompt/Gen_*.py` 中的字段引用（如 `OUTPUT_COLUMNS`）。

### 新增数据表 / 数据源

1. 在 `Config/stock_data_analysis.par` 增加配置节（数据源参数、开关）；
2. 按既有模式写导入脚本（参考 `Code_utl/Import_*`）与校验脚本（参考 `Code_utl/Verify_*`）；
3. 生成配套数据字典（`Code_utl/Generate_*_Dictionary.py`）；
4. 建表语句可参考 `Code_utl/create_hk_stock_info.sql`；注意 `stock_code` / `date` 等字段约定。

### 新增 / 修改超级提示词

1. 模板（LLM 直接消费的 md/txt）放 `Code_Prompt/`，版本号递增（如 V7 → V8），顶部注明更新日期；
2. 生成器放 `Code_Prompt/Gen_*.py`，输出到 `Prompt/`；
3. 模板引用的数据库字段必须与 `Config/*_dictionary.json` 一致；
4. 修改股票池时同步 `Config/stock_list.json` 与 `Code_Prompt/stock_list.json`（两者独立）。

## 验证与测试

- **单步调试**：从项目根目录直接运行目标脚本，如
  `.\.venv\Scripts\python.exe Core\Daily\Daily_TA2_Calculate_Indicators_akshare_mproc.py`；
- **数据校验**：使用 `Code_utl/Verify_*` 系列脚本核对待导入/分析数据，`Prompt/Verify_*.txt` 提供配套 LLM 校验提示词；
- **日志检查**：`Log/<脚本名>.log` 应无异常堆栈；入口日志 `run_*_workflow.log` 确认各步骤按序成功；
- **产物检查**：PDF 中文需正常渲染（依赖 Windows 中文字体 simsun/msyh），报告文件按 `<股票代码>_<周期>_*.pdf` 命名生成；
- **数据一致性**：分析表与字典字段一致；hist 与 analysis 表按 `(stock_code, date)` 对齐。

## 提交与协作

> 注意：当前目录**尚未初始化 git 仓库**，提交前请先 `git init` 并确定远端。

- 提交信息建议使用中文或英文均可，但保持同一风格，格式参考：`<类型>: <简述>`，如 `feat(daily): 新增 XX 指标`、`fix(weekly): 修复 XX 数据缺失`；
- 一次提交只做一件事，避免把无关改动混在一起；
- 不要提交：`Log/`、`Report/`、`Prompt/`、`Temp/`、`Data/`、`Config/*.json.bak`、`*_backup_*.json` 等运行产物（建议维护 `.gitignore`）；
- 涉及数据库表结构、字段语义的改动，必须同步更新数据字典与技术文档（`Doc/*.md`）。

## 常见问题排查

| 现象 | 排查方向 |
| ---- | ---- |
| 中文乱码 | 设置 `PYTHONIOENCODING=utf-8` / `PYTHONUTF8=1`，或改用 `Core/utl/stock_analysis_utl.py` 启动 |
| 下载失败 | 检查 Futu OpenD 是否启动、`[FUTU_MOOMOO]` 配置、网络与 akshare 可用性 |
| 步骤报"脚本不存在" | 文件名大小写/`2Remove_` 前缀等历史不一致，以 `SCRIPT_LIST` 引用为准 |
| SQLite 锁/慢 | 存在 `-wal/-shm` 时执行 `sqlite3 HK_Stock.db "PRAGMA wal_checkpoint(TRUNCATE);"` |
| PDF 中文缺失 | 检查系统字体（simsun.ttc / msyh.ttc）；缺失时脚本会插入提示页 |
| 路径错误 | 确认从项目根目录运行；旧脚本（`Daily_TA_report.py`）存在硬编码路径，仅参考 |

## 参考

- [AGENTS.md](AGENTS.md) — 架构、工作流、数据模型与完整约定
- `Doc/` — 各子系统技术文档与数据字典说明
- `Config/*_dictionary.md` — 各表字段字典
