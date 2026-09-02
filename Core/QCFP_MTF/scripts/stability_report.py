#!/usr/bin/env python
# coding: utf-8
"""QCFP-MTF 2.7 —— Decision Stability Report（决策稳定性）"""

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[3]
CORE_DIR = PROJECT_ROOT / "Core"
if str(CORE_DIR) not in sys.path:
    sys.path.insert(0, str(CORE_DIR))

from QCFP_MTF.common.db import connect
from QCFP_MTF.common.paths import get_report_root
from QCFP_MTF.config.settings import load_qcfp_settings
from QCFP_MTF.decision.stability import stability_report


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description="Decision Stability Report")
    p.add_argument("--stock", required=True)
    p.add_argument("--n", type=int, default=30)
    args = p.parse_args(argv)
    settings = load_qcfp_settings()
    from QCFP_MTF.scripts.dss_report import _latest_decision, _row
    conn = connect()
    try:
        date = _latest_decision(conn, args.stock)
        row = _row(conn, args.stock, date) if date else None
    finally:
        conn.close()
    if not row:
        print(f"❌ {args.stock} 无决策数据")
        return 1
    report = stability_report(row, settings, n_perturbations=args.n)
    out_dir = get_report_root() / "stability"
    out_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d")
    (out_dir / f"stability_{args.stock}_{stamp}.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"{args.stock} {date}：Stability={report['stability_score']}  "
          f"PermFlip={report['permission_flip_rate']}  "
          f"FSMFlip={report['fsm_flip_rate']}  "
          f"ExitFlip={report['exit_flip_rate']}  "
          f"PosSens={report['position_sensitivity']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
