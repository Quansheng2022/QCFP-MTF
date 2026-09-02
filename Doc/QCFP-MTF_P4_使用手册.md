# QCFP-MTF P4 用户使用手册（含实例）

> 适用版本：QCFP-MTF-2.1.1 / P4 多周期融合层
> 环境：Windows + 项目虚拟环境 `.venv`（Python 3.13）
> 所有命令默认在项目根目录执行

## 一、环境准备

```powershell
cd C:\Users\Quansheng\Documents\projects\TA_Workflow
$env:PYTHONIOENCODING="utf-8"
$env:PYTHONUTF8="1"
```

## 二、实例 1：完整跑一遍（含 P4 融合引擎）

```powershell
.venv\Scripts\python.exe run_QCFP_MTF_workflow.py
```

8 步全 ✅：init_db → audit → quality → structural → monthly → weekly → **mtf_fusion** → validate。

## 三、实例 2：只跑融合引擎

```powershell
# 全量（15 只股票 × 每周 = 9827 个决策点）
.venv\Scripts\python.exe Core\QCFP_MTF\scripts\mtf_fusion_engine.py

# 只看一只股票
.venv\Scripts\python.exe Core\QCFP_MTF\scripts\mtf_fusion_engine.py --stock 00700

# 预演不写库
.venv\Scripts\python.exe Core\QCFP_MTF\scripts\mtf_fusion_engine.py --stock 00700 --dry-run

# 只算指定决策日
.venv\Scripts\python.exe Core\QCFP_MTF\scripts\mtf_fusion_engine.py --date 2026-08-14
```

预期输出（全量）：

```text
00700 2026-08-14: BEARISH_CONFIRMED (conf=Low, align=Aligned, market=risk_off, dq=B, ai=PASSED)
...
已 UPSERT 9827 行到 qcfp_mtf_decision
```

## 四、实例 3：查看融合结果

```powershell
# 最新报告
Get-ChildItem Report\QCFP_MTF\fusion | Sort-Object LastWriteTime -Descending | Select-Object -First 3 Name
Invoke-Item (Get-ChildItem Report\QCFP_MTF\fusion\mtf_decision_*.csv | Sort-Object LastWriteTime -Descending | Select-Object -First 1).FullName

# 00700 最近 6 个决策
sqlite3 SQLiteDB\HK_Stock.db "SELECT decision_date, structural_regime, monthly_behavior_state, tactical_signal, mtf_regime, chip_stability_confidence, qcfp_score, market_context FROM qcfp_mtf_decision WHERE stock_code='00700' ORDER BY decision_date DESC LIMIT 6;"

# MTF 状态分布
sqlite3 SQLiteDB\HK_Stock.db "SELECT mtf_regime, COUNT(*) FROM qcfp_mtf_decision GROUP BY 1 ORDER BY 2 DESC;"

# 不越权全量验证（必须返回 0）
sqlite3 SQLiteDB\HK_Stock.db "SELECT COUNT(*) FROM qcfp_mtf_decision WHERE structural_regime IN ('STRUCTURAL_BULLISH','STRUCTURAL_ACCUMULATION') AND mtf_regime='BEARISH_CONFIRMED';"
```

## 五、实例 4：解读 MTF 状态与置信度

| MTF 状态 | 含义 |
| :-- | :-- |
| BULLISH_CONFIRMED | 结构强势 + 月线改善 + 周线突破（强共振） |
| BULLISH_STABLE | 结构强势，趋势健康，等待时机 |
| BULLISH_WARNING | 结构强势但战术预警（减仓观察，禁清仓） |
| BEARISH_RECOVERY_CANDIDATE | 底部候选 + 改善 + 突破（反弹候选，不构成反转） |
| BEARISH_CONFIRMED | 多周期退潮，坚决回避 |
| DATA_INSUFFICIENT | 结构证据不足/数据质量 D，不产生决策 |

| 置信度 | 含义 |
| :-- | :-- |
| High | 季度筹码强 + CBI 稳定（≥70 分） |
| Medium | 结构健康待确认（50~70 分） |
| Low | 季度筹码走弱（C↓ 强制）或综合 <50 分 |

## 六、实例 5：Anti-Inference 检查（Python 调用）

```powershell
$code = @'
import sys
sys.path.insert(0, "Core")
from QCFP_MTF.fusion.anti_inference import scan_conclusions, filter_conclusions

text = "换手率下降，机构锁仓迹象明显，价格站上VWAP"
print("命中:", scan_conclusions(text))
new_text, hits = filter_conclusions(text, mode="warn")
print(new_text)
'@
$code | .venv\Scripts\python.exe -
```

## 七、实例 6：运行测试

```powershell
# 全量 118 项
.venv\Scripts\python.exe Core\QCFP_MTF\tests\run_all_tests.py

# P4 专项
.venv\Scripts\python.exe Core\QCFP_MTF\tests\test_fusion\test_mtf_alignment.py
.venv\Scripts\python.exe Core\QCFP_MTF\tests\test_fusion\test_anti_inference.py
```

## 八、实例 7：日常维护

```powershell
# 表结构变更后重生成字典
.venv\Scripts\python.exe Code_utl\Generate_qcfp_Dictionaries.py

# 清理 WAL
sqlite3 SQLiteDB\HK_Stock.db "PRAGMA wal_checkpoint(TRUNCATE);"

# 引擎日志
Get-Content Log\mtf_fusion_engine.py.log -Tail 30
```

## 九、参数汇总

| 参数 | 入口 | 说明 |
| :-- | :-- | :-- |
| `--stock 00700` | 主控 / 融合引擎 | 只处理指定股票 |
| `--date 2026-08-14` | 融合引擎 | 只计算指定决策日（周） |
| `--dry-run` | 融合引擎 | 不写库，仅生成报告 |

## 十、常见问题

| 现象 | 说明 |
| :-- | :-- |
| 大量 BEARISH_CONFIRMED / BULLISH_WARNING | 结构状态路径依赖 + 当前市场风险偏好偏弱，属分布特征 |
| DATA_INSUFFICIENT 730 行 | 结构 UNDETERMINED（25%）或数据质量 D，按规格书不产生决策 |
| 置信度普遍 Low | 港股高换手 → CBI 低 + 部分股票 C↓，导致置信度低 |
| 为什么没有中间态被跳过 | 兜底规则保证任何三层组合都能映射到 5+1 种状态 |
| 修改兜底规则 | 在 `fusion/mtf_alignment.py` 的 `_fallback` 中调整，须同步单测 |

## 十一、方案 B 战术试多（V10 新增）

在 `qcfp_settings.yaml` 的 `decision.tactical_override` 开启后（默认开启），**空头季度结构（DECLINE/DISTRIBUTION）在满足「周线触发器 ∈ `min_trigger` ＋ 52 周位置 < `max_52w_position`」时输出 `BULLISH_WARNING`（method=`tactical_override`）**，结构状态本身不变，不违反"层级不可越权"。

```powershell
# 查看某股的试多标记与 CQS（写库后查询）
sqlite3 SQLiteDB\HK_Stock.db "SELECT decision_date, structural_regime, tactical_signal, q_position_52w, catalyst_score, catalyst_type, align_method, mtf_regime FROM qcfp_mtf_decision WHERE stock_code='01951' AND align_method='tactical_override' ORDER BY decision_date DESC LIMIT 8;"
```

新增输出列：

| 列 | 含义 |
| :-- | :-- |
| `catalyst_score` | 催化剂质量评分（-3~+3）：F 持续性＋趋势质量＋CBI 稳定性 |
| `catalyst_type` | 高质量反转 / 中性偏强 / 纯脉冲/噪音 |
| `align_method` | `matrix`/`fallback`/`tactical_override`/`data_insufficient`，`tactical_override` = 方案 B 试多行 |

回测/敏感性工具共用同一 `align_mtf` 与配置，生产与回测行为一致（详见 P6 手册 V10 节）。

## 十二、日线战术层（L4 · V14 新增）

日线以 **战术层** 身份正式纳入系统，但**不是第四个平权周期**：Q/M/W 决定战略方向，Daily 只决定时机。

- 新表 `qcfp_daily_tactical`（每股票×每日）：`daily_state`（ACCUMULATION/BREAKOUT/PULLBACK/DISTRIBUTION/NEUTRAL）+ 因子（d_flow_z/d_trend_score/d_vol_ratio 等）；
- 引擎：`daily_tactical_engine.py`，已加入 `run_QCFP_MTF_workflow.py`（位于 weekly 之后、fusion 之前）；
- 权限：Daily 可早入场/加仓/减仓/持有不减，**无权改变 Q/M/W 状态**；`fusion/daily_timing.py` 提供 Model B 时机门，默认 `daily.timing.enabled=false`（增量测试未过验收，保持诊断层）；
- 查看：`SELECT trade_date, daily_state, d_flow_z FROM qcfp_daily_tactical WHERE stock_code='01951' ORDER BY trade_date DESC LIMIT 5;`
