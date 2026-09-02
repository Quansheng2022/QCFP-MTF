# coding: utf-8
"""Alpha Discovery Pipeline 测试（41 号）"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[4]
CORE_DIR = PROJECT_ROOT / "Core"
if str(CORE_DIR) not in sys.path:
    sys.path.insert(0, str(CORE_DIR))

from QCFP_MTF.alpha.registry import AlphaRegistry
from QCFP_MTF.research.alpha_discovery import AlphaDiscoveryPipeline


def test_discovery_pipeline():
    p = AlphaDiscoveryPipeline()
    p.propose("CAND-1024", "机构资金流↑+换手↑+Wave 形成 → 上涨",
              ["inst_flow", "turnover"], "机构建仓+量能确认")
    c = p.record_test("CAND-1024", {"ic": 0.08, "oos_sharpe": 1.2},
                      confidence=0.72, evidence_level="L3_robust_oos")
    assert c.status == "validated"
    assert c.confidence == 0.72
    reg = AlphaRegistry()
    assert p.promote_to_registry("CAND-1024", registry=reg) is True
    assert reg.get("CAND-1024") is not None
    assert p.candidates["CAND-1024"].status == "in_registry"


def test_discovery_rejects_low_confidence():
    p = AlphaDiscoveryPipeline()
    p.propose("CAND-BAD", "h", ["f1"])
    c = p.record_test("CAND-BAD", {}, confidence=0.3,
                      evidence_level="L1_correlation")
    assert c.status == "rejected"
    assert p.promote_to_registry("CAND-BAD") is False
