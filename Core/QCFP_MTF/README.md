# QCFP-MTF（Core/QCFP_MTF）

季度筹码-资金-价格 三维多时间周期框架 股票分析系统。

> 版本权威：`decision/versions.py`（当前 `QCFP-MTF-2.5.0`）；
> 版本/规格/宪法/生产清单的机器冻结见 `audit/baseline/governance_baseline.json`
> 与 `Core/QCFP_MTF/CANONICAL_SPEC.md`。

## 流程治理（Flow Governance Engineering）

10 项流程治理已接入开发主流程（Sprint A–D），入口：

```powershell
# Sprint A（1-3）：Canonical Spec / Baseline Freeze / Traceability
python run_QCFP_Governance_workflow.py --sprint A

# 单步命令
python Core/QCFP_MTF/scripts/governance_flow.py spec
python Core/QCFP_MTF/scripts/governance_flow.py baseline-init
python Core/QCFP_MTF/scripts/governance_flow.py baseline-check
python Core/QCFP_MTF/scripts/governance_flow.py traceability
python Core/QCFP_MTF/scripts/governance_flow.py impact change.json
python Core/QCFP_MTF/scripts/governance_flow.py judge audit/bundle
```

对应资产：`CANONICAL_SPEC.md`、`audit/baseline/governance_baseline.json`、
`governance/traceability_manifest.yaml`、`governance/implementation_contract.yaml`、
`governance/acceptance_contract.yaml`、`governance/change_impact_classification.py`、
`governance/evidence_aware_review.py`、`governance/patch_scope_lock.py`、
`governance/pure_release_judge.py`、`governance/qualification_promotion.py`。

## P0 已交付能力

- `sql/create_qcfp_tables.sql`：6 张 `qcfp_*` 表（5 张结果表 + 1 张质量审计快照表）
- `common/`：路径、配置、日志、数据库、交易日历、标准化工具
- `config/settings.py`：`Config/qcfp_settings.yaml` + `stock_data_analysis.par [QCFP_MTF]` 合并加载
- `data/loader.py`：从现有 10 张源表加载并标准化
- `data/quality.py`：A/B/C/D 数据质量分级
- `data/evidence.py`：A/A-/B/C/D 证据等级标注
- `scripts/init_db.py`：建表
- `scripts/audit_coverage.py`：覆盖度审计（CSV/JSON 报告）
- `scripts/check_data_quality.py`：质量检测（写库快照 + 报告）

## 运行

> **依赖主工程 TA_Workflow**：QCFP-MTF 是 TA_Workflow 的一个模块，不是独立可运行程序。
> 运行前需要完整主工程环境：`Config/`（stock_data_analysis.par、stock_list.json、
> qcfp_settings.yaml）、`SQLiteDB/HK_Stock.db`、根目录 `run_QCFP_MTF_workflow.py`
> 以及 `Core/utl` 共享工具。单独解压 `Core/QCFP_MTF` 无法独立运行。

```powershell
# 方式一：整条 P0 工作流
python run_QCFP_MTF_workflow.py

# 方式二：单步执行
.venv\Scripts\python.exe Core\QCFP_MTF\scripts\init_db.py
.venv\Scripts\python.exe Core\QCFP_MTF\scripts\audit_coverage.py --stock 00700
.venv\Scripts\python.exe Core\QCFP_MTF\scripts\check_data_quality.py

# 测试
.venv\Scripts\python.exe Core\QCFP_MTF\tests\run_all_tests.py
.venv\Scripts\python.exe -m pytest Core\QCFP_MTF\tests
```

## 约定

- 只读现有 hist/analysis 表，写 `qcfp_*` 新表；
- `stock_code` 统一 5 位数字；日期统一 `YYYY-MM-DD`；
- 新增/修改表字段必须同步 `Code_utl/Generate_qcfp_Dictionaries.py` 并重新生成字典。

## 测试分层

- `pytest Core\QCFP_MTF\tests -m "not integration"`：纯单元测试（无需真实数据库）；
- `pytest Core\QCFP_MTF\tests`：全部测试（需 TA_Workflow 完整环境）；
- `python Core\QCFP_MTF\tests\run_all_tests.py --unit-only`：无 pytest 环境的单元测试子集。
