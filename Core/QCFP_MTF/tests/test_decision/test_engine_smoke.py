# coding: utf-8
"""P5 引擎集成冒烟测试（真实数据，00700）"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[4]
CORE_DIR = PROJECT_ROOT / "Core"
if str(CORE_DIR) not in sys.path:
    sys.path.insert(0, str(CORE_DIR))

from QCFP_MTF.scripts.decision_engine import main as decision_main
from QCFP_MTF.scripts.dss_report import main as report_main

try:
    import pytest
    pytestmark = pytest.mark.integration
except ImportError:
    pass


def test_decision_engine_dry_run():
    assert decision_main(["--stock", "00700", "--dry-run"]) == 0


def test_dss_report_generation():
    assert report_main(["--stock", "00700"]) == 0


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print(f"PASS {name}")
    print("test_engine_smoke 全部通过 ✅")
