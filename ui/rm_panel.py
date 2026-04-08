from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QMessageBox,
    QSplitter,
    QHeaderView,
)

from services.rm_service import RMService


class RMPanel(QWidget):
    """
    Panneau de gestion des exigences (Requirements Management).
    """

    def __init__(self, service: RMService, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._service = service
        self._project_code = "INNOVATION"  # Code par défaut, pourrait être dynamique

        # ---------- Toolbar ----------
        self._search_edit = QLineEdit()
        self._search_edit.setPlaceholderText("Rechercher dans les exigences...")
        self._search_edit.textChanged.connect(self._on_search_changed)

        self._init_btn = QPushButton("Initialiser RM")
        self._init_btn.setToolTip("Crée les tables RM et configure le projet.")
        self._init_btn.clicked.connect(self._on_initialize)

        self._reload_btn = QPushButton("Recharger")
        self._reload_btn.clicked.connect(self.reload_all)

        # ---------- Table ----------
        self._table = QTableWidget(0, 6)
        self._table.setHorizontalHeaderLabels([
            "Clé", "Titre", "Type", "Statut", "Version", "Mis à jour"
        ])
        self._table.setEditTriggers(QTableWidget.NoEditTriggers)
        self._table.setSelectionBehavior(QTableWidget.SelectRows)
        self._table.setSelectionMode(QTableWidget.SingleSelection)
        self._table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)

        # ---------- Layout ----------
        root = QVBoxLayout(self)

        toolbar = QHBoxLayout()
        toolbar.addWidget(QLabel("Projet:"))
        self._proj_label = QLabel(self._project_code)
        self._proj_label.setStyleSheet("font-weight: bold;")
        toolbar.addWidget(self._proj_label)
        toolbar.addSpacing(20)
        toolbar.addWidget(self._search_edit)
        toolbar.addStretch()
        toolbar.addWidget(self._init_btn)
        toolbar.addWidget(self._reload_btn)

        root.addLayout(toolbar)

        self._splitter = QSplitter(Qt.Vertical)
        self._splitter.addWidget(self._table)
        
        # Placeholder pour les détails
        self._details_widget = QWidget()
        details_layout = QVBoxLayout(self._details_widget)
        details_layout.addWidget(QLabel("Détails de l'exigence sélectionnée (à venir)"))
        self._splitter.addWidget(self._details_widget)
        
        root.addWidget(self._splitter)

        self.reload_all()

    def reload_all(self) -> None:
        """Charge la liste des exigences depuis le service."""
        try:
            reqs = self._service.list_requirements(self._project_code)
            self._render_table(reqs)
        except Exception as e:
            # Si les tables n'existent pas, on affiche un message dans la table
            self._table.setRowCount(0)
            print(f"Erreur reload RM: {e}")

    def _render_table(self, reqs: list[dict]) -> None:
        self._table.setRowCount(len(reqs))
        for i, r in enumerate(reqs):
            self._table.setItem(i, 0, QTableWidgetItem(str(r.get("req_key", ""))))
            self._table.setItem(i, 1, QTableWidgetItem(str(r.get("title", ""))))
            self._table.setItem(i, 2, QTableWidgetItem(str(r.get("kind_id", "")))) # TODO: Résoudre libellé
            self._table.setItem(i, 3, QTableWidgetItem(str(r.get("status_id", "")))) # TODO: Résoudre libellé
            self._table.setItem(i, 4, QTableWidgetItem(str(r.get("version_label", ""))))
            self._table.setItem(i, 5, QTableWidgetItem(str(r.get("updated_at", ""))))
        
        self._table.resizeColumnsToContents()
        self._table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)

    def _on_initialize(self) -> None:
        reply = QMessageBox.question(
            self, "Initialisation RM",
            f"Voulez-vous initialiser le module Requirements Management pour le projet '{self._project_code}' ?\n"
            "Cela créera les tables rm_* nécessaires.",
            QMessageBox.Yes | QMessageBox.No
        )
        if reply == QMessageBox.Yes:
            ok, msg = self._service.initialize_project(self._project_code)
            if ok:
                QMessageBox.information(self, "Succès", msg)
                self.reload_all()
            else:
                QMessageBox.critical(self, "Erreur", msg)

    def _on_search_changed(self, text: str) -> None:
        # Filtrage simple côté client pour commencer
        for i in range(self._table.rowCount()):
            match = False
            for j in range(self._table.columnCount()):
                item = self._table.item(i, j)
                if item and text.lower() in item.text().lower():
                    match = True
                    break
            self._table.setRowHidden(i, not match)
