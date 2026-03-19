from __future__ import annotations

from pathlib import Path
from typing import Optional

from PySide6.QtCore import QSettings


class AppSettings:
    KEY_DB_PATH = "database/file_path"

    def __init__(self) -> None:
        self._settings = QSettings()

    def get_database_path(self) -> Optional[Path]:
        raw_value = self._settings.value(self.KEY_DB_PATH, None)
        if raw_value is None:
            return None
        return Path(str(raw_value)).expanduser()

    def set_database_path(self, db_path: str | Path) -> None:
        self._settings.setValue(self.KEY_DB_PATH, str(Path(db_path).expanduser()))
        self._settings.sync()

    def clear_database_path(self) -> None:
        self._settings.remove(self.KEY_DB_PATH)
        self._settings.sync()