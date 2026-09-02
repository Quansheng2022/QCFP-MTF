# coding: utf-8
"""Operational Observability 测试（49 号）"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[4]
CORE_DIR = PROJECT_ROOT / "Core"
if str(CORE_DIR) not in sys.path:
    sys.path.insert(0, str(CORE_DIR))

from QCFP_MTF.monitoring.observability import observability_report, \
    observability_to_md


def _metrics(**kw):
    m = {"latency_ms": {"data": 100, "feature": 200, "decision": 300,
                        "ledger": 50, "replay": 400, "execution": 200},
         "error_rate": 0.001, "missing_rate": 0.01, "queue_backlog": 2,
         "ledger_write_ok": True, "research_validated": True}
    m.update(kw)
    return m


def test_observability_healthy():
    r = observability_report(_metrics())
    assert r.overall == "HEALTHY"
    assert r.halt is False


def test_ledger_failure_halts():
    r = observability_report(_metrics(ledger_write_ok=False))
    assert r.overall == "DEGRADED"
    assert r.halt is True
    assert r.dimensions["decision"] == "DEGRADED"
    assert any("LEDGER_WRITE_FAILURE" in x for x in r.reasons)


def test_latency_degraded():
    r = observability_report(_metrics(
        latency_ms={"data": 60000, "feature": 100, "decision": 300,
                    "ledger": 50, "replay": 400, "execution": 200}))
    assert r.dimensions["data"] == "DEGRADED"


def test_observability_to_md():
    md = observability_to_md(observability_report(_metrics()))
    assert "Operational Observability" in md
