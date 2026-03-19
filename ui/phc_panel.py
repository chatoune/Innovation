from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QStandardItemModel, QStandardItem
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QFileDialog,
    QMessageBox,
    QSplitter,
    QComboBox,
)

from matplotlib.figure import Figure
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas

from services.phc_service import PHCService, PHCFilters


class MultiSelectComboBox(QComboBox):
    def __init__(self, placeholder: str = "Sélection...", parent=None):
        super().__init__(parent)
        self.setModel(QStandardItemModel(self))
        self.setEditable(True)
        self.lineEdit().setReadOnly(True)
        self._placeholder = placeholder
        self._update_text()
        self.view().pressed.connect(self._on_pressed)

    def set_items_preserve(self, items: list[str], preserve: list[str]) -> None:
        preserve_set = set(preserve or [])
        model: QStandardItemModel = self.model()
        model.clear()
        for it in items:
            item = QStandardItem(it)
            item.setFlags(Qt.ItemIsEnabled | Qt.ItemIsUserCheckable)
            item.setData(Qt.Checked if it in preserve_set else Qt.Unchecked, Qt.CheckStateRole)
            model.appendRow(item)
        self._update_text()

    def selected_items(self) -> list[str]:
        model: QStandardItemModel = self.model()
        out = []
        for r in range(model.rowCount()):
            item = model.item(r)
            if item.checkState() == Qt.Checked:
                out.append(item.text())
        return out

    def clear_selection(self) -> None:
        model: QStandardItemModel = self.model()
        for r in range(model.rowCount()):
            model.item(r).setCheckState(Qt.Unchecked)
        self._update_text()

    def _on_pressed(self, index) -> None:
        model: QStandardItemModel = self.model()
        item = model.itemFromIndex(index)
        item.setCheckState(Qt.Unchecked if item.checkState() == Qt.Checked else Qt.Checked)
        self._update_text()

    def _update_text(self) -> None:
        selected = self.selected_items()
        self.lineEdit().setText(self._placeholder if not selected else ", ".join(selected))


class PHCPanel(QWidget):
    PAGE_SIZE = 200

    def __init__(self, service: PHCService, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._service = service
        self._offset = 0
        self._did_init = False

        # --- Rules table ---
        self._rules_title = QLabel("Règles famille / sous-famille : -")
        self._rules_table = QTableWidget(0, 6)
        self._rules_table.setHorizontalHeaderLabels(["Famille", "Sous-famille", "Enabled", "Priority", "StartsWith", "Contains/Not"])
        self._rules_table.setEditTriggers(QTableWidget.NoEditTriggers)

        self._export_bundle_btn = QPushButton("Exporter bundle (règles+articles)")
        self._export_bundle_btn.clicked.connect(self._export_bundle)

        self._import_bundle_btn = QPushButton("Importer bundle (mise à jour règles)")
        self._import_bundle_btn.clicked.connect(self._import_bundle)

        self._refresh_rules_btn = QPushButton("↻ Règles")
        self._refresh_rules_btn.clicked.connect(self._refresh_rules_ui)

        # --- Famille / sous-famille combo ---
        self._family_combo = QComboBox()
        self._family_combo.currentIndexChanged.connect(self._on_family_changed)

        # --- TIMESTAMP date columns ---
        self._date_col_combo = QComboBox()
        self._date_col_combo.currentIndexChanged.connect(self._on_date_changed)

        # --- Years multi-select ---
        self._years_combo = MultiSelectComboBox(placeholder="Années (toutes)")
        self._refresh_years_btn = QPushButton("↻")
        self._refresh_years_btn.clicked.connect(lambda: self._reload_years(preserve=True))

        self._apply_btn = QPushButton("Appliquer")
        self._apply_btn.clicked.connect(self._apply)

        self._reset_btn = QPushButton("Reset années")
        self._reset_btn.clicked.connect(self._reset)

        # --- Chart ---
        self._fig = Figure(figsize=(6, 4))
        self._ax = self._fig.add_subplot(111)
        self._canvas = FigureCanvas(self._fig)

        # --- Lines table ---
        self._title = QLabel("CDV_PHC - Lignes (niveau article) : -")
        self._title.setAlignment(Qt.AlignLeft)

        self._table = QTableWidget(0, 0)
        self._table.setEditTriggers(QTableWidget.NoEditTriggers)
        self._table.setSelectionBehavior(QTableWidget.SelectRows)
        self._table.setSelectionMode(QTableWidget.SingleSelection)

        self._prev_btn = QPushButton("◀")
        self._next_btn = QPushButton("▶")
        self._prev_btn.clicked.connect(self._prev)
        self._next_btn.clicked.connect(self._next)
        self._page_label = QLabel("Page : -")

        # Layout
        root = QVBoxLayout(self)

        # Top: rules controls
        rules_bar = QHBoxLayout()
        rules_bar.addWidget(self._export_bundle_btn)
        rules_bar.addWidget(self._import_bundle_btn)
        rules_bar.addWidget(self._refresh_rules_btn)
        rules_bar.addStretch()
        root.addLayout(rules_bar)

        root.addWidget(self._rules_title)
        root.addWidget(self._rules_table, stretch=0)

        # Filters bar
        top = QHBoxLayout()
        top.addWidget(QLabel("Famille:"))
        top.addWidget(self._family_combo)

        top.addWidget(QLabel("Date (TIMESTAMP):"))
        top.addWidget(self._date_col_combo)

        top.addWidget(QLabel("Années:"))
        top.addWidget(self._years_combo)
        top.addWidget(self._refresh_years_btn)

        top.addWidget(self._apply_btn)
        top.addWidget(self._reset_btn)
        root.addLayout(top)

        # Splitter: left table / right chart
        split = QSplitter(Qt.Horizontal)

        table_panel = QWidget()
        table_layout = QVBoxLayout(table_panel)
        table_layout.setContentsMargins(0, 0, 0, 0)

        pager = QHBoxLayout()
        pager.addWidget(self._prev_btn)
        pager.addWidget(self._page_label)
        pager.addWidget(self._next_btn)
        pager.addStretch()

        table_layout.addWidget(self._title)
        table_layout.addLayout(pager)
        table_layout.addWidget(self._table, stretch=1)

        chart_panel = QWidget()
        chart_layout = QVBoxLayout(chart_panel)
        chart_layout.setContentsMargins(0, 0, 0, 0)
        chart_layout.addWidget(QLabel("Répartition des quantités demandées (CDV_PHC)"))
        chart_layout.addWidget(self._canvas, stretch=1)

        split.addWidget(table_panel)
        split.addWidget(chart_panel)
        split.setSizes([850, 450])

        root.addWidget(split, stretch=1)

        self.reload_all()

    # ---------- Init / reload ----------
    def _ensure_initialized(self) -> None:
        if self._did_init:
            return

        ok, _ = self._service.is_available()
        if not ok:
            return

        if not self._service.config_ready():
            self._rules_title.setText("Règles famille / sous-famille : table de configuration absente dans la base DATA")
            self._init_date_columns()
            self._did_init = True
            return

        self._init_family_combo()
        self._init_date_columns()
        self._refresh_rules_ui()
        self._reload_years(preserve=False)
        self._did_init = True

    def _init_family_combo(self) -> None:
        ok, options, msg = self._service.get_family_subfamily_options()
        self._family_combo.blockSignals(True)
        try:
            prev = self._family_combo.currentData()
            self._family_combo.clear()
            if not ok:
                self._family_combo.addItem("(indisponible)", ("", ""))
                return
            for display, fam, sub in options:
                self._family_combo.addItem(display, (fam, sub))
            if prev is not None:
                for i in range(self._family_combo.count()):
                    if self._family_combo.itemData(i) == prev:
                        self._family_combo.setCurrentIndex(i)
                        break
        finally:
            self._family_combo.blockSignals(False)

    def _init_date_columns(self) -> None:
        ok, cols, msg = self._service.get_timestamp_date_columns()
        self._date_col_combo.blockSignals(True)
        try:
            prev = self._date_col_combo.currentText().strip()
            self._date_col_combo.clear()
            if ok and cols:
                self._date_col_combo.addItems(cols)
                if prev and prev in cols:
                    self._date_col_combo.setCurrentText(prev)
            else:
                self._date_col_combo.addItem("")
                self._title.setText(f"CDV_PHC - {msg}")
        finally:
            self._date_col_combo.blockSignals(False)

    def _current_family_selection(self) -> tuple[str, str]:
        data = self._family_combo.currentData()
        if isinstance(data, tuple) and len(data) == 2:
            return str(data[0]), str(data[1])
        return "", ""

    def _filters(self) -> PHCFilters:
        fam, sub = self._current_family_selection()
        return PHCFilters(
            date_column=self._date_col_combo.currentText().strip(),
            years=self._years_combo.selected_items(),
            family_root=fam,
            subfamily=sub,
        )

    # ---------- Rules UI ----------
    def _refresh_rules_ui(self) -> None:
        if not self._service.config_ready():
            self._rules_title.setText("Règles famille / sous-famille : table de configuration absente dans la base DATA")
            self._rules_table.setRowCount(0)
            return

        rules = self._service.get_all_rules_raw()
        self._rules_title.setText(f"Règles famille / sous-famille : {len(rules)} règle(s)")
        self._rules_table.setRowCount(len(rules))

        for r, rule in enumerate(rules):
            fam = str(rule.get("family", ""))
            sub = str(rule.get("subfamily", ""))
            en = str(rule.get("enabled", 1))
            pr = str(rule.get("priority", 0))
            crit = rule.get("criteria", {}) or {}
            sw = ",".join(crit.get("startswith_any", []) or [])
            ct = ",".join(crit.get("contains_any", []) or [])
            nsw = ",".join(crit.get("not_startswith_any", []) or [])
            nct = ",".join(crit.get("not_contains_any", []) or [])
            other = f"ct=[{ct}] nsw=[{nsw}] nct=[{nct}]"

            self._rules_table.setItem(r, 0, QTableWidgetItem(fam))
            self._rules_table.setItem(r, 1, QTableWidgetItem(sub))
            self._rules_table.setItem(r, 2, QTableWidgetItem(en))
            self._rules_table.setItem(r, 3, QTableWidgetItem(pr))
            self._rules_table.setItem(r, 4, QTableWidgetItem(sw))
            self._rules_table.setItem(r, 5, QTableWidgetItem(other))

        self._rules_table.resizeColumnsToContents()

        # refresh combo families too
        self._init_family_combo()

    def _export_bundle(self) -> None:
        if not self._service.config_ready():
            QMessageBox.information(self, "Export", "Choisis d'abord une base DATA ; la table de configuration y sera créée automatiquement.")
            return
        date_col = self._date_col_combo.currentText().strip()
        filepath, _ = QFileDialog.getSaveFileName(
            self,
            "Exporter bundle JSON",
            str(Path.home() / "phc_bundle.json"),
            "JSON (*.json);;Tous les fichiers (*)",
        )
        if not filepath:
            return
        ok, msg = self._service.export_bundle_json(filepath, date_col)
        if ok:
            QMessageBox.information(self, "Export", msg)
        else:
            QMessageBox.critical(self, "Export", msg)

    def _import_bundle(self) -> None:
        if not self._service.config_ready():
            QMessageBox.information(self, "Import", "Choisis d'abord une base DATA ; la table de configuration y sera créée automatiquement.")
            return
        filepath, _ = QFileDialog.getOpenFileName(
            self,
            "Importer bundle JSON",
            str(Path.home()),
            "JSON (*.json);;Tous les fichiers (*)",
        )
        if not filepath:
            return
        ok, msg = self._service.import_bundle_json(filepath)
        if ok:
            QMessageBox.information(self, "Import", msg)
            self._refresh_rules_ui()
            self._reload_years(preserve=False)
            self.reload_all()
        else:
            QMessageBox.critical(self, "Import", msg)

    # ---------- Events ----------
    def _on_family_changed(self) -> None:
        self._offset = 0
        self._reload_years(preserve=True)
        self.reload_all()

    def _on_date_changed(self) -> None:
        self._offset = 0
        self._reload_years(preserve=True)

    def _reload_years(self, preserve: bool) -> None:
        date_col = self._date_col_combo.currentText().strip()
        fam, sub = self._current_family_selection()
        prev = self._years_combo.selected_items() if preserve else []
        ok, years, _msg = self._service.list_distinct_years_for_selection(date_col, fam, sub)
        self._years_combo.set_items_preserve(years if ok else [], prev)

    # ---------- Actions ----------
    def _apply(self) -> None:
        self._offset = 0
        self.reload_all()

    def _reset(self) -> None:
        self._years_combo.clear_selection()
        self._offset = 0
        self._reload_years(preserve=False)
        self.reload_all()

    def _prev(self) -> None:
        if self._offset <= 0:
            return
        self._offset = max(0, self._offset - self.PAGE_SIZE)
        self._reload_table()

    def _next(self) -> None:
        self._offset += self.PAGE_SIZE
        self._reload_table()

    def reload_all(self) -> None:
        self._ensure_initialized()
        self._reload_table()
        self._reload_chart()

    def _reload_table(self) -> None:
        filters = self._filters()
        ok, page, msg = self._service.list_lines(filters, limit=self.PAGE_SIZE, offset=self._offset)
        if not ok or page is None:
            self._title.setText(f"CDV_PHC - {msg}")
            self._table.setRowCount(0)
            self._table.setColumnCount(0)
            self._page_label.setText("Page : -")
            return

        self._title.setText(f"CDV_PHC - Lignes (niveau article) : {page.message}")
        self._table.setColumnCount(len(page.columns))
        self._table.setHorizontalHeaderLabels(page.columns)
        self._table.setRowCount(len(page.rows))

        for r, row in enumerate(page.rows):
            for c, value in enumerate(row):
                self._table.setItem(r, c, QTableWidgetItem("" if value is None else str(value)))

        self._table.resizeColumnsToContents()
        current_page = (self._offset // self.PAGE_SIZE) + 1
        self._page_label.setText(f"Page : {current_page}")

    def _reload_chart(self) -> None:
        self._ax.clear()

        filters = self._filters()
        ok, series, msg = self._service.series_qty_distribution(filters)
        if not ok or series is None or not series.labels:
            self._ax.set_title("Aucune donnée")
            self._canvas.draw_idle()
            return

        self._ax.bar(series.labels, series.values)
        self._ax.set_title("Répartition des quantités demandées")
        self._ax.set_xlabel("Classes")
        self._ax.set_ylabel("Nombre de lignes")
        self._canvas.draw_idle()