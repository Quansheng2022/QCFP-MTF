# coding: utf-8
"""Decision Schema Registry 测试（41 号）"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[4]
CORE_DIR = PROJECT_ROOT / "Core"
if str(CORE_DIR) not in sys.path:
    sys.path.insert(0, str(CORE_DIR))

from QCFP_MTF.decision.schema_registry import (DEFAULT_SCHEMA_REGISTRY,
                                               SchemaEntry, SchemaRegistry)


def test_default_registry_readable():
    DEFAULT_SCHEMA_REGISTRY.assert_readable("DECISION-1.1")
    DEFAULT_SCHEMA_REGISTRY.assert_readable("DECISION-1.0")
    try:
        DEFAULT_SCHEMA_REGISTRY.assert_readable("DECISION-9.9")
        raise AssertionError("should raise")
    except ValueError:
        pass


def test_migrate_old_schema():
    old = {"decision_id": "d1", "stock_code": "01951",
           "decision_date": "2024-01-01", "target": 0.03}
    migrated = DEFAULT_SCHEMA_REGISTRY.migrate(old, "DECISION-1.0",
                                               "DECISION-1.1")
    assert migrated["target_position"] == 0.03
    assert "target" not in migrated


def test_compatibility():
    assert DEFAULT_SCHEMA_REGISTRY.compatibility_to(
        "DECISION-1.0", "DECISION-1.1") == "MIGRATE_REQUIRED"
    assert DEFAULT_SCHEMA_REGISTRY.compatibility_to(
        "DECISION-1.1", "DECISION-1.1") == "IDENTICAL"


def test_custom_registry():
    reg = SchemaRegistry()
    reg.register(SchemaEntry("S2", "INCOMPATIBLE"))
    try:
        reg.assert_readable("S2")
        raise AssertionError("should raise")
    except ValueError:
        pass
