# coding: utf-8
"""Evidence Run Freeze Contract（P0-1）

保证 20D/60D 证据窗口内"第 1 天和第 20 天是同一个系统"：
    每个 Evidence Window 冻结：
        release_id / release_manifest_hash / config_hash /
        feature_manifest_hash / dataset_contract_hash /
        universe_definition_hash / canonical_engine_version /
        runner_version / evidence_schema_version / window_start
    → evidence_freeze_id

窗口内任一身份字段变化 → EVIDENCE_WINDOW_IDENTITY_BREAK
→ streak reset → 新的 evidence_freeze_id。
"""

import hashlib
import json
from datetime import datetime

from ..common.paths import get_report_root
from ..decision.versions import MODEL_VERSION, RELEASE_TAG, \
    feature_manifest_hash


EVIDENCE_SCHEMA_VERSION = "EVIDENCE-FREEZE-1"

FREEZE_IDENTITY_FIELDS = (
    "release_id", "release_manifest_hash", "config_hash",
    "feature_manifest_hash", "dataset_contract_hash",
    "universe_definition_hash", "canonical_engine_version",
    "runner_version", "evidence_schema_version",
)


def canonical_settings_hash(settings) -> str:
    raw = json.dumps(settings, sort_keys=True, ensure_ascii=False,
                     default=str)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]


def build_freeze_contract(conn, settings, release_id=RELEASE_TAG,
                          window_start="", runner_version="",
                          universe_hash="", dataset_contract_hash="",
                          release_manifest_hash="") -> dict:
    """构造（不持久化）Freeze Contract。dataset/universe hash 缺省时
    从真实 DB 计算。"""
    from ..decision.decision_ledger import dataset_manifest_hash
    dataset_contract_hash = dataset_contract_hash or \
        dataset_manifest_hash(conn)
    if not universe_hash:
        from ..scripts.shadow_universe import universe_symbols
        universe = universe_symbols(conn, window_start or
                                    datetime.now().strftime("%Y-%m-%d"))
        raw = ",".join(sorted(str(c).zfill(5) for c in universe))
        universe_hash = hashlib.sha256(
            raw.encode("utf-8")).hexdigest()[:16]
    release_manifest_hash = release_manifest_hash or hashlib.sha256(
        f"{release_id}|{feature_manifest_hash()}".encode("utf-8")
    ).hexdigest()[:16]
    contract = {
        "schema": "EVIDENCE-FREEZE-CONTRACT-1",
        "release_id": release_id,
        "release_manifest_hash": release_manifest_hash,
        "config_hash": canonical_settings_hash(settings),
        "feature_manifest_hash": feature_manifest_hash(),
        "dataset_contract_hash": dataset_contract_hash,
        "universe_definition_hash": universe_hash,
        "canonical_engine_version": MODEL_VERSION,
        "runner_version": runner_version,
        "evidence_schema_version": EVIDENCE_SCHEMA_VERSION,
        "window_start": window_start,
        "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }
    contract["evidence_freeze_id"] = freeze_id(contract)
    return contract


def freeze_id(contract: dict) -> str:
    raw = json.dumps({k: contract.get(k) for k in FREEZE_IDENTITY_FIELDS},
                     sort_keys=True, ensure_ascii=False, default=str)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]


def window_identity_break(contract: dict, day_identity: dict) -> list:
    """day_identity 与 freeze contract 不一致的字段列表（空 = 一致）。"""
    breaks = []
    for k in FREEZE_IDENTITY_FIELDS:
        if str(contract.get(k) or "") != str(day_identity.get(k) or ""):
            breaks.append(k)
    return breaks


def persist_freeze_contract(contract: dict, out_dir=None) -> dict:
    """不可变持久化：已存在且 freeze_id 相同 → 拒绝覆盖；
    不同 freeze_id（新窗口）→ 允许新建。"""
    out_dir = out_dir or get_report_root() / "audit" / "runtime_evidence"
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / "evidence_freeze_contract.json"
    if path.exists():
        old = json.loads(path.read_text(encoding="utf-8"))
        if old.get("evidence_freeze_id") == contract["evidence_freeze_id"]:
            return {"frozen": False, "reason": "freeze contract 已存在且"
                                               "身份一致（不可变）",
                    "path": str(path),
                    "evidence_freeze_id":
                        contract["evidence_freeze_id"]}
        # 新 freeze_id = 新窗口（例如 hard reset 后）→ 覆盖旧契约
    path.write_text(json.dumps(contract, ensure_ascii=False, indent=2),
                    encoding="utf-8")
    return {"frozen": True, "path": str(path),
            "evidence_freeze_id": contract["evidence_freeze_id"]}


def load_freeze_contract(out_dir=None) -> dict:
    out_dir = out_dir or get_report_root() / "audit" / "runtime_evidence"
    path = out_dir / "evidence_freeze_contract.json"
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))
