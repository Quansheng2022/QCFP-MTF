# coding: utf-8
"""Data Degradation Simulator（QCFP-MTF 2.8：93 号数据退化模拟器）

数据不完整时系统是否安全（不只测数据正确时）：
    Missing / Delayed / Stale / Duplicate / Outlier / Wrong Timestamp /
    Corporate Action Error / Volume Anomaly

DATA_HEALTH = BAD → NEW_ENTRY = BLOCK（不让 Wave 模型继续计算）。
"""

from dataclasses import asdict, dataclass, field


@dataclass(frozen=True)
class DataHealth:
    status: str          # GOOD / DEGRADED / BAD
    new_entry_allowed: bool
    degrade_reasons: tuple

    def as_dict(self) -> dict:
        d = asdict(self)
        d["degrade_reasons"] = list(self.degrade_reasons)
        return d


def data_degradation_simulator(missing_rate=0.0, delay_minutes=0,
                               stale_hours=0, duplicate_ratio=0.0,
                               outlier_ratio=0.0, wrong_timestamp=False,
                               corporate_action_error=False,
                               volume_anomaly=False) -> DataHealth:
    """数据退化 → DATA_HEALTH + 权限效果。

    规则：
        BAD（禁新仓）  ：missing > 10% / stale > 24h / wrong_timestamp /
                         corporate_action_error / volume_anomaly
        DEGRADED       ：missing 5-10% / delay > 5min / duplicate > 5% /
                         outlier > 2%
        GOOD           ：其余
    """
    bad = []
    degraded = []
    if float(missing_rate or 0.0) > 0.10:
        bad.append("MISSING_RATE_HIGH")
    elif float(missing_rate or 0.0) > 0.05:
        degraded.append("MISSING_RATE_MEDIUM")
    if float(stale_hours or 0.0) > 24:
        bad.append("STALE_DATA")
    elif float(delay_minutes or 0.0) > 5:
        degraded.append("DATA_DELAY")
    if float(duplicate_ratio or 0.0) > 0.05:
        degraded.append("DUPLICATE_RATIO")
    if float(outlier_ratio or 0.0) > 0.02:
        degraded.append("OUTLIER_RATIO")
    if wrong_timestamp:
        bad.append("WRONG_TIMESTAMP")
    if corporate_action_error:
        bad.append("CORPORATE_ACTION_ERROR")
    if volume_anomaly:
        bad.append("VOLUME_ANOMALY")
    if bad:
        status = "BAD"
        new_entry = False
    elif degraded:
        status = "DEGRADED"
        new_entry = False
    else:
        status = "GOOD"
        new_entry = True
    return DataHealth(status=status, new_entry_allowed=new_entry,
                      degrade_reasons=tuple(bad + degraded))
