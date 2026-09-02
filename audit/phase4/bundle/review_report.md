# QCFP-MTF Evidence-Aware Review Report

**Verdict：REVIEW_ISSUES**
- Change ID：CHG-P4-FGC-1
- Reviewer：ChatGPT Evidence-Aware Review
- 收到输入：['actual_diff', 'architecture_baseline', 'authority_audit', 'change_id', 'changed_decision_samples', 'complexity_diff', 'implementation_contract', 'known_not_proven_items', 'spec_ids', 'test_evidence']
- Findings：3

## Findings
### F-P4-01 [MINOR] IMPLEMENTATION_DEFECT
- Spec ID：QCFP-SPEC-RLS-003
- Affected File：Core/QCFP_MTF/scripts/phase4_evidence_builder.py
- Evidence：code inspection: phase4_evidence_builder 原实现把 acceptance_results.invariants/unchanged 硬编码为 [True]
- Why：Acceptance Gate 的 invariants 必须来自真实机器 Gate 结果（Spec/Baseline/Traceability），硬编码 True 违反 evidence-first 语义。
- Required Correction：在 Acceptance 计算前先运行 Spec/Baseline/Traceability Gate，并把真实结果推导为 invariants/unchanged。
- Acceptance Condition：acceptance_result.json 的 invariants 与 bundle 中 spec_conformance/baseline/traceability 结果一致且全部为 True

### F-P4-02 [MINOR] IMPLEMENTATION_DEFECT
- Spec ID：QCFP-SPEC-CHG-002
- Affected File：Core/QCFP_MTF/scripts/phase4_regression_runner.py
- Evidence：code inspection: phase4_regression_runner 依赖脚本目录在 sys.path 才能 import phase3_regression_runner
- Why：隐式 sys.path 依赖在非脚本入口调用时可能 ImportError，降低 Runner 可复现性。
- Required Correction：显式把脚本目录插入 sys.path 后再导入，并保持 phase3 runner 复用（不复制 JUnit 解析）。
- Acceptance Condition：python Core/QCFP_MTF/scripts/phase4_regression_runner.py --suites phase4_flow 可独立运行

### F-P4-03 [MINOR] DOCUMENTATION_DRIFT
- Spec ID：QCFP-SPEC-RLS-003
- Affected File：Core/QCFP_MTF/governance/phase4.py
- Evidence：code inspection: phase4.py ARTIFACT_SCHEMAS 曾同时列 bundle artifact 与 out_dir 验证证据，未说明分层
- Why：evidence_pack_readonly / evidence_manifest_verification 是派生验证证据，不属于 bundle 输入；混列会造成读者误解。
- Required Correction：在 ARTIFACT_SCHEMAS 旁注释两件派生验证证据的位置（out_dir）与读取 Provider。
- Acceptance Condition：phase4.py 模块内注释明确两类证据分层；test_phase4 全绿

> Reviewer 无权输出 RELEASE_PASS；发布判定只属于 Pure Release Judge（SOFTWARE_QUALIFIED / NOT_PROVEN / REJECTED）。