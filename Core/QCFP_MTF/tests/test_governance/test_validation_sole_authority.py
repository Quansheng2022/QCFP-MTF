# coding: utf-8
"""ValidationCertificate 唯一权威静态扫描（Convergence 新 8 号）"""

import re
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[4]
CORE_DIR = PROJECT_ROOT / "Core"
if str(CORE_DIR) not in sys.path:
    sys.path.insert(0, str(CORE_DIR))


def test_research_validated_string_only_in_certificate():
    pattern = re.compile(r'RESEARCH VALIDATED')
    qcfp = Path(CORE_DIR) / "QCFP_MTF"
    offenders = []
    for py in qcfp.rglob("*.py"):
        if "validation_certificate" in str(py):
            continue
        if "test_" in py.name:
            continue
        for i, line in enumerate(py.read_text(encoding="utf-8").splitlines(),
                                 start=1):
            if pattern.search(line):
                offenders.append(f"{py.name}:{i}")
    assert offenders == [], f"非证书代码产生 RESEARCH VALIDATED: {offenders}"
