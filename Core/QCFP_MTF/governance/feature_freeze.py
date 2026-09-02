# coding: utf-8
"""Feature Freeze（QCFP-MTF 2.8：30 号功能冻结）

版本周期内：
    允许：Bug Fix / Governance Fix / PIT Fix / Replay Fix /
          Evidence Improvement / Ablation / Stress / Simplification /
          Retirement
    原则上禁止：新增未经证据支持的决策模块

每个新增模块必须先回答"它解决什么已经被测量出来的问题"，
并经 OOS/Ablation/Stress/Shadow/Incremental Value → KEEP/DROP
（默认不进入 Production）。
"""


ALLOWED_WORK = ("bug_fix", "governance_fix", "pit_fix", "replay_fix",
                "evidence_improvement", "ablation", "stress",
                "simplification", "retirement")


def feature_freeze_gate(work_type, measured_problem="",
                        incremental_value=0.0,
                        oos_ok=False, ablation_ok=False,
                        stress_ok=False, shadow_ok=False) -> dict:
    """功能冻结门。

    - 允许类工作直接放行
    - 新决策模块必须：有已测量问题 + 增量价值 > 0 +
      OOS/Ablation/Stress/Shadow 全过，否则默认 DROP/不进入生产。
    """
    if work_type in ALLOWED_WORK:
        return {"allowed": True, "reason": f"{work_type} 属于允许类工作",
                "default_decision": "ALLOWED"}
    missing = []
    if not measured_problem:
        missing.append("未回答'解决什么已测量的问题'")
    if float(incremental_value or 0.0) <= 0:
        missing.append("无正增量价值")
    for gate, ok in (("oos", oos_ok), ("ablation", ablation_ok),
                     ("stress", stress_ok), ("shadow", shadow_ok)):
        if not ok:
            missing.append(f"{gate} 未通过")
    if missing:
        return {"allowed": False,
                "reason": "Feature Freeze：默认不进入 Production（"
                          + "; ".join(missing) + "）",
                "default_decision": "DROP"}
    return {"allowed": True,
            "reason": f"新模块解决已测量问题：{measured_problem}",
            "default_decision": "KEEP_CANDIDATE"}
