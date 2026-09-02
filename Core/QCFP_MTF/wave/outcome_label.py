# coding: utf-8
"""WaveOutcomeLabel（QCFP-MTF 2.8：P0-9 号波段结果标签）

仅 Evaluation 层使用：允许 realized MFE/MAE / peak_date / end_date /
capture ratio（future-aware）。Production package 禁止 import 本模块。
"""

from dataclasses import asdict, dataclass, field


@dataclass(frozen=True)
class WaveOutcomeLabel:
    wave_id: str
    stock_code: str
    start_date: str
    peak_date: str = ""
    end_date: str = ""
    realized_mfe: float = 0.0
    realized_mae: float = 0.0
    capture_ratio: float = 0.0
    actual_return: float = 0.0
    future_aware: bool = True

    def as_dict(self) -> dict:
        return asdict(self)


def assert_evaluation_only() -> None:
    """Production 代码 import WaveOutcomeLabel → 拒绝（代码级隔离）。"""
    import traceback
    for frame in traceback.extract_stack():
        if "production" in frame.filename.lower() \
                or "decision" in frame.filename.lower():
            raise ImportError(
                "P0-9：WaveOutcomeLabel 是 Evaluation-only（future-aware），"
                "禁止从 Production/Decision 包 import")
