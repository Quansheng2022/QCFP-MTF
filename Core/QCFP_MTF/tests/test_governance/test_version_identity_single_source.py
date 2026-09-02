# coding: utf-8
"""VersionIdentity 唯一版本来源测试（新 13 号）"""

import re
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[4]
CORE_DIR = PROJECT_ROOT / "Core"
if str(CORE_DIR) not in sys.path:
    sys.path.insert(0, str(CORE_DIR))


def test_scripts_no_hardcoded_model_version():
    """运行脚本中硬编码模型版本数趋近 0（定义文件除外）。"""
    scripts = Path(CORE_DIR) / "QCFP_MTF" / "scripts"
    hardcoded = []
    pattern = re.compile(r'QCFP-MTF-2\.5\.0')
    for py in scripts.rglob("*.py"):
        for i, line in enumerate(py.read_text(encoding="utf-8").splitlines(),
                                 start=1):
            if pattern.search(line):
                hardcoded.append(f"{py.name}:{i}")
    assert hardcoded == [], f"脚本残留硬编码版本: {hardcoded}"


def test_versions_single_definition():
    from QCFP_MTF.decision.versions import DECISION_RULE_VERSION, \
        MODEL_VERSION, SCHEMA_VERSION
    assert MODEL_VERSION.startswith("QCFP-MTF-")
    assert DECISION_RULE_VERSION.startswith("GOV-")
    assert SCHEMA_VERSION.startswith("DECISION-")
