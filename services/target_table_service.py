from __future__ import annotations

from typing import Any, Optional

from app.settings import AppSettings
from app.table_analyzer import TableAnalyzer, TableAnalysis
from app.database_manager import DatabaseManager
from repositories.target_table_repository import TargetTableRepository, Page


class TargetTableService:
    def __init__(self, settings: AppSettings, db: DatabaseManager) -> None:
        self._settings = settings
        self._db = db
        self._analyzer = TableAnalyzer()
        self._repo = TargetTableRepository(db, self._analyzer)

    def get_target_table(self) -> Optional[str]:
        return self._settings.get_target_table()

    def analyze_target(self) -> tuple[bool, Optional[TableAnalysis], str]:
        table = self.get_target_table()
        if table is None:
            return False, None, "Aucune table métier définie."

        ok, analysis, msg = self._repo.analyze_target(table)
        return ok, analysis, msg

    def list_target_rows(self, limit: int = 100, offset: int = 0) -> tuple[bool, Optional[Page], str]:
        table = self.get_target_table()
        if table is None:
            return False, None, "Aucune table métier définie."

        ok, analysis, _msg = self._repo.analyze_target(table)
        if not ok:
            return False, None, "Impossible d'analyser la table cible."

        if not analysis.is_crud_compatible:
            # On autorise tout de même la lecture, mais on prévient
            ok2, page, msg2 = self._repo.list_rows(table, limit=limit, offset=offset, with_count=False)
            if ok2:
                return True, page, f"Lecture seule (CRUD simple non compatible). {msg2}"
            return False, None, msg2

        ok2, page, msg2 = self._repo.list_rows(table, limit=limit, offset=offset, with_count=False)
        if ok2:
            return True, page, msg2
        return False, None, msg2