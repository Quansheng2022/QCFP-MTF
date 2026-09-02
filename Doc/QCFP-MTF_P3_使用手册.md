# QCFP-MTF P3 用户使用手册（含实例）

> 适用版本：QCFP-MTF-2.1.1 / P3 周线战术引擎
> 环境：Windows + 项目虚拟环境 `.venv`（Python 3.13）
> 所有命令默认在项目根目录执行

## 一、环境准备

```powershell
cd C:\Users\Quansheng\Documents\projects\TA_Workflow
$env:PYTHONIOENCODING="utf-8"
$env:PYTHONUTF8="1"
```

## 二、实例 1：完整跑一遍（含 P3 周线引擎）

```powershell
.venv\Scripts\python.exe run_QCFP_MTF_workflow.py
```

7 步全 ✅：init_db → audit_coverage → check_data_quality → structural_engine → monthly_behavior_engine → **weekly_tactical_engine** → validate_structural。

## 三、实例 2：只跑周线战术引擎

```powershell
# 全量（15 只股票）
.venv\Scripts\python.exe Core\QCFP_MTF\scripts\weekly_tactical_engine.py

# 只看一只股票
.venv\Scripts\python.exe Core\QCFP_MTF\scripts\weekly_tactical_engine.py --stock 00700

# 预演不写库
.venv\Scripts\python.exe Core\QCFP_MTF\scripts\weekly_tactical_engine.py --stock 00700 --dry-run

# 只算指定周
.venv\Scripts\python.exe Core\QCFP_MTF\scripts\weekly_tactical_engine.py --week-end 2026-08-14
```

预期输出（全量）：

```text
00700 2026-08-14: Consolidation (vol_breakout=0, vol_shrink=0, turn_spike=0, vwap=-2.97%, slope=减速, dq=A)
...
已 UPSERT 9827 行到 qcfp_weekly_tactical
```

## 四、实例 3：查看引擎结果

```powershell
# 最新报告
Get-ChildItem Report\QCFP_MTF\weekly | Sort-Object LastWriteTime -Descending | Select-Object -First 3 Name
Invoke-Item (Get-ChildItem Report\QCFP_MTF\weekly\weekly_tactical_*.csv | Sort-Object LastWriteTime -Descending | Select-Object -First 1).FullName

# 00700 最近 6 周
sqlite3 SQLiteDB\HK_Stock.db "SELECT week_end, w_turnover_deviation, w_volume_breakout, w_volume_shrink, w_vwap_deviation, w_ma_slope, w_breakout, w_breakdown, tactical_signal FROM qcfp_weekly_tactical WHERE stock_code='00700' ORDER BY week_end DESC LIMIT 6;"

# 信号分布
sqlite3 SQLiteDB\HK_Stock.db "SELECT tactical_signal, COUNT(*) FROM qcfp_weekly_tactical GROUP BY 1 ORDER BY 2 DESC;"
```

## 五、实例 4：解读字段与信号

| 字段 | 含义 |
| :-- | :-- |
| w_volume_breakout | 放量：volume > MA20 × 1.8 |
| w_volume_shrink | 极度缩量：volume < MA20 × 0.5 |
| w_turnover_deviation | 周换手 vs 13 周（季度）周均的偏离 |
| w_turnover_spike | 极端换手：turnover > MA8 × 2.0 |
| w_vwap_deviation | 收盘价 vs 周 VWAP（amount/volume）偏离 |
| w_ma_slope | ema5 二阶差分：加速 / 减速 / 平稳 |
| w_breakout | 有效突破：新高 + 放量 + 价在 VWAP 上（三确认） |
| w_breakdown | 有效破位：新低 + 价在 VWAP 下 |

| tactical_signal | 触发条件 |
| :-- | :-- |
| Breakdown | w_breakdown=1 |
| Breakout | w_breakout=1 |
| Pullback | close < ema5 且 close > ema20（上升趋势回调） |
| Consolidation | 其余（盘整） |

## 六、实例 5：运行测试

```powershell
# 全量 97 项
.venv\Scripts\python.exe Core\QCFP_MTF\tests\run_all_tests.py

# P3 专项
.venv\Scripts\python.exe Core\QCFP_MTF\tests\test_tactical\test_weekly_signal.py
.venv\Scripts\python.exe Core\QCFP_MTF\tests\test_tactical\test_weekly_volume.py
```

## 七、实例 6：Python 直接调用（二次开发）

```powershell
$code = @'
import sys
sys.path.insert(0, "Core")

from QCFP_MTF.config.settings import load_qcfp_settings
from QCFP_MTF.data.loader import load_kline
from QCFP_MTF.tactical.weekly_volume import build_volume_factors
from QCFP_MTF.tactical.weekly_turnover import build_turnover_factors
from QCFP_MTF.tactical.weekly_vwap import build_vwap_factors
from QCFP_MTF.tactical.weekly_signal import build_signal

s = load_qcfp_settings()
w = load_kline("weekly", stocks=["00700"])
vol = build_volume_factors(w, s)
turn = build_turnover_factors(w, s)
vwap = build_vwap_factors(w, s)
sig = build_signal(w, vol, vwap, s)

m = w[["date"]].copy()
m["week_end"] = m["date"].dt.strftime("%Y-%m-%d")
m = m.merge(sig[["week_end","tactical_signal","w_breakout","w_breakdown"]], on="week_end", how="left")
print(m.tail(5).to_string())
'@
$code | .venv\Scripts\python.exe -
```

## 八、实例 7：日常维护

```powershell
# 表结构变更后重生成字典
.venv\Scripts\python.exe Code_utl\Generate_qcfp_Dictionaries.py

# 清理 WAL
sqlite3 SQLiteDB\HK_Stock.db "PRAGMA wal_checkpoint(TRUNCATE);"

# 引擎日志
Get-Content Log\weekly_tactical_engine.py.log -Tail 30
```

## 九、参数汇总

| 参数 | 入口 | 说明 |
| :-- | :-- | :-- |
| `--stock 00700` | 主控 / 周线引擎 | 只处理指定股票 |
| `--week-end 2026-08-14` | 周线引擎 | 只计算指定周 |
| `--dry-run` | 周线引擎 | 不写库，仅生成报告 |
| `--date 2026-08-19` | 主控 | 设置 WORKFLOW_DATE（当前暂未消费） |

## 十、常见问题

| 现象 | 说明 |
| :-- | :-- |
| Breakout 很少 | 突破需"新高+放量+VWAP 上"三确认，故意过滤假突破；可在 `tactical.volume.breakout_ratio` 调阈值 |
| w_breakdown 但信号是 Consolidation | 信号合成先判 breakdown，不可能出现；若出现请检查版本 |
| 2026-08-14 大多 Consolidation | 大盘回调周普遍未创新高/新低，属正常盘整分布 |
| 停牌周 | 因子置 NaN，w_volume_breakout 等标记为 0，不误报 |
| 数据质量 C 的来源 | 继承 weekly_kline 审计等级（早期脏数据），与 P0 审计一致 |
