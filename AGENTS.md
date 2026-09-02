# AGENTS.md — TA_Workflow 项目指南

## 项目定位

TA_Workflow 是一个面向**港股个股技术分析**的自动化工作台，覆盖完整链路：

1. **数据获取**：通过 Futu OpenD / moomoo API 下载 K 线与资金流数据，通过 akshare 聚合指标数据；
2. **指标计算**：批量计算 EMA、BIAS、MACD、RSI、KDJ、MFI、量比、筹码集中度、资金流（机构/散户、IDR、FBI）等技术指标；
3. **报告生成**：绘制图表并生成个股 PDF 分析报告（技术指标、筹码、资金流、买卖信号、宏观）；
4. **超级提示词生成**：将数据库中的行情/指标/资金流数据与人工维护的 LLM 提示词模板（`Code_Prompt/*.md`）结合，产出可直接交给大模型的个股研究/复盘提示词。

项目内代码与文档以中文为主。

## 模块化设计总览

项目按**四层**组织，层间通过 SQLite 表和配置文件解耦：

| 层次 | 位置 | 职责 |
| ---- | ---- | ---- |
| 入口编排层 | 根目录 `run_*_workflow.py` | 按 `SCRIPT_LIST` 顺序执行子脚本、管理日志、通过环境变量 `WORKFLOW_DATE` 传递日期 |
| 核心业务层 | `Core/{Daily,Weekly,Monthly,HK_Macro}` | 每个脚本只负责一个步骤，写入/读取 SQLite 表 |
| 共享工具层 | `Core/utl` | 路径解析、全局配置、股票列表、数据库查询、UTF-8 启动器 |
| 数据与产物层 | `SQLiteDB/Config/Report/Prompt/Log/Temp/Data` | 数据库、配置与数据字典、PDF 报告、提示词产物、日志 |

### 核心设计约定

- **单步单职责**：每个 `Core` 脚本只做一件事，脚本之间不直接 import，通过 SQLite 表传递数据（上游写表、下游读表）。
- **周期 × 步骤的统一编号**：日/周/月三个周期复用同一编号体系：
  - `TA2` = 计算指标，`TA3` = 分析+绘图，`TA4` = 资金流处理，`TA5` = 合并 PDF，`TA6` = 买卖信号，`TA7` = 合并最终报告；
  - 同一周期内脚本按 `TA{n}`、`TA{n}A/B/C` 区分依赖顺序。
- **配置驱动**：路径、开关、股票池、API 凭据等全部来自 `Config/stock_data_analysis.par` 与 `Config/stock_list.json`，避免硬编码（少数旧脚本遗留硬编码路径，见“常见坑”）。
- **数据字典驱动**：每张核心表都有 `Config/*_dictionary.{json,md,xlsx}` 数据字典，供校验与 LLM 提示词使用；**改表结构必须同步数据字典**。
- **UTF-8 第一**：Windows 下所有脚本均以 UTF-8 读写；统一使用 `PYTHONIOENCODING=utf-8`、`PYTHONUTF8=1`，或经 `Core/utl/stock_analysis_utl.py` 启动。
- **共享工具收口在 `Core/utl`**：新脚本需要路径/配置/股票列表能力时，优先复用 `utl` 模块，不要各自实现。

## 目录结构

```text
TA_Workflow/
├── run_Daily_TA_workflow.py            # 日线主控（顺序执行 Core/Daily 步骤）
├── run_Weekly_TA_workflow.py           # 周线主控
├── run_Monthly_TA_workflow.py          # 月线主控
├── run_HK_macro_dashboard_workflow.py  # 港股宏观仪表盘主控
├── Core/
│   ├── Daily/      # 日线 14 个步骤脚本（TA1A…TA7）
│   ├── Weekly/     # 周线脚本（TA2A…TA5 + Weekly_TA_report.py）
│   ├── Monthly/    # 月线脚本（TA2A…TA5 + Monthly_TA_Report.py）
│   ├── HK_Macro/   # HK_Macro_History.py / HK_Macro_Dashboard.py
│   └── utl/        # 共享工具（stock_analysis_utl / stock_list_loader）
├── Code_Prompt/    # 超级提示词模板（*.md）与提示词生成器（Gen_*.py）
├── Code_utl/       # 工具程序：数据字典生成、CSV→SQLite 导入、数据校验、源码收集等
├── Config/         # stock_data_analysis.par、stock_list.json、*_dictionary.*、分析缓存
├── SQLiteDB/       # HK_Stock.db（核心数据仓库）
├── Report/         # 最终 PDF 报告（按股票代码命名，如 00700_analysis_report.pdf）
├── Prompt/         # 提示词产物（Prompt_Daily_*.txt、research_DSS/ 等）
├── Log/            # 运行日志（入口与每个子脚本各一个 .log）
├── Data/           # 数据目录（当前为链接）
├── Temp/           # 中间/临时数据
├── Doc/            # 技术文档、数据字典说明、requirements.txt
├── converted_scripts/  # 转换后的脚本备份
├── md_docx_convert/    # Markdown↔Word 转换相关
└── output/         # 其他输出（如 document.docx）
```

## 工作流

### 1. 日线工作流（`run_Daily_TA_workflow.py`）

按 `SCRIPT_LIST` 顺序执行（当前仓库中大部分步骤被注释，仅保留 `Daily_TA7`，需要时按依赖顺序打开注释）：

| 步骤 | 脚本 | 功能 | 输入 → 输出 |
| ---- | ---- | ---- | ---- |
| 1 | `Daily_TA1A_download_moneyflow.py` | 下载个股资金流原始数据 | 外部 → `hk_hist_daily_moneyflow` |
| 2 | `Daily_TA1B_download_data_moomoo.py` | 下载日 K 线（含换手率/涨跌幅等），增量更新 | moomoo/OpenD → `hk_hist_daily_kline` |
| 3 | `Daily_TA2_Calculate_Indicators_akshare_mproc.py` | 计算 EMA/BIAS/MACD/RSI/KDJ/MFI/量比/筹码集中度等，多进程 | `hk_hist_daily_kline` → `hk_daily_kline_analysis` |
| 4 | `Daily_TA3A_Analyze_Indicators_Plot.py` | 指标状态表 + K 线/成交量/MACD/RSI 图 | 分析表 → `Report/*_daily_TA_indicator_analysis.pdf` |
| 5 | `Daily_TA3B_Chip_Signal_Analysis.py` | 筹码信号（底部/顶部、吸筹/派发） | → `Report/*_daily_chip_signal_analysis.pdf` |
| 6 | `Daily_TA3C_Chip_Distribution_Analysis.py` | 筹码分布可视化（20/60/250 日，VA 70% 区间） | → `Report/*_daily_chip_distribution_analysis.pdf` |
| 7 | `Daily_TA4A_Convert_MoneyFlow.py` | 资金流文本 → CSV（当前已重命名 `2Remove_…` 并从 SCRIPT_LIST 注释） | Temp → CSV |
| 8 | `Daily_TA4B_Caculate_MoneyFlow_Indicator_mproc.py` | 资金流指标（机构/散户净流入、IDR、FBI） | → `hk_daily_moneyflow_analysis` |
| 9 | `Daily_TA4C_Analyze_MoneyFlow_mproc.py` | 资金流图表与状态表 | → `Report/*_daily_moneyflow_analysis.pdf` |
| 10 | `Daily_TA5_MergePDF.py` | 合并中间 PDF | → `Report/*_daily_analysis_report.pdf` |
| 11 | `Daily_TA6A_Buy_Signal_Analyzer_Optimized.py` | 买入信号检测与打分 | → `hk_buy_signal_details`、PDF/CSV |
| 12 | `Daily_TA6B_Sell_Signal_Analyzer_Optimized.py` | 卖出信号检测与打分 | → `hk_sell_signal_details`、PDF/CSV |
| 13 | `Daily_TA7_Merge_Analysis_Report_Workflow.py` | 合并日/周线报告与买卖信号报告（缺失文件自动插入提示页） | → `Report/*_analysis_report.pdf` |

另有 `Daily_TA_report.py`（旧版顺序执行总控，内部硬编码 `TA_Workflow2` 路径，仅作参考）。

### 2. 周线 / 3. 月线工作流

两套流程结构相同，主控分别为 `run_Weekly_TA_workflow.py`、`run_Monthly_TA_workflow.py`：

1. `TA2A_Aggregate_Indicators_akshare.py` — 用 akshare 聚合行情/指标；
2. `TA2B_Calculate_indicators.py` — 计算周期指标 → `hk_{weekly,monthly}_kline_analysis`；
3. `TA3_Analyze_Indicators_Plot.py` — 分析与绘图；
4. `TA4A_Aggregate_MoneyFlow.py` / `TA4B_Analyze_MoneyFlow.py` — 资金流聚合与分析 → `hk_{weekly,monthly}_moneyflow_analysis`；
5. `TA5_MergePDF.py` — 合并报告。

### 4. 港股宏观工作流（`run_HK_macro_dashboard_workflow.py`）

- `HK_Macro_History.py`：下载宏观历史数据（DXY、美债收益率、联邦基金利率、SOFR、失业率、核心 CPI、VIX、USDCNY、南向资金）→ `macro_data_hist`、`southbound_flow_hist`；
- `HK_Macro_Dashboard.py`：生成宏观分析摘要/仪表盘报告。

### 5. 超级提示词生成（`Code_Prompt/`）

模板资产（人工维护，LLM 直接消费）：
- `个股超级Prompt_V5/V6.md`、`个股_research_DSS_超级Prompt_V7.md`（scan/research/review 多模式决策框架）、`个股review_复盘模板超级Prompt.txt`。

生成器（从 SQLite 取数并填充模板，输出到 `Prompt/`）：
- `Gen_Prompt_Daily.py` / `Gen_Prompt_Weekly.py` / `Gen_Monthly_Prompt.py`：按周期复盘提示词（全部股票）；
- `Gen_Prompt_General.py`：通用/组合提示词；
- `Gen_Stock_Research_DSS_Prompt.py`：DSS 研究提示词，支持 `-m scan|research|review`、`-s 股票代码`；
- `Gen_Stock_Research_DSS_Prompt_wo_data.py`：不带数据的模板版；
- `Gen_Stock_Review_Prompt.py`：复盘提示词。

用法示例：

```powershell
# 从项目根目录运行
.venv\Scripts\python.exe Code_Prompt\Gen_Stock_Research_DSS_Prompt.py -m research -s 00700
.venv\Scripts\python.exe Code_Prompt\Gen_Prompt_Daily.py
```

注意：`Code_Prompt/stock_list.json` 与 `Config/stock_list.json` 是两份独立的股票列表，修改股票池时需留意生成器读的是哪一份。

## 数据模型

### SQLite（`SQLiteDB/HK_Stock.db`）

表按用途分组：

| 分组 | 表 | 说明 |
| ---- | ---- | ---- |
| 原始行情 | `hk_hist_{daily,weekly,monthly}_kline` | open/high/low/close/volume/amount/turnover_rate/amplitude/change_* 等 |
| 原始资金流 | `hk_hist_{daily,weekly,monthly}_moneyflow` | extra_large/large/medium/small、capital_trend 等 |
| 技术分析 | `hk_{daily,weekly,monthly}_kline_analysis` | 基础行情 + 全部技术指标 + 信号状态（由 hist 表计算产出） |
| 资金流分析 | `hk_{daily,weekly,monthly}_moneyflow_analysis` | institutional_flow/individual_flow、inst_5ma/ind_5ma、idr、fbi |
| 买卖信号 | `hk_buy_signal_details`、`hk_sell_signal_details` | signal_type/signal_name、base_score/resonance_score/trend_score/volume_score/composite_score |
| 指数 | `hk_idx`、`hk_idx_hist`、`hk_idx_{hsi,hscei,hstech,vhsi,hnf,hnp,hnc,hnu,hsbio}` | 恒指/国企/科技/波幅及各细分指数 |
| 宏观 | `macro_data`、`macro_data_hist`、`southbound_flow_hist` | DXY、US2Y/10Y/30Y、FEDFUNDS、SOFR、UNRATE、CORE_CPI_YOY、VIX、USDCNY、南向资金 |
| 基础信息 | `hk_stock_info` | code/name/sector/market/stock_type/is_active |

字段约定：
- `stock_code` 统一为 **5 位数字字符串**（如 `00700`）；
- `date` 统一为 `YYYY-MM-DD`；
- hist 与 analysis 表通过 `(stock_code, date)` 关联（资金流分析表用 `price_chgpct` 等字段与行情表对齐）。

### Config

- `stock_data_analysis.par`：INI 主配置，关键 section：`[FOLDERS]`（目录）、`[DATABASE]`、`[DATA_DOWNLOAD]`、`[ANALYSIS_PERIOD]`、`[TICKERS]`（股票池）、`[PROCESS_SWITCHES]`（步骤开关）、`[MULTI_PROCESSING]`、`[FUTU_MOOMOO]`（OpenD 连接）、`[FREDAPI]`、`[HK_MACRO_DATA]`；
- `stock_list.json`：股票池（code/name/sector/market）；
- `*_dictionary.json/md/xlsx`：各表数据字典（字段名、类型、含义、示例），由 `Code_utl/Generate_*_Dictionary.py` 生成；
- `hk_*_analysis.json` 等：分析缓存/备份（含 `*_backup_*.json` 历史备份）。

### Code_utl 工具角色

- `Generate_*_Dictionary.py`：读取 SQLite 表结构生成数据字典（JSON/MD/XLSX）；
- `Import_*`：把 CSV/文本导入 SQLite（K 线、资金流、分析结果、宏观、股票信息）；
- `Verify_*`：逐表校验数据完整性与准确性（Prompt 目录下有配套校验提示词）；
- `collect_source_*.py`：收集项目源码；
- `synch_folders.py`：目录同步；`create_hk_stock_info.sql`：基础表建表脚本；
- `md_docx_conversion_software_precheck.py`：Markdown↔Word 转换环境预检。

## 运行环境

- Windows + 项目内虚拟环境 `.venv`（Python 3.13）；依赖清单见 `Doc/requirements.txt`（pandas、numpy、akshare、moomoo、reportlab、PyPDF2、pdfplumber 等）。
- **Futu OpenD**：`Daily_TA1B` 依赖 OpenD 客户端与账号（`[FUTU_MOOMOO]`），OpenD 未启动或离线时该步骤不可用。
- **akshare/网络**：周/月 `TA2A` 及部分指标源需要外网。
- 所有入口脚本都假定 **cwd = 项目根目录**；子脚本也通过 `Core/utl/stock_analysis_utl.py` 或 `GlobalConfig` 解析绝对路径。

## 常见坑与约定

- **编码**：Windows 控制台默认 GBK，中文输出乱码时设置 `PYTHONIOENCODING=utf-8`/`PYTHONUTF8=1`，或经 `Core/utl/stock_analysis_utl.py` 启动；读写文件一律 `encoding="utf-8"`。
- **目录大小写**：配置里用小写（`log`/`prompt`/`report`），实际文件夹为大写（`Log`/`Prompt`/`Report`），Windows 不区分大小写所以可运行；迁移到其他系统前需统一。
- **旧硬编码路径**：`Daily_TA_report.py` 等旧脚本硬编码了 `TA_Workflow2` 路径，仅作参考，不要在新脚本中复制这种写法。
- **utl 无 `__init__.py`**：`Core/utl` 是命名空间包；脚本通过把 `Core` 加入 `sys.path` 后 `from utl.xxx import ...` 导入。新增工具文件继续放 `Core/utl` 即可。
- **脚本命名不一致**：个别历史文件带 `2Remove_` 前缀或拼写差异（如 `Caculate_MoneyFlow_Indicator`），以 `SCRIPT_LIST` 实际引用的文件名为准。
- **SQLite WAL**：运行后可能出现 `HK_Stock.db-wal/-shm`；清理方式：`sqlite3 HK_Stock.db "PRAGMA wal_checkpoint(TRUNCATE);"`。
- **PDF 中文字体**：图表/PDF 依赖 Windows 系统字体（simsun.ttc / msyh.ttc），缺失时脚本会自动搜索或插入提示页。
- **多进程**：日线 TA2/TA4B/TA4C/TA6 使用 `ProcessPoolExecutor`，进程数与开关在 `[MULTI_PROCESSING]` 配置；多进程脚本日志名带 `_mproc`。
- **字段联动**：修改分析表字段或指标逻辑时，必须同步 `Config/*_dictionary.*` 与提示词生成器中的 `OUTPUT_COLUMNS` 等引用。

## 修改指南

- **新增流程步骤**：在 `Core/<周期>` 下新建 `TA{n}[A/B/C]_动作.py`，把文件名按依赖顺序加入对应 `run_*_TA_workflow.py` 的 `SCRIPT_LIST`。
- **新增技术指标**：在对应 `TA2` 脚本的 `calculate_*` 系列函数中添加列；同时给分析表增加字段并重新生成数据字典（`Code_utl/Generate_*_Dictionary.py`）。
- **新增数据表/数据源**：在 `Config/stock_data_analysis.par` 增加配置节，按 `Code_utl/Import_*` + `Verify_*` 模式写导入与校验脚本。
- **新增提示词模板**：模板放 `Code_Prompt/`，生成器输出到 `Prompt/`；若模板引用数据库字段，需与 `*_dictionary.json` 保持一致。
- **修改股票池**：编辑 `Config/stock_list.json`（及 `Code_Prompt/stock_list.json`，如生成器使用）；字段为 code/name/sector/market。
- **调试**：单个步骤可绕过主控直接运行，如 `.venv\Scripts\python.exe Core\Daily\Daily_TA2_Calculate_Indicators_akshare_mproc.py`；日志在 `Log/<脚本名>.log`。

## 参考文档

- `Doc/港股日线技术分析报告子系统技术文档.md`（含日线数据流与步骤表）
- `Doc/港股周线技术分析报告子系统技术文档.md`
- `Doc/港股宏观分析摘要报告技术文档.md`
- `Doc/数据字典.md`
- `Doc/Folder_Structure.txt`（目录清单）
- `Doc/requirements.txt`（依赖）
- `Config/*_dictionary.md`（各表数据字典）
