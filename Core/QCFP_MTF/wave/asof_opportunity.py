# coding: utf-8
"""AsOfWaveOpportunity（QCFP-MTF 2.8：P0-9 号 as-of 波段机会）

只含当时可知的字段：stage / strength / entry zone / invalidation /
expected MFE-MAE band / expiry。**禁止任何 realized/future 字段。**
"""

from dataclasses import asdict, dataclass, field


FORBIDDEN_FIELDS = ("realized_mfe", "realized_mae", "peak_date",
                    "end_date", "capture_ratio", "actual_return",
                    "mfe_peak")


@dataclass(frozen=True)
class AsOfWaveOpportunity:
    wave_id: str
    stock_code: str
    as_of_date: str
    stage: str = ""
    strength: float = 0.0
    direction: str = ""
    entry_zone_low: float = 0.0
    entry_zone_high: float = 0.0
    invalidation: float = 0.0
    expected_mfe_band: tuple = field(default_factory=tuple)
    expected_mae_band: tuple = field(default_factory=tuple)
    expiry: str = ""

    def as_dict(self) -> dict:
        d = asdict(self)
        d["expected_mfe_band"] = list(self.expected_mfe_band)
        d["expected_mae_band"] = list(self.expected_mae_band)
        return d


def assert_no_outcome_fields(opportunity: dict) -> None:
    """Feature Contract 阻断：outcome/future 字段进入 as-of 机会 → 抛错。"""
    forbidden = [f for f in FORBIDDEN_FIELDS if f in opportunity
                 and opportunity[f] is not None]
    if forbidden:
        from ..governance.feature_gate import FeatureGateError
        raise FeatureGateError(
            f"FeatureGate: as-of 机会禁止 outcome/future 字段 "
            f"{forbidden}")
