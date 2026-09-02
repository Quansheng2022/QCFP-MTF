# coding: utf-8
"""Strategy Lifecycle Management（QCFP-MTF 2.8）

Development → Research → Validation → Candidate → Shadow → Paper →
Production → Retired

禁止 Production 直接改参数：生产版本变更必须
    V2 Candidate → Ablation → OOS → Shadow → Approval → Production V2

2.8（36 号）：版本注册中心强化——
    每个版本绑定 strategy_id / engine_version / commit_hash / config_hash /
    data_snapshot_id；每个 Production Decision 可精确回答
    "当时是哪一个版本做出的决定"（bind_production_decision 登记）。
"""

from dataclasses import asdict, dataclass


LIFECYCLE_ORDER = ["development", "research", "validation", "candidate",
                   "shadow", "paper", "production", "retired"]


class StrategyLifecycleError(ValueError):
    pass


@dataclass(frozen=True)
class StrategyVersion:
    version: str
    strategy_id: str = ""
    data_version: str = "1.0"
    feature_version: str = ""
    rule_version: str = ""
    parameter_version: str = ""
    engine_version: str = ""
    commit_hash: str = ""
    config_hash: str = ""
    data_snapshot_id: str = ""
    release_status: str = ""       # RESEARCH/VALIDATED/SHADOW/APPROVED/
                                   # PRODUCTION/DEPRECATED/RETIRED
    approval_status: str = "development"
    effective_date: str = ""
    retirement_date: str = ""
    created_at: str = ""

    def as_dict(self) -> dict:
        return {k: v for k, v in asdict(self).items()}

    def bind_production_decision(self, decision_id, decision_date,
                                 commit_hash="", config_hash="",
                                 data_snapshot_id="") -> dict:
        """登记一次 Production Decision 的版本绑定（可审计）。"""
        return {
            "strategy_id": self.strategy_id,
            "version": self.version,
            "decision_id": decision_id,
            "decision_date": decision_date,
            "commit_hash": commit_hash or self.commit_hash,
            "config_hash": config_hash or self.config_hash,
            "data_snapshot_id": data_snapshot_id or self.data_snapshot_id,
            "release_status": self.release_status or self.approval_status,
        }


class StrategyLifecycle:
    def __init__(self, versions=None):
        self.versions = dict(versions or {})

    def register(self, v: StrategyVersion) -> None:
        if v.version in self.versions:
            raise StrategyLifecycleError(f"版本 {v.version} 已存在")
        self.versions[v.version] = v

    def register_v2(self, v: StrategyVersion) -> None:
        """注册（2.8 强化版）：strategy_id+version 唯一。"""
        key = f"{v.strategy_id}:{v.version}" if v.strategy_id \
            else v.version
        if key in self.versions:
            raise StrategyLifecycleError(f"版本 {key} 已存在")
        self.versions[key] = v

    def bind_decision(self, version, decision_id, decision_date,
                      commit_hash="", config_hash="", data_snapshot_id="",
                      registry=None) -> dict:
        """Production 版本绑定决策（写入 registry 列表）。"""
        v = self.versions.get(version)
        if not v:
            raise StrategyLifecycleError(f"未知版本 {version}")
        if v.approval_status != "production":
            raise StrategyLifecycleError(
                f"版本 {version} 非 Production（{v.approval_status}），"
                f"禁止绑定生产决策")
        rec = v.bind_production_decision(
            decision_id, decision_date, commit_hash=commit_hash,
            config_hash=config_hash, data_snapshot_id=data_snapshot_id)
        if registry is not None:
            registry.append(rec)
        return rec

    def promote(self, version, target: str) -> StrategyVersion:
        v = self.versions.get(version)
        if not v:
            raise StrategyLifecycleError(f"未知版本 {version}")
        if target not in LIFECYCLE_ORDER:
            raise StrategyLifecycleError(f"非法状态 {target}")
        cur = LIFECYCLE_ORDER.index(v.approval_status)
        nxt = LIFECYCLE_ORDER.index(target)
        if nxt < cur:
            raise StrategyLifecycleError("禁止回退生命周期状态")
        # P0-6：禁止手工重建丢失 provenance 字段——
        # 使用 dataclasses.replace 完整继承全部字段
        import dataclasses
        updated = dataclasses.replace(
            v, approval_status=target)
        self.versions[version] = updated
        return updated

    def retire(self, version, date: str) -> StrategyVersion:
        v = self.promote(version, "retired")
        import dataclasses
        updated = dataclasses.replace(v, approval_status="retired",
                                      retirement_date=date)
        self.versions[version] = updated
        return updated

    def assert_provenance_preserved(self, version) -> None:
        """P0-6：晋升后 commit/config/data snapshot/hash 必须与原认证
        对象完全一致；字段丢失 → 抛错。"""
        v = self.versions.get(version)
        if not v:
            raise StrategyLifecycleError(f"未知版本 {version}")
        if v.commit_hash or v.config_hash or v.data_snapshot_id \
                or v.strategy_id or v.engine_version:
            return
        raise StrategyLifecycleError(
            f"Provenance 丢失：{version} 缺少 commit/config/data/strategy "
            f"字段，禁止进入生产")

    def current_production(self) -> StrategyVersion:
        prods = [v for v in self.versions.values()
                 if v.approval_status == "production"]
        if not prods:
            raise StrategyLifecycleError("无 Production 版本")
        return sorted(prods, key=lambda v: v.effective_date)[-1]

    def production_change_gate(self, candidate, ablation_ok=False,
                               oos_ok=False, shadow_ok=False,
                               approved=False) -> tuple:
        """生产变更门：candidate → Ablation/OOS/Shadow → Approval → Production"""
        reasons = []
        if candidate.approval_status not in ("candidate", "shadow", "paper"):
            reasons.append("NOT_CANDIDATE")
        if not ablation_ok:
            reasons.append("ABLATION_NOT_PASSED")
        if not oos_ok:
            reasons.append("OOS_NOT_PASSED")
        if not shadow_ok:
            reasons.append("SHADOW_NOT_PASSED")
        if not approved:
            reasons.append("NOT_APPROVED")
        return not reasons, tuple(reasons)
