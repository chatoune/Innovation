from __future__ import annotations

from pathlib import Path
from typing import Optional

from PySide6.QtWidgets import (
    QMainWindow,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QPushButton,
    QLabel,
    QListWidget,
    QTableWidget,
    QTableWidgetItem,
    QFileDialog,
    QMessageBox,
    QTabWidget,
)

from app.config_db import ConfigDB
from app.database_manager import DatabaseManager
from app.database_reporter import DatabaseReporter, ReportOptions
from app.settings import AppSettings
from services.cdv_service import CDVService
from services.phc_service import PHCService
from ui.cdv_panel import CDVPanel
from ui.phc_panel import PHCPanel


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()

        self._settings = AppSettings()
        self._db_manager = DatabaseManager()
        self._reporter = DatabaseReporter(self._db_manager)

        # Services
        self._cdv_service = CDVService(self._db_manager)
        self._phc_service = PHCService(self._db_manager)

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

        init_cfg_action = file_menu.addAction("Initialiser la table de configuration PHC")
        init_cfg_action.triggered.connect(self._init_config_in_data_db)

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
            ConfigDB(db_path).init()
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
            ConfigDB(selected_path).init()
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

    def _init_config_in_data_db(self) -> None:
        db_path = self._db_manager.db_path
        if db_path is None:
            QMessageBox.information(self, "Configuration PHC", "Choisis d'abord une base DATA.")
            return

        try:
            ConfigDB(db_path).init()
            QMessageBox.information(
                self,
                "Configuration PHC",
                f"Table de configuration PHC initialisée dans la base DATA : {db_path}",
            )
        except Exception as e:
            QMessageBox.critical(self, "Configuration PHC", str(e))
            return

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

        self._refresh_tables_btn = QPushButton("Rafraîchir la liste")
        self._refresh_tables_btn.clicked.connect(self._refresh_explorer_tables)

        self._columns_table = QTableWidget(0, 5)
        self._columns_table.setHorizontalHeaderLabels(["Nom", "Type", "Nullable", "PK", "Default"])

        self._preview_table = QTableWidget(0, 0)

        left = QVBoxLayout()
        left.addWidget(self._refresh_tables_btn)
        left.addWidget(self._tables_list)

        right = QVBoxLayout()
        right.addWidget(self._expl_status)
        right.addWidget(QLabel("Colonnes"))
        right.addWidget(self._columns_table)
        right.addWidget(QLabel("Aperçu"))
        right.addWidget(self._preview_table)

        root = QWidget()
        layout = QHBoxLayout(root)
        layout.addLayout(left, 1)
        layout.addLayout(right, 3)
        return root

    def _refresh_explorer_tables(self) -> None:
        self._tables_list.clear()
        self._columns_table.setRowCount(0)
        self._preview_table.setRowCount(0)
        self._preview_table.setColumnCount(0)

        ok, tables, msg = self._db_manager.list_tables()
        self._expl_status.setText(msg)
        if not ok:
            return

        for table_name in tables:
            self._tables_list.addItem(table_name)

    def _on_table_selection_changed(self) -> None:
        items = self._tables_list.selectedItems()
        if not items:
            self._expl_status.setText("Aucune table sélectionnée.")
            self._columns_table.setRowCount(0)
            self._preview_table.setRowCount(0)
            self._preview_table.setColumnCount(0)
            return

        table_name = items[0].text()

        ok_cols, cols, msg_cols = self._db_manager.get_table_columns(table_name)
        self._expl_status.setText(msg_cols)
        self._columns_table.setRowCount(0)
        if ok_cols:
            self._columns_table.setRowCount(len(cols))
            for r, col in enumerate(cols):
                self._columns_table.setItem(r, 0, QTableWidgetItem(str(col.get("name", ""))))
                self._columns_table.setItem(r, 1, QTableWidgetItem(str(col.get("type", ""))))
                self._columns_table.setItem(r, 2, QTableWidgetItem(str(col.get("nullable", ""))))
                self._columns_table.setItem(r, 3, QTableWidgetItem(str(col.get("primary_key", ""))))
                self._columns_table.setItem(r, 4, QTableWidgetItem(str(col.get("default", ""))))
            self._columns_table.resizeColumnsToContents()

        ok_prev, col_names, rows, msg_prev = self._db_manager.get_table_preview(table_name, limit=100)
        if not ok_prev:
            self._expl_status.setText(msg_prev)
            self._preview_table.setRowCount(0)
            self._preview_table.setColumnCount(0)
            return

        self._preview_table.setColumnCount(len(col_names))
        self._preview_table.setHorizontalHeaderLabels(col_names)
        self._preview_table.setRowCount(len(rows))
        for r, row in enumerate(rows):
            for c, value in enumerate(row):
                self._preview_table.setItem(r, c, QTableWidgetItem("" if value is None else str(value)))
        self._preview_table.resizeColumnsToContents()
        self._expl_status.setText(msg_prev)