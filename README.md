# TA_Workflow

港股个股技术分析自动化工作台：**数据获取 → 指标计算 → 报告生成 → 超级提示词生成**，面向量化分析师与交易员，辅助个股投资决策。

## 功能特性

- **数据获取**：通过 Futu OpenD / moomoo API 下载港股日 K 线与资金流数据（增量更新）；通过 akshare 聚合周期行情；下载港股宏观数据（美债、美元指数、VIX、南向资金等）。
- **技术指标计算**：批量计算 EMA、BIAS、MACD、RSI、KDJ、MFI、量比、筹码集中度、资金流指标（机构/散户净流入、IDR、FBI）等，支持多进程加速。
- **报告生成**：自动产出个股 PDF 分析报告，覆盖技术指标、筹码分布、资金流、买入/卖出信号，并支持日/周/月报告合并。
- **超级提示词生成**：将 SQLite 中的行情与指标数据填充进人工维护的 LLM 提示词模板（`Code_Prompt/*.md`），一键生成个股研究/复盘提示词（scan / research / review 三种模式）。
- **数据字典驱动**：每张核心数据表配有 JSON/Markdown/Excel 数据字典，供数据校验与提示词生成使用。

## 系统架构

项目采用分层模块化设计，层间通过 SQLite 表与配置文件解耦：

```text
入口编排层（run_*_workflow.py，按 SCRIPT_LIST 顺序执行）
        │
        ▼
核心业务层（Core/Daily · Core/Weekly · Core/Monthly · Core/HK_Macro）
        │  每个脚本单步单职责：TA2 算指标 / TA3 分析绘图 / TA4 资金流
        │  / TA5 合并 PDF / TA6 买卖信号 / TA7 合并终稿
        ▼
共享工具层（Core/utl：路径、配置、股票列表、数据库查询、UTF-8 启动器）
        │
        ▼
数据与产物层（SQLiteDB/HK_Stock.db · Config · Report · Prompt · Log）
```

典型数据流（日线）：

```text
Futu OpenD / moomoo ──► hk_hist_daily_kline ──► hk_daily_kline_analysis ──► PDF 报告
                 └──► hk_hist_daily_moneyflow ─► hk_daily_moneyflow_analysis ─► PDF 报告
                                                     │
                                                     ▼
                                        hk_buy/sell_signal_details ──► Report/*_analysis_report.pdf
```

## 目录结构

```text
TA_Workflow/
├── run_{Daily,Weekly,Monthly}_TA_workflow.py   # 日/周/月线主控
├── run_HK_macro_dashboard_workflow.py          # 港股宏观仪表盘主控
├── Core/           # 核心业务脚本（按周期分目录）+ utl 共享工具
├── Code_Prompt/    # 超级提示词模板与生成器（Gen_*.py）
├── Code_utl/       # 数据字典生成、CSV→SQLite 导入、数据校验等工具
├── Config/         # 主配置 stock_data_analysis.par、股票列表、数据字典
├── SQLiteDB/       # HK_Stock.db 数据仓库
├── Report/         # 最终 PDF 报告（如 00700_analysis_report.pdf）
├── Prompt/         # 提示词产物（Prompt_Daily_*.txt、research_DSS/）
├── Log/            # 运行日志
├── Data/ Temp/     # 原始数据与中间数据
└── Doc/            # 技术文档、数据字典说明、依赖清单
```

完整结构与模块说明见 [AGENTS.md](AGENTS.md)。

## 快速开始

### 环境要求

- Windows 10/11（项目依赖部分 Windows 特性：中文字体、Futu OpenD）
- Python 3.13（项目自带 `.venv`）
- Futu OpenD 客户端（日线 K 线/资金流下载依赖，需在 `Config/stock_data_analysis.par` 的 `[FUTU_MOOMOO]` 配置）
- 网络（akshare 数据源、FRED 宏观数据）

### 安装与配置

```powershell
# 1. 创建并激活虚拟环境（如未创建）
python -m venv .venv
.\.venv\Scripts\Activate.ps1

# 2. 安装依赖
pip install -r Doc\requirements.txt

# 3. 配置（必须，所有路径/凭据/开关都在这里）
#    编辑 Config\stock_data_analysis.par 与 Config\stock_list.json
```

### 运行工作流

所有入口脚本均从**项目根目录**运行：

```powershell
# 日线技术分析（含资金流、筹码、买卖信号，最终合并为个股总报告）
.\.venv\Scripts\python.exe run_Daily_TA_workflow.py --date 2026-08-07

# 周线 / 月线技术分析
.\.venv\Scripts\python.exe run_Weekly_TA_workflow.py
.\.venv\Scripts\python.exe run_Monthly_TA_workflow.py

# 港股宏观仪表盘
.\.venv\Scripts\python.exe run_HK_macro_dashboard_workflow.py
```

> 提示：`run_Daily_TA_workflow.py` 的 `SCRIPT_LIST` 默认仅保留 `Daily_TA7`（报告合并），需要完整跑链路时按依赖顺序打开注释。

### 生成超级提示词

```powershell
# 生成个股研究提示词（scan / research / review 三模式）
.\.venv\Scripts\python.exe Code_Prompt\Gen_Stock_Research_DSS_Prompt.py -m research -s 00700

# 生成日线复盘提示词（全部股票）
.\.venv\Scripts\python.exe Code_Prompt\Gen_Prompt_Daily.py
```

输出位于 `Prompt/`；提示词模板位于 `Code_Prompt/*.md`。

## 输出产物

- **PDF 报告**：`Report/<股票代码>_analysis_report.pdf`（合并总报告）及各中间报告
- **提示词**：`Prompt/Prompt_*_<代码>_<名称>.txt`、`Prompt/research_DSS/`
- **日志**：`Log/`，入口日志（`run_*_workflow.log`）与每个子脚本日志各一份
- **数据字典**：`Config/*_dictionary.{json,md,xlsx}`

## 相关文档

- [AGENTS.md](AGENTS.md) — 项目指南（架构、工作流、数据模型、开发约定）
- [CONTRIBUTING.md](CONTRIBUTING.md) — 开发与贡献指南
- `Doc/港股日线技术分析报告子系统技术文档.md` — 日线子系统设计
- `Doc/港股周线技术分析报告子系统技术文档.md` — 周线子系统设计
- `Doc/港股宏观分析摘要报告技术文档.md` — 宏观子系统设计
- `Doc/数据字典.md` — 数据字典说明
- `Doc/requirements.txt` — 依赖清单
