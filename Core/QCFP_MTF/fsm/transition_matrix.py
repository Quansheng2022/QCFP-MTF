# coding: utf-8
"""FSM State Transition Probability（QCFP-MTF 2.7）

从真实历史（Ledger）统计状态转移概率矩阵，并按
Market Regime / Institutional Permission 分组；
进一步计算 Expected State Value，让 FSM 有历史统计依据。
"""

from collections import Counter


def build_transition_matrix(fsm_states) -> dict:
    """状态序列 → {from: {to: probability}}"""
    seq = list(fsm_states)
    pairs = Counter((a, b) for a, b in zip(seq, seq[1:]))
    out = {}
    for (a, b), n in pairs.items():
        out.setdefault(a, Counter())[b] += n
    for a, cnt in out.items():
        total = sum(cnt.values())
        out[a] = {b: round(v / total, 4) for b, v in cnt.items()}
    return out


def transition_matrix_by(ledger_df, by_cols=("institutional_permission",)) -> dict:
    """按分组列统计转移矩阵（需含 decision_date / next_fsm_state）"""
    out = {}
    for key, g in ledger_df.groupby(list(by_cols)):
        seq = g.sort_values("decision_date")["next_fsm_state"].tolist()
        out[str(key)] = build_transition_matrix(seq)
    return out


def expected_state_value(matrix, state_values) -> dict:
    """期望状态价值：EV(from) = Σ p(to|from) × value(to)"""
    out = {}
    for frm, row in matrix.items():
        ev = sum(p * float(state_values.get(to, 0.0))
                 for to, p in row.items())
        out[frm] = round(ev, 4)
    return out
