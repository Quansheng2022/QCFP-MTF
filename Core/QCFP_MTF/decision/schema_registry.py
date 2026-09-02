# coding: utf-8
"""Decision Schema Registry（QCFP-MTF 2.8：41 号 Schema 版本治理）

历史 Decision 永远不能因为代码升级而失去审计能力：
    Schema Registry
    ├── schema_id
    ├── schema_version
    ├── compatibility（BACKWARD_COMPATIBLE / MIGRATE_REQUIRED / INCOMPATIBLE）
    ├── migration_rule（字段重命名/填充规则）
    └── effective_date

读取旧 Schema 决策时按兼容关系自动迁移后再 Replay/Audit。
"""

from dataclasses import asdict, dataclass, field


@dataclass(frozen=True)
class SchemaEntry:
    schema_version: str
    compatibility: str = "BACKWARD_COMPATIBLE"
    migration_rule: str = ""      # 迁移规则（如 "final_target←target_position"）
    effective_date: str = ""
    fields: tuple = field(default_factory=tuple)

    def as_dict(self) -> dict:
        d = asdict(self)
        d["fields"] = list(self.fields)
        return d


class SchemaRegistry:
    def __init__(self, entries=None):
        self.entries = {e.schema_version: e for e in (entries or [])}

    def register(self, entry: SchemaEntry) -> None:
        self.entries[entry.schema_version] = entry

    def compatibility_to(self, old_version, new_version) -> str:
        """旧 → 新 的兼容关系。"""
        if old_version == new_version:
            return "IDENTICAL"
        old = self.entries.get(old_version)
        if old is None:
            return "UNKNOWN"
        return old.compatibility

    def migrate(self, record: dict, from_version, to_version) -> dict:
        """按迁移规则把旧 Schema 记录读到新版本（可 Replay/Audit）。"""
        out = dict(record)
        entry = self.entries.get(from_version)
        if entry is None:
            return out
        rule = entry.migration_rule
        if rule and "←" in rule:
            new_field, _, old_field = rule.partition("←")
            new_field, old_field = new_field.strip(), old_field.strip()
            if old_field in out and new_field not in out:
                out[new_field] = out.pop(old_field)
        return out

    def assert_readable(self, version) -> None:
        """未知/不兼容 Schema → 抛错（历史决策不得失去审计能力）。"""
        entry = self.entries.get(version)
        if entry is None:
            raise ValueError(
                f"SchemaRegistry: 未知 schema_version={version}，"
                f"历史决策无法读取")
        if entry.compatibility == "INCOMPATIBLE":
            raise ValueError(
                f"SchemaRegistry: {version} 与当前系统不兼容")


DEFAULT_SCHEMA_REGISTRY = SchemaRegistry([
    SchemaEntry("DECISION-1.1", "BACKWARD_COMPATIBLE",
                migration_rule="",
                effective_date="2026-08-21",
                fields=("decision_id", "stock_code", "decision_date",
                        "target_position", "raw_target_position")),
    SchemaEntry("DECISION-1.0", "MIGRATE_REQUIRED",
                migration_rule="target_position←target",
                effective_date="2026-01-01",
                fields=("decision_id", "stock_code", "decision_date",
                        "target")),
])
