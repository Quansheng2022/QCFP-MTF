# QCFP-MTF P5 用户使用手册（含实例）

> 适用版本：QCFP-MTF-2.1.1 / P5 DSS 决策层
> 环境：Windows + 项目虚拟环境 `.venv`（Python 3.13）
> 所有命令默认在项目根目录执行

## 一、环境准备

```powershell
cd C:\Users\Quansheng\Documents\projects\TA_Workflow
$env:PYTHONIOENCODING="utf-8"
$env:PYTHONUTF8="1"
```

## 二、实例 1：完整跑一遍（含 P5 决策引擎）

```powershell
.venv\Scripts\python.exe run_QCFP_MTF_workflow.py
```

9 步全 ✅：init_db → audit → quality → structural → monthly → weekly → mtf_fusion → **decision_engine** → validate。

## 三、实例 2：回写 Action / 风险

```powershell
# 全量（9827 个决策点）
.venv\Scripts\python.exe Core\QCFP_MTF\scripts\decision_engine.py

# 只看一只股票
.venv\Scripts\python.exe Core\QCFP_MTF\scripts\decision_engine.py --stock 00700

# 预演不写库
.venv\Scripts\python.exe Core\QCFP_MTF\scripts\decision_engine.py --dry-run
```

预期输出（全量）：

```text
00700 2026-08-14: BEARISH_CONFIRMED → EXIT (risk=Extreme, score=20.0)
已回写 9827 行 action/risk 到 qcfp_mtf_decision
```

## 四、实例 3：生成个股 DSS 报告

```powershell
# 默认取该股最新决策日
.venv\Scripts\python.exe Core\QCFP_MTF\scripts\dss_report.py --stock 00700

# 指定决策日
.venv\Scripts\python.exe Core\QCFP_MTF\scripts\dss_report.py --stock 00700 --date 2026-08-14

# 产物
Get-ChildItem Report\QCFP_MTF\dss | Sort-Object LastWriteTime -Descending | Select-Object -First 4 Name
Invoke-Item Report\QCFP_MTF\dss\00700_2026-08-14.md
```

## 五、实例 4：查看决策分布与门控验证

```powershell
# Action 分布
sqlite3 SQLiteDB\HK_Stock.db "SELECT action_signal, COUNT(*) FROM qcfp_mtf_decision GROUP BY 1 ORDER BY 2 DESC;"

# 风险分布
sqlite3 SQLiteDB\HK_Stock.db "SELECT risk_level, COUNT(*) FROM qcfp_mtf_decision GROUP BY 1 ORDER BY 2 DESC;"

# 门控验证（必须返回 0）
sqlite3 SQLiteDB\HK_Stock.db "SELECT COUNT(*) FROM qcfp_mtf_decision WHERE structural_regime IN ('STRUCTURAL_DECLINE','STRUCTURAL_DISTRIBUTION') AND action_signal IN ('BUY','ADD');"
sqlite3 SQLiteDB\HK_Stock.db "SELECT COUNT(*) FROM qcfp_mtf_decision WHERE structural_regime IN ('STRUCTURAL_BULLISH','STRUCTURAL_ACCUMULATION') AND action_signal='EXIT';"
```

## 六、实例 5：解读 Action 与风险

| MTF 状态 | Action | 含义 |
| :-- | :-- | :-- |
| BULLISH_CONFIRMED | BUY | 强共振，可建仓 |
| BULLISH_STABLE | HOLD | 结构健康，持仓等待 |
| BULLISH_WARNING | REDUCE | 战术预警，减仓观察（禁清仓） |
| BEARISH_RECOVERY_CANDIDATE | WAIT | 反弹候选，等待确认 |
| BEARISH_CONFIRMED | EXIT | 多周期退潮，回避 |
| DATA_INSUFFICIENT | WAIT | 数据不足，无信号 |

| 风险等级 | 说明 |
| :-- | :-- |
| Low | 结构健康 + 无背离 + 市场偏多 |
| Medium | 轻度预警（如 BULLISH_WARNING + 数据质量 C） |
| High | 结构走弱或市场风险偏好低 |
| Extreme | 空头 + 背离 + risk_off 叠加，或数据不足 |

## 七、实例 6：运行测试

```powershell
# 全量 133 项
.venv\Scripts\python.exe Core\QCFP_MTF\tests\run_all_tests.py

# P5 专项
.venv\Scripts\python.exe Core\QCFP_MTF\tests\test_decision\test_action_generator.py
.venv\Scripts\python.exe Core\QCFP_MTF\tests\test_decision\test_dss_output.py
```

## 八、实例 7：日常维护

```powershell
# 表结构变更后重生成字典
.venv\Scripts\python.exe Code_utl\Generate_qcfp_Dictionaries.py

# 清理 WAL
sqlite3 SQLiteDB\HK_Stock.db "PRAGMA wal_checkpoint(TRUNCATE);"

# 引擎日志
Get-Content Log\decision_engine.py.log -Tail 30
```

## 九、参数汇总

| 参数 | 入口 | 说明 |
| :-- | :-- | :-- |
| `--stock 00700` | 决策引擎 / dss_report | 只处理指定股票 |
| `--date 2026-08-14` | dss_report | 指定决策日（默认最新） |
| `--dry-run` | 决策引擎 | 不写库，仅打印结果 |

## 十、常见问题

| 现象 | 说明 |
| :-- | :-- |
| 00700 建议 EXIT 是否合理 | 结构 DECLINE + 周线 Consolidation → 空头族默认 BEARISH_CONFIRMED，符合"结构定生死"规则 |
| EXIT 占比高（34%） | 当前市场 risk_off 环境 + 空头结构股票多；可通过 P6 回测验证阈值 |
| 修改 Action 映射 | 在 `Config/qcfp_settings.yaml` 的 `decision.action_mapping` 调整 |
| risk 分布偏极端 | Extreme 由 空头+背离+risk_off 叠加导致，属保守设计 |
| 决策引擎重跑分布不变 | 幂等：同输入同输出（State-First 确定性） |

## 十一、2D 决策与日线战术层（V14 新增）

决策报告升级为二维表达，与 Q/M/W 战略层解耦：

| 维度 | 取值 | 来源 |
| :-- | :-- | :-- |
| 战略定位 | LONG / NEUTRAL / DEFENSIVE | Q/M/W MTF 状态 |
| 战术动作 | ENTER / ADD / HOLD / REDUCE / EXIT / WAIT | 战略状态 × 日线时机 |

- DSS 决策摘要新增"战略 × 战术"行（如 `NEUTRAL × 试多（TEST_BUY）`）；
- DSS 新增"## 4.5 日线战术层"小节：显示最新 `daily_state`（截至交易日）与时机提示（吸筹=潜在突破可关注 / 突破=允许早入场加仓 / 回调=持有不减 / 派发=战术减仓）；
- 日线层默认只读展示（`daily.timing.enabled=false`），不改变数据库 `action_signal`；通过 `daily_alpha_test.py` 验收后可开启为正式时机门。
