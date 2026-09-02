# coding: utf-8
"""Wave Multi-stage Output（QCFP-MTF 2.8：14 号多阶段波段引擎输出）

Wave 不再只是"Score=0.78"：
    wave_stage / score / strength / age / velocity / acceleration /
    exhaustion / breakdown

阶段：Formation → Trigger → Expansion → Acceleration → Distribution →
Decay（与筹码周期对应：筑底→吸筹→集中→蓄势→主升→派发→退潮）。
"""


WAVE_STAGES = ("FORMATION", "TRIGGER", "EXPANSION", "ACCELERATION",
               "DISTRIBUTION", "DECAY")


def wave_stage_output(score=0.0, strength=0.0, age=0, velocity=0.0,
                      acceleration=0.0, exhaustion=0.0,
                      breakdown=False) -> dict:
    """多阶段 Wave 输出。

    阶段判定：
        breakdown → DECAY
        exhaustion ≥ 0.8 → DECAY
        acceleration > 0.05 → ACCELERATION
        velocity > 0.03 → EXPANSION
        score ≥ 0.6 → TRIGGER
        其余 → FORMATION
    """
    if breakdown or float(exhaustion or 0.0) >= 0.8:
        stage = "DECAY"
    elif float(acceleration or 0.0) > 0.05:
        stage = "ACCELERATION"
    elif float(velocity or 0.0) > 0.03:
        stage = "EXPANSION"
    elif float(score or 0.0) >= 0.6:
        stage = "TRIGGER"
    else:
        stage = "FORMATION"
    return {
        "wave_stage": stage,
        "wave_score": round(float(score or 0.0), 4),
        "wave_strength": round(float(strength or 0.0), 4),
        "wave_age": int(age or 0),
        "wave_velocity": round(float(velocity or 0.0), 4),
        "wave_acceleration": round(float(acceleration or 0.0), 4),
        "wave_exhaustion": round(float(exhaustion or 0.0), 4),
        "wave_breakdown": bool(breakdown),
    }
