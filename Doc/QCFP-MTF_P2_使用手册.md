# QCFP-MTF P2 用户使用手册（含实例）

> 适用版本：QCFP-MTF-2.1.1 / P2 月线行为引擎
> 环境：Windows + 项目虚拟环境 `.venv`（Python 3.13）
> 所有命令默认在项目根目录执行

## 一、环境准备

```powershell
cd C:\Users\Quansheng\Documents\projects\TA_Workflow
$env:PYTHONIOENCODING="utf-8"
$env:PYTHONUTF8="1"
```

## 二、实例 1：完整跑一遍（含 P2 月线引擎）

```powershell
.venv\Scripts\python.exe run_QCFP_MTF_workflow.py
```

6 步全 ✅：init_db → audit_coverage → check_data_quality → structural_engine → **monthly_behavior_engine** → validate_structural。

## 三、实例 2：只跑月线行为引擎

```powershell
# 全量（15 只股票）
.venv\Scripts\python.exe Core\QCFP_MTF\scripts\monthly_behavior_engine.py

# 只看一只股票
.venv\Scripts\python.exe Core\QCFP_MTF\scripts\monthly_behavior_engine.py --stock 00700

# 预演不写库
.venv\Scripts\python.exe Core\QCFP_MTF\scripts\monthly_behavior_engine.py --stock 00700 --dry-run

# 只算指定月份
.venv\Scripts\python.exe Core\QCFP_MTF\scripts\monthly_behavior_engine.py --month-end 2026-07-31
```

预期输出（全量）：

```text
00700 2026-07-31: Stable (T=T5, VP=VP_EXPANSION, CBI=19.5 CBI_TURBULENT, cost=COST_ADVANTAGE, dq=A)
00354 2026-07-31: Deteriorating (T=T5, VP=VP_OVERHEAT, ...)
...
已 UPSERT 2267 行到 qcfp_monthly_behavior
```

## 四、实例 3：查看引擎结果

```powershell
# 最新报告
Get-ChildItem Report\QCFP_MTF\monthly | Sort-Object LastWriteTime -Descending | Select-Object -First 3 Name
Invoke-Item (Get-ChildItem Report\QCFP_MTF\monthly\monthly_behavior_*.csv | Sort-Object LastWriteTime -Descending | Select-Object -First 1).FullName

# 00700 最近 6 个月
sqlite3 SQLiteDB\HK_Stock.db "SELECT month_end, m_turnover_zscore, m_turnover_pctl, m_vp_regime, turnover_liquidity_regime, monthly_behavior_state, cbi_score, cost_position FROM qcfp_monthly_behavior WHERE stock_code='00700' ORDER BY month_end DESC LIMIT 6;"

# 阶段分布
sqlite3 SQLiteDB\HK_Stock.db "SELECT monthly_behavior_state, COUNT(*) FROM qcfp_monthly_behavior GROUP BY 1 ORDER BY 2 DESC;"

# VP 分布
sqlite3 SQLiteDB\HK_Stock.db "SELECT m_vp_regime, COUNT(*) FROM qcfp_monthly_behavior GROUP BY 1 ORDER BY 2 DESC;"
```

## 五、实例 4：解读状态

### T1~T5（换手-流动性）

| 状态 | Z 区间 | 含义 |
| :-- | :-- | :-- |
| T1 | < -1.5 | 极低交换（<10% 分位） |
| T2 | -1.5 ~ -0.5 | 低交换 |
| T3 | -0.5 ~ +0.5 | 正常交换 |
| T4 | +0.5 ~ +1.5 | 高交换 |
| T5 | > +1.5 | 极端交换（>90% 分位） |

### VP_Regime（9 种 + 中性）

| 组合（价/量/换手） | 状态 | 含义 |
| :-- | :-- | :-- |
| ↑↑↑ | VP_EXPANSION | 趋势扩张（健康） |
| ↑→→ | VP_STABLE_ASCENT | 稳步上涨 |
| ↑↓↓ | VP_LOCKED_CANDIDATE | 缩量上涨（锁定候选） |
| ↑↑↑↑ | VP_OVERHEAT | 加速/博弈升温 |
| →↓↓ | VP_SHRINK | 缩量整理 |
| →↑↑ | VP_DIVERGENCE_HIGH | 高换手分歧 |
| ↓↓↓ | VP_DECLINE_SILENT | 缓慢退潮 |
| ↓↑↑ | VP_SELLING_ACTIVE | 主动抛售 |
| ↓↑↑↑ | VP_PANIC | 恐慌 |
| 其余 | VP_NEUTRAL | 中性 |

### CBI（0~100）

| 区间 | 状态 | 含义 |
| :-- | :-- | :-- |
| > 70 | CBI_LOCKED_CANDIDATE | 筹码交换极低（锁定候选，需季度 C 验证） |
| 50~70 | CBI_STABLE | 行为平稳 |
| 30~50 | CBI_ACTIVE | 交换加速 |
| < 30 | CBI_TURBULENT | 剧烈博弈/分歧 |

### Cost Position 与 Stage

- `COST_ADVANTAGE`：月末价 > 月 VWAP 且 > 季 VWAP；`COST_DISADVANTAGE` 反之；其余 `COST_NEUTRAL`；
- `Improving`：健康 VP 且无极端换手；`Deteriorating`：过热/抛售/恐慌类 VP；`Stable`：缩量整理或中性。

## 六、实例 5：运行测试

```powershell
# 全量 81 项
.venv\Scripts\python.exe Core\QCFP_MTF\tests\run_all_tests.py

# P2 专项
.venv\Scripts\python.exe Core\QCFP_MTF\tests\test_behavioral\test_cbi.py
.venv\Scripts\python.exe Core\QCFP_MTF\tests\test_behavioral\test_vp_matrix.py
```

## 七、实例 6：Python 直接调用（二次开发）

```powershell
$code = @'
import sys
sys.path.insert(0, "Core")

from QCFP_MTF.config.settings import load_qcfp_settings
from QCFP_MTF.data.loader import load_kline
from QCFP_MTF.behavioral.turnover_factors import build_turnover_factors
from QCFP_MTF.behavioral.volume_factors import build_volume_factors
from QCFP_MTF.behavioral.vp_matrix import build_vp_regime
from QCFP_MTF.behavioral.cbi import build_cbi
from QCFP_MTF.behavioral.cost_position import build_cost_position
from QCFP_MTF.behavioral.monthly_stage import build_monthly_stage

s = load_qcfp_settings()
m = load_kline("monthly", stocks=["00700"])
w = load_kline("weekly", stocks=["00700"])
q = load_kline("quarterly", stocks=["00700"])

turn = build_turnover_factors(m, s)
vol = build_volume_factors(m, s)
vp = build_vp_regime(m, vol, s)
cbi = build_cbi(m, s)
cost = build_cost_position(m, w, q, s)
merged = turn.merge(vol[["month_end","m_volume_ma_ratio","m_volume_accel"]], on="month_end") \
             .merge(vp[["month_end","m_vp_regime"]], on="month_end") \
             .merge(cbi[["month_end","cbi_score","cbi_state"]], on="month_end") \
             .merge(cost[["month_end","cost_position"]], on="month_end")
merged["stage"] = build_monthly_stage(merged["m_vp_regime"], merged["turnover_liquidity_regime"])
print(merged.tail(3).to_string())
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
Get-Content Log\monthly_behavior_engine.py.log -Tail 30
```

## 九、参数汇总

| 参数 | 入口 | 说明 |
| :-- | :-- | :-- |
| `--stock 00700` | 主控 / 月线引擎 | 只处理指定股票 |
| `--month-end 2026-07-31` | 月线引擎 | 只计算指定月份 |
| `--dry-run` | 月线引擎 | 不写库，仅生成报告 |
| `--date 2026-08-19` | 主控 | 设置 WORKFLOW_DATE（当前暂未消费） |

## 十、常见问题

| 现象 | 说明 |
| :-- | :-- |
| CBI 普遍偏低（TURBULENT 占一半） | CBI 是"低换手=高稳定"的逆向指数，2021+ 港股高换手常态导致 CBI 偏低的分布，属正常 |
| COST_DISADVANTAGE 占比高 | 2010~2026 下行月份多；位置判断与市场环境一致即可 |
| 00700 2026-07 T5+EXPANSION 却是 Stable | T5 极端换手阻断 Improving，规格书要求；未落入 Deteriorating 集合故为 Stable |
| 停牌/零成交月 | 因子置 NaN，不参与状态判定，不产生错误信号 |
| data_quality 大量 C | 继承自月/周/季 K 线审计等级（负价格脏数据导致），与 P0 审计一致 |
