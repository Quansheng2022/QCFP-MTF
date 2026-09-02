#!/usr/bin/env python
# coding: utf-8
"""QCFP-MTF 2.7 —— Cross-Section Opportunity Ranking Report"""

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
from QCFP_MTF.ranking.opportunity_ranking import rank_opportunities, \
    select_top_n


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description="Opportunity Ranking Report")
    p.add_argument("--top-n", type=int, default=5)
    p.add_argument("--date", default=None)
    args = p.parse_args(argv)
    conn = connect()
    try:
        if args.date:
            rows = conn.execute(
                "SELECT stock_code, decision_date, institutional_permission, "
                "setup_type, trade_quality FROM "
                "qcfp_decision_ledger WHERE status='ACTIVE' "
                "AND decision_date=?", (args.date,)).fetchall()
        else:
            rows = conn.execute(
                "SELECT stock_code, decision_date, institutional_permission, "
                "setup_type, trade_quality FROM "
                "qcfp_decision_ledger WHERE status='ACTIVE' "
                "AND id IN (SELECT MAX(id) FROM qcfp_decision_ledger "
                "WHERE status='ACTIVE' GROUP BY stock_code)").fetchall()
    finally:
        conn.close()
    ranked = rank_opportunities([dict(r) for r in rows])
    top = select_top_n(ranked, n=args.top_n)
    out_dir = get_report_root() / "ranking"
    out_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d")
    out = {"generated_at": stamp, "top_n": args.top_n,
           "ranked": ranked, "selected": top}
    (out_dir / f"opportunity_ranking_{stamp}.json").write_text(
        json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Opportunity Ranking 已保存: {stamp}.json")
    for i, t in enumerate(top, 1):
        print(f"  #{i} {t['stock_code']} score={t['score']} "
              f"perm={t['permission']} setup={t['setup']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
