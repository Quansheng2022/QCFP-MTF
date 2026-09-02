# coding: utf-8
"""SQLite 数据库访问工具"""

import sqlite3
from pathlib import Path
from typing import Iterable, List

from .paths import get_db_path


def connect(db_path=None, timeout: float = 30.0) -> sqlite3.Connection:
    """打开 SQLite 连接（默认项目数据库）"""
    path = Path(db_path) if db_path else get_db_path()
    conn = sqlite3.connect(str(path), timeout=timeout)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def table_exists(conn: sqlite3.Connection, table_name: str) -> bool:
    cur = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
        (table_name,),
    )
    return cur.fetchone() is not None


def list_tables(conn: sqlite3.Connection, prefix: str = None) -> List[str]:
    sql = "SELECT name FROM sqlite_master WHERE type='table'"
    params = ()
    if prefix:
        sql += " AND name LIKE ?"
        params = (f"{prefix}%",)
    sql += " ORDER BY name"
    return [r[0] for r in conn.execute(sql, params).fetchall()]


def execute_sql_file(conn: sqlite3.Connection, sql_path) -> int:
    """执行 SQL 文件（按分号切分语句），返回执行语句数

    注意：先剥离整行注释再切分，避免文件头注释吞掉第一条语句。
    """
    sql_path = Path(sql_path)
    text = sql_path.read_text(encoding="utf-8")
    kept_lines = []
    for line in text.splitlines():
        stripped = line.lstrip()
        if stripped.startswith("--") or stripped.startswith("#"):
            continue
        kept_lines.append(line)
    cleaned = "\n".join(kept_lines)
    statements = [s.strip() for s in cleaned.split(";") if s.strip()]
    count = 0
    for stmt in statements:
        conn.execute(stmt)
        count += 1
    conn.commit()
    return count


def delete_rows(conn: sqlite3.Connection, table: str, where: str = None, params: Iterable = ()) -> int:
    """删除指定行，返回影响行数（供审计/快照类表使用）"""
    sql = f"DELETE FROM {table}"
    if where:
        sql += f" WHERE {where}"
    cur = conn.execute(sql, tuple(params))
    conn.commit()
    return cur.rowcount
