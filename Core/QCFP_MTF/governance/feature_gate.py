# coding: utf-8
"""Feature Permission Matrix（QCFP-MTF 2.6：信息层不可越权）

防止 Evaluation Feature（未来信息标签）被误用到 Decision Engine：
    WaveLabel / future_peak / future_return 只能用于 Evaluation；
    WaveSignal（as-of）才允许进入 Wave 层与 Decision 层。
"""

FEATURE_LAYERS = ("structural", "wave", "decision", "evaluation")

FEATURE_PERMISSION_MATRIX = {
    "C/F/P": {"structural": True, "wave": False,
              "decision": True, "evaluation": True},
    "institutional_permission": {"structural": False, "wave": False,
                                 "decision": True, "evaluation": True},
    "c_state": {"structural": True, "wave": False,
                "decision": True, "evaluation": True},
    "f_state": {"structural": True, "wave": False,
                "decision": True, "evaluation": True},
    "p_state": {"structural": True, "wave": False,
                "decision": True, "evaluation": True},
    "q_position_52w": {"structural": True, "wave": False,
                       "decision": True, "evaluation": True},
    "data_quality": {"structural": True, "wave": True,
                     "decision": True, "evaluation": True},
    "daily_state": {"structural": False, "wave": True,
                    "decision": True, "evaluation": True},
    "wave_signal": {"structural": False, "wave": True,
                    "decision": True, "evaluation": True},
    "wave_label": {"structural": False, "wave": False,
                   "decision": False, "evaluation": True},
    "future_peak": {"structural": False, "wave": False,
                    "decision": False, "evaluation": True},
    "future_return": {"structural": False, "wave": False,
                      "decision": False, "evaluation": True},
    "disclosure_date": {"structural": True, "wave": False,
                        "decision": True, "evaluation": False},
}


class FeatureGateError(ValueError):
    pass


def feature_allowed(feature: str, layer: str) -> bool:
    return bool(FEATURE_PERMISSION_MATRIX.get(feature, {}).get(layer, False))


def assert_feature_allowed(feature: str, layer: str) -> None:
    """Evaluation 特征（如 WaveLabel）进入 Decision 层即抛错"""
    if not feature_allowed(feature, layer):
        raise FeatureGateError(
            f"FeatureGate: {feature} 不允许进入 {layer} 层"
            f"（请检查 Feature Permission Matrix）")
