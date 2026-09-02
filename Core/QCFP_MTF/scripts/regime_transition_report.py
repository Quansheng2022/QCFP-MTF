#!/usr/bin/env python
# coding: utf-8
"""QCFP-MTF 2.7 —— Regime Transition Report（市场转折检测）"""

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
from QCFP_MTF.data.loader import load_idx_hist
from QCFP_MTF.market.transition import (detect_transitions,
                                        regime_series_from_idx,
                                        transition_risk_adjustment)


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description="Regime Transition Report")
    p.add_argument("--start", default="2023-01-01")
    args = p.parse_args(argv)
    idx = load_idx_hist()
    import pandas as pd
    dates = pd.date_range(args.start, idx["date"].max(), freq="W-FRI")
    series = regime_series_from_idx(idx, dates)
    transitions = detect_transitions(series)
    for t in transitions:
        t["risk_adjustment"] = transition_risk_adjustment(
            t["from"], t["to"])
    out_dir = get_report_root() / "regime"
    out_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d")
    out = {"generated_at": stamp, "n_transitions": len(transitions),
           "transitions": transitions}
    (out_dir / f"regime_transition_{stamp}.json").write_text(
        json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Regime Transition Report 已保存: {stamp}.json")
    for t in transitions[-10:]:
        print(f"  {t['date']} {t['from']}→{t['to']} "
              f"conf={t['confidence']} risk×{t['risk_adjustment']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
