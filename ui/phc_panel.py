from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QSettings, Qt
from PySide6.QtGui import QStandardItem, QStandardItemModel
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFileDialog,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSizePolicy,
    QSpinBox,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

import matplotlib.pyplot as plt
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure

from services.phc_service import PHCFilters, PHCService


class ChartWidget(FigureCanvas):
    def __init__(self, parent=None, width=5, height=4, dpi=100):
        self.fig = Figure(figsize=(width, height), dpi=dpi)
        self.axes = self.fig.add_subplot(111)
        super().__init__(self.fig)
        self.setParent(parent)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.updateGeometry()

    def clear(self):
        self.axes.clear()
        self.draw()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.fig.tight_layout()
        self.draw()


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
        out: list[str] = []
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
        self._selected_rule_id: int | None = None
        self._selected_rule_is_generated = False

        self._export_bundle_btn = QPushButton("Exporter bundle")
        self._export_bundle_btn.clicked.connect(self._export_bundle)

        self._import_bundle_btn = QPushButton("Importer bundle")
        self._import_bundle_btn.clicked.connect(self._import_bundle)

        self._diagnostic_btn = QPushButton("Diagnostic familles")
        self._diagnostic_btn.clicked.connect(self._export_family_diagnostic)

        self._refresh_rules_btn = QPushButton("Règles")
        self._refresh_rules_btn.clicked.connect(self._refresh_rules_ui)

        self._family_combo = QComboBox()
        self._family_combo.currentIndexChanged.connect(self._on_family_changed)
        self._family_combo.setMinimumWidth(220)

        self._date_col_combo = QComboBox()
        self._date_col_combo.currentIndexChanged.connect(self._on_date_changed)
        self._date_col_combo.setMinimumWidth(180)

        self._years_combo = MultiSelectComboBox(placeholder="Années (toutes)")
        self._years_combo.setMinimumWidth(220)

        self._refresh_years_btn = QPushButton("↻")
        self._refresh_years_btn.clicked.connect(lambda: self._reload_years(preserve=True))

        self._apply_btn = QPushButton("Appliquer")
        self._apply_btn.clicked.connect(self._apply)

        self._reset_btn = QPushButton("Reset années")
        self._reset_btn.clicked.connect(self._reset)

        self._rules_title = QLabel("Règles famille / sous-famille : -")

        self._rules_table = QTableWidget(0, 7)
        self._rules_table.setHorizontalHeaderLabels(
            [
                "Famille",
                "Sous-famille",
                "Activée",
                "Priorité",
                "Expression régulière",
                "Contient",
                "Ne contient pas",
            ]
        )
        self._rules_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self._rules_table.setSelectionBehavior(QTableWidget.SelectRows)
        self._rules_table.setSelectionMode(QTableWidget.SingleSelection)
        self._rules_table.verticalHeader().setVisible(False)
        self._rules_table.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self._rules_table.setMaximumHeight(240)
        self._rules_table.horizontalHeader().setStretchLastSection(True)
        self._rules_table.itemSelectionChanged.connect(self._on_rule_selected)

        self._rule_form_box = QGroupBox("Édition de règle")
        form = QGridLayout(self._rule_form_box)

        self._rule_family_edit = QLineEdit()
        self._rule_subfamily_edit = QLineEdit()
        self._rule_enabled_check = QCheckBox("Activée")
        self._rule_enabled_check.setChecked(True)
        self._rule_priority_spin = QSpinBox()
        self._rule_priority_spin.setRange(-100000, 100000)
        self._rule_regex_edit = QLineEdit()
        self._rule_contains_edit = QLineEdit()
        self._rule_not_contains_edit = QLineEdit()

        form.addWidget(QLabel("Famille"), 0, 0)
        form.addWidget(self._rule_family_edit, 0, 1)
        form.addWidget(QLabel("Sous-famille"), 0, 2)
        form.addWidget(self._rule_subfamily_edit, 0, 3)
        form.addWidget(self._rule_enabled_check, 0, 4)

        form.addWidget(QLabel("Priorité"), 1, 0)
        form.addWidget(self._rule_priority_spin, 1, 1)
        form.addWidget(QLabel("Expression régulière"), 1, 2)
        form.addWidget(self._rule_regex_edit, 1, 3, 1, 2)

        form.addWidget(QLabel("Contient (csv)"), 2, 0)
        form.addWidget(self._rule_contains_edit, 2, 1, 1, 2)
        form.addWidget(QLabel("Ne contient pas (csv)"), 2, 3)
        form.addWidget(self._rule_not_contains_edit, 2, 4)

        buttons = QHBoxLayout()
        self._rule_new_btn = QPushButton("Nouvelle")
        self._rule_new_btn.clicked.connect(self._clear_rule_form)

        self._rule_save_btn = QPushButton("Enregistrer")
        self._rule_save_btn.clicked.connect(self._save_rule)

        self._rule_delete_btn = QPushButton("Supprimer")
        self._rule_delete_btn.clicked.connect(self._delete_rule)

        buttons.addWidget(self._rule_new_btn)
        buttons.addWidget(self._rule_save_btn)
        buttons.addWidget(self._rule_delete_btn)
        buttons.addStretch()

        form.addLayout(buttons, 3, 0, 1, 5)

        self._title = QLabel("CDV_PHC - Lignes (niveau article) : -")
        self._title.setAlignment(Qt.AlignLeft)

        self._table = QTableWidget(0, 0)
        self._table.setEditTriggers(QTableWidget.NoEditTriggers)
        self._table.setSelectionBehavior(QTableWidget.SelectRows)
        self._table.setSelectionMode(QTableWidget.SingleSelection)
        self._table.verticalHeader().setVisible(False)
        self._table.setAlternatingRowColors(True)
        self._table.horizontalHeader().setStretchLastSection(False)
        self._table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeToContents)

        self._prev_btn = QPushButton("◀")
        self._next_btn = QPushButton("▶")
        self._prev_btn.clicked.connect(self._prev)
        self._next_btn.clicked.connect(self._next)
        self._page_label = QLabel("Page : -")

        self._hist_chart = ChartWidget(self, width=4, height=3)
        self._pie_chart = ChartWidget(self, width=4, height=3)

        root = QVBoxLayout(self)

        top_bar = QHBoxLayout()
        top_bar.addWidget(self._export_bundle_btn)
        top_bar.addWidget(self._import_bundle_btn)
        top_bar.addWidget(self._diagnostic_btn)
        top_bar.addWidget(self._refresh_rules_btn)
        top_bar.addSpacing(16)
        top_bar.addWidget(QLabel("Famille:"))
        top_bar.addWidget(self._family_combo)
        top_bar.addWidget(QLabel("Date (TIMESTAMP):"))
        top_bar.addWidget(self._date_col_combo)
        top_bar.addWidget(QLabel("Années:"))
        top_bar.addWidget(self._years_combo)
        top_bar.addWidget(self._refresh_years_btn)
        top_bar.addWidget(self._apply_btn)
        top_bar.addWidget(self._reset_btn)
        top_bar.addStretch()
        root.addLayout(top_bar)

        root.addWidget(self._rules_title)
        root.addWidget(self._rules_table)
        root.addWidget(self._rule_form_box)

        # Splitter principal (Table vs Charts)
        self._main_splitter = QSplitter(Qt.Horizontal)
        
        # Partie Table
        self._table_container = QWidget()
        table_part = QVBoxLayout(self._table_container)
        table_part.setContentsMargins(0, 0, 0, 0)
        pager = QHBoxLayout()
        pager.addWidget(self._prev_btn)
        pager.addWidget(self._page_label)
        pager.addWidget(self._next_btn)
        pager.addStretch()

        table_part.addWidget(self._title)
        table_part.addLayout(pager)
        table_part.addWidget(self._table, stretch=1)
        
        # Partie Charts avec Splitter vertical
        self._charts_splitter = QSplitter(Qt.Vertical)
        
        self._hist_container = QWidget()
        hist_layout = QVBoxLayout(self._hist_container)
        hist_layout.setContentsMargins(0, 0, 0, 0)
        hist_layout.addWidget(QLabel("<b>Qté par année</b> (hors filtre années)"))
        hist_layout.addWidget(self._hist_chart)
        
        self._pie_container = QWidget()
        pie_layout = QVBoxLayout(self._pie_container)
        pie_layout.setContentsMargins(0, 0, 0, 0)
        pie_layout.addWidget(QLabel("<b>Top 10 Raison sociale</b> (sur années sélectionnées)"))
        pie_layout.addWidget(self._pie_chart)
        
        self._charts_splitter.addWidget(self._hist_container)
        self._charts_splitter.addWidget(self._pie_container)
        
        self._main_splitter.addWidget(self._table_container)
        self._main_splitter.addWidget(self._charts_splitter)
        
        # Stretch par défaut
        self._main_splitter.setStretchFactor(0, 3)
        self._main_splitter.setStretchFactor(1, 1)

        root.addWidget(self._main_splitter, stretch=1)

        self._load_settings()
        self.reload_all()

    def _load_settings(self) -> None:
        settings = QSettings("GEORGIN", "Innovation")
        main_state = settings.value("phc_main_splitter")
        if main_state:
            self._main_splitter.restoreState(main_state)
        charts_state = settings.value("phc_charts_splitter")
        if charts_state:
            self._charts_splitter.restoreState(charts_state)

    def _save_settings(self) -> None:
        settings = QSettings("GEORGIN", "Innovation")
        settings.setValue("phc_main_splitter", self._main_splitter.saveState())
        settings.setValue("phc_charts_splitter", self._charts_splitter.saveState())

    def _ensure_initialized(self) -> None:
        if self._did_init:
            return

        ok, _ = self._service.is_available()
        if not ok:
            return

        self._init_date_columns()
        self._refresh_rules_ui()
        self._reload_years(preserve=False)
        self._did_init = True

    def _init_family_combo(self, preferred: tuple[str, str] | None = None) -> None:
        ok, options, _msg = self._service.get_family_subfamily_options()
        self._family_combo.blockSignals(True)
        try:
            prev = preferred if preferred is not None else self._family_combo.currentData()
            self._family_combo.clear()
            if not ok:
                self._family_combo.addItem("(indisponible)", ("", ""))
                return
            for display, fam, sub in options:
                self._family_combo.addItem(display, (fam, sub))

            target = prev if isinstance(prev, tuple) and len(prev) == 2 else None
            if target is not None:
                for i in range(self._family_combo.count()):
                    if self._family_combo.itemData(i) == target:
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

    def _refresh_rules_ui(self, preferred_family_selection: tuple[str, str] | None = None) -> None:
        if not self._service.config_ready():
            self._rules_title.setText("Règles famille / sous-famille : table de configuration absente dans la base DATA")
            self._rules_table.setRowCount(0)
            self._init_family_combo(preferred_family_selection)
            self._clear_rule_form()
            return

        rules = self._service.get_all_rules_raw()
        persisted = self._service.has_persisted_rules()
        if persisted:
            self._rules_title.setText(f"Règles famille / sous-famille : {len(rules)} règle(s) en base")
        else:
            self._rules_title.setText(f"Règles famille / sous-famille : {len(rules)} règle(s) générée(s) (table vide)")

        self._rules_table.setRowCount(len(rules))
        for r, rule in enumerate(rules):
            criteria = rule.get("criteria", {}) or {}
            self._rules_table.setItem(r, 0, QTableWidgetItem(str(rule.get("family", ""))))
            self._rules_table.setItem(r, 1, QTableWidgetItem(str(rule.get("subfamily", ""))))
            self._rules_table.setItem(r, 2, QTableWidgetItem(str(rule.get("enabled", 1))))
            self._rules_table.setItem(r, 3, QTableWidgetItem(str(rule.get("priority", 0))))
            self._rules_table.setItem(r, 4, QTableWidgetItem(str(criteria.get("regex_pattern", ""))))
            self._rules_table.setItem(r, 5, QTableWidgetItem(", ".join(criteria.get("contains_any", []) or [])))
            self._rules_table.setItem(r, 6, QTableWidgetItem(", ".join(criteria.get("not_contains_any", []) or [])))

            self._rules_table.item(r, 0).setData(Qt.UserRole, rule.get("id"))
            self._rules_table.item(r, 0).setData(Qt.UserRole + 1, rule)

        self._rules_table.resizeColumnsToContents()
        self._init_family_combo(preferred_family_selection)
        self._update_delete_button_state()

    def _parse_csv_line(self, value: str) -> list[str]:
        return [item.strip() for item in value.split(",") if item.strip()]

    def _clear_rule_form(self) -> None:
        self._selected_rule_id = None
        self._selected_rule_is_generated = False
        self._rules_table.clearSelection()
        self._rule_family_edit.setText("")
        self._rule_subfamily_edit.setText("")
        self._rule_enabled_check.setChecked(True)
        self._rule_priority_spin.setValue(0)
        self._rule_regex_edit.setText("")
        self._rule_contains_edit.setText("")
        self._rule_not_contains_edit.setText("")
        self._update_delete_button_state()

    def _on_rule_selected(self) -> None:
        items = self._rules_table.selectedItems()
        if not items:
            self._clear_rule_form()
            return

        row = items[0].row()
        anchor = self._rules_table.item(row, 0)
        if anchor is None:
            return

        rule = anchor.data(Qt.UserRole + 1) or {}
        criteria = rule.get("criteria", {}) or {}

        rule_id = anchor.data(Qt.UserRole)
        self._selected_rule_id = int(rule_id) if rule_id is not None else None
        self._selected_rule_is_generated = self._selected_rule_id is None

        self._rule_family_edit.setText(str(rule.get("family", "")))
        self._rule_subfamily_edit.setText(str(rule.get("subfamily", "")))
        self._rule_enabled_check.setChecked(int(rule.get("enabled", 1) or 0) == 1)
        self._rule_priority_spin.setValue(int(rule.get("priority", 0) or 0))
        self._rule_regex_edit.setText(str(criteria.get("regex_pattern", "")))
        self._rule_contains_edit.setText(", ".join(criteria.get("contains_any", []) or []))
        self._rule_not_contains_edit.setText(", ".join(criteria.get("not_contains_any", []) or []))
        self._update_delete_button_state()

    def _update_delete_button_state(self) -> None:
        self._rule_delete_btn.setEnabled(self._selected_rule_id is not None and not self._selected_rule_is_generated)

    def _save_rule(self) -> None:
        target_selection = (
            self._rule_family_edit.text().strip(),
            self._rule_subfamily_edit.text().strip(),
        )
        ok, msg = self._service.save_rule(
            rule_id=self._selected_rule_id if not self._selected_rule_is_generated else None,
            family=target_selection[0],
            subfamily=target_selection[1],
            enabled=self._rule_enabled_check.isChecked(),
            priority=self._rule_priority_spin.value(),
            regex_pattern=self._rule_regex_edit.text(),
            contains_any=self._parse_csv_line(self._rule_contains_edit.text()),
            not_contains_any=self._parse_csv_line(self._rule_not_contains_edit.text()),
        )
        if ok:
            QMessageBox.information(self, "Règles", msg)
            self._refresh_rules_ui(target_selection)
            self._reload_years(preserve=True)
            self.reload_all()
            self._clear_rule_form()
        else:
            QMessageBox.critical(self, "Règles", msg)

    def _delete_rule(self) -> None:
        if self._selected_rule_id is None:
            QMessageBox.information(self, "Règles", "Sélectionne une règle enregistrée à supprimer.")
            return

        ok, msg = self._service.delete_rule(self._selected_rule_id)
        if ok:
            QMessageBox.information(self, "Règles", msg)
            self._refresh_rules_ui()
            self._reload_years(preserve=True)
            self.reload_all()
            self._clear_rule_form()
        else:
            QMessageBox.critical(self, "Règles", msg)

    def _export_bundle(self) -> None:
        if not self._service.config_ready():
            QMessageBox.information(
                self,
                "Export",
                "Choisis d'abord une base DATA ; la table de configuration y sera créée automatiquement.",
            )
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

    def _export_family_diagnostic(self) -> None:
        filepath, _ = QFileDialog.getSaveFileName(
            self,
            "Exporter diagnostic familles",
            str(Path.home() / "phc_family_diagnostic.json"),
            "JSON (*.json);;Tous les fichiers (*)",
        )
        if not filepath:
            return

        ok, msg = self._service.export_family_diagnostic_json(filepath)
        if ok:
            QMessageBox.information(self, "Diagnostic familles", msg)
        else:
            QMessageBox.critical(self, "Diagnostic familles", msg)

    def _import_bundle(self) -> None:
        if not self._service.config_ready():
            QMessageBox.information(
                self,
                "Import",
                "Choisis d'abord une base DATA ; la table de configuration y sera créée automatiquement.",
            )
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
            self._clear_rule_form()
        else:
            QMessageBox.critical(self, "Import", msg)

    def _on_family_changed(self) -> None:
        self._offset = 0
        self._reload_years(preserve=True)

    def _on_date_changed(self) -> None:
        self._offset = 0
        self._reload_years(preserve=True)

    def _reload_years(self, preserve: bool) -> None:
        date_col = self._date_col_combo.currentText().strip()
        fam, sub = self._current_family_selection()
        prev = self._years_combo.selected_items() if preserve else []
        ok, years, _msg = self._service.list_distinct_years_for_selection(date_col, fam, sub)
        self._years_combo.set_items_preserve(years if ok else [], prev)

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

        ok, msg = self._service.is_available()
        if not ok:
            self._title.setText(f"CDV_PHC - {msg}")
            self._clear_table()
            self._page_label.setText("Page : -")
            self._prev_btn.setEnabled(False)
            self._next_btn.setEnabled(False)
            self._hist_chart.clear()
            self._pie_chart.clear()
            return

        self._reload_table()
        self._reload_charts()

    def _reload_table(self) -> None:
        ok, page, msg = self._service.list_lines(self._filters(), limit=self.PAGE_SIZE, offset=self._offset)
        fam, sub = self._current_family_selection()
        suffix = ""
        if fam:
            suffix = f" | {fam}" + (f" / {sub}" if sub else "")
        self._title.setText(f"CDV_PHC - Lignes (niveau article) : {msg}{suffix}")

        if not ok or page is None:
            self._clear_table()
            self._page_label.setText("Page : -")
            self._prev_btn.setEnabled(False)
            self._next_btn.setEnabled(False)
            return

        self._render_table(page.columns, page.rows)
        page_num = (self._offset // self.PAGE_SIZE) + 1
        self._page_label.setText(f"Page : {page_num} | {page.message}")
        self._prev_btn.setEnabled(self._offset > 0)
        self._next_btn.setEnabled(len(page.rows) == self.PAGE_SIZE)

    def _clear_table(self) -> None:
        self._table.setRowCount(0)
        self._table.setColumnCount(0)

    def _render_table(self, columns: list[str], rows: list[list[object]]) -> None:
        self._table.setColumnCount(len(columns))
        self._table.setHorizontalHeaderLabels(columns)
        self._table.setUpdatesEnabled(False)
        try:
            self._table.setRowCount(len(rows))
            for r, row_vals in enumerate(rows):
                for c, v in enumerate(row_vals):
                    self._table.setItem(r, c, QTableWidgetItem("" if v is None else str(v)))
            self._table.resizeColumnsToContents()
        finally:
            self._table.setUpdatesEnabled(True)

    def _reload_charts(self) -> None:
        filters = self._filters()
        if not filters.date_column:
            self._hist_chart.clear()
            self._pie_chart.clear()
            return

        # 1. Histogramme (Quantité par année, sans filtre années)
        ok_hist, hist_data, _msg = self._service.get_qty_by_year_data(filters)
        self._hist_chart.axes.clear()
        if ok_hist and hist_data:
            years = [d[0] for d in hist_data]
            qtys = [d[1] for d in hist_data]
            bars = self._hist_chart.axes.bar(years, qtys, color="skyblue")
            self._hist_chart.axes.bar_label(bars, padding=3)
            self._hist_chart.axes.set_ylabel("Quantité")
            self._hist_chart.axes.tick_params(axis="x", rotation=45)
            self._hist_chart.fig.tight_layout()
        self._hist_chart.draw()

        # 2. Pie Chart (Raison sociale par Qté, sur années sélectionnées)
        ok_pie, pie_data, _msg = self._service.get_rs_distribution_data(filters, top_n=10)
        self._pie_chart.axes.clear()
        if ok_pie and pie_data:
            labels = []
            for d in pie_data:
                label = d[0]
                if label != "Autres" and len(label) > 20:
                    label = label[:20] + "..."
                labels.append(label)

            values = [d[1] for d in pie_data]
            self._pie_chart.axes.pie(values, labels=labels, autopct="%1.1f%%", startangle=140)
            self._pie_chart.fig.tight_layout()
        self._pie_chart.draw()