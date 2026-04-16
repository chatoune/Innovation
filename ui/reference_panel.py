from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QSplitter,
    QComboBox,
)

from services.reference_service import ReferenceService

from matplotlib.figure import Figure
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
import numpy as np
import re


class ReferencePanel(QWidget):
    """
    Panel pour l'affichage des références (Article GR/GA)
    avec un graphe robuste et cohérent.
    """

    PAGE_SIZE = 500

    def __init__(self, service: ReferenceService, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._service = service
        self._offset = 0
        self._all_relevant_data: list[dict] = []

        # Titre
        self._title_label = QLabel("Références (Article GR/GA) : -")
        self._title_label.setAlignment(Qt.AlignLeft)

        # Filtre Date
        self._date_col_combo = QComboBox()
        self._date_col_combo.addItems(["Date", "Date exp", "Date facture", "Date livraison"])
        self._date_col_combo.currentIndexChanged.connect(self.reload_all)

        # Table principale (Aperçu)
        self._table = QTableWidget(0, 0)
        self._table.setEditTriggers(QTableWidget.NoEditTriggers)
        self._table.setSelectionBehavior(QTableWidget.SelectRows)

        # Boutons
        self._reload_btn = QPushButton("Recharger")
        self._reload_btn.clicked.connect(self.reload_all)

        # Pagination (Aperçu)
        self._prev_btn = QPushButton("◀")
        self._next_btn = QPushButton("▶")
        self._prev_btn.clicked.connect(self._prev_page)
        self._next_btn.clicked.connect(self._next_page)
        self._page_label = QLabel("Page : -")

        # Graphe
        self._fig = Figure(figsize=(8, 4))
        self._ax = self._fig.add_subplot(111)
        self._canvas = FigureCanvas(self._fig)
        self._canvas.mpl_connect('button_press_event', self._on_chart_click)

        # Table de détail
        self._detail_table = QTableWidget(0, 0)
        self._detail_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self._detail_label = QLabel("Clique sur une barre du graphe pour voir le détail.")

        # Layout
        root = QVBoxLayout(self)

        top_bar = QHBoxLayout()
        top_bar.addWidget(self._title_label)
        top_bar.addStretch()
        top_bar.addWidget(QLabel("Date graphe:"))
        top_bar.addWidget(self._date_col_combo)
        top_bar.addWidget(self._reload_btn)
        root.addLayout(top_bar)

        pager = QHBoxLayout()
        pager.addWidget(self._prev_btn)
        pager.addWidget(self._page_label)
        pager.addWidget(self._next_btn)
        pager.addStretch()
        root.addLayout(pager)

        splitter = QSplitter(Qt.Vertical)
        splitter.addWidget(self._table)
        
        graph_area = QWidget()
        gl = QVBoxLayout(graph_area)
        gl.addWidget(QLabel("Ventes annuelles par famille (Cliques pour détail)"))
        gl.addWidget(self._canvas)
        splitter.addWidget(graph_area)

        detail_area = QWidget()
        dl = QVBoxLayout(detail_area)
        dl.addWidget(self._detail_label)
        dl.addWidget(self._detail_table)
        splitter.addWidget(detail_area)
        
        splitter.setSizes([200, 400, 300])
        root.addWidget(splitter, stretch=1)

        self.reload_all()

    def _prev_page(self) -> None:
        if self._offset <= 0: return
        self._offset = max(0, self._offset - self.PAGE_SIZE)
        self.reload_all()

    def _next_page(self) -> None:
        self._offset += self.PAGE_SIZE
        self.reload_all()

    def reload_all(self) -> None:
        # 1. Charger l'aperçu paginé (SQL pur)
        ok_p, res_p, msg_p = self._service.list_references(limit=self.PAGE_SIZE, offset=self._offset)
        if ok_p and res_p:
            self._table.setColumnCount(len(res_p.columns))
            self._table.setHorizontalHeaderLabels(res_p.columns)
            self._table.setRowCount(len(res_p.rows))
            for r, rv in enumerate(res_p.rows):
                for c, v in enumerate(rv):
                    self._table.setItem(r, c, QTableWidgetItem(str(v) if v is not None else ""))
            self._table.resizeColumnsToContents()
            pn = (self._offset // self.PAGE_SIZE) + 1
            self._page_label.setText(f"Page : {pn} | {msg_p}")
            self._prev_btn.setEnabled(self._offset > 0)
            self._next_btn.setEnabled(len(res_p.rows) == self.PAGE_SIZE)

        # 2. Charger TOUTES les lignes pour le graphe (pour cohérence totale)
        dc = self._date_col_combo.currentText()
        ok, data, msg = self._service.get_all_relevant_lines(dc)
        if not ok:
            self._all_relevant_data = []
            self._title_label.setText(f"Erreur chargement data: {msg}")
        else:
            # On enrichit les données avec Famille et Année calculées en Python
            self._all_relevant_data = self._enrich_and_filter(data)
            self._title_label.setText(f"Références (Article GR/GA) : {len(self._all_relevant_data)} lignes filtrées")

        self._reload_chart()
        self._detail_table.setRowCount(0)
        self._detail_label.setText("Clique sur une barre pour voir le détail.")

    def _enrich_and_filter(self, data: list[dict]) -> list[dict]:
        """Catégorise en Python pour être sûr de ne rien rater."""
        out = []
        map_fam = {"3": "GR3/GA3", "E": "GRE/GAE", "F": "GRF/GAF", "K": "GRK/GAK"}
        
        for d in data:
            art = d["article"]
            # On cherche le 3ème caractère signifiant
            # On ignore les espaces (déjà fait par TRIM en SQL normalement)
            if len(art) >= 3:
                c3 = art[2]
                fam = map_fam.get(c3)
                if fam:
                    # Extraction année robuste (YYYY-...)
                    match = re.search(r"(\d{4})", d["raw_date"])
                    year = match.group(1) if match else "Inconnu"
                    
                    d["family"] = fam
                    d["year"] = year
                    out.append(d)
        return out

    def _reload_chart(self) -> None:
        self._ax.clear()
        self._rects_map = []
        if not self._all_relevant_data:
            self._canvas.draw(); return

        all_years = sorted(list(set(d["year"] for d in self._all_relevant_data if d["year"] != "Inconnu")))
        families = ["GR3/GA3", "GRE/GAE", "GRF/GAF", "GRK/GAK"]
        
        # Agrégation pour le plot
        fam_series = {fam: [0.0] * len(all_years) for fam in families}
        for d in self._all_relevant_data:
            if d["year"] in all_years and d["family"] in fam_series:
                y_idx = all_years.index(d["year"])
                fam_series[d["family"]][y_idx] += d["qty"]

        x = np.arange(len(all_years))
        width = 0.2
        offsets = [-1.5 * width, -0.5 * width, 0.5 * width, 1.5 * width]
        colors = ['#1f77b4', '#ff7f0e', '#2ca02c', '#d62728']

        for i, fam in enumerate(families):
            values = fam_series[fam]
            rects = self._ax.bar(x + offsets[i], values, width, label=fam, color=colors[i])
            for r_idx, rect in enumerate(rects):
                self._rects_map.append((rect, all_years[r_idx], fam))
                h = rect.get_height()
                if h > 0:
                    self._ax.annotate(f"{h:g}", xy=(rect.get_x() + rect.get_width()/2, h),
                                      xytext=(0,3), textcoords="offset points", ha='center', va='bottom', fontsize=8, fontweight='bold')

        self._ax.set_xticks(x)
        self._ax.set_xticklabels(all_years)
        self._ax.legend(title="Familles (Pression)")
        self._ax.grid(axis='y', linestyle='--', alpha=0.5)
        self._fig.tight_layout()
        self._canvas.draw()

    def _on_chart_click(self, event) -> None:
        if event.inaxes != self._ax: return
        for rect, year, fam in self._rects_map:
            contains, _ = rect.contains(event)
            if contains:
                self._show_detail(year, fam); break

    def _show_detail(self, year: str, family: str) -> None:
        # On filtre la LISTE UNIQUE DE VÉRITÉ
        rows = [d for d in self._all_relevant_data if d["year"] == year and d["family"] == family]
        cols = ["Commande", "Article", "Tiers", "Raison sociale", "Qté", "Date", "Source"]
        
        self._detail_label.setText(f"Détail {family} en {year} : {len(rows)} lignes (Somme Qté = {sum(d['qty'] for d in rows):g})")
        self._detail_table.setColumnCount(len(cols))
        self._detail_table.setHorizontalHeaderLabels(cols)
        self._detail_table.setRowCount(len(rows))
        for r, d in enumerate(rows):
            vals = [d["commande"], d["article"], d["tiers"], d["rs"], d["qty"], d["raw_date"], d["source"]]
            for c, v in enumerate(vals):
                self._detail_table.setItem(r, c, QTableWidgetItem(str(v) if v is not None else ""))
        self._detail_table.resizeColumnsToContents()
