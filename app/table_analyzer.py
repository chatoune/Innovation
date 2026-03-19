from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass
class ColumnInfo:
    name: str
    type_name: str
    nullable: bool | None
    primary_key: bool
    default: Any


@dataclass
class TableAnalysis:
    table_name: str
    exists: bool
    columns: list[ColumnInfo]
    primary_key_columns: list[str]
    editable_columns: list[str]
    display_columns: list[str]
    is_crud_compatible: bool
    message: str


class TableAnalyzer:
    """
    Interprète les métadonnées brutes d'une table pour décider
    si elle est exploitable dans une vue CRUD simple.
    """

    def analyze_table(self, table_name: str, raw_columns: list[dict[str, Any]]) -> TableAnalysis:
        if not table_name.strip():
            return TableAnalysis(
                table_name=table_name,
                exists=False,
                columns=[],
                primary_key_columns=[],
                editable_columns=[],
                display_columns=[],
                is_crud_compatible=False,
                message="Nom de table vide.",
            )

        if not raw_columns:
            return TableAnalysis(
                table_name=table_name,
                exists=False,
                columns=[],
                primary_key_columns=[],
                editable_columns=[],
                display_columns=[],
                is_crud_compatible=False,
                message="Aucune colonne détectée.",
            )

        columns: list[ColumnInfo] = []
        primary_key_columns: list[str] = []

        for raw_col in raw_columns:
            pk_raw = raw_col.get("primary_key", None)

            # Selon dialecte SQLAlchemy, ça peut être bool ou int
            if isinstance(pk_raw, bool):
                is_pk = pk_raw
            elif isinstance(pk_raw, int):
                is_pk = pk_raw > 0
            else:
                is_pk = False

            col = ColumnInfo(
                name=str(raw_col.get("name", "")),
                type_name=str(raw_col.get("type", "")),
                nullable=raw_col.get("nullable", None),
                primary_key=is_pk,
                default=raw_col.get("default", None),
            )

            columns.append(col)

            if is_pk:
                primary_key_columns.append(col.name)

        # Colonnes affichables : toutes les colonnes non vides
        display_columns = [c.name for c in columns if c.name]

        # Colonnes éditables : version simple
        # On exclut les colonnes PK, souvent auto-générées ou sensibles
        editable_columns = [c.name for c in columns if c.name and not c.primary_key]

        # Compatibilité CRUD simple :
        # - il faut au moins une clé primaire
        # - il faut au moins une colonne affichable
        # - il faut au moins une colonne éditable
        is_crud_compatible = (
            len(primary_key_columns) >= 1
            and len(display_columns) >= 1
            and len(editable_columns) >= 1
        )

        if not primary_key_columns:
            message = "Table sans clé primaire détectée : CRUD simple déconseillé."
        elif len(primary_key_columns) > 1:
            message = "Clé primaire composite détectée : CRUD possible mais plus complexe."
        elif is_crud_compatible:
            message = "Table compatible avec un CRUD simple."
        else:
            message = "Table partiellement exploitable, mais pas idéale pour CRUD simple."

        return TableAnalysis(
            table_name=table_name,
            exists=True,
            columns=columns,
            primary_key_columns=primary_key_columns,
            editable_columns=editable_columns,
            display_columns=display_columns,
            is_crud_compatible=is_crud_compatible,
            message=message,
        )