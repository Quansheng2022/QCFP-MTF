# coding: utf-8
"""Autonomous Research Guard（QCFP-MTF 2.8：50 号自动研究防越权）

系统可以自动研究，但不能自动给自己授予生产权限：
    Research Agent → Hypothesis → Experiment Registry → Pre-registered Test
    → Ablation → OOS → Statistical Validation → Human/Governance Approval
    → Candidate Model

严格禁止：Production Data → 自动调参 → Production。
记录 Search Space / Trials / Best Result / Selection Rule / Multiple Testing。
"""

from dataclasses import asdict, dataclass, field
from datetime import datetime


class ResearchGuardError(ValueError):
    pass


@dataclass(frozen=True)
class SearchSession:
    session_id: str
    hypothesis: str
    search_space: dict
    max_trials: int
    created_at: str
    trials: tuple = field(default_factory=tuple)
    pre_registered: bool = False
    human_approved: bool = False

    def as_dict(self) -> dict:
        d = asdict(self)
        d["trials"] = list(self.trials)
        return d


class ResearchGuard:
    def __init__(self):
        self.sessions = {}

    def begin_search(self, session_id, hypothesis, search_space,
                     max_trials=20) -> SearchSession:
        if session_id in self.sessions:
            raise ResearchGuardError(f"搜索会话 {session_id} 已存在")
        s = SearchSession(
            session_id=session_id, hypothesis=hypothesis,
            search_space=dict(search_space), max_trials=int(max_trials),
            created_at=datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
        self.sessions[session_id] = s
        return s

    def pre_register(self, session_id) -> SearchSession:
        s = self._get(session_id)
        updated = SearchSession(
            session_id=s.session_id, hypothesis=s.hypothesis,
            search_space=s.search_space, max_trials=s.max_trials,
            created_at=s.created_at, trials=s.trials,
            pre_registered=True, human_approved=s.human_approved)
        self.sessions[session_id] = updated
        return updated

    def record_trial(self, session_id, version, result, selection_rule) -> None:
        s = self._get(session_id)
        if len(s.trials) >= s.max_trials:
            raise ResearchGuardError(
                f"搜索 {session_id} 超过最大试验次数 {s.max_trials}")
        trial = {"version": version, "result": round(float(result), 6),
                 "selection_rule": selection_rule,
                 "at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
        updated = SearchSession(
            session_id=s.session_id, hypothesis=s.hypothesis,
            search_space=s.search_space, max_trials=s.max_trials,
            created_at=s.created_at, trials=s.trials + (trial,),
            pre_registered=s.pre_registered, human_approved=s.human_approved)
        self.sessions[session_id] = updated

    def approve(self, session_id) -> SearchSession:
        s = self._get(session_id)
        updated = SearchSession(
            session_id=s.session_id, hypothesis=s.hypothesis,
            search_space=s.search_space, max_trials=s.max_trials,
            created_at=s.created_at, trials=s.trials,
            pre_registered=s.pre_registered, human_approved=True)
        self.sessions[session_id] = updated
        return updated

    def multiple_testing_check(self, session_id) -> dict:
        """多重检验：试验次数越多，要求显著性越严。"""
        s = self._get(session_id)
        n = len(s.trials)
        if n == 0:
            return {"trials": 0, "alpha_effective": 0.05,
                    "risk": "LOW"}
        alpha = 0.05 / n
        risk = "HIGH" if n >= 20 else "MEDIUM" if n >= 8 else "LOW"
        return {"trials": n, "alpha_effective": round(alpha, 5),
                "risk": risk}

    def promote_candidate(self, session_id, candidate_version,
                          ablation_ok=False, oos_ok=False,
                          statistical_ok=False) -> dict:
        """晋升候选：全部满足才允许进入 Candidate Model。
        缺任一 → ResearchGuardError（禁止自动调参直通生产）。"""
        s = self._get(session_id)
        failures = []
        if not s.pre_registered:
            failures.append("NOT_PRE_REGISTERED")
        if not s.human_approved:
            failures.append("NO_HUMAN_APPROVAL")
        if not ablation_ok:
            failures.append("ABLATION_NOT_PASSED")
        if not oos_ok:
            failures.append("OOS_NOT_PASSED")
        if not statistical_ok:
            failures.append("STATISTICAL_NOT_PASSED")
        mt = self.multiple_testing_check(session_id)
        if mt["risk"] == "HIGH" and not s.human_approved:
            failures.append("MULTIPLE_TESTING_HIGH")
        if failures:
            raise ResearchGuardError(
                f"ResearchGuard: {session_id} 晋升被阻止："
                f"{'; '.join(failures)}")
        return {"session_id": session_id,
                "candidate_version": candidate_version,
                "status": "CANDIDATE",
                "multiple_testing": mt}

    def _get(self, session_id) -> SearchSession:
        s = self.sessions.get(session_id)
        if not s:
            raise ResearchGuardError(f"未知搜索会话 {session_id}")
        return s


def guard_to_md(session: SearchSession, guard: ResearchGuard) -> str:
    mt = guard.multiple_testing_check(session.session_id)
    lines = [
        f"# Autonomous Research Guard　{session.session_id}",
        "",
        f"**假设：{session.hypothesis}**",
        f"- 搜索空间：{session.search_space}",
        f"- 最大试验：{session.max_trials}　已试验：{len(session.trials)}",
        f"- 预注册：{'✅' if session.pre_registered else '❌'}　"
        f"人工批准：{'✅' if session.human_approved else '❌'}",
        f"- 多重检验风险：{mt['risk']}（α_eff={mt['alpha_effective']}）",
        "",
        "| 试验 | 版本 | 结果 | 选择规则 |",
        "| --- | --- | --- | --- |",
    ]
    for i, t in enumerate(session.trials, 1):
        lines.append(f"| {i} | {t['version']} | {t['result']:+.2%} | "
                     f"{t['selection_rule']} |")
    return "\n".join(lines)
