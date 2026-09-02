# coding: utf-8
"""QCFP-MTF 2.2 Institutional 领域包（机构行为过滤器）

职责边界（ARCHITECTURE.md RULE 01/07）：
    Institutional Permission 是交易上限（upper-bound gate），不是 Alpha Score、不是信号。
"""

from .permission import (InstitutionalPermission,
                         evaluate_institutional_permission)
from .state_engine import institutional_state
from .pressure import institutional_pressure
from .persistence import institutional_persistence
from .divergence import institutional_divergence
from .confidence import institutional_confidence

__all__ = [
    "InstitutionalPermission", "evaluate_institutional_permission",
    "institutional_state", "institutional_pressure",
    "institutional_persistence", "institutional_divergence",
    "institutional_confidence",
]
