# coding: utf-8
"""Standard Stress Scenario Library（QCFP-MTF 2.8：19 号固定场景库）

所有策略版本跑同一套场景（策略不能选择对自己有利的 Stress 条件）：
    BASE / COST_1.5X / COST_2X / SLIPPAGE_2X / ADV_50% / ADV_25% /
    ENTRY_DELAY_1D / ENTRY_DELAY_2D / GAP_DOWN / BEAR_REGIME /
    HIGH_VOL / LIQUIDITY_SHOCK

Certification 使用固定 Scenario Set + version。
"""


SCENARIO_LIBRARY = {
    "BASE": {"cost_mult": 1.0, "slippage_mult": 1.0, "adv_scale": 1.0,
             "entry_delay_days": 0, "gap": 0.0, "regime": "Bull",
             "vol_scale": 1.0, "liquidity_shock": False},
    "COST_1.5X": {"cost_mult": 1.5, "slippage_mult": 1.0, "adv_scale": 1.0,
                  "entry_delay_days": 0, "gap": 0.0, "regime": "Bull",
                  "vol_scale": 1.0, "liquidity_shock": False},
    "COST_2X": {"cost_mult": 2.0, "slippage_mult": 1.0, "adv_scale": 1.0,
                "entry_delay_days": 0, "gap": 0.0, "regime": "Bull",
                "vol_scale": 1.0, "liquidity_shock": False},
    "SLIPPAGE_2X": {"cost_mult": 1.0, "slippage_mult": 2.0, "adv_scale": 1.0,
                    "entry_delay_days": 0, "gap": 0.0, "regime": "Bull",
                    "vol_scale": 1.0, "liquidity_shock": False},
    "ADV_50%": {"cost_mult": 1.0, "slippage_mult": 1.0, "adv_scale": 0.5,
                "entry_delay_days": 0, "gap": 0.0, "regime": "Bull",
                "vol_scale": 1.0, "liquidity_shock": False},
    "ADV_25%": {"cost_mult": 1.0, "slippage_mult": 1.0, "adv_scale": 0.25,
                "entry_delay_days": 0, "gap": 0.0, "regime": "Bull",
                "vol_scale": 1.0, "liquidity_shock": False},
    "ENTRY_DELAY_1D": {"cost_mult": 1.0, "slippage_mult": 1.0,
                       "adv_scale": 1.0, "entry_delay_days": 1,
                       "gap": 0.0, "regime": "Bull", "vol_scale": 1.0,
                       "liquidity_shock": False},
    "ENTRY_DELAY_2D": {"cost_mult": 1.0, "slippage_mult": 1.0,
                       "adv_scale": 1.0, "entry_delay_days": 2,
                       "gap": 0.0, "regime": "Bull", "vol_scale": 1.0,
                       "liquidity_shock": False},
    "GAP_DOWN": {"cost_mult": 1.0, "slippage_mult": 1.0, "adv_scale": 1.0,
                 "entry_delay_days": 0, "gap": 0.03, "regime": "Bull",
                 "vol_scale": 1.0, "liquidity_shock": False},
    "BEAR_REGIME": {"cost_mult": 1.0, "slippage_mult": 1.0, "adv_scale": 1.0,
                    "entry_delay_days": 0, "gap": 0.0, "regime": "Bear",
                    "vol_scale": 1.0, "liquidity_shock": False},
    "HIGH_VOL": {"cost_mult": 1.0, "slippage_mult": 1.0, "adv_scale": 1.0,
                 "entry_delay_days": 0, "gap": 0.0, "regime": "Sideway",
                 "vol_scale": 2.0, "liquidity_shock": False},
    "LIQUIDITY_SHOCK": {"cost_mult": 1.0, "slippage_mult": 2.0,
                        "adv_scale": 0.3, "entry_delay_days": 0, "gap": 0.02,
                        "regime": "Bear", "vol_scale": 1.5,
                        "liquidity_shock": True},
}

SCENARIO_LIBRARY_VERSION = "SCEN-LIB-1.0"


def scenario_library() -> dict:
    """固定场景库（所有策略版本同一套）。"""
    return {"version": SCENARIO_LIBRARY_VERSION,
            "scenarios": dict(SCENARIO_LIBRARY)}


def certification_scenario_set() -> list:
    """Certification 固定使用完整库（策略不能挑场景）。"""
    return list(SCENARIO_LIBRARY)
