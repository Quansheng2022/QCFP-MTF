# coding: utf-8
"""Field Lineage 测试（44 号：关键字段血缘反查）"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[4]
CORE_DIR = PROJECT_ROOT / "Core"
if str(CORE_DIR) not in sys.path:
    sys.path.insert(0, str(CORE_DIR))

from QCFP_MTF.decision.field_lineage import field_lineage


def _trace(binding_constraint, final):
    return {
        "final_target": final,
        "steps": [
            {"constraint": "raw_target", "output_value": 0.60,
             "limit": 0.60, "reason": "raw"},
            {"constraint": binding_constraint, "output_value": final,
             "limit": final, "reason": "binding"},
        ],
    }


def test_permission_lineage():
    r = field_lineage("final_target", _trace("permission_cap", 0.2),
                      {"institutional_permission": "TEST"})
    assert r["binding_constraint"] == "permission_cap"
    nodes = [n["node"] for n in r["chain"]]
    assert "institutional_permission" in nodes


def test_liquidity_lineage():
    r = field_lineage("final_target", _trace("liquidity_cap", 0.2),
                      {"adv": 5e7})
    assert r["binding_constraint"] == "liquidity_cap"
    nodes = [n["node"] for n in r["chain"]]
    assert "ADV" in nodes
    assert r["chain"][-1]["source"] == "raw_target"


def test_no_binding_single_node():
    r = field_lineage("final_target", {"final_target": 0.2, "steps": []})
    assert r["binding_constraint"] is None
    assert len(r["chain"]) == 1
    assert r["chain"][0]["node"] == "final_target"
