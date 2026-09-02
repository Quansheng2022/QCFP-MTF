# coding: utf-8
"""Research Artifact Bundle（QCFP-MTF 2.8：55 号研究制品包）

每次正式研究实验自动冻结可重跑 bundle：
    experiment_id / hypothesis / code commit / config / dataset snapshot /
    universe snapshot / random seed / metric contract / results / plots /
    validation status

验收标准：进入 Promotion Gate 的实验必须有唯一 ResearchArtifactID；
无法重现的研究结果只能标记 UNVERIFIED。
"""

import hashlib
import json


BUNDLE_FIELDS = (
    "experiment_id", "hypothesis", "code_commit", "config",
    "dataset_snapshot", "universe_snapshot", "random_seed",
    "metric_contract", "results", "plots", "validation_status",
)


def freeze_research_bundle(bundle: dict) -> dict:
    """冻结研究制品：生成唯一 ResearchArtifactID（内容 hash）。"""
    canonical = {k: bundle.get(k) for k in BUNDLE_FIELDS}
    raw = json.dumps(canonical, sort_keys=True, ensure_ascii=False,
                     default=str)
    artifact_id = hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]
    out = dict(canonical)
    out["research_artifact_id"] = artifact_id
    out["frozen"] = True
    out["validation_status"] = \
        bundle.get("validation_status") or "UNVERIFIED"
    return out


def verify_reproducible(frozen: dict, rerun_results: dict) -> dict:
    """重跑结果与冻结结果一致 → VERIFIED，否则 UNVERIFIED。"""
    reproducible = frozen.get("results") == rerun_results
    return {
        "research_artifact_id": frozen.get("research_artifact_id"),
        "reproducible": reproducible,
        "validation_status": "VERIFIED" if reproducible else "UNVERIFIED",
        "note": "无法重现的研究结果只能标记 UNVERIFIED",
    }


def promotion_requires_artifact(experiment: dict) -> dict:
    """新 55 号：进入 Promotion Gate 的实验必须有唯一 ResearchArtifactID
    且通过 reproducibility verification，否则不能进入 Candidate。"""
    artifact_id = experiment.get("research_artifact_id")
    verification = experiment.get("validation_status")
    missing = []
    if not artifact_id:
        missing.append("RESEARCH_ARTIFACT_ID")
    if verification != "VERIFIED":
        missing.append("REPRODUCIBILITY_VERIFIED")
    return {
        "experiment_id": experiment.get("experiment_id"),
        "research_artifact_id": artifact_id,
        "validation_status": verification,
        "missing": missing,
        "verdict": "CANDIDATE_ELIGIBLE" if not missing
        else "NOT_CANDIDATE_ELIGIBLE",
        "rule": "跑一个脚本看结果不错 ≠ 进入 Candidate；"
                "必须可重现",
    }
