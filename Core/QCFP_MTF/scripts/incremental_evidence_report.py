#!/usr/bin/env python
# coding: utf-8
"""QCFP-MTF 2.7 —— Incremental Evidence Report（模块增量价值判定）"""

import json
import sys
from datetime import datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[3]
CORE_DIR = PROJECT_ROOT / "Core"
if str(CORE_DIR) not in sys.path:
    sys.path.insert(0, str(CORE_DIR))

from QCFP_MTF.ablation.incremental import incremental_evidence
from QCFP_MTF.common.paths import get_report_root


def main(argv=None) -> int:
    bt_dir = get_report_root() / "backtest"
    files = sorted(bt_dir.glob("permission_fsm_ablation_*.json"),
                   key=lambda p: p.stat().st_mtime)
    if not files:
        print("❌ 无 Ablation JSON")
        return 1
    data = json.loads(files[-1].read_text(encoding="utf-8"))
    evidence = incremental_evidence(data)
    out_dir = bt_dir
    stamp = datetime.now().strftime("%Y%m%d")
    (out_dir / f"incremental_evidence_{stamp}.json").write_text(
        json.dumps(evidence, ensure_ascii=False, indent=2), encoding="utf-8")
    print("Incremental Evidence：")
    for k, v in evidence.items():
        print(f"  {k}: {v['verdict']}（{v['class']}）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
