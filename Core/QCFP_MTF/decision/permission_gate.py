# coding: utf-8
"""Permission Gate（QCFP-MTF 2.8：2 号权限前置不可绕过）

Institutional Permission 是最高交易权限，不是 Alpha Score。
Release 2（新 11 号）：BLOCK 语义统一——只读 PermissionPolicy：
    BLOCK + FLAT        → 0
    BLOCK + HOLDING     → progressive derisk（target < previous，
                          不要求立即 =0）
    BLOCK + Hard Exit   → 0 immediately
禁止各模块自行 `if permission == "BLOCK"` 解释仓位规则。

本模块是权限上限的唯一权威出口（engine/backtest/report 共用）：
    permission_cap(permission)          → 权限上限
    assert_permission_upper_bound(...)  → target > 权限允许即抛错
    assert_wave_cannot_upgrade(...)     → Wave↑ ≠ Permission↑
"""

from .permission_policy import PERMISSION_POSITION_CAP


class PermissionGateError(ValueError):
    pass


def permission_cap(permission) -> float:
    """数值权限上限（PERMISSION_POSITION_CAP 的唯一出口）。"""
    return float(PERMISSION_POSITION_CAP.get(permission, 0.0))


def assert_permission_upper_bound(permission, target,
                                  previous_position=0.0,
                                  exit_severity=0) -> None:
    """硬约束：final_target 不得超过权限上限。

    BLOCK → 渐进去风险（target ≤ previous），Hard Exit（severity≥3）→ 0；
    其余权限：target ≤ max(previous, cap)（既有仓位允许维持）。
    """
    t = float(target or 0.0)
    prev = float(previous_position or 0.0)
    cap = permission_cap(permission)
    if int(exit_severity or 0) >= 3 and t > 1e-9:
        raise PermissionGateError(
            f"PermissionGate: HardExit 但 target={t}")
    if permission == "BLOCK" and t > prev + 1e-9:
        raise PermissionGateError(
            f"PermissionGate: BLOCK 只允许渐进去风险（target ≤ previous="
            f"{prev}），当前 target={t}；立即归零由 Risk/Hard Exit 决定")
    if t > max(prev, cap) + 1e-9:
        raise PermissionGateError(
            f"PermissionGate: target={t} > max(previous={prev}, cap={cap})"
            f" for {permission}")


def assert_wave_cannot_upgrade(permission_before, wave_before,
                               permission_after, wave_after) -> None:
    """单调性守卫：Wave 增强不能导致 Permission 升级。

    若 wave_after > wave_before 而 permission_after 高于 permission_before
    → 抛 PermissionGateError（除非权限同时有独立机构证据，但本守卫
    强制要求在决策链中由 Institutional 单点计算，不允许 Wave 驱动）。
    """
    from .permission_policy import permission_level
    wb, wa = float(wave_before or 0.0), float(wave_after or 0.0)
    pb, pa = permission_level(permission_before), \
        permission_level(permission_after)
    if wa > wb and pa > pb:
        raise PermissionGateError(
            f"PermissionGate: Wave↑({wb}→{wa}) 导致 Permission↑"
            f"({permission_before}→{permission_after})，禁止")


PERMISSION_STRENGTH = {
    "BLOCK": 0.0, "WATCH": 0.10, "TEST": 0.25, "LIMITED": 0.50,
    "ALLOW": 0.75, "STRONG_ALLOW": 1.00,
}


def permission_strength(permission) -> float:
    """权限强度（72 号）：
        BLOCK=0 / WATCH=0.10 / TEST=0.25 / LIMITED=0.50 /
        ALLOW=0.75 / FULL_ALLOW=1.00
    是"限制上限"的连续化，不是 Alpha 分数——只能降低上限，
    不能提高上限。
    """
    return float(PERMISSION_STRENGTH.get(permission, 0.0))


def permission_strength_cap(raw_target, permission, previous_position=0.0,
                            strength_input=None) -> dict:
    """按权限强度计算目标上限：
        Cap = max(previous, raw × strength)
    只会 ≤ raw（从不提高），且 ≤ 数值权限上限。
    """
    raw = float(raw_target or 0.0)
    prev = float(previous_position or 0.0)
    s = float(strength_input if strength_input is not None
              else permission_strength(permission))
    capped = min(raw, max(prev, raw * s))
    return {
        "raw_target": round(raw, 4),
        "permission": permission,
        "strength": round(s, 4),
        "permission_cap": round(max(prev, raw * s), 4),
        "final_cap": round(capped, 4),
        "lowered": capped < raw - 1e-9,
    }
