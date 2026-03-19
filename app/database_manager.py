from __future__ import annotations

from pathlib import Path
from typing import Optional, Any

from sqlalchemy import create_engine, text, inspect
from sqlalchemy.engine import Engine
from sqlalchemy.exc import SQLAlchemyError, NoSuchTableError
from sqlalchemy.orm import sessionmaker


class DatabaseManager:
    """
    Gère la construction/reconstruction dynamique de l'engine SQLAlchemy
    à partir d'un fichier SQLite choisi par l'utilisateur.
    """

    def __init__(self) -> None:
        self._db_path: Optional[Path] = None
        self._engine: Optional[Engine] = None
        self._session_factory: Optional[sessionmaker] = None

    @property
    def db_path(self) -> Optional[Path]:
        return self._db_path

    @property
    def engine(self) -> Optional[Engine]:
        return self._engine

    @property
    def session_factory(self) -> Optional[sessionmaker]:
        return self._session_factory

    def configure_sqlite_file(self, db_path: str | Path) -> None:
        """
        Configure (ou reconfigure) l'engine SQLAlchemy sur un fichier SQLite.
        """
        path_obj = Path(db_path).expanduser().resolve()
        url = f"sqlite:///{path_obj}"

        engine = create_engine(
            url,
            echo=False,   # True pour voir le SQL généré (utile au début)
            future=True,  # style SQLAlchemy 2.x
        )

        session_factory = sessionmaker(
            bind=engine,
            autoflush=False,
            autocommit=False,
            future=True,
        )

        self._db_path = path_obj
        self._engine = engine
        self._session_factory = session_factory

    def clear(self) -> None:
        """
        Réinitialise le manager (plus de base configurée).
        """
        self._db_path = None
        self._engine = None
        self._session_factory = None

    def test_connection(self) -> tuple[bool, str]:
        """
        Teste la connexion DB et retourne (ok, message).
        """
        if self._engine is None:
            return False, "Aucun engine configuré."

        try:
            with self._engine.connect() as conn:
                conn.execute(text("SELECT 1"))
            return True, "Connexion SQLite OK"
        except SQLAlchemyError as e:
            return False, f"Erreur SQLAlchemy: {e}"
        except Exception as e:
            return False, f"Erreur inattendue: {e}"

    def list_tables(self) -> tuple[bool, list[str], str]:
        """
        Retourne (ok, table_names, message)
        """
        if self._engine is None:
            return False, [], "Aucun engine configuré."

        try:
            inspector = inspect(self._engine)
            table_names = inspector.get_table_names()
            table_names = sorted(table_names, key=str.lower)
            return True, table_names, f"{len(table_names)} table(s) trouvée(s)"
        except SQLAlchemyError as e:
            return False, [], f"Erreur SQLAlchemy (introspection): {e}"
        except Exception as e:
            return False, [], f"Erreur inattendue (introspection): {e}"

    def get_table_columns(self, table_name: str) -> tuple[bool, list[dict[str, Any]], str]:
        """
        Retourne (ok, columns, message)

        columns = liste de dicts simplifiés pour l'UI :
          {
            "name": str,
            "type": str,
            "nullable": bool | None,
            "primary_key": bool | int | None,
            "default": Any
          }
        """
        if self._engine is None:
            return False, [], "Aucun engine configuré."

        table_name = table_name.strip()
        if not table_name:
            return False, [], "Nom de table vide."

        try:
            inspector = inspect(self._engine)
            raw_columns = inspector.get_columns(table_name)

            columns: list[dict[str, Any]] = []
            for col in raw_columns:
                columns.append(
                    {
                        "name": str(col.get("name", "")),
                        "type": str(col.get("type", "")),
                        "nullable": col.get("nullable", None),
                        "primary_key": col.get("primary_key", None),
                        "default": col.get("default", None),
                    }
                )

            return True, columns, f"{len(columns)} colonne(s) dans '{table_name}'"

        except NoSuchTableError:
            return False, [], f"Table introuvable : {table_name}"
        except SQLAlchemyError as e:
            return False, [], f"Erreur SQLAlchemy (colonnes): {e}"
        except Exception as e:
            return False, [], f"Erreur inattendue (colonnes): {e}"

    def get_table_preview(
        self, table_name: str, limit: int = 100
    ) -> tuple[bool, list[str], list[list[object]], str]:
        """
        Retourne (ok, column_names, rows, message)

        - column_names : list[str]
        - rows : list[list[object]] (valeurs brutes, l'UI les convertira en str)
        """
        if self._engine is None:
            return False, [], [], "Aucun engine configuré."

        table_name = table_name.strip()
        if not table_name:
            return False, [], [], "Nom de table vide."

        if limit <= 0:
            limit = 100

        try:
            inspector = inspect(self._engine)
            tables = inspector.get_table_names()
            if table_name not in tables:
                return False, [], [], f"Table introuvable : {table_name}"

            cols = inspector.get_columns(table_name)
            col_names = [str(c.get("name", "")) for c in cols if c.get("name")]

            # Quotation SQLite: "table"
            safe_table = table_name.replace('"', '""')
            sql = text(f'SELECT * FROM "{safe_table}" LIMIT :limit')

            with self._engine.connect() as conn:
                result = conn.execute(sql, {"limit": int(limit)})
                fetched = result.fetchall()

            rows = [list(r) for r in fetched]
            return True, col_names, rows, f"{len(rows)} ligne(s) (LIMIT {limit})"

        except SQLAlchemyError as e:
            return False, [], [], f"Erreur SQLAlchemy (preview): {e}"
        except Exception as e:
            return False, [], [], f"Erreur inattendue (preview): {e}"