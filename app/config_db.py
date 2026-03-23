from __future__ import annotations

import re
import sqlite3
from pathlib import Path


CREATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS phc_family_rules (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    family TEXT NOT NULL,
    subfamily TEXT NOT NULL DEFAULT '',
    enabled INTEGER NOT NULL DEFAULT 1,
    priority INTEGER NOT NULL DEFAULT 0,
    regex_pattern TEXT NOT NULL DEFAULT '',
    contains_any TEXT NOT NULL DEFAULT '',
    not_contains_any TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_phc_family_rules_family_subfamily
    ON phc_family_rules(family, subfamily);
"""


class ConfigDB:
    """
    Initialise et migre la table de règles PHC dans la base SQLite métier.

    Évolution principale :
    - remplacement de "startswith_any" par "regex_pattern"
    - conservation d'une migration automatique depuis l'ancien schéma
    """

    def __init__(self, db_path: str | Path) -> None:
        self._path = Path(db_path)

    @property
    def path(self) -> Path:
        return self._path

    def init(self) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(self._path) as conn:
            conn.executescript(CREATE_TABLE_SQL)
            self._migrate_phc_family_rules(conn)
            conn.commit()

    def _migrate_phc_family_rules(self, conn: sqlite3.Connection) -> None:
        columns = self._get_columns(conn, "phc_family_rules")
        if not columns:
            return

        wanted = {
            "subfamily": "TEXT NOT NULL DEFAULT ''",
            "enabled": "INTEGER NOT NULL DEFAULT 1",
            "priority": "INTEGER NOT NULL DEFAULT 0",
            "regex_pattern": "TEXT NOT NULL DEFAULT ''",
            "contains_any": "TEXT NOT NULL DEFAULT ''",
            "not_contains_any": "TEXT NOT NULL DEFAULT ''",
            "created_at": "TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP",
            "updated_at": "TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP",
        }

        for name, ddl in wanted.items():
            if name not in columns:
                conn.execute(f'ALTER TABLE "phc_family_rules" ADD COLUMN "{name}" {ddl}')

        columns = self._get_columns(conn, "phc_family_rules")
        if "startswith_any" in columns and "regex_pattern" in columns:
            rows = conn.execute(
                'SELECT id, COALESCE(startswith_any, ""), COALESCE(regex_pattern, "") '
                'FROM "phc_family_rules"'
            ).fetchall()
            for rule_id, startswith_any, regex_pattern in rows:
                if str(regex_pattern or "").strip():
                    continue
                converted = self._prefixes_csv_to_regex(str(startswith_any or ""))
                if converted:
                    conn.execute(
                        'UPDATE "phc_family_rules" '
                        'SET regex_pattern = ?, updated_at = CURRENT_TIMESTAMP '
                        'WHERE id = ?',
                        (converted, int(rule_id)),
                    )

    @staticmethod
    def _get_columns(conn: sqlite3.Connection, table_name: str) -> set[str]:
        rows = conn.execute(f'PRAGMA table_info("{table_name}")').fetchall()
        return {str(row[1]) for row in rows if len(row) > 1}

    @staticmethod
    def _prefixes_csv_to_regex(value: str) -> str:
        prefixes = [item.strip() for item in value.split(",") if item.strip()]
        if not prefixes:
            return ""
        escaped = [re.escape(prefix) for prefix in prefixes]
        if len(escaped) == 1:
            return f"^{escaped[0]}"
        return "^(?:" + "|".join(escaped) + ")"