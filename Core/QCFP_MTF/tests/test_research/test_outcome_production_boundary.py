# coding: utf-8
"""Outcome Production Import Boundary（Runtime Evidence Wiring：第 4 项）

Production packages（decision/execution/institutional/wave/risk/portfolio）
禁止 import research.research_outcome / future_return / mfe / mae /
missed_opportunity——Outcome 只能被 monitoring/research/evaluation 读取。
"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[4]
CORE_DIR = PROJECT_ROOT / "Core"
if str(CORE_DIR) not in sys.path:
    sys.path.insert(0, str(CORE_DIR))


FORBIDDEN_PACKAGES = ("decision", "execution", "institutional", "wave",
                      "risk", "portfolio")
FORBIDDEN_IMPORT_PATTERNS = (
    "from QCFP_MTF.research", "import QCFP_MTF.research",
    "from ..research", "from .research",
    "research_outcome",
)


def test_production_packages_cannot_import_future_aware():
    qcfp_root = Path(CORE_DIR) / "QCFP_MTF"
    violations = []
    for pkg in FORBIDDEN_PACKAGES:
        pkg_dir = qcfp_root / pkg
        if not pkg_dir.exists():
            continue
        for py in pkg_dir.rglob("*.py"):
            if "__pycache__" in py.parts:
                continue
            src = py.read_text(encoding="utf-8", errors="ignore")
            # 只检查 import 语句/模块名，不检查 schema 契约字符串
            import re
            for line in src.splitlines():
                stripped = line.strip()
                if not stripped.startswith(("import ", "from ")):
                    continue
                if any(pat in stripped for pat in FORBIDDEN_IMPORT_PATTERNS):
                    violations.append(
                        f"{py.relative_to(qcfp_root)} 含 {stripped}")
    assert violations == []


def test_outcome_terms_absent_from_production_source():
    """future_return / missed_opportunity（realized outcome 字段）
    不得作为 import 或字段出现在 Production 源码。"""
    import re
    qcfp_root = Path(CORE_DIR) / "QCFP_MTF"
    for pkg in FORBIDDEN_PACKAGES:
        pkg_dir = qcfp_root / pkg
        if not pkg_dir.exists():
            continue
        for py in pkg_dir.rglob("*.py"):
            if "__pycache__" in py.parts:
                continue
            src = py.read_text(encoding="utf-8", errors="ignore")
            # schema_contract 的 FORBIDDEN 标记是禁止声明，允许
            for term in ("future_return", "missed_opportunity"):
                for m in re.finditer(rf"\b{term}\b", src):
                    line = src[:m.start()].rfind("\n")
                    line_text = src[line + 1:src.find("\n", m.start())]
                    if "FORBIDDEN" in line_text:
                        continue
                    assert False, f"{py} 含未来感知字段 {term}"


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print(f"PASS {name}")
    print("test_outcome_production_boundary 全部通过 ✅")
