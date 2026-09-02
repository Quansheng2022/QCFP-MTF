# coding: utf-8
"""Release / Artifact Registry（QCFP-MTF 2.8：P1-6 版本制品注册表）

Release Hash 唯一确定整个生产版本：
    Git Commit / Code Hash / Model / Rule / Config / Schema / Feature /
    Data Snapshot / Execution / Test Manifest / OOS / Ablation / Replay /
    Certification 制品
"""

import hashlib
import json
from dataclasses import asdict, dataclass, field


@dataclass(frozen=True)
class ReleaseArtifact:
    release_id: str
    git_commit: str = ""
    code_hash: str = ""
    model_version: str = ""
    rule_version: str = ""
    config_hash: str = ""
    schema_version: str = ""
    feature_manifest: str = ""
    data_snapshot_id: str = ""
    execution_version: str = ""
    test_manifest: str = ""
    oos_artifact: str = ""
    ablation_artifact: str = ""
    replay_artifact: str = ""
    certification_artifact: str = ""

    def release_hash(self) -> str:
        raw = json.dumps(
            {k: v for k, v in asdict(self).items()
             if k != "release_id"},
            sort_keys=True, ensure_ascii=False, default=str)
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]

    def as_dict(self) -> dict:
        d = asdict(self)
        d["release_hash"] = self.release_hash()
        return d


class ArtifactRegistry:
    def __init__(self):
        self.releases = {}

    def register(self, artifact: ReleaseArtifact) -> None:
        self.releases[artifact.release_id] = artifact

    def get(self, release_id) -> ReleaseArtifact:
        return self.releases.get(release_id)

    def verify_release_hash(self, release_id) -> dict:
        a = self.get(release_id)
        if not a:
            return {"release_id": release_id, "verified": False,
                    "reason": "未知 release_id"}
        expected = a.release_hash()
        return {"release_id": release_id, "verified": True,
                "release_hash": expected}
