# QCFP-MTF P2 测试清单

> 适用范围：月线行为引擎（T1~T5 / VP_Regime / CBI / Cost Position / Stage）
> 验收口径：A~G 全部勾选 = P2 完成
> 记录：2026-08-19 实测基线（当前全部通过）

## 运行环境

- 项目根目录 `C:\Users\Quansheng\Documents\projects\TA_Workflow`；
- 使用 `.venv\Scripts\python.exe`；中文乱码先执行 `$env:PYTHONIOENCODING="utf-8"; $env:PYTHONUTF8="1"`；
- 数据库：`SQLiteDB/HK_Stock.db`。

---

## A. 单元测试（自动化）

- [ ] A1 全量回归：`.venv\Scripts\python.exe Core\QCFP_MTF\tests\run_all_tests.py`
  → 共 81 项全部 PASS（P0 40 + P1 20 + P2 21），退出码 0
- [ ] A2 pytest：`.venv\Scripts\python.exe -m pytest Core\QCFP_MTF\tests -v`
  → 81 passed
- [ ] A3 P2 专项：`... python Core\QCFP_MTF\tests\test_behavioral\test_vp_matrix.py`（其余 6 个 P2 模块同理）
  → 每模块"全部通过 ✅"

## B. 因子模块单测（合成数据）

- [ ] B1 换手因子：T1/T5 边界、零换手月 → NaN、MA 比值公式（含当期）
- [ ] B2 量因子：3 期滞后加速度、↑/↑↑/→ 方向阈值
- [ ] B3 VP 矩阵：9 种规格组合 + VP_NEUTRAL 全通过、方向缺失 → NaN
- [ ] B4 CBI：0~100 范围、稳定序列高分、剧烈波动低分、状态四类
- [ ] B5 Cost Position：ADVANTAGE / NEUTRAL / DISADVANTAGE + VWAP 偏离手算一致
- [ ] B6 Stage：Improving / Stable / Deteriorating / T4~T5 阻断 / 缺失

## C. 数据表验证（qcfp_monthly_behavior）

- [ ] C1 行数与股票：`SELECT COUNT(*), COUNT(DISTINCT stock_code) FROM qcfp_monthly_behavior`
  → 2267 行 / 15 只
- [ ] C2 时间范围：`SELECT MIN(month_end), MAX(month_end) ...`
  → 2010-01-31 ~ 2026-07-31
- [ ] C3 阶段分布：`SELECT monthly_behavior_state, COUNT(*) ... GROUP BY 1`
  → Deteriorating 945 / Stable 739 / Improving 583
- [ ] C4 换手状态分布：`SELECT turnover_liquidity_regime, COUNT(*) ...`
  → T2:733 / T3:684 / T4:312 / T5:294 / T1:90
- [ ] C5 VP 分布：`SELECT m_vp_regime, COUNT(*) ...`
  → 规格书 9 种 + VP_NEUTRAL 共 10 类全部出现（如 VP_DECLINE_SILENT 497 / VP_NEUTRAL 441 ...）
- [ ] C6 CBI 范围：`SELECT MIN(cbi_score), MAX(cbi_score) FROM ...`
  → 1.9 ~ 100.0（全在 0~100），非空 2119 行
- [ ] C7 Cost 分布：`SELECT cost_position, COUNT(*) ...`
  → DISADVANTAGE 1253 / NEUTRAL 638 / ADVANTAGE 169
- [ ] C8 数据质量：`SELECT data_quality, COUNT(*) ...`
  → C:1860 / A:407
- [ ] C9 幂等性：重复运行 `monthly_behavior_engine.py` 两次
  → 行数不变（2267）、无唯一键冲突
- [ ] C10 唯一索引：`PRAGMA index_list(qcfp_monthly_behavior)`
  → 含 `idx_qcfp_mb_code_month`（UNIQUE）
- [ ] C11 新增列：`PRAGMA table_info(qcfp_monthly_behavior)`
  → 含 cbi_score / cbi_state / cost_position / cost_vs_weekly_vwap / cost_vs_monthly_vwap / cost_vs_quarterly_vwap

## D. 引擎运行

- [ ] D1 单股：`... monthly_behavior_engine.py --stock 00700`
  → 日志显示"已 UPSERT 189 行"（00700 月线数），退出码 0
- [ ] D2 全量：不加参数
  → "已 UPSERT 2267 行"
- [ ] D3 预演：`--dry-run` → 生成报告不写库
- [ ] D4 指定月份：`--month-end 2026-07-31` → 仅该月
- [ ] D5 报告产物：`Report/QCFP_MTF/monthly/monthly_behavior_<时间戳>.{csv,json}`

## E. 合理性检查

- [ ] E1 CBI 状态占比合理：TURBULENT/ACTIVE 为主（1073/850），LOCKED_CANDIDATE 少（26）
- [ ] E2 COST_ADVANTAGE 月份平均收益应明显高于 COST_DISADVANTAGE（可用 SQL/脚本验证）
- [ ] E3 00700 最新月（2026-07-31）：T5 / VP_EXPANSION / CBI 19.5 / COST_ADVANTAGE / Stage=Stable（T5 阻断 Improving）
- [ ] E4 缺失处理：停牌/零成交月份因子为 NaN，不产生错误状态

## F. 工作流集成

- [ ] F1 全流程：`.venv\Scripts\python.exe run_QCFP_MTF_workflow.py`
  → 6 步全 ✅（init_db → audit → quality → structural → **monthly_behavior** → validate），退出码 0
- [ ] F2 日志：`Log/monthly_behavior_engine.py.log` 存在且中文正常
- [ ] F3 幂等：连续两次全流程不报错

## G. 工程约定

- [ ] G1 字典同步：`Code_utl\Generate_qcfp_Dictionaries.py` 重跑后，
  `Config/qcfp_monthly_behavior_dictionary.json` 字段数 = PRAGMA 列数（含 6 个新增列）
- [ ] G2 源表只读：`hk_*` 表结构未被 P2 改动
- [ ] G3 无乱码：CSV 报告 utf-8-sig

---

## 验收标准

- 必备：A1、B1~B6、C1~C11、D1~D2、D5、E1~E4、F1~F3、G1~G3；
- 可选：A2~A3、D3~D4；
- 说明：E2 属于抽样合理性验证，可结合最新报告 CSV 抽查。
