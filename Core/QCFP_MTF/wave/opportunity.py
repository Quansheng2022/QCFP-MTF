# coding: utf-8
"""Wave Opportunity Object（QCFP-MTF 2.8：从 Signal 升级为 Opportunity）

WaveSignal 只回答"价格过程如何"；WaveOpportunity 回答
"这是一个什么样的波段、模型何时发现、当时权限如何、捕获了多少"。
OQS（Opportunity Quality Score）评估"值不值得下注"（评价用，不改变权限）。

2.8 强化（P1-1/㉓）：Opportunity 携带完整的波段画像：
    wave_type / stage / strength / direction / expected_duration /
    expected_mfe / expected_mae / invalidation / entry_zone /
    confirmation / expiry，供 Entry Quality / Time-in-Trade / Replay 消费。
"""

from dataclasses import asdict, dataclass
from datetime import datetime, timedelta


@dataclass(frozen=True)
class WaveOpportunity:
    wave_id: str
    stock_code: str
    start_date: str
    trigger_date: str = ""
    peak_date: str = ""
    end_date: str = ""
    peak_return: float = 0.0
    max_drawdown: float = 0.0
    duration: int = 0
    regime: str = ""
    institutional_state: str = ""
    permission_at_start: str = ""
    permission_at_trigger: str = ""
    capture_by_model: float = None
    # ---- 2.8 强化字段（波段画像，供决策/评价层消费）----
    wave_type: str = ""           # BREAKOUT / PULLBACK / RECOVERY / ACCUMULATION
    stage: str = ""               # 生命周期阶段（见 wave.lifecycle）
    strength: float = 0.0         # 0-1
    direction: str = ""           # UP / DOWN / SIDEWAYS
    expected_duration: int = 0    # 预期持有交易日/周（由历史分布校准）
    expected_mfe: float = 0.0     # 预期最大有利偏移（比例）
    expected_mae: float = 0.0     # 预期最大不利偏移（比例）
    invalidation: float = 0.0     # 失效价（跌破即波段证伪）
    entry_zone_low: float = 0.0   # 理想介入区下沿
    entry_zone_high: float = 0.0  # 理想介入区上沿
    confirmation: str = ""        # WAIT / PRICE / VOLUME / TIMING
    expiry: str = ""              # 机会过期日（YYYY-MM-DD）

    def as_dict(self) -> dict:
        return asdict(self)


def build_wave_opportunity(wave_label, snap_at_start=None,
                           snap_at_trigger=None, capture_by_model=None,
                           regime="", duration=None, wave_signal=None,
                           expected_duration=0, expected_mfe=0.0,
                           expected_mae=0.0, invalidation=0.0,
                           entry_zone_low=0.0, entry_zone_high=0.0,
                           confirmation="", expiry="") -> WaveOpportunity:
    """WaveLabel（评价标签）+ 决策快照 → WaveOpportunity"""
    wave_type = (wave_signal and getattr(wave_signal, "wave_type", "")
                 or "" )
    stage = (wave_signal and getattr(wave_signal, "lifecycle", "") or "")
    return WaveOpportunity(
        wave_id=f"{wave_label.stock_code}_{wave_label.start_date}",
        stock_code=wave_label.stock_code,
        start_date=wave_label.start_date,
        trigger_date=snap_at_trigger.decision_date if snap_at_trigger else "",
        peak_date=wave_label.peak_date,
        end_date=wave_label.end_date,
        peak_return=round(float(wave_label.gain), 4),
        max_drawdown=0.0,
        duration=duration or 0,
        regime=regime,
        institutional_state=(
            snap_at_start.institutional_state if snap_at_start else ""),
        permission_at_start=(
            snap_at_start.institutional_permission if snap_at_start else ""),
        permission_at_trigger=(
            snap_at_trigger.institutional_permission if snap_at_trigger else ""),
        capture_by_model=capture_by_model,
        wave_type=wave_type or "",
        stage=stage,
        strength=round(float(getattr(wave_signal, "strength", 0.0) or 0.0), 4),
        direction=getattr(wave_signal, "direction", "") or "",
        expected_duration=int(expected_duration or 0),
        expected_mfe=round(float(expected_mfe or 0.0), 4),
        expected_mae=round(float(expected_mae or 0.0), 4),
        invalidation=round(float(invalidation or 0.0), 4),
        entry_zone_low=round(float(entry_zone_low or 0.0), 4),
        entry_zone_high=round(float(entry_zone_high or 0.0), 4),
        confirmation=confirmation or "",
        expiry=expiry or _default_expiry(snap_at_trigger.decision_date
                                         if snap_at_trigger else ""))


def _default_expiry(decision_date: str) -> str:
    """默认机会过期日：决策日 + 30 天（可被显式 expiry 覆盖）。"""
    if not decision_date:
        return ""
    try:
        d = datetime.strptime(str(decision_date)[:10], "%Y-%m-%d")
        return (d + timedelta(days=30)).strftime("%Y-%m-%d")
    except Exception:
        return ""


def opportunity_quality(wave_signal, permission, risk_level, tqs,
                        liquidity_score=None) -> tuple:
    """Opportunity Quality Score（0-100，评价用，不改变 Permission）"""
    s = 0.0
    # Wave Strength（30）
    s += float(getattr(wave_signal, "strength", 0.0) or 0.0) * 30
    if getattr(wave_signal, "recovery", False):
        s += 8
    if getattr(wave_signal, "failure", False):
        s -= 12
    # Institutional Alignment（20）
    s += {"STRONG_ALLOW": 20, "ALLOW": 16, "TEST": 10,
          "WATCH": 4, "BLOCK": 0}.get(permission, 0)
    # Entry Timing（15）：越早越好
    s += {"RECOVERY": 15, "EARLY": 12, "EXPANSION": 8,
          "MATURE": 4, "FAILURE": 0}.get(
        getattr(wave_signal, "lifecycle", "EARLY"), 8)
    # Risk-Reward（20）
    s += {"Low": 20, "Medium": 12, "High": 4, "Extreme": 0}.get(risk_level, 8)
    # Liquidity（5）+ TQS（10）
    s += min(5.0, float(liquidity_score or 0.0))
    s += min(10.0, max(0.0, float(tqs or 0.0) / 10.0))
    score = max(0.0, min(100.0, s))
    band = "A+" if score >= 80 else "High" if score >= 60 else \
        "Tradable" if score >= 40 else "Weak"
    return round(score, 2), band


def waiting_value(setup_type, risk_level, permission, tqs) -> str:
    """等待价值：机会存在但条件未到位 → WAIT_FOR_CONFIRMATION"""
    if setup_type in (None, "NONE"):
        return "WAIT（无 Setup）"
    if risk_level not in ("Low", "Medium"):
        return "WAIT_FOR_RISK"
    if permission in ("BLOCK", "WATCH"):
        return "WAIT_FOR_PERMISSION"
    if float(tqs or 0) < 60:
        return "WAIT_FOR_CONFIRMATION"
    return "ACT（条件齐备）"
