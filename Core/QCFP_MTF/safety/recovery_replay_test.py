# coding: utf-8
"""Recovery Replay Test（QCFP-MTF 2.8：77 号故障恢复回放认证）

系统在 Ledger 异常、服务重启、数据修正、配置回滚后，
必须能从最后可信 checkpoint 重放到一致状态。

验收标准：恢复不是"服务能启动"，而是
"恢复后的 Canonical Decision 与可信历史完全一致"，
否则不能回到 NORMAL。
"""


def recovery_replay_test(checkpoint_id, replayed_decisions,
                         trusted_decisions) -> dict:
    """逐条对比重放决策与可信历史。"""
    replayed = list(replayed_decisions or [])
    trusted = list(trusted_decisions or [])
    mismatches = []
    for i, (r, t) in enumerate(zip(replayed, trusted)):
        if r != t:
            mismatches.append({"index": i, "replayed": r, "trusted": t})
    if len(replayed) != len(trusted):
        mismatches.append({"index": "length",
                           "replayed_len": len(replayed),
                           "trusted_len": len(trusted)})
    verified = not mismatches
    return {
        "checkpoint_id": checkpoint_id,
        "replayed_count": len(replayed),
        "trusted_count": len(trusted),
        "mismatches": mismatches,
        "verified": verified,
        "verdict": "RECOVERY_OK" if verified else "RECOVERY_FAILED",
        "can_return_normal": verified,
        "rule": "恢复 = 决策与可信历史完全一致，不是服务能启动",
    }


def recovery_state_consistency(ledger_hash, position, fsm, permission,
                               release_identity, config_hash,
                               decision_hash) -> dict:
    """新 77 号：恢复 Production 前必须证明状态一致
    （Last Trusted Ledger Hash / Position / FSM / Permission / Release /
    Config / Decision Hash）。"""
    checks = {
        "ledger_hash": ledger_hash.get("expected") ==
        ledger_hash.get("actual"),
        "position_state": position.get("expected") ==
        position.get("actual"),
        "fsm_state": fsm.get("expected") == fsm.get("actual"),
        "permission_state": permission.get("expected") ==
        permission.get("actual"),
        "release_identity": release_identity.get("expected") ==
        release_identity.get("actual"),
        "config_hash": config_hash.get("expected") ==
        config_hash.get("actual"),
        "decision_hash": decision_hash.get("expected") ==
        decision_hash.get("actual"),
    }
    mismatches = [k for k, ok in checks.items() if not ok]
    return {
        "checks": checks,
        "mismatches": mismatches,
        "consistent": not mismatches,
        "verdict": "REACTIVATION" if not mismatches
        else "STAY_DECISION_HALTED",
        "rule": "服务启动 ≠ 恢复；状态不一致仍 DECISION_HALTED",
    }


def recovery_replay_certificate_required(service_started,
                                         replay_consistent) -> dict:
    """新 77 号：Production 从 Halt 恢复必须
    RecoveryReplayCertificate（REQUIRED）。"""
    if service_started and not replay_consistent:
        return {"certificate_required": True,
                "state": "DECISION_HALTED",
                "reason": "服务已启动但 Replay 不一致 → 仍 HALTED"}
    return {"certificate_required": True,
            "state": "RECOVERY_VALIDATION" if replay_consistent
            else "DECISION_HALTED",
            "reason": "恢复必须产生 RecoveryReplayCertificate"}
