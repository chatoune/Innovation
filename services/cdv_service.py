from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional

from sqlalchemy import inspect, text
from sqlalchemy.engine import Engine
from sqlalchemy.exc import SQLAlchemyError

from app.database_manager import DatabaseManager


@dataclass
class CDVFilters:
    article_contains: str = ""
    date_column: str = "Date"
    years: list[str] | None = None


@dataclass
class PageResult:
    columns: list[str]
    rows: list[list[Any]]
    message: str


@dataclass
class SeriesResult:
    labels: list[str]
    values: list[float]
    message: str


class CDVService:
    """
    Service Panel 1 (CDV) - version stable:
    - filtres : Article + (date_column + years)
    - table lignes : ajoute Montant(Qté×Prix net) si dispo
    - graphe : répartition Qté (buckets)
    - export CSV (lignes)
    """

    TABLE = "CDV_ALL"

    COL_CDV = "Commande"
    COL_ARTICLE = "Article"
    COL_RS = "Raison sociale"
    COL_QTY = "Qté"
    COL_PRICE_NET = "Prix net"

    # Intitulés exacts pour la drop-down date du panel 1
    DATE_COLUMNS_FIXED = [
        "Date",
        "Date exp",
        "Livraison dem",
        "Date livraison",
        "Date facture",
    ]

    CALC_COL_ALIAS = "Montant_Qte_PrixNet"
    CALC_COL_HEADER = "Montant (Qté×Prix net)"

    def __init__(self, db: DatabaseManager) -> None:
        self._db = db

    def is_available(self) -> tuple[bool, str]:
        engine = self._db.engine
        if engine is None:
            return False, "Aucune base configurée."
        ok, msg = self._db.test_connection()
        if not ok:
            return False, msg
        if not self._table_exists(engine, self.TABLE):
            return False, f"Table introuvable : {self.TABLE}"
        return True, "OK"

    def get_fixed_date_columns(self) -> list[str]:
        return list(self.DATE_COLUMNS_FIXED)

    def list_distinct_years(self, date_column: str) -> tuple[bool, list[str], str]:
        engine = self._db.engine
        if engine is None:
            return False, [], "Aucun engine configuré."

        ok, msg = self.is_available()
        if not ok:
            return False, [], msg

        date_column = (date_column or "").strip()
        if date_column not in self.DATE_COLUMNS_FIXED:
            return False, [], f"Colonne date invalide : {date_column}"

        try:
            cols = self._get_table_columns(engine, self.TABLE)
            if date_column not in cols:
                return False, [], f"Colonne absente : {date_column}"

            year_expr = self._year_expr(date_column)
            sql = text(
                f"SELECT DISTINCT {year_expr} AS y "
                f"FROM {self._q(self.TABLE)} "
                f"WHERE y IS NOT NULL AND y != '' "
                f"ORDER BY y DESC"
            )
            with engine.connect() as conn:
                rows = conn.execute(sql).fetchall()

            years = [str(r[0]) for r in rows if r and r[0] is not None]
            years = [y for y in years if len(y) == 4 and y.isdigit()]
            return True, years, f"{len(years)} année(s)"

        except SQLAlchemyError as e:
            return False, [], f"Erreur SQLAlchemy: {e}"
        except Exception as e:
            return False, [], f"Erreur inattendue: {e}"

    def list_lines(
        self,
        filters: CDVFilters,
        limit: int = 200,
        offset: int = 0,
        order_desc: bool = True,
    ) -> tuple[bool, Optional[PageResult], str]:
        engine = self._db.engine
        if engine is None:
            return False, None, "Aucun engine configuré."
        ok, msg = self.is_available()
        if not ok:
            return False, None, msg

        try:
            available_cols = self._get_table_columns(engine, self.TABLE)

            date_col = (filters.date_column or "").strip()
            if date_col not in available_cols:
                # fallback (évite crash)
                date_col = "Date" if "Date" in available_cols else ""

            cols_to_select: list[str] = []
            for c in [self.COL_CDV, date_col, self.COL_RS, self.COL_ARTICLE, self.COL_QTY, self.COL_PRICE_NET]:
                if c and c in available_cols and c not in cols_to_select:
                    cols_to_select.append(c)

            calc_expr = None
            if self.COL_QTY in available_cols and self.COL_PRICE_NET in available_cols:
                calc_expr = (
                    f"COALESCE(CAST({self._q(self.COL_QTY)} AS REAL), 0) "
                    f"* COALESCE(CAST({self._q(self.COL_PRICE_NET)} AS REAL), 0)"
                    f' AS "{self.CALC_COL_ALIAS}"'
                )

            where_sql, params = self._build_where(filters, available_cols)

            order_parts = []
            if date_col:
                order_parts.append(f"{self._q(date_col)} {'DESC' if order_desc else 'ASC'}")
            if self.COL_CDV in available_cols:
                order_parts.append(f"{self._q(self.COL_CDV)} DESC")
            order_sql = f" ORDER BY {', '.join(order_parts)}" if order_parts else ""

            select_parts = [self._q(c) for c in cols_to_select]
            if calc_expr is not None:
                select_parts.append(calc_expr)

            sql = text(
                f"SELECT {', '.join(select_parts)} "
                f"FROM {self._q(self.TABLE)}"
                f"{where_sql}"
                f"{order_sql} "
                f"LIMIT :limit OFFSET :offset"
            )
            params["limit"] = int(max(1, limit))
            params["offset"] = int(max(0, offset))

            with engine.connect() as conn:
                rows = conn.execute(sql, params).fetchall()

            out_columns = list(cols_to_select)
            if calc_expr is not None:
                out_columns.append(self.CALC_COL_HEADER)

            out_rows = [list(r) for r in rows]
            return True, PageResult(columns=out_columns, rows=out_rows, message=f"{len(out_rows)} ligne(s)"), "OK"

        except SQLAlchemyError as e:
            return False, None, f"Erreur SQLAlchemy: {e}"
        except Exception as e:
            return False, None, f"Erreur inattendue: {e}"

    def series_qty_distribution(self, filters: CDVFilters) -> tuple[bool, Optional[SeriesResult], str]:
        engine = self._db.engine
        if engine is None:
            return False, None, "Aucun engine configuré."
        ok, msg = self.is_available()
        if not ok:
            return False, None, msg

        try:
            available_cols = self._get_table_columns(engine, self.TABLE)
            if self.COL_QTY not in available_cols:
                return False, None, "Colonne Qté introuvable."

            where_sql, params = self._build_where(filters, available_cols)
            qty_expr = f"CAST({self._q(self.COL_QTY)} AS REAL)"

            bucket_expr = (
                f"CASE "
                f"WHEN {qty_expr} <= 1 THEN '0-1' "
                f"WHEN {qty_expr} <= 5 THEN '2-5' "
                f"WHEN {qty_expr} <= 10 THEN '6-10' "
                f"WHEN {qty_expr} <= 20 THEN '11-20' "
                f"WHEN {qty_expr} <= 50 THEN '21-50' "
                f"WHEN {qty_expr} <= 100 THEN '51-100' "
                f"ELSE '100+' END"
            )

            sql = text(
                f"SELECT {bucket_expr} AS bucket, COUNT(*) AS n "
                f"FROM {self._q(self.TABLE)}"
                f"{where_sql} "
                f"GROUP BY bucket"
            )
            with engine.connect() as conn:
                rows = conn.execute(sql, params).fetchall()

            order = ["0-1", "2-5", "6-10", "11-20", "21-50", "51-100", "100+"]
            counts = {str(r[0]): float(r[1]) for r in rows}
            labels = [b for b in order if b in counts]
            values = [counts[b] for b in labels]
            return True, SeriesResult(labels=labels, values=values, message="OK"), "OK"

        except SQLAlchemyError as e:
            return False, None, f"Erreur SQLAlchemy: {e}"
        except Exception as e:
            return False, None, f"Erreur inattendue: {e}"

    def export_lines_csv(self, filepath: str | Path, filters: CDVFilters, limit: int = 50000) -> tuple[bool, str]:
        ok, page, msg = self.list_lines(filters, limit=limit, offset=0)
        if not ok or page is None:
            return False, msg

        out_path = Path(filepath)
        try:
            with out_path.open("w", newline="", encoding="utf-8") as f:
                w = csv.writer(f, delimiter=";")
                w.writerow(page.columns)
                for r in page.rows:
                    w.writerow(["" if v is None else v for v in r])
            return True, f"Export CSV OK ({len(page.rows)} lignes) : {out_path}"
        except Exception as e:
            return False, f"Impossible d'écrire le CSV: {e}"

    # ---------- Internals ----------
    def _table_exists(self, engine: Engine, table: str) -> bool:
        inspector = inspect(engine)
        return table in inspector.get_table_names()

    def _get_table_columns(self, engine: Engine, table: str) -> list[str]:
        inspector = inspect(engine)
        cols = inspector.get_columns(table)
        return [str(c.get("name", "")) for c in cols if c.get("name")]

    def _build_where(self, f: CDVFilters, available_cols: list[str]) -> tuple[str, dict[str, Any]]:
        clauses = []
        params: dict[str, Any] = {}

        # Article contains (robuste)
        v = (f.article_contains or "").strip()
        if v and self.COL_ARTICLE in available_cols:
            clauses.append(f"LOWER(TRIM(CAST({self._q(self.COL_ARTICLE)} AS TEXT) || '')) LIKE :article")
            params["article"] = f"%{v.lower()}%"

        # Years filter
        date_col = (f.date_column or "").strip()
        years = f.years or []
        years = [y.strip() for y in years if y and y.strip()]
        if date_col in available_cols and years:
            year_expr = self._year_expr(date_col)
            in_params = []
            for i, y in enumerate(years):
                key = f"y{i}"
                params[key] = y
                in_params.append(f":{key}")
            clauses.append(f"{year_expr} IN ({', '.join(in_params)})")

        if not clauses:
            return "", params
        return " WHERE " + " AND ".join(clauses), params

    @staticmethod
    def _q(identifier: str) -> str:
        safe = identifier.replace('"', '""')
        return f'"{safe}"'

    def _year_expr(self, date_col: str) -> str:
        q = self._q(date_col)
        return (
            f"CASE "
            f"WHEN substr({q}, 1, 4) GLOB '[0-9][0-9][0-9][0-9]' THEN substr({q}, 1, 4) "
            f"WHEN substr({q}, -4) GLOB '[0-9][0-9][0-9][0-9]' THEN substr({q}, -4) "
            f"ELSE NULL END"
        )