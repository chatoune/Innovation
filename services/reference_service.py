from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional

from sqlalchemy import inspect, text
from sqlalchemy.engine import Engine
from sqlalchemy.exc import SQLAlchemyError

from app.database_manager import DatabaseManager


@dataclass
class ReferencePageResult:
    columns: list[str]
    rows: list[list[Any]]
    message: str


class ReferenceService:
    """
    Service pour le panel Références :
    - Filtre CDV_ALL sur Article commençant par GR ou GA.
    - Exclut le tiers 7421.
    """

    TABLE = "CDV_ALL"
    COL_ARTICLE = "Article"
    COL_QTY = "Qté"

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

    def get_all_relevant_lines(self, date_col: str) -> tuple[bool, list[dict[str, Any]], str]:
        """
        Récupère toutes les lignes GR/GA (excluant Tiers 7421) sans aggrégation SQL
        pour garantir la cohérence totale côté UI.
        """
        engine = self._db.engine
        if engine is None:
            return False, [], "Aucun engine configuré."

        # On prend une marge de sécurité sur les colonnes
        available_cols = self._get_table_columns(engine, self.TABLE)
        
        # Filtre de base : Article commence par GR ou GA (TRIM/UPPER)
        art_expr = f"TRIM(UPPER(CAST({self._q(self.COL_ARTICLE)} AS TEXT)))"
        
        # On ne filtre PAS encore sur le 3ème caractère pour être sûr de ne rien rater
        # On filtrera en Python pour plus de flexibilité.
        where_parts = [
            f"({art_expr} LIKE 'GR%' OR {art_expr} LIKE 'GA%')"
        ]
        
        if "Tiers" in available_cols:
            # On exclut 7421 et 7421.0
            where_parts.append(f"(Tiers IS NULL OR TRIM(CAST(Tiers AS TEXT)) NOT IN ('7421', '7421.0'))")
        
        where_sql = " WHERE " + " AND ".join(where_parts)
        
        # On récupère les colonnes nécessaires
        sql = text(f"""
            SELECT 
                Commande, 
                {self._q(self.COL_ARTICLE)} as art, 
                Tiers, 
                "Raison sociale", 
                CAST({self._q(self.COL_QTY)} AS REAL) as qty, 
                "{date_col}" as d,
                source_table
            FROM {self._q(self.TABLE)}
            {where_sql}
        """)

        try:
            with engine.connect() as conn:
                rows = conn.execute(sql).fetchall()
            
            results = []
            for r in rows:
                results.append({
                    "commande": r[0],
                    "article": str(r[1] or "").strip().upper(),
                    "tiers": r[2],
                    "rs": r[3],
                    "qty": float(r[4] or 0),
                    "raw_date": str(r[5] or ""),
                    "source": r[6]
                })
            return True, results, f"{len(results)} lignes lues"
        except Exception as e:
            return False, [], f"Erreur SQL: {e}"

    def list_references(
        self,
        limit: int = 500,
        offset: int = 0
    ) -> tuple[bool, Optional[ReferencePageResult], str]:
        # On garde cette méthode pour la table du haut (aperçu général)
        # Mais on va utiliser get_all_relevant_lines pour le graphe
        engine = self._db.engine
        if engine is None: return False, None, "Pas d'engine."
        try:
            available_cols = self._get_table_columns(engine, self.TABLE)
            art_expr = f"TRIM(UPPER(CAST({self._q(self.COL_ARTICLE)} AS TEXT)))"
            where_sql = f" WHERE ({art_expr} LIKE 'GR%' OR {art_expr} LIKE 'GA%')"
            if "Tiers" in available_cols:
                where_sql += f" AND (Tiers IS NULL OR TRIM(CAST(Tiers AS TEXT)) NOT IN ('7421', '7421.0'))"
            
            sql = text(f"SELECT * FROM {self._q(self.TABLE)} {where_sql} LIMIT :l OFFSET :o")
            with engine.connect() as conn:
                res = conn.execute(sql, {"l": limit, "o": offset})
                cols = list(res.keys())
                rows = [list(r) for r in res.fetchall()]
            return True, ReferencePageResult(columns=cols, rows=rows, message=f"{len(rows)} lignes"), "OK"
        except Exception as e:
            return False, None, str(e)

    def _table_exists(self, engine: Engine, table: str) -> bool:
        inspector = inspect(engine)
        return table in inspector.get_table_names()

    def _get_table_columns(self, engine: Engine, table: str) -> list[str]:
        inspector = inspect(engine)
        cols = inspector.get_columns(table)
        return [str(c.get("name", "")) for c in cols if c.get("name")]

    @staticmethod
    def _q(identifier: str) -> str:
        safe = identifier.replace('"', '""')
        return f'"{safe}"'
