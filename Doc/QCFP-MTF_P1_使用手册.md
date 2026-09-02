# QCFP-MTF P1 用户使用手册（含实例）

> 适用版本：QCFP-MTF-2.1.1 / P1 季度结构引擎
> 环境：Windows + 项目虚拟环境 `.venv`（Python 3.13）
> 所有命令默认在项目根目录执行

## 一、环境准备

```powershell
cd C:\Users\Quansheng\Documents\projects\TA_Workflow
$env:PYTHONIOENCODING="utf-8"
$env:PYTHONUTF8="1"
```

## 二、实例 1：完整跑一遍（含 P1 两步）

```powershell
.venv\Scripts\python.exe run_QCFP_MTF_workflow.py
```

依次执行 5 步：

```text
init_db → audit_coverage → check_data_quality
→ structural_engine（季度结构引擎，写 qcfp_quarterly_structural）
→ validate_structural（交叉验证）
QCFP-MTF 工作流全部完成 ✅
```

## 三、实例 2：只跑季度结构引擎

```powershell
# 全量（14 只有机构数据的股票）
.venv\Scripts\python.exe Core\QCFP_MTF\scripts\structural_engine.py

# 只看一只股票
.venv\Scripts\python.exe Core\QCFP_MTF\scripts\structural_engine.py --stock 00700

# 预演：生成报告但不写库
.venv\Scripts\python.exe Core\QCFP_MTF\scripts\structural_engine.py --stock 00700 --dry-run

# 只算指定季度
.venv\Scripts\python.exe Core\QCFP_MTF\scripts\structural_engine.py --period-end 2026-06-30
```

预期输出（全量）：

```text
无机构数据股票跳过（DATA_INSUFFICIENT）: ['03033']
00700 2026-06-30: STRUCTURAL_DECLINE (score=20.0, method=hold_unmapped, C=C→ F=F→ P=P↓, dq=B)
...
已 UPSERT 944 行到 qcfp_quarterly_structural
```

## 四、实例 3：查看引擎结果

```powershell
# 最新报告文件
Get-ChildItem Report\QCFP_MTF\structural | Sort-Object LastWriteTime -Descending | Select-Object -First 4 Name

# 用 Excel 打开
Invoke-Item (Get-ChildItem Report\QCFP_MTF\structural\structural_*.csv | Sort-Object LastWriteTime -Descending | Select-Object -First 1).FullName

# 数据库查询：00700 状态时间线
sqlite3 SQLiteDB\HK_Stock.db "SELECT period_end, c_state, f_state, p_state, structural_regime, core_score, resolve_method, data_quality FROM qcfp_quarterly_structural WHERE stock_code='00700' ORDER BY period_end DESC LIMIT 8;"

# 状态分布
sqlite3 SQLiteDB\HK_Stock.db "SELECT structural_regime, COUNT(*) FROM qcfp_quarterly_structural GROUP BY structural_regime ORDER BY 2 DESC;"
```

## 五、实例 4：交叉验证（M1 验收）

```powershell
.venv\Scripts\python.exe Core\QCFP_MTF\scripts\validate_structural.py
```

预期输出：

```text
可比季度: 144（有资金流 + 双方方向明确）
方向一致: 75 / 144 = 52.1%
direct 证据行: 9 / 10 = 90.0%
direct 一致率达标（≥70%）✅
hold 保持行（参考，路径依赖）: 134 行，一致 66
```

结果含义：

- `direct` = 当季 C/F/P 证据直接命中的状态，与现有 QCFP 1.x 标签方向一致率 90%，这是验收口径；
- `hold` = 未定义组合下的路径依赖保持，与"季度反应式"标签天然存在差异，仅作参考；
- 全量 52.1% 不代表模型差，而是"慢结构"与"快季度标签"的口径差异。

## 六、实例 5：解读状态与解析方法

| 状态 | 含义 | 组合示例 |
| :-- | :-- | :-- |
| STRUCTURAL_BULLISH | 季度主升 | C↑ F↑ P↑ |
| STRUCTURAL_ACCUMULATION | 蓄势 | C↑ F↑ P→ |
| STRUCTURAL_DIVERGENCE | 结构背离 | C↑ F↓ P↑ |
| STRUCTURAL_DISTRIBUTION | 派发 | C↓ F↓ P↑ |
| STRUCTURAL_DECLINE | 退潮 | C↓ F↓ P↓ |
| STRUCTURAL_BOTTOM_CANDIDATE | 底部候选 | C↓ F↑ P↓ |
| STATE_UNDETERMINED | 证据不足，无结论 | 其余组合 |

| resolve_method | 含义 |
| :-- | :-- |
| direct | 当季 C/F/P 直接命中规格书组合 |
| fallback_f_missing | 资金流缺失（2021 前），C+P 降级映射 |
| hold_unmapped / hold_missing_factor | 未定义组合/因子缺失，保持上一状态 |
| unmapped | 无历史且未定义组合 |

## 七、实例 6：运行测试

```powershell
# 全量 60 项
.venv\Scripts\python.exe Core\QCFP_MTF\tests\run_all_tests.py

# pytest
.venv\Scripts\python.exe -m pytest Core\QCFP_MTF\tests -v

# P1 专项
.venv\Scripts\python.exe Core\QCFP_MTF\tests\test_structural\test_structural_regime.py
```

## 八、实例 7：Python 直接调用（二次开发）

```powershell
$code = @'
import sys
sys.path.insert(0, "Core")

from QCFP_MTF.config.settings import load_qcfp_settings
from QCFP_MTF.data.loader import load_derived, load_kline
from QCFP_MTF.structural.chip_factors import build_c_factors
from QCFP_MTF.structural.flow_factors import build_f_factors
from QCFP_MTF.structural.price_factors import build_p_factors
from QCFP_MTF.structural.structural_regime import resolve_regime

s = load_qcfp_settings()
ih = load_derived("quarterly_institutional_holdings_analysis")
chip = load_derived("quarterly_chip_analysis")
q = load_kline("quarterly", stocks=["00700"])
d = load_kline("daily", stocks=["00700"])

c = build_c_factors(ih[ih["stock_code"]=="00700"], s)
f = build_f_factors(chip[chip["stock_code"]=="00700"], s)
p = build_p_factors(q, d, s)

m = c.merge(f[["period_end","f_state"]], on="period_end").merge(p[["period_end","p_state"]], on="period_end")
r = m.iloc[-1]
print(r["period_end"], resolve_regime(r["c_state"], r["f_state"], r["p_state"]))
'@
$code | .venv\Scripts\python.exe -
```

## 九、实例 8：日常维护

```powershell
# 表结构变更后重生成数据字典
.venv\Scripts\python.exe Code_utl\Generate_qcfp_Dictionaries.py

# 清理 WAL
sqlite3 SQLiteDB\HK_Stock.db "PRAGMA wal_checkpoint(TRUNCATE);"

# 查看引擎日志
Get-Content Log\structural_engine.py.log -Tail 30
```

## 十、参数汇总

| 参数 | 入口 | 说明 |
| :-- | :-- | :-- |
| `--stock 00700` | 主控 / engine / validate | 只处理指定股票 |
| `--period-end 2026-06-30` | engine | 只计算指定季度 |
| `--dry-run` | engine | 不写库，仅生成报告 |
| `--date 2026-08-19` | 主控 | 设置 WORKFLOW_DATE（当前步骤暂未消费） |

## 十一、常见问题

| 现象 | 说明 |
| :-- | :-- |
| 大量 STATE_UNDETERMINED | 规格书 6 状态表只覆盖 ↑/↓ 组合；真实数据平向组合走"保持"或 UNDETERMINED（当前 25%），属冻结规格的固有稀疏性 |
| 2021 前季度 F=UNKNOWN | 资金流源表从 2021 起；该季度走 C+P 降级映射，data_quality 降一级，报告会标注 |
| data_quality 为什么没有 D | D 表示"无法形成判断"；F 缺失降级仍产出 A- 级结论，故最高降级到 C |
| 重复运行结果是否稳定 | 稳定。状态按"本次运行内时间顺序传播"，与历史运行无关 |
| 00700 为什么一直 DECLINE | 一旦进入退潮，未定义组合保守保持；只有命中规格书转换组合才会切换 |
