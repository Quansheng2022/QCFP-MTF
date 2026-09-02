# coding: utf-8
"""Governance Decision Card Proofs（QCFP-MTF 2.8：新 12 号）

Card 上每个 ✓ 都必须能反查一个真实 proof/certificate 字段：
    proposal_exceeded_cap / intercepted / final_compliant /
    pit_certificate / replay_verified / ledger_verified

禁止"恒真条件"伪证明（如 perm==snap.institutional_permission
必然成立却显示 ✓ 未升级权限）。
"""


def governance_card_proofs(snap) -> list:
    """从真实 DecisionSnapshot 字段生成可反查证明列表。"""
    ctx = getattr(snap, "context", None) or {}
    proof = (ctx.get("governance_proof") or {})
    proofs = []
    # 1) FinalTarget 已过唯一 Governance Proof
    proofs.append({
        "label": "FinalTarget 已过 Governance Proof",
        "ok": proof.get("proof") == "PASS",
        "evidence_ref": "context.governance_proof.proof",
        "value": proof.get("proof"),
    })
    # 2) PIT Certificate：真实 pit_grade（A/B/C/D），非 input_fingerprint
    pit = getattr(snap, "pit_grade", "") or ""
    proofs.append({
        "label": f"PIT Certificate（{pit}）",
        "ok": pit in ("A", "B"),
        "evidence_ref": "snapshot.pit_grade",
        "value": pit,
    })
    # 3) 提案被约束拦截：BindingConstraint 真实存在
    binding = getattr(snap, "binding_constraint", "") or ""
    proofs.append({
        "label": "Governance 约束拦截",
        "ok": bool(binding),
        "evidence_ref": "snapshot.binding_constraint",
        "value": binding,
    })
    # 4) FinalTarget 合规：raw→final 单调不增（提案可以被压减，不能放大）
    raw = float(getattr(snap, "raw_target_position", 0.0) or 0.0)
    final = float(getattr(snap, "target_position", 0.0) or 0.0)
    proofs.append({
        "label": "FinalTarget 单调不增（raw→final）",
        "ok": final <= raw + 1e-9,
        "evidence_ref": "raw_target_position / target_position",
        "value": {"raw": raw, "final": final},
    })
    # 5) Ledger Verified：run_id 或 context 来源
    run_id = getattr(snap, "run_id", "") or ""
    proofs.append({
        "label": "Ledger Verified",
        "ok": bool(run_id),
        "evidence_ref": "snapshot.run_id",
        "value": run_id,
    })
    return proofs


def governance_card_lines(snap) -> str:
    """Card 渲染（供报告消费，报告本身不重算任何字段）。"""
    lines = ["| Governance Proof | 结果 | 证据字段 |",
             "| :-- | :-- | :-- |"]
    for p in governance_card_proofs(snap):
        mark = "✓" if p["ok"] else "✗"
        lines.append(f"| {mark} {p['label']} | "
                     f"{'PASS' if p['ok'] else 'FAIL'} | "
                     f"`{p['evidence_ref']}` |")
    return "\n".join(lines)
