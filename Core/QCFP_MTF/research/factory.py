# coding: utf-8
"""Research Experiment Factory（QCFP-MTF 2.8：19 号研究实验工厂）

把 Hypothesis → Dataset → PIT → Baseline → Treatment → Parameter Sweep →
OOS → Ablation → Stress → Replay → Statistical Test → Certification
统一为一次可复现实验：

    experiment_spec → Research Runner → Artifacts → Metrics →
    Comparison → Research Report → Registry
"""

from dataclasses import asdict, dataclass, field
from datetime import datetime


@dataclass(frozen=True)
class ExperimentSpec:
    experiment_id: str
    hypothesis: str
    dataset: str = ""
    pit_grade: str = "C"
    baseline: str = ""
    treatment: str = ""
    parameter_space: dict = field(default_factory=dict)
    cost_model: str = "BASE"
    execution_model: str = "T+1"
    created_at: str = ""

    def as_dict(self) -> dict:
        return asdict(self)


class ResearchExperimentFactory:
    """统一研究实验工厂。"""

    def __init__(self, registry=None):
        self.registry = registry
        self.runs = {}

    def create(self, spec: ExperimentSpec) -> str:
        """创建实验（登记到 Registry）。"""
        if spec.experiment_id in self.runs:
            raise ValueError(f"实验 {spec.experiment_id} 已存在")
        self.runs[spec.experiment_id] = {
            "spec": spec.as_dict(),
            "status": "created",
            "metrics": {},
            "artifacts": {},
            "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        }
        if self.registry is not None:
            self.registry.register_research(
                spec.experiment_id, spec.hypothesis, spec.baseline,
                spec.treatment, spec.dataset, pit_grade=spec.pit_grade,
                oos_window="", cost_model=spec.cost_model,
                execution_model=spec.execution_model,
                parameter_space=spec.parameter_space)
        return spec.experiment_id

    def record_metrics(self, experiment_id, metrics: dict) -> None:
        self.runs[experiment_id]["metrics"] = dict(metrics)

    def record_artifact(self, experiment_id, artifact_name, path) -> None:
        self.runs[experiment_id]["artifacts"][artifact_name] = path

    def finalize(self, experiment_id, status="completed") -> dict:
        run = self.runs.get(experiment_id)
        if not run:
            raise ValueError(f"未知实验 {experiment_id}")
        run["status"] = status
        run["finalized_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        return run

    def report(self, experiment_id) -> dict:
        run = self.runs.get(experiment_id)
        if not run:
            raise ValueError(f"未知实验 {experiment_id}")
        return {
            "experiment_id": experiment_id,
            "spec": run["spec"],
            "status": run["status"],
            "metrics": run["metrics"],
            "artifacts": run["artifacts"],
            "comparison": self._compare(run["metrics"]),
        }

    def _compare(self, metrics) -> dict:
        """Baseline vs Treatment 对比（若有）。"""
        if not metrics:
            return {}
        return {"n_metrics": len(metrics),
                "top_metrics": dict(sorted(
                    metrics.items(), key=lambda x: -abs(float(x[1])))
                    [:5])}
