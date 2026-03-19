from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Optional


SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS phe_patterns (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    family TEXT NOT NULL,
    regex TEXT NOT NULL,
    description TEXT DEFAULT '',
    priority INTEGER DEFAULT 0,
    group_map_json TEXT DEFAULT ''
);
CREATE INDEX IF NOT EXISTS idx_phe_patterns_family ON phe_patterns(family);
"""


class ConfigDB:
    def __init__(self, db_path: str | Path) -> None:
        self._path = Path(db_path)

    @property
    def path(self) -> Path:
        return self._path

    def init(self) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(self._path) as conn:
            conn.executescript(SCHEMA_SQL)
            conn.commit()