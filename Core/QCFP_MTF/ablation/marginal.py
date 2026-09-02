# coding: utf-8
"""Marginal Utility Matrix（QCFP-MTF 2.7：Ablation 从"比较收益"升级为"证明边际效用"）

对每个治理模块，输出四维增量：
    Return Δ / MDD Δ / Capture Δ / Turnover Δ
并标注该模块是"Alpha 类"还是"风险治理类"（职责不同，评价不同）。
"""


def marginal_utility_matrix(abl_json: dict) -> dict:
    """从 permission_fsm_ablation JSON 构造边际效用矩阵"""
    models = {m["model"]: m for m in abl_json.get("models", [])}
    matrix = {}
    pairs = {
        "permission": ("A5_PermFSM", "A2_FSM", "governance"),
        "fsm": ("A2_FSM", "A0_Legacy", "retail"),
        "soft_exit": ("A3_FSM_SoftExit", "A2_FSM", "governance"),
        "hard_exit": ("A4_FSM_HardExit", "A2_FSM", "governance"),
        "daily": ("A8_PermFSM_FullExit", "A9_FullNoDaily", "alpha"),
        "budget": ("A8_PermFSM_FullExit", "A10_FullNoBudget", "governance"),
        "observation": ("A8_PermFSM_FullExit", "A13_FullNoObservation",
                        "governance"),
    }

    def _d(a_name, b_name, key):
        a, b = models.get(a_name), models.get(b_name)
        if not a or not b:
            return None
        x, y = a.get(key), b.get(key)
        return round(x - y, 4) if x is not None and y is not None else None

    for name, (a, b, cls) in pairs.items():
        matrix[name] = {
            "class": cls,
            "return_delta": _d(a, b, "annualized_return"),
            "mdd_delta": _d(a, b, "max_drawdown"),
            "capture_delta": _d(a, b, "wave_capture_ratio"),
            "turnover_delta": _d(a, b, "annual_turnover"),
        }
    return matrix
