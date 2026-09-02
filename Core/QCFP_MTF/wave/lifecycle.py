# coding: utf-8
"""Wave Lifecycle（QCFP-MTF 2.8：波段生命周期治理）

Wave 不再只是"一个信号"，而是带生命周期的对象：
    DISCOVERY → CONFIRMING → ACTIVE → MATURE → EXHAUSTING → INVALID

生命周期记录：
    - 起点（discovered_at）/ 年龄（age_days / age_weeks）
    - 最大存活时长（max_duration_days，超期未确认 → 衰减/失效）
    - 失效条件（invalidation：跌破 invalidation_level 即失效）
    - 衰减（decay：随年龄增长机会强度自然衰减）

约束：本模块只管理"波段生命周期"状态，不决定 Permission / FSM / 仓位；
它与 WaveSignal（as-of）兼容，禁止任何 future-aware 字段进入决策。
"""

from dataclasses import asdict, dataclass, field
from datetime import date, datetime


WAVE_LIFECYCLE_STAGES = (
    "DISCOVERY", "CONFIRMING", "ACTIVE", "MATURE",
    "EXHAUSTING", "INVALID",
)


class WaveLifecycleError(ValueError):
    pass


@dataclass(frozen=True)
class WaveLifecycle:
    wave_id: str
    stock_code: str
    stage: str = "DISCOVERY"
    discovered_at: str = ""
    confirmed_at: str = ""
    activated_at: str = ""
    matured_at: str = ""
    invalidated_at: str = ""
    age_days: int = 0
    age_weeks: int = 0
    max_duration_days: int = 90
    invalidation_level: float = 0.0
    last_price: float = 0.0
    last_close: float = 0.0
    decay: float = 1.0
    reasons: tuple = field(default_factory=tuple)

    def as_dict(self) -> dict:
        return asdict(self)

    def is_alive(self) -> bool:
        return self.stage not in ("INVALID", "EXHAUSTING")


def _parse_date(value) -> date:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    return datetime.strptime(str(value)[:10], "%Y-%m-%d").date()


def _age_days(start, now) -> int:
    try:
        return max(0, (_parse_date(now) - _parse_date(start)).days)
    except Exception:
        return 0


def _decay_factor(age_days: int, max_duration_days: int) -> float:
    """生命周期衰减：0–60% 时长内无衰减，之后线性衰减到 0.6（并非失效）。"""
    if max_duration_days <= 0:
        return 1.0
    ratio = age_days / max_duration_days
    if ratio <= 0.6:
        return 1.0
    if ratio >= 1.0:
        return 0.6
    return round(1.0 - 0.4 * (ratio - 0.6) / 0.4, 4)


def advance_lifecycle(lc: WaveLifecycle, as_of: str, price: float,
                      confirmed: bool = False, active: bool = False,
                      matured: bool = False) -> WaveLifecycle:
    """按 as_of 推进生命周期。

    规则：
        DISCOVERY  + 确认  → CONFIRMING（confirmed_at 首次落时间）
        CONFIRMING + 激活  → ACTIVE
        ACTIVE     + 成熟  → MATURE
        任意阶段    价格跌破 invalidation_level → INVALID
        超 max_duration_days → EXHAUSTING（允许外部在超期时人工确认）
    返回新的不可变实例（原对象不变）。
    """
    reasons = list(lc.reasons)
    price = float(price or 0.0)
    age = _age_days(lc.discovered_at or as_of, as_of)
    decay = _decay_factor(age, lc.max_duration_days)
    stage = lc.stage
    confirmed_at, activated_at, matured_at = (
        lc.confirmed_at, lc.activated_at, lc.matured_at)

    # 失效优先（价格跌破失效位 → INVALID，不可被确认覆盖）
    if lc.invalidation_level > 0 and price < lc.invalidation_level:
        stage = "INVALID"
        if not lc.invalidated_at:
            reasons.append(f"INVALIDATION_PRICE_BREAK@{price:.3f}"
                           f"<{lc.invalidation_level:.3f}")
    elif stage == "DISCOVERY" and confirmed:
        stage = "CONFIRMING"
        confirmed_at = confirmed_at or as_of
        reasons.append(f"CONFIRMED@{as_of}")
    elif stage == "CONFIRMING" and active:
        stage = "ACTIVE"
        activated_at = activated_at or as_of
        reasons.append(f"ACTIVATED@{as_of}")
    elif stage == "ACTIVE" and matured:
        stage = "MATURE"
        matured_at = matured_at or as_of
        reasons.append(f"MATURED@{as_of}")
    # 超期未确认 → EXHAUSTING（不是 INVALID，允许再确认窗口）
    if stage not in ("INVALID", "EXHAUSTING") \
            and lc.max_duration_days > 0 and age > lc.max_duration_days:
        stage = "EXHAUSTING"
        reasons.append(f"MAX_DURATION_EXCEEDED@{as_of}")

    return WaveLifecycle(
        wave_id=lc.wave_id, stock_code=lc.stock_code, stage=stage,
        discovered_at=lc.discovered_at or as_of, confirmed_at=confirmed_at,
        activated_at=activated_at, matured_at=matured_at,
        invalidated_at=as_of if stage == "INVALID" else lc.invalidated_at,
        age_days=age, age_weeks=age // 7, max_duration_days=lc.max_duration_days,
        invalidation_level=lc.invalidation_level, last_price=price,
        last_close=price, decay=decay, reasons=tuple(reasons))


def start_lifecycle(wave_id, stock_code, discovered_at, start_price,
                    invalidation_level=0.0, max_duration_days=90,
                    confirmed=False) -> WaveLifecycle:
    """新建 WaveLifecycle（DISCOVERY 或直接 CONFIRMING）。"""
    lc = WaveLifecycle(
        wave_id=wave_id, stock_code=stock_code, discovered_at=discovered_at,
        max_duration_days=max_duration_days,
        invalidation_level=float(invalidation_level or 0.0),
        last_price=float(start_price or 0.0),
        last_close=float(start_price or 0.0))
    if confirmed:
        lc = advance_lifecycle(lc, discovered_at, start_price, confirmed=True)
    return lc
