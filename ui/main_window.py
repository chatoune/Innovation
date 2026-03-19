from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QMainWindow,
    QFileDialog,
    QMessageBox,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QSplitter,
    QTabWidget,
)

from app.settings import AppSettings
from app.database_manager import DatabaseManager
from app.database_reporter import DatabaseReporter, ReportOptions
from app.config_db import ConfigDB

from services.cdv_service import CDVService
from ui.cdv_panel import CDVPanel

from services.phc_service import PHCService
from ui.phc_panel import PHCPanel


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()

        self._settings = AppSettings()
        self._db_manager = DatabaseManager()
        self._reporter = DatabaseReporter(self._db_manager)

        # Services
        self._cdv_service = CDVService(self._db_manager)
        self._phc_service = PHCService(self._db_manager)  # <-- pas d'arg config_db_path

        # UI
        self.setWindowTitle("Innovation - Exploitation SQLite")
        self.resize(1500, 950)

        self._tabs = QTabWidget()

        self._cdv_panel = CDVPanel(self._cdv_service)
        self._tabs.addTab(self._cdv_panel, "Panel 1 (CDV)")

        self._phc_panel = PHCPanel(self._phc_service)
        self._tabs.addTab(self._phc_panel, "Analyse CDV_PHC")

        self._explorer_tab = self._build_explorer_tab()
        self._tabs.addTab(self._explorer_tab, "Explorateur")

        self.setCentralWidget(self._tabs)
        self.statusBar().showMessage("Initialisation...")

        self._build_menu()

        # Charger DB DATA depuis settings
        self._load_database_from_settings()

        # Charger DB CONFIG (DB2) depuis settings
        self._load_config_db_from_settings()

        # Refresh
        self._refresh_explorer_tables()
        self._cdv_panel.reload_all()
        self._phc_panel.reload_all()

    # ---------- Menu ----------
    def _build_menu(self) -> None:
        menubar = self.menuBar()
        file_menu = menubar.addMenu("&Fichier")

        choose_db_action = file_menu.addAction("Choisir une base DATA (SQLite)...")
        choose_db_action.triggered.connect(self._choose_database_file)

        clear_db_action = file_menu.addAction("Effacer la base DATA")
        clear_db_action.triggered.connect(self._clear_database_file)

        file_menu.addSeparator()

        choose_cfg_action = file_menu.addAction("Choisir une base CONFIG (DB2)...")
        choose_cfg_action.triggered.connect(self._choose_config_db)

        init_cfg_action = file_menu.addAction("Initialiser la base CONFIG (DB2)")
        init_cfg_action.triggered.connect(self._init_config_db)

        clear_cfg_action = file_menu.addAction("Effacer la base CONFIG (DB2)")
        clear_cfg_action.triggered.connect(self._clear_config_db)

        file_menu.addSeparator()

        export_report_action = file_menu.addAction("Exporter rapport (sans données) ...")
        export_report_action.triggered.connect(self._export_report)

        file_menu.addSeparator()

        quit_action = file_menu.addAction("Quitter")
        quit_action.triggered.connect(self.close)

    # ---------- DATA DB ----------
    def _load_database_from_settings(self) -> None:
        db_path = self._settings.get_database_path()
        if db_path is None or not db_path.exists():
            self._db_manager.clear()
            return
        try:
            self._db_manager.configure_sqlite_file(db_path)
            self.statusBar().showMessage(f"Base DATA: {db_path}")
        except Exception:
            self._db_manager.clear()

    def _choose_database_file(self) -> None:
        current_path = self._settings.get_database_path()
        start_dir = str(current_path.parent) if current_path is not None else str(Path.home())

        selected_file, _ = QFileDialog.getOpenFileName(
            self,
            "Choisir une base de données (DATA)",
            start_dir,
            "Bases SQLite (*.db *.sqlite *.sqlite3);;Tous les fichiers (*)",
        )
        if not selected_file:
            return

        selected_path = Path(selected_file)
        if not selected_path.exists():
            QMessageBox.warning(self, "Fichier introuvable", str(selected_path))
            return

        self._settings.set_database_path(selected_path)

        try:
            self._db_manager.configure_sqlite_file(selected_path)
        except Exception as e:
            QMessageBox.critical(self, "Erreur configuration", str(e))
            return

        self.statusBar().showMessage(f"Base DATA: {selected_path}")
        self._refresh_explorer_tables()
        self._cdv_panel.reload_all()
        self._phc_panel.reload_all()

    def _clear_database_file(self) -> None:
        self._settings.clear_database_path()
        self._db_manager.clear()
        self.statusBar().showMessage("Base DATA effacée")
        self._refresh_explorer_tables()
        self._cdv_panel.reload_all()
        self._phc_panel.reload_all()

    # ---------- CONFIG DB (DB2) ----------
    def _load_config_db_from_settings(self) -> None:
        cfg = self._settings.get_config_db_path()
        if cfg is None:
            return
        try:
            # crée/init le schéma si nécessaire
            ConfigDB(cfg).init()
            # connecte le service à la DB2
            if hasattr(self._phc_service, "set_config_db_path"):
                self._phc_service.set_config_db_path(cfg)  # type: ignore[attr-defined]
            self.statusBar().showMessage(f"Base CONFIG: {cfg}")
        except Exception:
            pass

    def _choose_config_db(self) -> None:
        current = self._settings.get_config_db_path()
        start_dir = str(current.parent) if current is not None else str(Path.home())

        selected_file, _ = QFileDialog.getSaveFileName(
            self,
            "Choisir/Créer une base CONFIG (DB2)",
            str(Path(start_dir) / "phc_config.db"),
            "Bases SQLite (*.db *.sqlite *.sqlite3);;Tous les fichiers (*)",
        )
        if not selected_file:
            return

        cfg_path = Path(selected_file)
        self._settings.set_config_db_path(cfg_path)

        try:
            ConfigDB(cfg_path).init()
            if hasattr(self._phc_service, "set_config_db_path"):
                self._phc_service.set_config_db_path(cfg_path)  # type: ignore[attr-defined]
        except Exception as e:
            QMessageBox.critical(self, "CONFIG", str(e))
            return

        self.statusBar().showMessage(f"Base CONFIG: {cfg_path}")
        self._phc_panel.reload_all()

    def _init_config_db(self) -> None:
        cfg = self._settings.get_config_db_path()
        if cfg is None:
            QMessageBox.information(self, "CONFIG", "Choisis d'abord une base CONFIG (DB2).")
            return

        try:
            ConfigDB(cfg).init()
            if hasattr(self._phc_service, "set_config_db_path"):
                self._phc_service.set_config_db_path(cfg)  # type: ignore[attr-defined]
            QMessageBox.information(self, "CONFIG", f"Base CONFIG initialisée : {cfg}")
        except Exception as e:
            QMessageBox.critical(self, "CONFIG", str(e))
            return

        self._phc_panel.reload_all()

    def _clear_config_db(self) -> None:
        self._settings.clear_config_db_path()
        if hasattr(self._phc_service, "set_config_db_path"):
            self._phc_service.set_config_db_path(None)  # type: ignore[attr-defined]
        self.statusBar().showMessage("Base CONFIG effacée")
        self._phc_panel.reload_all()

    # ---------- Rapport sans données ----------
    def _export_report(self) -> None:
        ok_conn, msg_conn = self._db_manager.test_connection()
        if not ok_conn:
            QMessageBox.warning(self, "Rapport", f"Connexion DB indisponible.\n\n{msg_conn}")
            return

        filepath, _ = QFileDialog.getSaveFileName(
            self,
            "Enregistrer le rapport JSON",
            str(Path.home() / "db_report.json"),
            "JSON (*.json);;Tous les fichiers (*)",
        )
        if not filepath:
            return

        options = ReportOptions(
            include_create_sql=False,
            include_row_counts=True,
            include_table_sizes=False,
            include_column_stats=False,
        )
        ok, msg = self._reporter.save_report_json(filepath, options=options)
        if ok:
            QMessageBox.information(self, "Rapport", msg)
        else:
            QMessageBox.critical(self, "Rapport", msg)

    # ---------- Explorateur ----------
    def _build_explorer_tab(self) -> QWidget:
        self._expl_status = QLabel("Explorateur : sélectionne une table.")
        self._expl_status.setWordWrap(True)

        self._tables_list = QListWidget()
        self._tables_list.itemSelectionChanged.connect(self._on_table_selection_changed)

        self._columns_table = QTableWidget(0, 5)
        self._columns_table.setHorizontalHeaderLabels(["Nom", "Type", "Nullable", "PK", "Default"])
        self._columns_table.setEditTriggers(QTableWidget.NoEditTriggers)

        self._preview_table = QTableWidget(0, 0)
        self._preview_table.setEditTriggers(QTableWidget.NoEditTriggers)

        self._refresh_tables_btn = QPushButton("Rafraîchir")
        self._refresh_tables_btn.clicked.connect(self._refresh_explorer_tables)

        left = QWidget()
        llo = QVBoxLayout(left)
        header = QHBoxLayout()
        header.addWidget(QLabel("Tables"))
        header.addStretch()
        header.addWidget(self._refresh_tables_btn)
        llo.addLayout(header)
        llo.addWidget(self._tables_list, stretch=1)

        right = QWidget()
        rlo = QVBoxLayout(right)
        rlo.addWidget(QLabel("Colonnes"))
        rlo.addWidget(self._columns_table, stretch=1)
        rlo.addWidget(QLabel("Aperçu (LIMIT 50)"))
        rlo.addWidget(self._preview_table, stretch=1)

        split = QSplitter(Qt.Horizontal)
        split.addWidget(left)
        split.addWidget(right)
        split.setSizes([300, 1000])

        tab = QWidget()
        root = QVBoxLayout(tab)
        root.addWidget(self._expl_status)
        root.addWidget(split, stretch=1)
        return tab

    def _refresh_explorer_tables(self) -> None:
        self._tables_list.blockSignals(True)
        try:
            self._tables_list.clear()
            ok, msg = self._db_manager.test_connection()
            if not ok:
                self._expl_status.setText(f"Explorateur : {msg}")
                self._tables_list.addItem("(connexion non disponible)")
                self._clear_explorer_right()
                return

            ok2, tables, msg2 = self._db_manager.list_tables()
            if not ok2:
                self._expl_status.setText(f"Explorateur : {msg2}")
                self._tables_list.addItem("(erreur introspection)")
                self._clear_explorer_right()
                return

            self._expl_status.setText(f"Explorateur : {msg2}")
            for t in tables:
                self._tables_list.addItem(t)
        finally:
            self._tables_list.blockSignals(False)

    def _on_table_selection_changed(self) -> None:
        items = self._tables_list.selectedItems()
        if not items:
            self._clear_explorer_right()
            return

        table_name = items[0].text()
        if not table_name or table_name.startswith("("):
            self._clear_explorer_right()
            return

        ok, cols, msg = self._db_manager.get_table_columns(table_name)
        if not ok:
            self._expl_status.setText(f"Explorateur : {msg}")
            self._clear_explorer_right()
            return

        self._columns_table.setRowCount(len(cols))
        for r, c in enumerate(cols):
            self._columns_table.setItem(r, 0, QTableWidgetItem(str(c.get("name", ""))))
            self._columns_table.setItem(r, 1, QTableWidgetItem(str(c.get("type", ""))))
            self._columns_table.setItem(r, 2, QTableWidgetItem(str(c.get("nullable", ""))))
            self._columns_table.setItem(r, 3, QTableWidgetItem(str(c.get("primary_key", ""))))
            self._columns_table.setItem(r, 4, QTableWidgetItem(str(c.get("default", ""))))
        self._columns_table.resizeColumnsToContents()

        okp, col_names, rows, msgp = self._db_manager.get_table_preview(table_name, limit=50)
        if not okp:
            self._expl_status.setText(f"Explorateur : {msgp}")
            self._preview_table.setRowCount(0)
            self._preview_table.setColumnCount(0)
            return

        self._preview_table.setColumnCount(len(col_names))
        self._preview_table.setHorizontalHeaderLabels(col_names)
        self._preview_table.setRowCount(len(rows))
        for rr, row_vals in enumerate(rows):
            for cc, v in enumerate(row_vals):
                self._preview_table.setItem(rr, cc, QTableWidgetItem("" if v is None else str(v)))
        self._preview_table.resizeColumnsToContents()
        self._expl_status.setText(f"Explorateur : {table_name} | {msgp}")

    def _clear_explorer_right(self) -> None:
        self._columns_table.setRowCount(0)
        self._preview_table.setRowCount(0)
        self._preview_table.setColumnCount(0)