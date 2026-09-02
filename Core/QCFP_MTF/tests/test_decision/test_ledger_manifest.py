# coding: utf-8
"""Ledger Dataset Manifest / Append-only Event 测试（P0-3 号）"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[4]
CORE_DIR = PROJECT_ROOT / "Core"
if str(CORE_DIR) not in sys.path:
    sys.path.insert(0, str(CORE_DIR))

from QCFP_MTF.common.db import connect
from QCFP_MTF.decision.decision_ledger import dataset_manifest_hash


def test_dataset_manifest_hash():
    conn = connect()
    try:
        h1 = dataset_manifest_hash(conn)
        h2 = dataset_manifest_hash(conn)
        assert h1 == h2
        assert len(h1) == 16
    finally:
        conn.close()


def test_manifest_content_sensitive():
    conn = connect()
    try:
        h = dataset_manifest_hash(conn)
        # 不同表集合 → 不同哈希（内容变化可检测）
        h2 = dataset_manifest_hash(conn, tables=("qcfp_quarterly_structural",))
        assert h != h2
    finally:
        conn.close()
