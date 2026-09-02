# coding: utf-8
"""DeterminismContract（QCFP-MTF 2.8：43 号确定性契约）

Production Decision 禁止随机；Research 随机实验必须保存 seed；
Ablation/Bootstrap 保存 experiment seed；Replay 恢复相同 deterministic
context。

相同 Evidence + Code + Config + Version + Seed → 相同结果。
"""


def audit_random_usage(code_patterns: dict) -> dict:
    """code_patterns：{module: [patterns]}（random/np.random/bootstrap/
    permutation/sample/unordered iteration）"""
    violations = []
    for module, patterns in (code_patterns or {}).items():
        for p in patterns:
            violations.append({"module": module, "pattern": p})
    return {"random_usages": violations,
            "requires_seed": bool(violations),
            "note": "Production Decision 禁止随机；"
                    "Research 随机必须保存 seed"}


def determinism_contract(evidence_id, code_hash, config_hash, version,
                         seed=None, replay_context=None) -> dict:
    """确定性契约：Production 必须 seed=None 且无随机；Replay 恢复 context。"""
    production_ok = seed is None
    return {
        "evidence_id": evidence_id,
        "code_hash": code_hash,
        "config_hash": config_hash,
        "version": version,
        "seed": seed,
        "replay_context": replay_context or {},
        "production_deterministic": production_ok,
        "contract_ok": production_ok,
        "note": "相同 Evidence+Code+Config+Version+Seed → 相同结果",
    }


def assert_deterministic(contract: dict) -> None:
    if not contract.get("contract_ok"):
        raise ValueError("DeterminismContract: Production Decision 禁止随机")


def determinism_identity(seed=None, determinism_version="DET-1.0",
                         numpy_version="", sampling_method="",
                         block_size=None, n_permutations=None) -> dict:
    """新 43 号：Replay Identity 增加 random_seed + determinism_version +
    numpy/sampling/block/permutations 冻结。"""
    return {
        "random_seed": seed,
        "determinism_version": determinism_version,
        "numpy_version": numpy_version,
        "sampling_method": sampling_method,
        "block_size": block_size,
        "n_permutations": n_permutations,
        "research_seed_required": seed is None,
        "production_random_forbidden": seed is not None,
    }


def replay_determinism_check(evidence_id, release_manifest, config_hash,
                             feature_manifest_hash, universe_snapshot_id,
                             run_a, run_b) -> dict:
    """新 43 号：相同 Evidence/Release/Config/Feature/Universe 必须得到
    完全相同 Decision/PathHash/FinalTarget/ReasonCodes——不是"差不多"。"""
    identity = {
        "evidence": evidence_id,
        "release": release_manifest,
        "config": config_hash,
        "feature": feature_manifest_hash,
        "universe": universe_snapshot_id,
    }
    fields = ("decision_id", "decision_path_hash", "final_target",
              "reason_codes")
    mismatches = [f for f in fields
                  if run_a.get(f) != run_b.get(f)]
    return {
        "identity": identity,
        "mismatches": mismatches,
        "deterministic": not mismatches,
        "verdict": "DETERMINISTIC" if not mismatches
        else "DETERMINISM_FAILURE",
        "rule": "Replay 应该重现事实，而不是重新估计事实",
    }
