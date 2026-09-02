# coding: utf-8
"""Permission Policy（QCFP-MTF 2.2 V31）

权限的唯一定义：**能否新增风险 / 能否维持既有风险 / 是否必须去风险**。

    BLOCK        new_risk=forbidden, maintain=forbidden, de_risk=required
    WATCH        new_risk=forbidden, maintain=allowed,  de_risk=allowed
    TEST         new_risk=limited,   maintain=allowed,  de_risk=allowed
    ALLOW        new_risk=allowed,   maintain=allowed,  de_risk=allowed
    STRONG_ALLOW new_risk=allowed,   maintain=allowed,  de_risk=allowed

审计口径（V31 起）：
    1) 风险增量不变量：BLOCK/WATCH 下 target_position <= previous_position
       （见 retail_position_fsm.assert_no_risk_increase / apply_permission_position_cap）；
    2) 状态-仓位一致性：0 仓位不得停留在 TESTING/BUILDING/HOLDING/TRIMMING
       （见 retail_position_fsm.state_position_consistent）；
    3) 状态级违规：BLOCK 下任何风险承载状态（TESTING/BUILDING/HOLDING）均为违规；
       WATCH+ 状态本身不违规（维持允许），违规由 1)/2) 判定。

旧口径 "permission_cap" 仅作"可新建风险上限"展示（如 WATCH → TESTING），
不再作为绝对状态上限——避免 WATCH×BUILDING"矩阵合法但 Cap 越权"的矛盾。

P0-A（新 3 号）：BLOCK 语义唯一化——BLOCK 只规定
    禁止新增 / 禁止加仓 / 必须降低风险；
是否立即归零（derisk_mode=IMMEDIATE_EXIT）由 Risk/Hard Exit 决定，
默认 PROGRESSIVE（允许 target < previous 渐进去风险）。
全代码库不得再用 `if permission=="BLOCK"` 各自解释仓位规则，
只能读取 PermissionPolicy / permission_policy_object。
"""

from dataclasses import dataclass

PERMISSION_POLICY = {
    "BLOCK":        {"new_risk": False, "maintain": False, "de_risk": True},
    "WATCH":        {"new_risk": False, "maintain": True,  "de_risk": True},
    "TEST":         {"new_risk": True,  "maintain": True,  "de_risk": True},
    "ALLOW":        {"new_risk": True,  "maintain": True,  "de_risk": True},
    "STRONG_ALLOW": {"new_risk": True,  "maintain": True,  "de_risk": True},
}


@dataclass(frozen=True)
class PermissionPolicy:
    """统一机器可执行权限策略（P0-A 新 3 号）：
    BLOCK 默认 PROGRESSIVE 去风险，Hard Exit 由 Risk 层改为
    IMMEDIATE_EXIT。"""
    permission: str
    new_risk_allowed: bool = False
    add_allowed: bool = False
    maintain_allowed: bool = False
    mandatory_derisk: bool = False
    derisk_mode: str = "NONE"          # NONE / PROGRESSIVE / IMMEDIATE_EXIT
    max_new_risk: float = 0.0
    observation_allowed: bool = False

    @classmethod
    def from_permission(cls, permission: str,
                        exit_severity: int = 0) -> "PermissionPolicy":
        pol = permission_policy_object(permission)
        derisk_mode = permission_derisk_mode(
            permission, exit_severity=exit_severity)
        return cls(
            permission=permission,
            new_risk_allowed=bool(pol["new_risk_allowed"]),
            add_allowed=bool(pol["add_allowed"]),
            maintain_allowed=bool(pol["maintain_allowed"]),
            mandatory_derisk=bool(pol["mandatory_derisk"]),
            derisk_mode=derisk_mode,
            max_new_risk=float(pol.get("max_new_risk") or 0.0),
            observation_allowed=bool(pol.get("observation_allowed")
                                     or False),
        )

    def as_dict(self) -> dict:
        return {
            "permission": self.permission,
            "new_risk_allowed": self.new_risk_allowed,
            "add_allowed": self.add_allowed,
            "maintain_allowed": self.maintain_allowed,
            "mandatory_derisk": self.mandatory_derisk,
            "derisk_mode": self.derisk_mode,
            "max_new_risk": self.max_new_risk,
            "observation_allowed": self.observation_allowed,
        }

# Permission Partial Order（2.6：仅用于比较层级，不代表仓位百分比）
PERMISSION_LEVEL = {
    "BLOCK": 0,
    "WATCH": 1,
    "TEST": 2,
    "ALLOW": 3,
    "STRONG_ALLOW": 4,
}

# 数值仓位上限（A1 与 FSM 路径共用同一 Policy；BLOCK/WATCH 增量由 FSM 封顶控制）
PERMISSION_POSITION_CAP = {
    "BLOCK": 0.0,
    "WATCH": 0.20,
    "TEST": 0.20,
    "ALLOW": 0.50,
    "STRONG_ALLOW": 0.70,
}

RISK_BEARING_STATES = ("TESTING", "BUILDING", "HOLDING")


def permission_new_risk_allowed(permission: str) -> bool:
    return bool(PERMISSION_POLICY.get(permission, {}).get("new_risk", False))


def permission_maintain_allowed(permission: str) -> bool:
    return bool(PERMISSION_POLICY.get(permission, {}).get("maintain", False))


def permission_policy_object(permission: str) -> dict:
    """统一机器可执行权限策略对象（P0-2 号）：
        new_risk_allowed / add_allowed / maintain_allowed / max_target /
        mandatory_derisk / observation_allowed

    所有模块只读此对象，禁止自行 `if permission=="BLOCK"` 解释含义。
    """
    pol = PERMISSION_POLICY.get(permission, PERMISSION_POLICY["WATCH"])
    # BLOCK：禁新增 + 禁加仓 + 强制去风险（Policy 明确规定）
    if permission == "BLOCK":
        return {
            "permission": "BLOCK",
            "new_risk_allowed": False,
            "add_allowed": False,
            "maintain_allowed": False,
            "max_target": 0.0,
            "max_new_risk": 0.0,
            "mandatory_derisk": True,
            "derisk_mode": "PROGRESSIVE",
            "observation_allowed": False,
        }
    # WATCH：禁新增、禁加仓、可维持、可观察
    if permission == "WATCH":
        return {
            "permission": "WATCH",
            "new_risk_allowed": False,
            "add_allowed": False,
            "maintain_allowed": True,
            "max_target": 0.0,
            "max_new_risk": 0.0,
            "mandatory_derisk": False,
            "derisk_mode": "NONE",
            "observation_allowed": True,
        }
    # TEST：有限新增、可维持、可观察
    if permission == "TEST":
        return {
            "permission": "TEST",
            "new_risk_allowed": True,
            "add_allowed": False,
            "maintain_allowed": True,
            "max_target": 0.20,
            "max_new_risk": 0.20,
            "mandatory_derisk": False,
            "derisk_mode": "NONE",
            "observation_allowed": True,
        }
    # ALLOW / STRONG_ALLOW：可新增、可加仓
    if permission == "ALLOW":
        return {
            "permission": "ALLOW",
            "new_risk_allowed": True,
            "add_allowed": True,
            "maintain_allowed": True,
            "max_target": 0.50,
            "max_new_risk": 0.50,
            "mandatory_derisk": False,
            "derisk_mode": "NONE",
            "observation_allowed": False,
        }
    return {
        "permission": "STRONG_ALLOW",
        "new_risk_allowed": True,
        "add_allowed": True,
        "maintain_allowed": True,
        "max_target": 0.70,
        "max_new_risk": 0.70,
        "mandatory_derisk": False,
        "derisk_mode": "NONE",
        "observation_allowed": False,
    }


def permission_derisk_mode(permission: str, exit_severity: int = 0,
                           hard_exit: bool = False) -> str:
    """去风险模式唯一判定（P0-A 新 3 号）：
        - Hard Exit（severity>=3）→ IMMEDIATE_EXIT（Risk 层决定立即归零）
        - BLOCK → PROGRESSIVE（允许 target < previous 渐进去风险）
        - 其余 → NONE
    """
    if int(exit_severity or 0) >= 3 or hard_exit:
        return "IMMEDIATE_EXIT"
    if permission == "BLOCK":
        return "PROGRESSIVE"
    return "NONE"


def permission_de_risk_required(permission: str) -> bool:
    return bool(PERMISSION_POLICY.get(permission, {}).get("de_risk", False))


def permission_level(permission: str) -> int:
    return PERMISSION_LEVEL.get(permission, -1)


def permission_monotonic(a: str, b: str) -> bool:
    """a >= b（层级比较，用于"下游不得升级权限"校验）"""
    return permission_level(a) >= permission_level(b)


def can_add_risk(permission: str, previous_position: float,
                 target_position: float, observation: bool = False) -> bool:
    """新增风险资格（2.6 ADD_RISK_GATE 数值层）

    BLOCK         → target == 0（不承担错误）
    WATCH         → target <= previous（或仅允许 OBSERVE 观察仓）
    TEST/ALLOW/STRONG_ALLOW → 允许新增（幅度由参与预算/上限控制）
    """
    target = float(target_position or 0.0)
    prev = float(previous_position or 0.0)
    if permission == "BLOCK":
        return target <= 1e-9
    if permission == "WATCH":
        if observation:
            return target <= 0.05 + 1e-9   # 观察仓上限（与预算默认一致）
        return target <= prev + 1e-9
    return True


def permission_state_violation(permission: str, state: str,
                               target_position: float) -> bool:
    """位置感知的权限状态违规（V31）：
    - BLOCK：TESTING/BUILDING/HOLDING 无论仓位均违规（维持被禁止，必须去风险）；
    - 其余权限：状态本身合法，但 0 仓位却停留在风险承载状态 → 死状态违规。
    """
    if permission == "BLOCK":
        return state in RISK_BEARING_STATES
    if state in RISK_BEARING_STATES and float(target_position or 0.0) <= 1e-9:
        return True
    return False
