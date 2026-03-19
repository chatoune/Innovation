from __future__ import annotations

import json
from dataclasses import dataclass, asdict
from datetime import datetime
from typing import Any, Optional

from sqlalchemy import inspect, text
from sqlalchemy.engine import Engine
from sqlalchemy.exc import SQLAlchemyError

from app.database_manager import DatabaseManager


@dataclass
class ReportOptions:
    include_create_sql: bool = False   # DDL CREATE TABLE/INDEX (peut contenir des noms)
    include_row_counts: bool = True    # COUNT(*) par table (sans contenu)
    include_table_sizes: bool = False  # taille DB + pages (approx, SQLite pragmas)
    # EXTENDED (toujours sans valeurs brutes, mais agrégats)
    include_column_stats: bool = False  # ex: null_count, distinct_count approx -> peut être sensible


class DatabaseReporter:
    def __init__(self, db: DatabaseManager) -> None:
        self._db = db

    def build_report(self, options: Optional[ReportOptions] = None) -> dict[str, Any]:
        options = options or ReportOptions()
        engine = self._db.engine
        if engine is None:
            return {
                "ok": False,
                "error": "Aucun engine configuré.",
                "generated_at": datetime.now().isoformat(timespec="seconds"),
            }

        try:
            inspector = inspect(engine)

            report: dict[str, Any] = {
                "ok": True,
                "generated_at": datetime.now().isoformat(timespec="seconds"),
                "database": self._get_sqlite_pragmas(engine, options),
                "schema": {
                    "tables": [],
                    "views": [],
                },
            }

            # Tables + vues
            table_names = sorted(inspector.get_table_names(), key=str.lower)
            view_names = sorted(inspector.get_view_names(), key=str.lower)

            report["schema"]["views"] = view_names

            for tname in table_names:
                report["schema"]["tables"].append(
                    self._describe_table(engine, inspector, tname, options)
                )

            return report

        except SQLAlchemyError as e:
            return {
                "ok": False,
                "error": f"Erreur SQLAlchemy: {e}",
                "generated_at": datetime.now().isoformat(timespec="seconds"),
            }
        except Exception as e:
            return {
                "ok": False,
                "error": f"Erreur inattendue: {e}",
                "generated_at": datetime.now().isoformat(timespec="seconds"),
            }

    def save_report_json(self, filepath: str, options: Optional[ReportOptions] = None) -> tuple[bool, str]:
        report = self.build_report(options)
        try:
            with open(filepath, "w", encoding="utf-8") as f:
                json.dump(report, f, indent=2, ensure_ascii=False)
            return True, f"Rapport écrit: {filepath}"
        except Exception as e:
            return False, f"Impossible d'écrire le fichier: {e}"

    # -------------------- Internals --------------------

    def _get_sqlite_pragmas(self, engine: Engine, options: ReportOptions) -> dict[str, Any]:
        # Informations SQLite utiles (sans contenu)
        info: dict[str, Any] = {}
        with engine.connect() as conn:
            # Version SQLite (renvoyée par SQLite)
            info["sqlite_version"] = conn.execute(text("select sqlite_version()")).scalar_one()

            # PRAGMAs courants
            for pragma in [
                "encoding",
                "foreign_keys",
                "journal_mode",
                "synchronous",
                "temp_store",
                "cache_size",
                "page_size",
                "auto_vacuum",
                "application_id",
                "user_version",
            ]:
                try:
                    value = conn.execute(text(f"PRAGMA {pragma}")).fetchone()
                    # PRAGMA renvoie parfois une ligne à 1 colonne
                    info[pragma] = value[0] if value is not None else None
                except Exception:
                    info[pragma] = None

            if options.include_table_sizes:
                # Approx taille : page_count * page_size
                try:
                    page_count = conn.execute(text("PRAGMA page_count")).scalar_one()
                    page_size = conn.execute(text("PRAGMA page_size")).scalar_one()
                    info["page_count"] = int(page_count)
                    info["approx_file_size_bytes"] = int(page_count) * int(page_size)
                except Exception:
                    pass

        return info

    def _describe_table(self, engine: Engine, inspector, table_name: str, options: ReportOptions) -> dict[str, Any]:
        table: dict[str, Any] = {"name": table_name}

        # Colonnes
        cols = inspector.get_columns(table_name)
        table["columns"] = [
            {
                "name": c.get("name"),
                "type": str(c.get("type")),
                "nullable": c.get("nullable"),
                "default": c.get("default"),
                "primary_key": c.get("primary_key"),
            }
            for c in cols
        ]

        # PK (meilleure lecture)
        pk_cols = []
        for c in cols:
            pk = c.get("primary_key")
            if pk is True:
                pk_cols.append(c.get("name"))
            elif isinstance(pk, int) and pk > 0:
                pk_cols.append(c.get("name"))
        table["primary_key_columns"] = pk_cols

        # Foreign keys
        try:
            fks = inspector.get_foreign_keys(table_name)
        except Exception:
            fks = []
        table["foreign_keys"] = [
            {
                "name": fk.get("name"),
                "constrained_columns": fk.get("constrained_columns"),
                "referred_table": fk.get("referred_table"),
                "referred_columns": fk.get("referred_columns"),
                "options": fk.get("options"),  # onupdate/ondelete/deferrable…
            }
            for fk in fks
        ]

        # Indexes
        try:
            idx = inspector.get_indexes(table_name)
        except Exception:
            idx = []
        table["indexes"] = [
            {
                "name": i.get("name"),
                "unique": i.get("unique"),
                "column_names": i.get("column_names"),
                "dialect_options": i.get("dialect_options"),
            }
            for i in idx
        ]

        # Row counts (sans contenu)
        if options.include_row_counts:
            safe_table = table_name.replace('"', '""')
            try:
                with engine.connect() as conn:
                    count = conn.execute(text(f'SELECT COUNT(*) FROM "{safe_table}"')).scalar_one()
                table["row_count"] = int(count)
            except Exception as e:
                table["row_count"] = None
                table["row_count_error"] = str(e)

        # CREATE SQL (DDL) optionnel
        if options.include_create_sql:
            try:
                with engine.connect() as conn:
                    create_sql = conn.execute(
                        text("SELECT sql FROM sqlite_master WHERE type='table' AND name=:name"),
                        {"name": table_name},
                    ).scalar_one_or_none()
                table["create_sql"] = create_sql
            except Exception:
                table["create_sql"] = None

            # Index DDL (optionnel)
            try:
                with engine.connect() as conn:
                    rows = conn.execute(
                        text("SELECT name, sql FROM sqlite_master WHERE type='index' AND tbl_name=:name"),
                        {"name": table_name},
                    ).fetchall()
                table["indexes_sql"] = [{"name": r[0], "sql": r[1]} for r in rows]
            except Exception:
                table["indexes_sql"] = None

        # EXTENDED: stats par colonne (toujours sans valeurs brutes)
        if options.include_column_stats:
            table["column_stats"] = self._compute_column_stats(engine, table_name, cols)

        return table

    def _compute_column_stats(self, engine: Engine, table_name: str, cols: list[dict[str, Any]]) -> dict[str, Any]:
        """
        Stats sans valeurs: null_count, non_null_count, distinct_count.
        Attention: distinct_count peut être sensible selon ton contexte.
        """
        stats: dict[str, Any] = {}
        safe_table = table_name.replace('"', '""')

        with engine.connect() as conn:
            for c in cols:
                col_name = str(c.get("name", ""))
                if not col_name:
                    continue
                safe_col = col_name.replace('"', '""')

                try:
                    total = conn.execute(text(f'SELECT COUNT(*) FROM "{safe_table}"')).scalar_one()
                    non_null = conn.execute(text(f'SELECT COUNT("{safe_col}") FROM "{safe_table}"')).scalar_one()
                    null_count = int(total) - int(non_null)
                    # DISTINCT (peut être coûteux)
                    distinct = conn.execute(text(f'SELECT COUNT(DISTINCT "{safe_col}") FROM "{safe_table}"')).scalar_one()

                    stats[col_name] = {
                        "total_rows": int(total),
                        "non_null_count": int(non_null),
                        "null_count": int(null_count),
                        "distinct_count": int(distinct),
                    }
                except Exception as e:
                    stats[col_name] = {"error": str(e)}

        return stats