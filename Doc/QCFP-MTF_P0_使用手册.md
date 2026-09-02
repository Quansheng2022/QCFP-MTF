# QCFP-MTF P0 用户使用手册（含实例）

> 适用版本：QCFP-MTF-2.1.1 / P0 阶段
> 环境：Windows + 项目虚拟环境 `.venv`（Python 3.13）
> 所有命令默认在项目根目录 `C:\Users\Quansheng\Documents\projects\TA_Workflow` 执行

## 一、环境准备

```powershell
# 1. 进入项目根目录
cd C:\Users\Quansheng\Documents\projects\TA_Workflow

# 2. 中文乱码时先设置 UTF-8（建议每次运行前执行）
$env:PYTHONIOENCODING="utf-8"
$env:PYTHONUTF8="1"

# 3. 验证环境
.venv\Scripts\python.exe --version
```

---

## 二、实例 1：完整跑一遍 P0 工作流（最常用）

```powershell
.venv\Scripts\python.exe run_QCFP_MTF_workflow.py
```

依次执行 3 个步骤并打印结果：

```text
开始运行 init_db.py → ✅ init_db.py 完成        （建 qcfp_* 表，幂等）
开始运行 audit_coverage.py → ✅ audit_coverage.py 完成  （数据覆盖度审计）
开始运行 check_data_quality.py → ✅ check_data_quality.py 完成  （A/B/C/D 质量检测）
QCFP-MTF P0 工作流全部完成 ✅
```

全程约 30 秒。日志写入 `Log\run_qcfp_mtf_workflow.log`。

## 三、实例 2：只看某只股票

```powershell
# 整条工作流只处理 00700（腾讯）
.venv\Scripts\python.exe run_QCFP_MTF_workflow.py --stock 00700

# 只跑质量检测，只看 00700
.venv\Scripts\python.exe Core\QCFP_MTF\scripts\check_data_quality.py --stock 00700
```

预期输出（质量检测单股）：

```text
已写入 qcfp_data_quality_audit 快照: 10 行
00700: C（daily_kline）异常值 4 条（负价格 4）；...
等级分布 A:6  B:3  C:1  D:0
```

## 四、实例 3：只执行单个步骤

```powershell
# 建表（已存在时无副作用）
.venv\Scripts\python.exe Core\QCFP_MTF\scripts\init_db.py

# 覆盖度审计（全量或单股）
.venv\Scripts\python.exe Core\QCFP_MTF\scripts\audit_coverage.py
.venv\Scripts\python.exe Core\QCFP_MTF\scripts\audit_coverage.py --stock 00700

# 数据质量检测
.venv\Scripts\python.exe Core\QCFP_MTF\scripts\check_data_quality.py

# 指定报告输出目录（默认 Report/QCFP_MTF/audit）
.venv\Scripts\python.exe Core\QCFP_MTF\scripts\audit_coverage.py --output-dir "Report\QCFP_MTF\audit\20260819"
```

## 五、实例 4：查看输出报告

报告按时间戳命名，位于 `Report\QCFP_MTF\audit\`：

```powershell
# 查看最新报告文件
Get-ChildItem Report\QCFP_MTF\audit | Sort-Object LastWriteTime -Descending | Select-Object -First 6 Name, Length

# Excel 直接打开（CSV 为 utf-8-sig，中文不乱码）
Invoke-Item "Report\QCFP_MTF\audit\coverage_report_20260819_185341.csv"
```

报告内容：

- `coverage_report_*.csv`：每行 = 股票 × 数据源，含行数、首末日期、周期完整度；
- `data_quality_report_*.csv`：每行 = 股票 × 数据源，含 A/B/C/D 等级、缺失率、异常分项原因。

## 六、实例 5：数据库查询验证

sqlite3 CLI 已安装（`C:\sqlite\sqlite3.exe`）：

```powershell
# 查看 6 张 qcfp 表
sqlite3 SQLiteDB\HK_Stock.db "SELECT name FROM sqlite_master WHERE type='table' AND name LIKE 'qcfp_%';"

# 审计快照总数与日期
sqlite3 SQLiteDB\HK_Stock.db "SELECT audit_date, COUNT(*) FROM qcfp_data_quality_audit GROUP BY audit_date;"

# 00700 的质量明细
sqlite3 SQLiteDB\HK_Stock.db "SELECT data_type, grade, rows, reasons FROM qcfp_data_quality_audit WHERE stock_code='00700' ORDER BY grade;"

# 覆盖度：某只股票在哪些表没有数据
sqlite3 SQLiteDB\HK_Stock.db "SELECT DISTINCT stock_code FROM hk_hist_daily_kline ORDER BY stock_code;"
```

## 七、实例 6：运行测试

```powershell
# 方式一：无需 pytest
.venv\Scripts\python.exe Core\QCFP_MTF\tests\run_all_tests.py

# 方式二：pytest（venv 已安装）
.venv\Scripts\python.exe -m pytest Core\QCFP_MTF\tests -v

# 方式三：单个模块
.venv\Scripts\python.exe Core\QCFP_MTF\tests\test_calendar.py
```

预期：36 项全部通过，最后一行 `✅ 全部单元测试通过`。

## 八、实例 7：在 Python 里直接调用模块（二次开发）

```powershell
$code = @'
import sys
sys.path.insert(0, "Core")

from QCFP_MTF.config.settings import load_qcfp_settings
from QCFP_MTF.data.loader import load_kline, load_institutional_holdings
from QCFP_MTF.data.evidence import annotate

# 1) 读配置
s = load_qcfp_settings()
print("模型版本:", s["model"]["version"])
print("CBI 权重:", s["cbi_weights"])

# 2) 读数据（00700 最近 30 个交易日）
df = load_kline("daily", stocks=["00700"]).tail(30)
print(df[["stock_code", "date", "close", "volume", "turnover_rate"]].to_string())

# 3) 机构持股（季度）
ih = load_institutional_holdings(stocks=["00700"])
print(ih[["period_text", "quarter_end_date", "holder_pct"]].tail(4).to_string())

# 4) 证据等级标注
print(annotate(["inst_ownership_pct_chg", "q_inst_flow_raw", "tactical_signal"],
               source_map={"q_inst_flow_raw": "derived"}).to_string())
'@
$code | .venv\Scripts\python.exe -
```

## 九、实例 8：修改表结构后重新生成数据字典

```powershell
# 改过 qcfp_* 表结构后，必须重新生成字典（项目约定）
.venv\Scripts\python.exe Code_utl\Generate_qcfp_Dictionaries.py

# 验证
Get-ChildItem Config -Filter "qcfp_*_dictionary.json" | Select-Object Name
```

## 十、实例 9：日常维护

```powershell
# 清理 SQLite WAL 残留（项目约定做法）
sqlite3 SQLiteDB\HK_Stock.db "PRAGMA wal_checkpoint(TRUNCATE);"

# 查看运行日志
Get-Content Log\run_qcfp_mtf_workflow.log -Tail 20
```

## 十一、常见问题

| 现象 | 原因 | 处理 |
| :-- | :-- | :-- |
| 控制台中文乱码 | Windows 默认 GBK | 先执行 `$env:PYTHONIOENCODING="utf-8"; $env:PYTHONUTF8="1"` |
| `.venv\Scripts\python.exe` 报 Access denied | WindowsApps 解释器冲突 | 用 `python.exe` 完整路径或修复 venv 解释器 |
| 报告中文在 Excel 乱码 | 编码不对 | 报告已用 utf-8-sig 输出，直接双击打开即可 |
| 重复运行报错 | — | P0 全部幂等，理论上不会；查看 `Log\*.py.log` 定位 |

## 十二、参数说明汇总

| 参数 | 入口 | 说明 |
| :-- | :-- | :-- |
| `--stock 00700` | 主控 / audit / quality | 只处理指定股票 |
| `--date 2026-08-19` | 主控 | 设置 `WORKFLOW_DATE` 环境变量（P0 步骤暂未消费，P1+ 使用） |
| `--output-dir 路径` | audit / quality | 自定义报告输出目录 |
| `--no-persist` | quality | 不写数据库快照，仅生成报告 |

> 后续 P1~P6 步骤将在 `run_QCFP_MTF_workflow.py` 的 `SCRIPT_LIST` 中按依赖顺序追加，使用方式不变。
