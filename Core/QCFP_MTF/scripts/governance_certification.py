#!/usr/bin/env python
# coding: utf-8
"""
QCFP-MTF 2.8 —— End-to-End Governance Certification（全链路治理认证）

五维认证：不可越权 / 可审计 / 可回测 / 可Ablation / 牛散实战

用法：
    python Core/QCFP_MTF/scripts/governance_certification.py \
        [--checks-file checks.json]

checks-file：{"permission_gate": true, "ledger": true, ...}
缺省全部 false（诚实显示未达标项）。
"""

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[3]
CORE_DIR = PROJECT_ROOT / "Core"
if str(CORE_DIR) not in sys.path:
    sys.path.insert(0, str(CORE_DIR))

from QCFP_MTF.common.paths import get_report_root
from QCFP_MTF.governance.certification import CERTIFICATION_DIMENSIONS, \
    certification_to_md, governance_certification


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="QCFP-MTF 治理认证")
    parser.add_argument("--checks-file", default=None)
    args = parser.parse_args(argv)
    checks = {}
    if args.checks_file:
        checks.update(json.loads(Path(args.checks_file).read_text(
            encoding="utf-8")))
    cert = governance_certification(checks)
    output = {
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "certification": cert,
    }
    report_root = get_report_root() / "certification"
    report_root.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d")
    (report_root / f"governance_certification_{stamp}.json").write_text(
        json.dumps(output, ensure_ascii=False, indent=2, default=str),
        encoding="utf-8")
    md = certification_to_md(cert)
    (report_root / f"governance_certification_{stamp}.md").write_text(
        md, encoding="utf-8")
    print(md)
    return 0 if cert["certified"] else 1


if __name__ == "__main__":
    sys.exit(main())
