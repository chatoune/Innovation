from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional

from sqlalchemy import inspect, text
from sqlalchemy.exc import SQLAlchemyError

from app.database_manager import DatabaseManager
from app.table_analyzer import TableAnalyzer, TableAnalysis


@dataclass
class Page:
    columns: list[str]
    rows: list[list[Any]]
    total_count: Optional[int]  # None si non calculé
    message: str


class TargetTableRepository:
    """
    Repository générique au-dessus de DatabaseManager, basé sur la table métier cible.

    Hypothèse pour CRUD simple:
    - une seule colonne PK
    """

    def __init__(self, db: DatabaseManager, analyzer: TableAnalyzer) -> None:
        self._db = db
        self._analyzer = analyzer

    def analyze_target(self, table_name: str) -> tuple[bool, TableAnalysis, str]:
        ok, raw_cols, msg = self._db.get_table_columns(table_name)
        if not ok:
            return False, self._analyzer.analyze_table(table_name, []), msg

        analysis = self._analyzer.analyze_table(table_name, raw_cols)
        return True, analysis, analysis.message

    def list_rows(self, table_name: str, limit: int = 100, offset: int = 0, with_count: bool = False) -> tuple[bool, Page, str]:
        """
        Retourne une page de lignes de la table cible.
        """
        engine = self._db.engine
        if engine is None:
            return False, Page([], [], None, "Aucun engine configuré."), "Aucun engine configuré."

        table_name = table_name.strip()
        if not table_name:
            return False, Page([], [], None, "Nom de table vide."), "Nom de table vide."

        if limit <= 0:
            limit = 100
        if offset < 0:
            offset = 0

        try:
            inspector = inspect(engine)
            tables = inspector.get_table_names()
            if table_name not in tables:
                return False, Page([], [], None, f"Table introuvable: {table_name}"), f"Table introuvable: {table_name}"

            cols = inspector.get_columns(table_name)
            col_names = [str(c.get("name", "")) for c in cols if c.get("name")]

            safe_table = table_name.replace('"', '""')
            sql = text(f'SELECT * FROM "{safe_table}" LIMIT :limit OFFSET :offset')

            with engine.connect() as conn:
                result = conn.execute(sql, {"limit": int(limit), "offset": int(offset)})
                rows = [list(r) for r in result.fetchall()]

                total = None
                if with_count:
                    count_sql = text(f'SELECT COUNT(*) FROM "{safe_table}"')
                    total = int(conn.execute(count_sql).scalar_one())

            page = Page(columns=col_names, rows=rows, total_count=total, message=f"{len(rows)} lignes")
            return True, page, page.message

        except SQLAlchemyError as e:
            msg = f"Erreur SQLAlchemy (list_rows): {e}"
            return False, Page([], [], None, msg), msg
        except Exception as e:
            msg = f"Erreur inattendue (list_rows): {e}"
            return False, Page([], [], None, msg), msg

    def get_row_by_pk(self, table_name: str, pk_column: str, pk_value: Any) -> tuple[bool, dict[str, Any], str]:
        """
        Lit une ligne par PK (CRUD simple). Retourne dict(col_name -> value).
        """
        engine = self._db.engine
        if engine is None:
            return False, {}, "Aucun engine configuré."

        table_name = table_name.strip()
        pk_column = pk_column.strip()
        if not table_name or not pk_column:
            return False, {}, "Nom de table / colonne PK vide."

        try:
            inspector = inspect(engine)
            tables = inspector.get_table_names()
            if table_name not in tables:
                return False, {}, f"Table introuvable: {table_name}"

            cols = inspector.get_columns(table_name)
            col_names = [str(c.get("name", "")) for c in cols if c.get("name")]
            if pk_column not in col_names:
                return False, {}, f"Colonne PK introuvable: {pk_column}"

            safe_table = table_name.replace('"', '""')
            safe_col = pk_column.replace('"', '""')

            sql = text(f'SELECT * FROM "{safe_table}" WHERE "{safe_col}" = :pk LIMIT 1')

            with engine.connect() as conn:
                row = conn.execute(sql, {"pk": pk_value}).fetchone()

            if row is None:
                return False, {}, "Ligne introuvable."

            # row est un Row ; on convertit en dict basé sur col_names
            values = list(row)
            data = {col_names[i]: values[i] for i in range(min(len(col_names), len(values)))}
            return True, data, "OK"

        except SQLAlchemyError as e:
            return False, {}, f"Erreur SQLAlchemy (get_row_by_pk): {e}"
        except Exception as e:
            return False, {}, f"Erreur inattendue (get_row_by_pk): {e}"