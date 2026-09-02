# coding: utf-8
"""ReleaseManifest / ProductionBundle（QCFP-MTF 2.8：31 号生产捆绑冻结）

把真正进入 Production 的所有身份冻结成不可变 ReleaseManifest：
    strategy_version + engine_version + governance_version + config_hash +
    feature_manifest_hash + code_commit + data_contract_version +
    decision_schema_version

验收：任何 Production Decision 必须唯一反查一个 ReleaseManifest；
不能出现"代码版本相同但配置实际上不同"的隐性版本。
"""

import hashlib
import json
from dataclasses import asdict, dataclass, field


@dataclass(frozen=True)
class ReleaseManifest:
    release_id: str
    strategy_version: str = ""
    engine_version: str = ""
    governance_version: str = ""
    config_hash: str = ""
    feature_manifest_hash: str = ""
    code_commit: str = ""
    data_contract_version: str = ""
    decision_schema_version: str = ""

    def manifest_hash(self) -> str:
        raw = json.dumps(
            {k: v for k, v in asdict(self).items()
             if k != "release_id"},
            sort_keys=True, ensure_ascii=False, default=str)
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]

    def as_dict(self) -> dict:
        d = asdict(self)
        d["manifest_hash"] = self.manifest_hash()
        return d


class ReleaseManifestRegistry:
    def __init__(self):
        self.manifests = {}

    def freeze(self, manifest: ReleaseManifest) -> None:
        """冻结不可变 Manifest（同 config 不同代码 → 不同 manifest）。"""
        key = manifest.manifest_hash()
        if key in self.manifests \
                and self.manifests[key].release_id != manifest.release_id:
            raise ValueError(
                "ReleaseManifest: 相同 manifest hash 不同 release_id——"
                "存在隐性版本冲突")
        self.manifests[key] = manifest

    def resolve(self, manifest_hash) -> ReleaseManifest:
        m = self.manifests.get(manifest_hash)
        if not m:
            raise ValueError(f"未知 manifest {manifest_hash}")
        return m

    def verify_production_identity(self, manifest: ReleaseManifest) -> bool:
        """Production Decision 唯一反查：manifest_hash 必须存在且一致。"""
        try:
            registered = self.resolve(manifest.manifest_hash())
            return (registered.release_id == manifest.release_id
                    and registered.config_hash == manifest.config_hash
                    and registered.code_commit == manifest.code_commit)
        except ValueError:
            return False


def production_release_identity(manifest: ReleaseManifest) -> dict:
    """新 31 号：唯一生产发布身份（ProductionBundle）。"""
    d = manifest.as_dict()
    return {
        "release_id": manifest.release_id,
        "strategy_version": manifest.strategy_version,
        "engine_version": manifest.engine_version,
        "governance_rule_version": manifest.governance_version,
        "decision_schema_version": manifest.decision_schema_version,
        "config_hash": manifest.config_hash,
        "feature_manifest_hash": manifest.feature_manifest_hash,
        "code_commit": manifest.code_commit,
        "data_contract_version": manifest.data_contract_version,
        "manifest_hash": d["manifest_hash"],
        "chain": "Production Decision → release_id → ReleaseManifest "
                 "→ EvidencePack",
    }


def release_required_check(decision: dict) -> dict:
    """新 31 号：任何 Production Decision 缺 release_id → NOT CERTIFIED。"""
    release_id = decision.get("release_id") or \
        (decision.get("context") or {}).get("release_id")
    return {
        "release_id": release_id,
        "certification": "CERTIFIED" if release_id else "NOT_CERTIFIED",
        "certified": bool(release_id),
        "rule": "Production Decision 缺 release_id → NOT CERTIFIED",
    }
