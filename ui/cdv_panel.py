from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QStandardItemModel, QStandardItem
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QFileDialog,
    QMessageBox,
    QSplitter,
    QComboBox,
)

from services.cdv_service import CDVService, CDVFilters

from matplotlib.figure import Figure
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas


class MultiSelectComboBox(QComboBox):
    """
    QComboBox multi-sélection basé sur des items checkables.
    Supporte la conservation de sélection lors d'un rechargement.
    """
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
            item.setFlags(Qt.ItemIsUserCheckable | Qt.ItemIsEnabled)
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
        if item.checkState() == Qt.Checked:
            item.setCheckState(Qt.Unchecked)
        else:
            item.setCheckState(Qt.Checked)
        self._update_text()

    def _update_text(self) -> None:
        selected = self.selected_items()
        self.lineEdit().setText(self._placeholder if not selected else ", ".join(selected))


class CDVPanel(QWidget):
    PAGE_SIZE_LINES = 200

    def __init__(self, service: CDVService, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._service = service
        self._offset_lines = 0

        # ---------- Filtres demandés ----------
        self._article_edit = QLineEdit()
        self._article_edit.setPlaceholderText("Filtre Article (contient)")

        # Drop-down EXACT intitulés (toujours présents)
        self._date_col_combo = QComboBox()
        self._date_col_combo.addItems(self._service.get_fixed_date_columns())
        self._date_col_combo.currentIndexChanged.connect(self._on_date_column_changed)

        # Multi-sélection années (dépendante de la colonne date sélectionnée)
        self._years_combo = MultiSelectComboBox(placeholder="Années (toutes)")
        self._refresh_years_btn = QPushButton("↻")
        self._refresh_years_btn.clicked.connect(self._reload_years_list)

        self._apply_btn = QPushButton("Appliquer")
        self._apply_btn.clicked.connect(self._apply_filters)

        self._reset_btn = QPushButton("Reset")
        self._reset_btn.clicked.connect(self._reset_filters)

        self._export_btn = QPushButton("Exporter CSV")
        self._export_btn.clicked.connect(self._export_csv)

        self._reload_btn = QPushButton("Recharger")
        self._reload_btn.clicked.connect(self.reload_all)

        # ---------- Graphe répartition Qté ----------
        self._fig_qty = Figure(figsize=(6, 4))
        self._ax_qty = self._fig_qty.add_subplot(111)
        self._canvas_qty = FigureCanvas(self._fig_qty)

        # ---------- Table Lignes ----------
        self._lines_title = QLabel("Lignes (niveau article) : -")
        self._lines_title.setAlignment(Qt.AlignLeft)

        self._lines_table = QTableWidget(0, 0)
        self._lines_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self._lines_table.setSelectionBehavior(QTableWidget.SelectRows)
        self._lines_table.setSelectionMode(QTableWidget.SingleSelection)

        # Pagination
        self._prev_lines_btn = QPushButton("◀")
        self._next_lines_btn = QPushButton("▶")
        self._prev_lines_btn.clicked.connect(self._prev_lines)
        self._next_lines_btn.clicked.connect(self._next_lines)
        self._lines_page_label = QLabel("Page : -")

        # ---------- Layout ----------
        root = QVBoxLayout(self)

        # Barre filtres
        filters = QHBoxLayout()
        filters.addWidget(QLabel("Article:"))
        filters.addWidget(self._article_edit)

        filters.addWidget(QLabel("Date:"))
        filters.addWidget(self._date_col_combo)

        filters.addWidget(QLabel("Années:"))
        filters.addWidget(self._years_combo)
        filters.addWidget(self._refresh_years_btn)

        filters.addWidget(self._apply_btn)
        filters.addWidget(self._reset_btn)
        filters.addWidget(self._export_btn)
        filters.addStretch()
        filters.addWidget(self._reload_btn)

        root.addLayout(filters)

        # Splitter horizontal : gauche table, droite graphe
        split = QSplitter(Qt.Horizontal)

        # Gauche : table + pagination
        table_panel = QWidget()
        table_layout = QVBoxLayout(table_panel)
        table_layout.setContentsMargins(0, 0, 0, 0)

        pager = QHBoxLayout()
        pager.addWidget(self._prev_lines_btn)
        pager.addWidget(self._lines_page_label)
        pager.addWidget(self._next_lines_btn)
        pager.addStretch()

        table_layout.addWidget(self._lines_title)
        table_layout.addLayout(pager)
        table_layout.addWidget(self._lines_table, stretch=1)

        split.addWidget(table_panel)

        # Droite : graphe
        chart_panel = QWidget()
        chart_layout = QVBoxLayout(chart_panel)
        chart_layout.setContentsMargins(0, 0, 0, 0)
        chart_layout.addWidget(QLabel("Répartition des quantités demandées"))
        chart_layout.addWidget(self._canvas_qty, stretch=1)

        split.addWidget(chart_panel)

        # Taille initiale : table plus large que graphe
        split.setSizes([850, 450])

        root.addWidget(split, stretch=1)

        # Initial load des années + data
        self._reload_years_list(preserve_checked=False)
        self.reload_all()

    # ---------- Date / Years logic ----------
    def _on_date_column_changed(self) -> None:
        self._reload_years_list(preserve_checked=True)

    def _reload_years_list(self, preserve_checked: bool = True) -> None:
        date_col = self._date_col_combo.currentText().strip()
        prev_checked = self._years_combo.selected_items() if preserve_checked else []

        ok, years, _msg = self._service.list_distinct_years(date_col)
        self._years_combo.set_items_preserve(years if ok else [], prev_checked)

    # ---------- Filters ----------
    def _current_filters(self) -> CDVFilters:
        return CDVFilters(
            article_contains=self._article_edit.text(),
            date_column=self._date_col_combo.currentText().strip(),
            years=self._years_combo.selected_items(),
        )

    def _apply_filters(self) -> None:
        self._offset_lines = 0
        self.reload_all()

    def _reset_filters(self) -> None:
        self._article_edit.setText("")
        self._years_combo.clear_selection()
        self._offset_lines = 0
        self.reload_all()

    # ---------- Pagination ----------
    def _prev_lines(self) -> None:
        if self._offset_lines <= 0:
            return
        self._offset_lines = max(0, self._offset_lines - self.PAGE_SIZE_LINES)
        self._reload_lines()

    def _next_lines(self) -> None:
        self._offset_lines += self.PAGE_SIZE_LINES
        self._reload_lines()

    # ---------- Export ----------
    def _export_csv(self) -> None:
        ok, msg = self._service.is_available()
        if not ok:
            QMessageBox.warning(self, "Export", msg)
            return

        filepath, _ = QFileDialog.getSaveFileName(
            self,
            "Exporter CSV (lignes)",
            str(Path.home() / "cdv_lignes_export.csv"),
            "CSV (*.csv);;Tous les fichiers (*)",
        )
        if not filepath:
            return

        ok2, msg2 = self._service.export_lines_csv(filepath, self._current_filters(), limit=50000)
        if ok2:
            QMessageBox.information(self, "Export", msg2)
        else:
            QMessageBox.critical(self, "Export", msg2)

    # ---------- Reload ----------
    def reload_all(self) -> None:
        ok, msg = self._service.is_available()
        if not ok:
            self._lines_title.setText(f"Lignes (niveau article) : {msg}")
            self._clear_table()
            self._ax_qty.clear()
            self._ax_qty.text(0.5, 0.5, msg, ha="center", va="center", transform=self._ax_qty.transAxes)
            self._canvas_qty.draw()
            return

        # Garder sélection date + années
        self._reload_years_list(preserve_checked=True)
        self._reload_chart_qty_distribution()
        self._reload_lines()

    def _reload_chart_qty_distribution(self) -> None:
        self._ax_qty.clear()
        ok, series, msg = self._service.series_qty_distribution(self._current_filters())
        if ok and series and series.labels:
            self._ax_qty.bar(series.labels, series.values)
            self._ax_qty.set_xlabel("Qté (buckets)")
            self._ax_qty.set_ylabel("Nb lignes")
        else:
            self._ax_qty.text(0.5, 0.5, msg, ha="center", va="center", transform=self._ax_qty.transAxes)
        self._fig_qty.tight_layout()
        self._canvas_qty.draw()

    def _reload_lines(self) -> None:
        ok, page, msg = self._service.list_lines(
            self._current_filters(),
            limit=self.PAGE_SIZE_LINES,
            offset=self._offset_lines,
        )
        self._lines_title.setText(f"Lignes (niveau article) : {msg}")

        if not ok or page is None:
            self._clear_table()
            self._lines_page_label.setText("Page : -")
            self._prev_lines_btn.setEnabled(False)
            self._next_lines_btn.setEnabled(False)
            return

        self._render_table(page.columns, page.rows)
        page_num = (self._offset_lines // self.PAGE_SIZE_LINES) + 1
        self._lines_page_label.setText(f"Page : {page_num} | {msg}")
        self._prev_lines_btn.setEnabled(self._offset_lines > 0)
        self._next_lines_btn.setEnabled(len(page.rows) == self.PAGE_SIZE_LINES)

    # ---------- Table helpers ----------
    def _clear_table(self) -> None:
        self._lines_table.setRowCount(0)
        self._lines_table.setColumnCount(0)

    def _render_table(self, columns: list[str], rows: list[list[object]]) -> None:
        self._lines_table.setColumnCount(len(columns))
        self._lines_table.setHorizontalHeaderLabels(columns)
        self._lines_table.setRowCount(len(rows))

        for r, row_vals in enumerate(rows):
            for c, v in enumerate(row_vals):
                self._lines_table.setItem(r, c, QTableWidgetItem("" if v is None else str(v)))

        self._lines_table.resizeColumnsToContents()