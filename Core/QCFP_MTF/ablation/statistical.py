# coding: utf-8
"""Statistical Validation Layer（QCFP-MTF 2.8：29/39 号）

把"看起来有效"升级为"证据支持有效"：
    Baseline / Treatment / Delta / Sample Size / Bootstrap CI /
    Effect Size / Permutation p-value / Sub-period / Regime Breakdown

并内置 Experiment Registry 防止多重检验挑最优：
    - 每个实验登记 candidate_version + selection_rule + validation_set
    - 实验次数越多，要求显著性越严（Bonferroni 风格）：
      alpha_eff = 0.05 / n_experiments

2.8（39 号）：升级为 Research Experiment Registry——
    完整记录 Hypothesis / Baseline / Treatment / Dataset / PIT Grade /
    OOS Window / Metrics / Statistical Test / Selection Rule / Result；
    未注册实验 → 不得作为正式研究结论（assert_registered 强制）。
"""

from dataclasses import asdict, dataclass, field
from datetime import datetime

import numpy as np


@dataclass(frozen=True)
class StatisticalResult:
    experiment_id: str
    baseline: float
    treatment: float
    delta: float
    sample_size: int
    ci_low: float
    ci_high: float
    p_value: float
    effect_size: float
    sub_periods: dict
    regime_breakdown: dict
    alpha_effective: float
    significant: bool
    verdict: str

    def as_dict(self) -> dict:
        return asdict(self)


def _bootstrap_ci(base_obs, treat_obs, n=1000, seed=42) -> tuple:
    rng = np.random.default_rng(seed)
    deltas = []
    for _ in range(n):
        b = rng.choice(base_obs, size=len(base_obs), replace=True)
        t = rng.choice(treat_obs, size=len(treat_obs), replace=True)
        deltas.append(float(np.mean(t) - np.mean(b)))
    return float(np.percentile(deltas, 2.5)), float(np.percentile(deltas, 97.5))


def _permutation_p(base_obs, treat_obs, n=500, seed=42) -> float:
    """置换检验：随机打乱分组，观察|Δ|大于实际|Δ|的比例。"""
    rng = np.random.default_rng(seed)
    obs = np.concatenate([base_obs, treat_obs])
    n_b = len(base_obs)
    actual = abs(float(np.mean(treat_obs) - np.mean(base_obs)))
    count = 0
    for _ in range(n):
        rng.shuffle(obs)
        b, t = obs[:n_b], obs[n_b:]
        if abs(float(np.mean(t) - np.mean(b))) >= actual:
            count += 1
    return round((count + 1) / (n + 1), 4)


def _effect_size(base_obs, treat_obs) -> float:
    pooled = np.std(np.concatenate([base_obs, treat_obs]))
    if pooled == 0:
        return 0.0
    return round(float((np.mean(treat_obs) - np.mean(base_obs)) / pooled), 4)


def statistical_validation(base_obs, treat_obs, experiment_id="exp",
                           n_bootstrap=1000, n_perm=500, seed=42,
                           n_experiments=1, sub_periods=None,
                           regime_breakdown=None,
                           baseline_label="baseline",
                           treatment_label="treatment") -> StatisticalResult:
    """统一统计验证输出。"""
    base = np.asarray(base_obs, float)
    treat = np.asarray(treat_obs, float)
    if len(base) == 0 or len(treat) == 0:
        raise ValueError("base_obs / treat_obs 均不能为空")
    delta = round(float(np.mean(treat) - np.mean(base)), 4)
    ci_low, ci_high = _bootstrap_ci(base, treat, n_bootstrap, seed)
    p = _permutation_p(base, treat, n_perm, seed)
    es = _effect_size(base, treat)
    alpha_eff = round(0.05 / max(1, int(n_experiments)), 5)
    significant = bool(ci_low > 0 or ci_high < 0) and p < alpha_eff
    verdict = "SIGNIFICANT" if significant else \
        "MARGINAL" if (ci_low > 0 or ci_high < 0) else "NOT_SIGNIFICANT"
    return StatisticalResult(
        experiment_id=experiment_id,
        baseline=round(float(np.mean(base)), 4),
        treatment=round(float(np.mean(treat)), 4),
        delta=delta,
        sample_size=min(len(base), len(treat)),
        ci_low=round(ci_low, 4), ci_high=round(ci_high, 4),
        p_value=p, effect_size=es,
        sub_periods=dict(sub_periods or {}),
        regime_breakdown=dict(regime_breakdown or {}),
        alpha_effective=alpha_eff,
        significant=significant, verdict=verdict)


@dataclass
class ExperimentRegistry:
    """实验注册表：登记每次候选实验，防止挑最优不报总数。"""
    experiments: list = field(default_factory=list)

    def register(self, experiment_id, candidate_version, selection_rule,
                 validation_set, result: StatisticalResult = None) -> None:
        self.experiments.append({
            "experiment_id": experiment_id,
            "candidate_version": candidate_version,
            "selection_rule": selection_rule,
            "validation_set": validation_set,
            "result": result.as_dict() if result else None,
            "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        })

    def register_research(self, experiment_id, hypothesis, baseline,
                          treatment, dataset, pit_grade="C",
                          oos_window="", metrics=None,
                          statistical_test="", selection_rule="",
                          result: StatisticalResult = None,
                          pit_specification="", feature_version="",
                          parameter_space=None, train_period="",
                          validation_period="", cost_model="",
                          execution_model="", ablation_definition="",
                          promotion_status="research") -> None:
        """36 号：完整研究实验登记（含 PIT/参数空间/训练-验证-OOS/
        成本/执行/消融定义/晋升状态）。"""
        self.experiments.append({
            "experiment_id": experiment_id,
            "hypothesis": hypothesis,
            "baseline": baseline,
            "treatment": treatment,
            "dataset": dataset,
            "pit_grade": pit_grade,
            "pit_specification": pit_specification,
            "feature_version": feature_version,
            "parameter_space": parameter_space or {},
            "train_period": train_period,
            "validation_period": validation_period,
            "oos_window": oos_window,
            "cost_model": cost_model,
            "execution_model": execution_model,
            "ablation_definition": ablation_definition,
            "metrics": metrics or {},
            "statistical_test": statistical_test,
            "selection_rule": selection_rule,
            "result": result.as_dict() if result else None,
            "promotion_status": promotion_status,
            "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        })

    def get(self, experiment_id) -> dict:
        for e in self.experiments:
            if e["experiment_id"] == experiment_id:
                return e
        return None

    def assert_registered(self, experiment_id) -> None:
        """39 号强制：未注册实验不得作为正式研究结论。"""
        if self.get(experiment_id) is None:
            raise ValueError(
                f"UnregisteredExperiment: {experiment_id} 未在 "
                f"Research Experiment Registry 登记，禁止作为正式研究结论")

    def count(self) -> int:
        return len(self.experiments)

    def report(self) -> dict:
        n = self.count()
        significant = sum(
            1 for e in self.experiments
            if e.get("result") and e["result"].get("significant"))
        return {
            "experiment_count": n,
            "candidate_count": len({
                e.get("candidate_version") for e in self.experiments
                if e.get("candidate_version")}),
            "significant_count": significant,
            "selection_rule": [e["selection_rule"] for e in self.experiments
                               if e.get("selection_rule")],
            "validation_set": list({
                e["validation_set"] for e in self.experiments
                if e.get("validation_set")}),
            "alpha_effective": round(0.05 / max(1, n), 5),
            "warning": bool(n >= 10),
            "research_records": [
                {k: e[k] for k in ("experiment_id", "hypothesis", "baseline",
                                   "treatment", "dataset", "pit_grade",
                                   "oos_window", "statistical_test",
                                   "selection_rule")
                 if k in e} for e in self.experiments],
        }

    def check_selection_bias(self) -> dict:
        """多重检验警告：实验次数多但只有少数显著 → 谨慎采信。"""
        r = self.report()
        if r["experiment_count"] == 0:
            return {"risk": "NONE", "reason": "无实验记录"}
        sig_ratio = r["significant_count"] / r["experiment_count"]
        if r["experiment_count"] >= 20 and sig_ratio < 0.1:
            risk = "HIGH"
            reason = "实验≥20 次而显著率<10%，疑似多重检验挑最优"
        elif r["experiment_count"] >= 10:
            risk = "MEDIUM"
            reason = f"实验={r['experiment_count']}，需用 alpha_eff=" \
                     f"{r['alpha_effective']} 复核显著性"
        else:
            risk, reason = "LOW", "实验次数有限，正常复核"
        return {"risk": risk, "reason": reason,
                **{k: r[k] for k in ("experiment_count", "significant_count",
                                     "alpha_effective")}}

    def holdout_lock(self, experiment_id, oos_period, used_in_selection) \
            -> dict:
        """37 号 Holdout Lock：最终 OOS 数据不得参与参数选择。

        used_in_selection=True → 该 OOS 已被用于调参 → 不能作为最终 OOS
        （需另冻结独立 OOS）。
        """
        e = self.get(experiment_id)
        if e is None:
            raise ValueError(f"未登记实验 {experiment_id}")
        if used_in_selection:
            return {"locked": True, "ok": False,
                    "reason": "OOS 已参与参数选择，禁止作为最终 OOS，"
                              "须冻结独立 OOS 窗口"}
        e["oos_window"] = oos_period
        e["holdout_locked"] = True
        return {"locked": True, "ok": True, "reason": "Holdout 已锁定"}


def validation_to_md(result: StatisticalResult, registry: ExperimentRegistry
                     = None) -> str:
    lines = [
        f"# Statistical Validation　{result.experiment_id}",
        "",
        f"**Verdict：{result.verdict}**（α_eff = {result.alpha_effective}）",
        "",
        f"- Baseline：{result.baseline:.2%}　Treatment：{result.treatment:.2%}",
        f"- Delta：{result.delta:+.2%}",
        f"- Bootstrap 95% CI：[{result.ci_low:.2%}, {result.ci_high:.2%}]",
        f"- Permutation p-value：{result.p_value:.4f}",
        f"- Effect Size：{result.effect_size:.3f}（Sample n={result.sample_size}）",
        "",
    ]
    if result.sub_periods:
        lines += ["| 子区间 | Δ |", "| --- | --- |"]
        for k, v in result.sub_periods.items():
            lines.append(f"| {k} | {v:+.2%} |")
        lines += [""]
    if result.regime_breakdown:
        lines += ["| Regime | Δ |", "| --- | --- |"]
        for k, v in result.regime_breakdown.items():
            lines.append(f"| {k} | {v:+.2%} |")
        lines += [""]
    if registry is not None:
        bias = registry.check_selection_bias()
        lines += [
            "## 实验注册表（防多重检验）",
            "",
            f"- 实验次数：{bias['experiment_count']}",
            f"- 显著次数：{bias['significant_count']}",
            f"- 挑选风险：{bias['risk']}（{bias['reason']}）",
            "",
        ]
    return "\n".join(lines)


def paired_ablation(baseline_series, treatment_series,
                    regime_series=None, n_perm=1000, seed=42,
                    block_size=4) -> dict:
    """Paired time-series Ablation（P0-10 号）：
        Δ_t = Treatment_t − Baseline_t（paired block statistics）

    - Block/stationary bootstrap（保持时序依赖）
    - Permutation（保持原分布/状态持续性）
    - Regime 分层
    - Effect Size
    输出：每个模块 KEEP/REVIEW/DROP + 贡献类型。
    """
    base = np.asarray([float(x) for x in baseline_series], float)
    treat = np.asarray([float(x) for x in treatment_series], float)
    n = min(len(base), len(treat))
    if n < 4:
        return {"n": n, "verdict": "NO_DATA",
                "contribution_type": "none"}
    delta = treat[:n] - base[:n]
    mean_delta = float(delta.mean())
    # Block bootstrap（保持时序依赖）
    rng = np.random.default_rng(seed)
    n_blocks = int(np.ceil(n / block_size))
    boot_deltas = []
    for _ in range(500):
        blocks = rng.integers(0, n_blocks, size=n_blocks)
        sample = np.concatenate([
            delta[b * block_size: (b + 1) * block_size] for b in blocks])
        boot_deltas.append(float(sample[:n].mean()))
    ci_low = float(np.quantile(boot_deltas, 0.025))
    ci_high = float(np.quantile(boot_deltas, 0.975))
    # Block Sign-Flip Permutation（P0-C 新 9 号修复）：
    # 对 delta 按块做 ±1 符号翻转构造正确的 null distribution。
    # （旧实现 treat[perm]-base[perm]=delta[perm]，均值不变，无法构造 null。）
    perm_count = 0
    blocks = [delta[i:i + block_size]
              for i in range(0, n, block_size)]
    for _ in range(n_perm):
        flipped = []
        for b in blocks:
            sign = 1.0 if rng.random() < 0.5 else -1.0
            flipped.append(sign * b)
        d_perm = np.concatenate(flipped)[:n]
        if abs(float(d_perm.mean())) >= abs(mean_delta):
            perm_count += 1
    p_value = (perm_count + 1) / (n_perm + 1)
    pooled_std = float(np.std(delta))
    effect_size = mean_delta / pooled_std if pooled_std > 0 else 0.0
    # Regime 分层
    regime_breakdown = {}
    if regime_series is not None and len(regime_series) >= n:
        regimes = list(dict.fromkeys(regime_series[:n]))
        for reg in regimes:
            mask = [i for i, r in enumerate(regime_series[:n])
                    if r == reg]
            if mask:
                regime_breakdown[reg] = round(
                    float(delta[mask].mean()), 4)
    # 判定
    significant = (ci_low > 0 or ci_high < 0) and p_value < 0.05
    if significant and abs(effect_size) >= 0.2:
        verdict = "KEEP"
        contribution_type = "alpha" if mean_delta > 0 else "risk_reduction"
    elif abs(mean_delta) >= 0.001:
        verdict = "REVIEW"
        contribution_type = "execution_efficiency"
    else:
        verdict = "DROP"
        contribution_type = "none"
    return {
        "n": n,
        "mean_delta": round(mean_delta, 4),
        "ci_low": round(ci_low, 4),
        "ci_high": round(ci_high, 4),
        "p_value": round(p_value, 4),
        "effect_size": round(effect_size, 4),
        "regime_breakdown": regime_breakdown,
        "n_permutations": n_perm,
        "verdict": verdict,
        "contribution_type": contribution_type,
    }


def formal_ablation_authority() -> dict:
    """Convergence 新 9A 号：Formal Ablation Authority = 1——
    Paired time-series comparison 是唯一认证口径。"""
    return {
        "authority": "PAIRED_TIME_SERIES_ABLATION",
        "methods": ("paired_time_series", "block_aware_inference",
                    "bootstrap_sign_flip", "regime_breakdown",
                    "effect_size"),
        "legacy_permutation": "RESEARCH_ARCHIVE",
        "legacy_certifiable": False,
        "formal_authority_count": 1,
        "rule": "旧 permutation ablation 退役为 RESEARCH_ARCHIVE，"
                "NON_CERTIFIABLE",
    }
