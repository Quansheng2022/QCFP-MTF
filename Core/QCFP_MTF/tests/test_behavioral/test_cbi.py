# coding: utf-8
"""CBI 测试"""

import sys
from pathlib import Path

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[4]
CORE_DIR = PROJECT_ROOT / "Core"
if str(CORE_DIR) not in sys.path:
    sys.path.insert(0, str(CORE_DIR))

from QCFP_MTF.config.settings import DEFAULT_SETTINGS
from QCFP_MTF.behavioral.cbi import build_cbi


def _m_df(n=20):
    rng = pd.date_range("2024-01-31", periods=n, freq="ME")
    return pd.DataFrame({
        "stock_code": ["00700"] * n,
        "date": rng,
        "turnover_rate": [2.0 + (0.02 if i % 2 else -0.02) for i in range(n)],  # 近常数 → 高稳定
        "volume": [1_000_000.0 + i * 1000 for i in range(n)],
        "amplitude": [5.0] * n,
    })


def test_cbi_range_and_state():
    df = build_cbi(_m_df(), DEFAULT_SETTINGS)
    last = df.iloc[-1]
    assert 0.0 <= last["cbi_score"] <= 100.0
    assert last["cbi_state"] in {"CBI_LOCKED_CANDIDATE", "CBI_STABLE",
                                 "CBI_ACTIVE", "CBI_TURBULENT"}


def test_turbulent_low_cbi():
    n = 20
    rng = pd.date_range("2024-01-31", periods=n, freq="ME")
    rows = []
    for st, turb in [("A", True), ("B", False), ("C", False)]:
        for i, m in enumerate(rng):
            if turb:
                t = 1.0 + (i % 3) * 4.0          # 剧烈波动 → 低稳定
                v = 1_000_000.0 + (i % 2) * 1_000_000
                a = 5.0 + (i % 4) * 5.0
            else:
                t = 2.0 + (i % 2) * 0.1          # 平稳
                v = 1_000_000.0
                a = 5.0
            rows.append({"stock_code": st, "date": m,
                         "turnover_rate": t, "volume": v, "amplitude": a})
    out = build_cbi(pd.DataFrame(rows), DEFAULT_SETTINGS)
    last_a = out[out["stock_code"] == "A"].iloc[-1]["cbi_score"]
    last_b = out[out["stock_code"] == "B"].iloc[-1]["cbi_score"]
    assert last_a < last_b       # 横截面：剧烈波动股 CBI 显著低于平稳股
    assert last_a < 50.0


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print(f"PASS {name}")
    print("test_cbi 全部通过 ✅")
