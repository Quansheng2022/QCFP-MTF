# coding: utf-8
"""Entry Quality Engine（QCFP-MTF 2.8：进场质量评估）

回答"现在进场划不划算"，与 Wave Strength 解耦：
    STRONG Wave + LOW Entry Quality → WAIT（等待更好的介入点）

八因子（每项 0-1 或比例，加权合成为 0-100 分）：
    1. price_position     价格位置（52W 低位好、高位差）
    2. confirmation       确认度（价格/量能/时间三重确认）
    3. volume             量能配合（放量确认/缩量假突破）
    4. volatility         波动率（过高 → 执行成本高、易被洗）
    5. invalidation_dist  失效距离（止损空间小 → 性价比高）
    6. expected_mfe       预期 MFE（与 MAE 的赔率）
    7. execution_cost     执行成本（含冲击/滑点）
    8. trend_momentum     趋势/动量（trend_score + momentum 合成）

2.8 增量（新 14 号）：输出时机分档 timing_band——
    EARLY / OPTIMAL / ACCEPTABLE / LATE / INVALID
    由 wave_stage + trend + 价格位置 + 是否回撤介入综合判定，
    与 band（HIGH/MEDIUM/LOW）并存：band 衡量"质量"，timing_band
    衡量"现在是不是好位置"。

约束：Entry Quality 不改变 Permission，不直接决定仓位；
它只影响 action_gate 的 ENTRY 决策（strong+low → WAIT）。
"""

from dataclasses import asdict, dataclass, field


@dataclass(frozen=True)
class EntryQuality:
    score: float
    band: str              # HIGH / MEDIUM / LOW
    timing_band: str = "ACCEPTABLE"   # EARLY/OPTIMAL/ACCEPTABLE/LATE/INVALID
    factors: dict = field(default_factory=dict)
    reasons: tuple = field(default_factory=tuple)

    def as_dict(self) -> dict:
        d = asdict(self)
        d["reasons"] = list(self.reasons)
        return d


def _band(score: float) -> str:
    if score >= 70:
        return "HIGH"
    if score >= 45:
        return "MEDIUM"
    return "LOW"


def _clamp01(v) -> float:
    try:
        return float(max(0.0, min(1.0, v)))
    except Exception:
        return 0.0


def evaluate_entry_quality(
        price_position_52w=None,      # 0-1（52W 区间位置）
        confirmation=None,            # 0-1 确认度
        volume_confirmation=None,     # 0-1 量能配合度
        weekly_volatility=None,       # 周波动率（比例，如 0.08）
        invalidation_distance=None,   # 进场价到失效价距离（比例）
        expected_mfe=None,            # 预期 MFE（比例）
        expected_mae=None,            # 预期 MAE（比例）
        execution_cost=None,          # 总执行成本（比例，含冲击+滑点）
        trend_score=None,             # 0-100 趋势分（2.8）
        momentum=None,                # 动量（比例，如 0.05）
        pullback=None,                # 是否回撤介入（2.8）
        wave_stage=None,              # 波段阶段（2.8）
        realized_mfe_ratio=None,      # 已实现 MFE / 预期 MFE（2.8）
        weights=None) -> EntryQuality:
    """七因子进场质量评分。

    各因子缺失时取中性 0.5，保证可部分输入。
    """
    w = weights or {
        "price_position": 0.15,
        "confirmation": 0.20,
        "volume": 0.15,
        "volatility": 0.10,
        "invalidation_dist": 0.15,
        "expected_mfe": 0.15,
        "execution_cost": 0.10,
    }
    reasons = []
    # 1) 价格位置：52W 低位 → 高分
    pp = 1.0 - _clamp01(price_position_52w)
    if price_position_52w is not None:
        if price_position_52w >= 0.85:
            reasons.append("PRICE_AT_52W_HIGH")
        elif price_position_52w <= 0.20:
            reasons.append("PRICE_AT_52W_LOW")
    # 2) 确认度
    cf = _clamp01(confirmation)
    # 3) 量能
    vol = _clamp01(volume_confirmation)
    # 4) 波动率：过高 → 执行风险大
    if weekly_volatility is None:
        vol_score = 0.5
    else:
        v = _clamp01(float(weekly_volatility) / 0.10)
        vol_score = 1.0 - v
        if float(weekly_volatility) > 0.12:
            reasons.append("HIGH_VOLATILITY")
    # 5) 失效距离：止损空间占价格比例越小越好（0-10% 高分）
    if invalidation_distance is None:
        inv_score = 0.5
    else:
        inv_score = 1.0 - _clamp01(float(invalidation_distance) / 0.15)
        if float(invalidation_distance) > 0.10:
            reasons.append("WIDE_INVALIDATION")
    # 6) 预期 MFE/MAE 赔率
    if expected_mfe is None or expected_mae is None:
        mfe_score = 0.5
    else:
        mfe = max(0.0, float(expected_mfe))
        mae = max(0.0001, float(expected_mae))
        rr = mfe / mae
        mfe_score = _clamp01((rr - 0.5) / 2.5)   # 0.5x→0, 3x→1
        if rr < 1.0:
            reasons.append("POOR_RISK_REWARD")
    # 7) 执行成本：成本占预期 MFE 越小越好
    if execution_cost is None:
        cost_score = 0.5
    else:
        cost = float(execution_cost or 0.0)
        cost_score = 1.0 - _clamp01(cost / 0.02)  # 0.5%→0.75, 2%→0
        if cost > 0.01:
            reasons.append("HIGH_EXECUTION_COST")
    # 8) 趋势/动量
    if trend_score is None and momentum is None:
        tm = 0.5
    else:
        t = _clamp01((float(trend_score or 50.0) - 30.0) / 60.0)
        m = _clamp01((float(momentum or 0.0) + 0.1) / 0.2)
        tm = 0.6 * t + 0.4 * m
        if trend_score is not None and float(trend_score) < 45:
            reasons.append("WEAK_TREND")

    factors = {
        "price_position_52w": round(pp, 3),
        "confirmation": round(cf, 3),
        "volume": round(vol, 3),
        "volatility": round(vol_score, 3),
        "invalidation_dist": round(inv_score, 3),
        "expected_mfe": round(mfe_score, 3),
        "execution_cost": round(cost_score, 3),
        "trend_momentum": round(tm, 3),
    }
    score = (pp * w["price_position"] + cf * w["confirmation"]
             + vol * w["volume"] + vol_score * w["volatility"]
             + inv_score * w["invalidation_dist"]
             + mfe_score * w["expected_mfe"]
             + cost_score * w["execution_cost"]
             + tm * 0.10)
    score = round(max(0.0, min(100.0, score * 100.0)), 2)
    timing = _timing_band(
        wave_stage=wave_stage, price_position_52w=price_position_52w,
        trend_score=trend_score, pullback=pullback,
        realized_mfe_ratio=realized_mfe_ratio)
    return EntryQuality(score=score, band=_band(score),
                        timing_band=timing, factors=factors,
                        reasons=tuple(reasons))


def _timing_band(wave_stage=None, price_position_52w=None, trend_score=None,
                 pullback=None, realized_mfe_ratio=None) -> str:
    """时机分档：现在是不是好位置。"""
    stage = str(wave_stage or "").upper()
    if stage in ("INVALID", "EXHAUSTING") \
            or (realized_mfe_ratio is not None
                and float(realized_mfe_ratio) >= 0.9):
        return "INVALID"
    if stage in ("MATURE", "LATE") \
            or (price_position_52w is not None
                and float(price_position_52w) >= 0.75):
        return "LATE"
    if stage in ("DISCOVERY", "CONFIRMING") \
            or (trend_score is not None and float(trend_score) < 45):
        return "EARLY"
    if stage == "ACTIVE" and pullback \
            and (price_position_52w is None
                 or float(price_position_52w) <= 0.5):
        return "OPTIMAL"
    return "ACCEPTABLE"


def entry_quality_gate(wave_strength, entry_quality,
                       strong_threshold=0.7, weak_band=("LOW",)) -> tuple:
    """进场门：STRONG Wave + LOW Entry → WAIT。

    返回 (allowed, reason)。
    allowed=False 表示"机会存在但介入点差"，不是 Permission 否决。
    """
    eq = entry_quality if isinstance(entry_quality, EntryQuality) \
        else evaluate_entry_quality()
    strength = float(wave_strength or 0.0)
    if strength >= strong_threshold and eq.band in weak_band:
        return False, f"STRONG_WAVE_LOW_ENTRY(band={eq.band},score={eq.score})"
    if eq.band in weak_band:
        return False, f"LOW_ENTRY_QUALITY(band={eq.band},score={eq.score})"
    return True, "ENTRY_QUALITY_OK"
