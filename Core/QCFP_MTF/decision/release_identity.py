# coding: utf-8
"""Release Identity / Version Lock（QCFP-MTF 2.8：35 号版本锁定）

禁止 Model v2.5 + Rule v2.4 + Config v2.6 这类未验证组合混跑：
    Release Identity = model + rule + config + schema + feature +
                       data_snapshot + execution → release_id

每个 Decision 绑定 release_id；validate_release_lock 校验组件组合
是否在已批准版本清单内（混版本 → ReleaseLockError）。
"""

import hashlib
import json
from dataclasses import asdict, dataclass, field


@dataclass(frozen=True)
class ReleaseIdentity:
    model_version: str
    rule_version: str
    config_version: str = ""
    schema_version: str = ""
    feature_manifest: str = ""
    data_snapshot: str = ""
    execution_version: str = ""

    def release_id(self) -> str:
        raw = json.dumps(asdict(self), sort_keys=True,
                         ensure_ascii=False, default=str)
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]

    def as_dict(self) -> dict:
        d = asdict(self)
        d["release_id"] = self.release_id()
        return d


class ReleaseLockError(ValueError):
    pass


class ReleaseRegistry:
    """已批准版本组合清单（生产只能运行清单内的组合）。"""

    def __init__(self, approved=None):
        self.approved = list(approved or [])

    def approve(self, identity: ReleaseIdentity) -> None:
        self.approved.append(identity)

    def validate_release_lock(self, identity: ReleaseIdentity) -> None:
        """混版本 → ReleaseLockError。"""
        for a in self.approved:
            if (a.model_version == identity.model_version
                    and a.rule_version == identity.rule_version
                    and (not a.config_version
                         or a.config_version == identity.config_version)
                    and (not a.schema_version
                         or a.schema_version == identity.schema_version)):
                return
        raise ReleaseLockError(
            f"ReleaseLock: 未批准版本组合 "
            f"model={identity.model_version} rule={identity.rule_version} "
            f"config={identity.config_version}")


def build_release_identity(model_version, rule_version,
                           config_version="", schema_version="",
                           feature_manifest="", data_snapshot="",
                           execution_version="") -> ReleaseIdentity:
    return ReleaseIdentity(
        model_version=model_version, rule_version=rule_version,
        config_version=config_version, schema_version=schema_version,
        feature_manifest=feature_manifest, data_snapshot=data_snapshot,
        execution_version=execution_version)
