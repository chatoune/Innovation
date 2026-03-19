from __future__ import annotations

import sqlite3
from pathlib import Path


SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS phc_family_rules (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    family TEXT NOT NULL,
    subfamily TEXT NOT NULL DEFAULT '',
    enabled INTEGER NOT NULL DEFAULT 1,
    priority INTEGER NOT NULL DEFAULT 0,
    startswith_any TEXT NOT NULL DEFAULT '',
    contains_any TEXT NOT NULL DEFAULT '',
    not_startswith_any TEXT NOT NULL DEFAULT '',
    not_contains_any TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_phc_family_rules_family_subfamily
    ON phc_family_rules(family, subfamily);
"""


class ConfigDB:
    """
    Initialise la table de configuration PHC dans la base SQLite métier existante.
    Il n'y a pas de seconde base : la configuration est stockée dans la même base.
    """

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