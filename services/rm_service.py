from __future__ import annotations

import re
from typing import Any, Optional

from app.database_manager import DatabaseManager
from repositories.rm_repository import RMRepository


def slug_code(value: str, max_len: int = 12) -> str:
    value = (value or "").strip().upper()
    value = value.replace("-", "_").replace(" ", "_")
    value = re.sub(r"[^A-Z0-9_]", "", value)
    value = re.sub(r"_+", "_", value).strip("_")
    return value[:max_len]


class RMService:
    """
    Service métier pour la gestion des exigences.
    Assure la cohérence des identifiants et le cycle de vie (versioning).
    """

    def __init__(self, db: DatabaseManager) -> None:
        self._db = db
        self._repo = RMRepository(db)

    def initialize_project(self, project_code: str) -> tuple[bool, str]:
        """Initialise les tables et la règle de nommage pour un projet."""
        return self._repo.migrate(project_code)

    def list_requirements(self, project_code: str) -> list[dict[str, Any]]:
        return self._repo.list_requirements(project_code)

    def generate_next_key(self, project_code: str, domain_code: str, kind_code: str) -> str:
        """
        Génère la prochaine clé REQ-PROJ-DOM-KIND-NNNN.
        """
        rule = self._repo.get_naming_rule(project_code)
        if not rule:
            raise ValueError(f"Projet {project_code} non initialisé dans RM.")

        # On récupère le short_code du kind
        # Pour simplifier, on suppose que le repo ou une table de ref est accessible
        # Ici on va faire une requête directe via repo pour le short_code
        engine = self._db.engine
        kind_short = "UNK"
        if engine:
            with engine.connect() as conn:
                from sqlalchemy import text
                row = conn.execute(
                    text("SELECT short_code FROM rm_requirement_kind WHERE code = :c"),
                    {"c": kind_code}
                ).fetchone()
                if row:
                    kind_short = row[0]

        sequence_key = f"{project_code}:{domain_code}:{kind_short}"
        seq_value = self._repo.get_next_sequence_value(sequence_key)
        
        prefix = rule["prefix"]
        sep = rule["separator"]
        padding = rule["seq_padding"]
        
        return sep.join([
            prefix,
            slug_code(project_code, 20),
            slug_code(domain_code, 12),
            kind_short,
            str(seq_value).zfill(padding)
        ])

    def create_requirement(
        self,
        project_code: str,
        domain_code: str,
        kind_code: str,
        title: str,
        text_content: str,
        **kwargs
    ) -> str:
        """
        Crée une nouvelle exigence avec sa clé générée automatiquement.
        """
        req_key = self.generate_next_key(project_code, domain_code, kind_code)
        
        # Mapping des codes vers IDs
        engine = self._db.engine
        ids = {}
        if engine:
            with engine.connect() as conn:
                from sqlalchemy import text
                for table, key in [
                    ("rm_requirement_kind", kind_code),
                    ("rm_quality_class", kwargs.get("quality_code")),
                    ("rm_status", kwargs.get("status_code", "draft")),
                    ("rm_verification_method", kwargs.get("verification_code"))
                ]:
                    if key:
                        row = conn.execute(text(f"SELECT id FROM {table} WHERE code = :c"), {"c": key}).fetchone()
                        if row: ids[table.replace("rm_", "") + "_id"] = row[0]

        data = {
            "req_key": req_key,
            "project_code": project_code,
            "domain_code": domain_code,
            "title": title,
            "text_content": text_content,
            "author": kwargs.get("author"),
            "owner": kwargs.get("owner"),
            "source": kwargs.get("source"),
            "source_reference": kwargs.get("source_reference"),
            "rationale": kwargs.get("rationale"),
            "priority": kwargs.get("priority"),
            "criticality": kwargs.get("criticality"),
            "maturity": kwargs.get("maturity"),
            "stability": kwargs.get("stability"),
            **ids
        }
        
        return self._repo.create_requirement(data)
