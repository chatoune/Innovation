#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Application SQLite3 de gestion d'exigences
==========================================

But
---
Ajouter à une base SQLite3 existante :
- une règle de nommage des exigences,
- une gestion de version,
- le schéma minimal de gestion d'exigences,
- quelques commandes CLI pour créer et réviser des exigences.

Convention de nommage proposée
------------------------------
Format :
    REQ-<PROJET>-<DOMAINE>-<TYPE>-<NNNN>

Exemples :
    REQ-MONPROJ-SYS-FNC-0001
    REQ-MONPROJ-HMI-INT-0007
    REQ-MONPROJ-SAF-CST-0012

Signification :
- REQ      : préfixe fixe "requirement"
- PROJET   : code projet court, ex. MONPROJ
- DOMAINE  : code domaine/sous-système, ex. SYS, HMI, ELE, SW, MEC, SAF
- TYPE     : code du type d'exigence, ex. FNC, NFR, INT, CST, OPE, REG
- NNNN     : compteur séquentiel par combinaison PROJET+DOMAINE+TYPE

Règles :
- lettres majuscules, chiffres et underscore uniquement
- pas d'espace ni accent
- identifiant lisible et stable
- l'identifiant ne change jamais, même si l'exigence évolue

Gestion de version proposée
---------------------------
Chaque exigence possède :
- un identifiant stable : req_key
- une version de contenu : major.minor

Règles :
- version majeure +1 :
    changement de sens, de périmètre, de critère d'acceptation,
    de méthode de vérification, ou modification nécessitant revalidation
- version mineure +1 :
    reformulation, précision, correction éditoriale, amélioration de clarté
    sans changement d'intention métier

Exemples :
- 1.0 : création initiale
- 1.1 : reformulation sans changement de fond
- 2.0 : ajout d'une contrainte fonctionnelle importante

Utilisation
-----------
1) Initialiser / migrer la base :
    python rm_sqlite_app.py migrate --db chemin/vers/base.db --project MONPROJ

2) Créer une exigence :
    python rm_sqlite_app.py create \
        --db chemin/vers/base.db \
        --project MONPROJ \
        --domain SYS \
        --kind functional \
        --title "Le système doit démarrer en moins de 5 secondes" \
        --text "Le système doit atteindre l'état opérationnel en moins de 5 secondes après mise sous tension." \
        --author "E. Dupont" \
        --owner "Equipe système" \
        --source "CDC v1.2"

3) Réviser une exigence :
    python rm_sqlite_app.py revise \
        --db chemin/vers/base.db \
        --req-key REQ-MONPROJ-SYS-FNC-0001 \
        --change-type minor \
        --summary "Précision du texte" \
        --text "Le système doit atteindre l'état opérationnel en moins de 5 secondes après mise sous tension nominale." \
        --author "E. Dupont"

4) Afficher une exigence :
    python rm_sqlite_app.py show --db chemin/vers/base.db --req-key REQ-MONPROJ-SYS-FNC-0001
"""

from __future__ import annotations

import argparse
import json
import re
import sqlite3
import sys
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

APP_VERSION = "1.0.0"


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def slug_code(value: str, max_len: int = 12) -> str:
    """
    Normalise un code pour les identifiants :
    - majuscules
    - A-Z, 0-9, underscore
    """
    value = (value or "").strip().upper()
    value = value.replace("-", "_").replace(" ", "_")
    value = re.sub(r"[^A-Z0-9_]", "", value)
    value = re.sub(r"_+", "_", value).strip("_")
    return value[:max_len]


@dataclass
class RequirementSnapshot:
    title: str
    text_content: str
    rationale: Optional[str]
    source: Optional[str]
    source_reference: Optional[str]
    kind_id: Optional[int]
    quality_class_id: Optional[int]
    status_id: Optional[int]
    verification_method_id: Optional[int]
    priority: Optional[int]
    criticality: Optional[int]
    maturity: Optional[int]
    stability: Optional[int]
    owner: Optional[str]
    author: Optional[str]


class RMDatabase:
    def __init__(self, db_path: str) -> None:
        self.db_path = db_path

    def connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON;")
        return conn

    def migrate(self, project_code: str) -> None:
        project_code = slug_code(project_code, 20)
        if not project_code:
            raise ValueError("Le code projet est obligatoire.")

        with self.connect() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS rm_requirement_kind (
                    id              INTEGER PRIMARY KEY,
                    code            TEXT NOT NULL UNIQUE,
                    short_code      TEXT NOT NULL UNIQUE,
                    label           TEXT NOT NULL,
                    description     TEXT
                );

                CREATE TABLE IF NOT EXISTS rm_quality_class (
                    id              INTEGER PRIMARY KEY,
                    code            TEXT NOT NULL UNIQUE,
                    short_code      TEXT NOT NULL UNIQUE,
                    label           TEXT NOT NULL,
                    description     TEXT
                );

                CREATE TABLE IF NOT EXISTS rm_status (
                    id              INTEGER PRIMARY KEY,
                    code            TEXT NOT NULL UNIQUE,
                    label           TEXT NOT NULL,
                    is_closed       INTEGER NOT NULL DEFAULT 0 CHECK (is_closed IN (0,1))
                );

                CREATE TABLE IF NOT EXISTS rm_verification_method (
                    id              INTEGER PRIMARY KEY,
                    code            TEXT NOT NULL UNIQUE,
                    short_code      TEXT NOT NULL UNIQUE,
                    label           TEXT NOT NULL,
                    description     TEXT
                );

                CREATE TABLE IF NOT EXISTS rm_relation_type (
                    id              INTEGER PRIMARY KEY,
                    code            TEXT NOT NULL UNIQUE,
                    label           TEXT NOT NULL,
                    description     TEXT,
                    inverse_code    TEXT
                );

                CREATE TABLE IF NOT EXISTS rm_naming_rule (
                    id                  INTEGER PRIMARY KEY,
                    project_code        TEXT NOT NULL UNIQUE,
                    prefix              TEXT NOT NULL DEFAULT 'REQ',
                    separator           TEXT NOT NULL DEFAULT '-',
                    seq_padding         INTEGER NOT NULL DEFAULT 4 CHECK (seq_padding BETWEEN 3 AND 8),
                    version_scheme      TEXT NOT NULL DEFAULT 'major.minor',
                    created_at          TEXT NOT NULL,
                    updated_at          TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS rm_sequence (
                    id                  INTEGER PRIMARY KEY,
                    sequence_key        TEXT NOT NULL UNIQUE,
                    current_value       INTEGER NOT NULL DEFAULT 0,
                    updated_at          TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS rm_requirement (
                    id                      INTEGER PRIMARY KEY,
                    uuid                    TEXT NOT NULL UNIQUE,
                    req_key                 TEXT NOT NULL UNIQUE,
                    project_code            TEXT NOT NULL,
                    domain_code             TEXT NOT NULL,
                    title                   TEXT NOT NULL,
                    text_content            TEXT NOT NULL,
                    rationale               TEXT,
                    source                  TEXT,
                    source_reference        TEXT,

                    kind_id                 INTEGER,
                    quality_class_id        INTEGER,
                    status_id               INTEGER,
                    verification_method_id  INTEGER,

                    priority                INTEGER CHECK (priority BETWEEN 1 AND 5),
                    criticality             INTEGER CHECK (criticality BETWEEN 1 AND 5),
                    maturity                INTEGER CHECK (maturity BETWEEN 1 AND 5),
                    stability               INTEGER CHECK (stability BETWEEN 1 AND 5),

                    owner                   TEXT,
                    author                  TEXT,

                    version_major           INTEGER NOT NULL DEFAULT 1,
                    version_minor           INTEGER NOT NULL DEFAULT 0,
                    version_label           TEXT NOT NULL DEFAULT '1.0',
                    change_summary          TEXT NOT NULL DEFAULT 'Création initiale',

                    is_baselined            INTEGER NOT NULL DEFAULT 0 CHECK (is_baselined IN (0,1)),
                    is_deleted              INTEGER NOT NULL DEFAULT 0 CHECK (is_deleted IN (0,1)),

                    created_at              TEXT NOT NULL,
                    updated_at              TEXT NOT NULL,

                    FOREIGN KEY (kind_id) REFERENCES rm_requirement_kind(id),
                    FOREIGN KEY (quality_class_id) REFERENCES rm_quality_class(id),
                    FOREIGN KEY (status_id) REFERENCES rm_status(id),
                    FOREIGN KEY (verification_method_id) REFERENCES rm_verification_method(id)
                );

                CREATE INDEX IF NOT EXISTS idx_rm_requirement_kind
                    ON rm_requirement(kind_id);

                CREATE INDEX IF NOT EXISTS idx_rm_requirement_status
                    ON rm_requirement(status_id);

                CREATE INDEX IF NOT EXISTS idx_rm_requirement_project_domain
                    ON rm_requirement(project_code, domain_code);

                CREATE TABLE IF NOT EXISTS rm_requirement_version (
                    id                      INTEGER PRIMARY KEY,
                    requirement_id          INTEGER NOT NULL,
                    version_major           INTEGER NOT NULL,
                    version_minor           INTEGER NOT NULL,
                    version_label           TEXT NOT NULL,
                    change_type             TEXT NOT NULL CHECK (change_type IN ('major','minor','initial')),
                    change_summary          TEXT NOT NULL,
                    snapshot_json           TEXT NOT NULL,
                    created_at              TEXT NOT NULL,
                    created_by              TEXT,
                    is_current              INTEGER NOT NULL DEFAULT 1 CHECK (is_current IN (0,1)),

                    FOREIGN KEY (requirement_id) REFERENCES rm_requirement(id) ON DELETE CASCADE
                );

                CREATE UNIQUE INDEX IF NOT EXISTS uq_rm_requirement_version_label
                    ON rm_requirement_version(requirement_id, version_label);

                CREATE INDEX IF NOT EXISTS idx_rm_requirement_version_current
                    ON rm_requirement_version(requirement_id, is_current);

                CREATE TABLE IF NOT EXISTS rm_requirement_relation (
                    id                      INTEGER PRIMARY KEY,
                    source_requirement_id   INTEGER NOT NULL,
                    target_requirement_id   INTEGER NOT NULL,
                    relation_type_id        INTEGER NOT NULL,
                    rationale               TEXT,
                    sort_order              INTEGER,
                    created_at              TEXT NOT NULL,

                    FOREIGN KEY (source_requirement_id) REFERENCES rm_requirement(id) ON DELETE CASCADE,
                    FOREIGN KEY (target_requirement_id) REFERENCES rm_requirement(id) ON DELETE CASCADE,
                    FOREIGN KEY (relation_type_id) REFERENCES rm_relation_type(id),
                    CHECK (source_requirement_id <> target_requirement_id)
                );

                CREATE UNIQUE INDEX IF NOT EXISTS uq_rm_requirement_relation
                    ON rm_requirement_relation(source_requirement_id, target_requirement_id, relation_type_id);

                CREATE TABLE IF NOT EXISTS rm_collection (
                    id                  INTEGER PRIMARY KEY,
                    uuid                TEXT NOT NULL UNIQUE,
                    collection_key      TEXT NOT NULL UNIQUE,
                    title               TEXT NOT NULL,
                    description         TEXT,
                    kind                TEXT NOT NULL DEFAULT 'requirement_collection',
                    created_at          TEXT NOT NULL,
                    updated_at          TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS rm_collection_item (
                    id                  INTEGER PRIMARY KEY,
                    collection_id       INTEGER NOT NULL,
                    requirement_id      INTEGER NOT NULL,
                    parent_item_id      INTEGER,
                    sort_order          INTEGER NOT NULL DEFAULT 0,
                    chapter_number      TEXT,
                    is_heading_only     INTEGER NOT NULL DEFAULT 0 CHECK (is_heading_only IN (0,1)),
                    FOREIGN KEY (collection_id) REFERENCES rm_collection(id) ON DELETE CASCADE,
                    FOREIGN KEY (requirement_id) REFERENCES rm_requirement(id) ON DELETE CASCADE,
                    FOREIGN KEY (parent_item_id) REFERENCES rm_collection_item(id) ON DELETE CASCADE
                );

                CREATE UNIQUE INDEX IF NOT EXISTS uq_rm_collection_item
                    ON rm_collection_item(collection_id, requirement_id);

                CREATE TABLE IF NOT EXISTS rm_attribute_definition (
                    id                  INTEGER PRIMARY KEY,
                    code                TEXT NOT NULL UNIQUE,
                    label               TEXT NOT NULL,
                    data_type           TEXT NOT NULL CHECK (
                                            data_type IN ('text','xhtml','integer','real','boolean','date','enum')
                                        ),
                    applies_to          TEXT NOT NULL DEFAULT 'requirement' CHECK (
                                            applies_to IN ('requirement','collection','relation')
                                        ),
                    is_required         INTEGER NOT NULL DEFAULT 0 CHECK (is_required IN (0,1)),
                    is_multivalue       INTEGER NOT NULL DEFAULT 0 CHECK (is_multivalue IN (0,1)),
                    enum_values_json    TEXT,
                    description         TEXT
                );

                CREATE TABLE IF NOT EXISTS rm_requirement_attribute_value (
                    id                      INTEGER PRIMARY KEY,
                    requirement_id          INTEGER NOT NULL,
                    attribute_definition_id INTEGER NOT NULL,
                    value_text              TEXT,
                    value_integer           INTEGER,
                    value_real              REAL,
                    value_boolean           INTEGER CHECK (value_boolean IN (0,1)),
                    value_date              TEXT,
                    FOREIGN KEY (requirement_id) REFERENCES rm_requirement(id) ON DELETE CASCADE,
                    FOREIGN KEY (attribute_definition_id) REFERENCES rm_attribute_definition(id) ON DELETE CASCADE
                );

                CREATE INDEX IF NOT EXISTS idx_rm_req_attr_req
                    ON rm_requirement_attribute_value(requirement_id);

                CREATE INDEX IF NOT EXISTS idx_rm_req_attr_def
                    ON rm_requirement_attribute_value(attribute_definition_id);
                """
            )

            now = utc_now_iso()
            conn.execute(
                """
                INSERT INTO rm_naming_rule(project_code, prefix, separator, seq_padding, version_scheme, created_at, updated_at)
                VALUES (?, 'REQ', '-', 4, 'major.minor', ?, ?)
                ON CONFLICT(project_code) DO UPDATE SET
                    updated_at = excluded.updated_at
                """,
                (project_code, now, now),
            )

            self._seed_reference_tables(conn)

    def _seed_reference_tables(self, conn: sqlite3.Connection) -> None:
        requirement_kinds = [
            ("stakeholder", "STK", "Exigence de partie prenante", "Besoin exprimé par une partie prenante."),
            ("business", "BUS", "Exigence métier", "Règle ou besoin métier."),
            ("system", "SYS", "Exigence système", "Exigence portant sur le système global."),
            ("subsystem", "SUB", "Exigence de sous-système", "Exigence portant sur un sous-système."),
            ("component", "CMP", "Exigence de composant", "Exigence portant sur un composant."),
            ("functional", "FNC", "Exigence fonctionnelle", "Fonction ou comportement attendu."),
            ("non_functional", "NFR", "Exigence non fonctionnelle", "Propriété de qualité ou contrainte de performance."),
            ("interface", "INT", "Exigence d'interface", "Interface HMI, logicielle, matérielle, réseau."),
            ("constraint", "CST", "Exigence de contrainte", "Restriction de conception ou contrainte imposée."),
            ("operational", "OPE", "Exigence opérationnelle", "Condition d'utilisation ou d'exploitation."),
            ("regulatory", "REG", "Exigence réglementaire", "Conformité à une loi, norme ou règlement."),
            ("verification", "VER", "Exigence de vérification", "Critère ou mécanisme de vérification."),
        ]
        conn.executemany(
            """
            INSERT INTO rm_requirement_kind(code, short_code, label, description)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(code) DO UPDATE SET
                short_code = excluded.short_code,
                label = excluded.label,
                description = excluded.description
            """,
            requirement_kinds,
        )

        quality_classes = [
            ("functional_suitability", "FSU", "Adéquation fonctionnelle", "Couverture correcte des fonctions attendues."),
            ("performance_efficiency", "PER", "Efficience de performance", "Temps, ressources, capacité."),
            ("compatibility", "COM", "Compatibilité", "Interopérabilité et coexistence."),
            ("usability", "USA", "Utilisabilité", "Ergonomie et facilité d'utilisation."),
            ("reliability", "REL", "Fiabilité", "Disponibilité, tolérance aux fautes, maturité."),
            ("security", "SEC", "Sécurité", "Confidentialité, intégrité, traçabilité, authenticité."),
            ("maintainability", "MAI", "Maintenabilité", "Testabilité, modularité, analysabilité."),
            ("portability", "POR", "Portabilité", "Adaptation à divers environnements."),
        ]
        conn.executemany(
            """
            INSERT INTO rm_quality_class(code, short_code, label, description)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(code) DO UPDATE SET
                short_code = excluded.short_code,
                label = excluded.label,
                description = excluded.description
            """,
            quality_classes,
        )

        statuses = [
            ("draft", "Brouillon", 0),
            ("proposed", "Proposée", 0),
            ("approved", "Approuvée", 0),
            ("implemented", "Implémentée", 0),
            ("verified", "Vérifiée", 1),
            ("rejected", "Rejetée", 1),
            ("obsolete", "Obsolète", 1),
        ]
        conn.executemany(
            """
            INSERT INTO rm_status(code, label, is_closed)
            VALUES (?, ?, ?)
            ON CONFLICT(code) DO UPDATE SET
                label = excluded.label,
                is_closed = excluded.is_closed
            """,
            statuses,
        )

        verification_methods = [
            ("test", "TST", "Test", "Vérification par essai ou test."),
            ("analysis", "ANL", "Analyse", "Vérification par analyse."),
            ("inspection", "INSP", "Inspection", "Vérification par inspection."),
            ("demonstration", "DEMO", "Démonstration", "Vérification par démonstration."),
        ]
        conn.executemany(
            """
            INSERT INTO rm_verification_method(code, short_code, label, description)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(code) DO UPDATE SET
                short_code = excluded.short_code,
                label = excluded.label,
                description = excluded.description
            """,
            verification_methods,
        )

        relation_types = [
            ("decomposes", "décompose", "Décomposition de l'exigence.", "decomposed_by"),
            ("decomposed_by", "est décomposée par", "Lien inverse de décomposition.", "decomposes"),
            ("elaborates", "élabore", "Affinage d'une exigence.", "elaborated_by"),
            ("elaborated_by", "est élaborée par", "Lien inverse d'affinage.", "elaborates"),
            ("satisfies", "satisfait", "Satisfaction par un élément lié.", "satisfied_by"),
            ("satisfied_by", "est satisfaite par", "Lien inverse de satisfaction.", "satisfies"),
            ("specified_by", "est spécifiée par", "Spécification par un artefact lié.", "specifies"),
            ("specifies", "spécifie", "Spécifie un autre artefact.", "specified_by"),
            ("validated_by", "est validée par", "Validation par essai ou preuve.", "validates"),
            ("validates", "valide", "Valide une exigence.", "validated_by"),
            ("implemented_by", "est implémentée par", "Implémentation par un artefact.", "implements"),
            ("implements", "implémente", "Implémente une exigence.", "implemented_by"),
            ("tracked_by", "est suivie par", "Suivi par un ticket, test ou item.", "tracks"),
            ("tracks", "suit", "Suit une exigence.", "tracked_by"),
            ("constrained_by", "est contrainte par", "Contrainte imposée par un autre élément.", "constrains"),
            ("constrains", "contraint", "Contraint une exigence.", "constrained_by"),
        ]
        conn.executemany(
            """
            INSERT INTO rm_relation_type(code, label, description, inverse_code)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(code) DO UPDATE SET
                label = excluded.label,
                description = excluded.description,
                inverse_code = excluded.inverse_code
            """,
            relation_types,
        )

    def _lookup_id(self, conn: sqlite3.Connection, table: str, code: Optional[str]) -> Optional[int]:
        if not code:
            return None
        row = conn.execute(f"SELECT id FROM {table} WHERE code = ?", (code,)).fetchone()
        if row is None:
            raise ValueError(f"Code inconnu dans {table}: {code}")
        return int(row["id"])

    def _lookup_kind_short_code(self, conn: sqlite3.Connection, kind_code: str) -> str:
        row = conn.execute(
            "SELECT short_code FROM rm_requirement_kind WHERE code = ?",
            (kind_code,),
        ).fetchone()
        if row is None:
            raise ValueError(f"Type d'exigence inconnu: {kind_code}")
        return str(row["short_code"])

    def _get_naming_rule(self, conn: sqlite3.Connection, project_code: str) -> sqlite3.Row:
        row = conn.execute(
            "SELECT * FROM rm_naming_rule WHERE project_code = ?",
            (project_code,),
        ).fetchone()
        if row is None:
            raise ValueError(
                f"Aucune règle de nommage trouvée pour le projet {project_code}. "
                f"Exécutez d'abord la commande migrate."
            )
        return row

    def _next_sequence_value(self, conn: sqlite3.Connection, sequence_key: str) -> int:
        now = utc_now_iso()
        row = conn.execute(
            "SELECT current_value FROM rm_sequence WHERE sequence_key = ?",
            (sequence_key,),
        ).fetchone()
        if row is None:
            conn.execute(
                "INSERT INTO rm_sequence(sequence_key, current_value, updated_at) VALUES (?, 1, ?)",
                (sequence_key, now),
            )
            return 1

        next_value = int(row["current_value"]) + 1
        conn.execute(
            "UPDATE rm_sequence SET current_value = ?, updated_at = ? WHERE sequence_key = ?",
            (next_value, now, sequence_key),
        )
        return next_value

    def generate_req_key(self, conn: sqlite3.Connection, project_code: str, domain_code: str, kind_code: str) -> str:
        project_code = slug_code(project_code, 20)
        domain_code = slug_code(domain_code, 12)
        if not project_code or not domain_code:
            raise ValueError("Les codes projet et domaine sont obligatoires.")

        naming_rule = self._get_naming_rule(conn, project_code)
        kind_short = self._lookup_kind_short_code(conn, kind_code)
        prefix = naming_rule["prefix"]
        separator = naming_rule["separator"]
        seq_padding = int(naming_rule["seq_padding"])

        sequence_key = f"{project_code}:{domain_code}:{kind_short}"
        seq_value = self._next_sequence_value(conn, sequence_key)
        req_key = separator.join(
            [
                prefix,
                project_code,
                domain_code,
                kind_short,
                str(seq_value).zfill(seq_padding),
            ]
        )
        return req_key

    def create_requirement(
        self,
        *,
        project_code: str,
        domain_code: str,
        kind_code: str,
        title: str,
        text_content: str,
        author: Optional[str],
        owner: Optional[str],
        source: Optional[str],
        source_reference: Optional[str],
        rationale: Optional[str],
        quality_code: Optional[str],
        status_code: str,
        verification_code: Optional[str],
        priority: Optional[int],
        criticality: Optional[int],
        maturity: Optional[int],
        stability: Optional[int],
    ) -> str:
        project_code = slug_code(project_code, 20)
        domain_code = slug_code(domain_code, 12)

        if not title.strip():
            raise ValueError("Le titre est obligatoire.")
        if not text_content.strip():
            raise ValueError("Le texte de l'exigence est obligatoire.")

        with self.connect() as conn:
            req_key = self.generate_req_key(conn, project_code, domain_code, kind_code)
            kind_id = self._lookup_id(conn, "rm_requirement_kind", kind_code)
            quality_id = self._lookup_id(conn, "rm_quality_class", quality_code)
            status_id = self._lookup_id(conn, "rm_status", status_code)
            verification_id = self._lookup_id(conn, "rm_verification_method", verification_code)

            now = utc_now_iso()
            req_uuid = str(uuid.uuid4())
            version_major = 1
            version_minor = 0
            version_label = f"{version_major}.{version_minor}"
            change_summary = "Création initiale"

            cur = conn.execute(
                """
                INSERT INTO rm_requirement(
                    uuid, req_key, project_code, domain_code,
                    title, text_content, rationale, source, source_reference,
                    kind_id, quality_class_id, status_id, verification_method_id,
                    priority, criticality, maturity, stability,
                    owner, author,
                    version_major, version_minor, version_label, change_summary,
                    created_at, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    req_uuid, req_key, project_code, domain_code,
                    title.strip(), text_content.strip(), rationale, source, source_reference,
                    kind_id, quality_id, status_id, verification_id,
                    priority, criticality, maturity, stability,
                    owner, author,
                    version_major, version_minor, version_label, change_summary,
                    now, now,
                ),
            )
            requirement_id = cur.lastrowid

            snapshot = {
                "title": title.strip(),
                "text_content": text_content.strip(),
                "rationale": rationale,
                "source": source,
                "source_reference": source_reference,
                "kind_id": kind_id,
                "quality_class_id": quality_id,
                "status_id": status_id,
                "verification_method_id": verification_id,
                "priority": priority,
                "criticality": criticality,
                "maturity": maturity,
                "stability": stability,
                "owner": owner,
                "author": author,
            }

            conn.execute(
                """
                INSERT INTO rm_requirement_version(
                    requirement_id, version_major, version_minor, version_label,
                    change_type, change_summary, snapshot_json, created_at, created_by, is_current
                )
                VALUES (?, ?, ?, ?, 'initial', ?, ?, ?, ?, 1)
                """,
                (
                    requirement_id,
                    version_major,
                    version_minor,
                    version_label,
                    change_summary,
                    json.dumps(snapshot, ensure_ascii=False, sort_keys=True),
                    now,
                    author,
                ),
            )
            return req_key

    def _get_requirement_row(self, conn: sqlite3.Connection, req_key: str) -> sqlite3.Row:
        row = conn.execute(
            "SELECT * FROM rm_requirement WHERE req_key = ? AND is_deleted = 0",
            (req_key,),
        ).fetchone()
        if row is None:
            raise ValueError(f"Exigence introuvable: {req_key}")
        return row

    def revise_requirement(
        self,
        *,
        req_key: str,
        change_type: str,
        summary: str,
        author: Optional[str],
        title: Optional[str],
        text_content: Optional[str],
        rationale: Optional[str],
        source: Optional[str],
        source_reference: Optional[str],
        quality_code: Optional[str],
        status_code: Optional[str],
        verification_code: Optional[str],
        priority: Optional[int],
        criticality: Optional[int],
        maturity: Optional[int],
        stability: Optional[int],
        owner: Optional[str],
    ) -> str:
        if change_type not in {"major", "minor"}:
            raise ValueError("change_type doit valoir 'major' ou 'minor'.")
        if not summary.strip():
            raise ValueError("Le résumé de changement est obligatoire.")

        with self.connect() as conn:
            row = self._get_requirement_row(conn, req_key)

            quality_id = row["quality_class_id"] if quality_code is None else self._lookup_id(conn, "rm_quality_class", quality_code)
            status_id = row["status_id"] if status_code is None else self._lookup_id(conn, "rm_status", status_code)
            verification_id = (
                row["verification_method_id"]
                if verification_code is None
                else self._lookup_id(conn, "rm_verification_method", verification_code)
            )

            current_major = int(row["version_major"])
            current_minor = int(row["version_minor"])

            if change_type == "major":
                new_major = current_major + 1
                new_minor = 0
            else:
                new_major = current_major
                new_minor = current_minor + 1

            new_version_label = f"{new_major}.{new_minor}"

            new_title = row["title"] if title is None else title.strip()
            new_text_content = row["text_content"] if text_content is None else text_content.strip()
            new_rationale = row["rationale"] if rationale is None else rationale
            new_source = row["source"] if source is None else source
            new_source_reference = row["source_reference"] if source_reference is None else source_reference
            new_priority = row["priority"] if priority is None else priority
            new_criticality = row["criticality"] if criticality is None else criticality
            new_maturity = row["maturity"] if maturity is None else maturity
            new_stability = row["stability"] if stability is None else stability
            new_owner = row["owner"] if owner is None else owner
            new_author = row["author"] if author is None else author

            now = utc_now_iso()

            conn.execute(
                "UPDATE rm_requirement_version SET is_current = 0 WHERE requirement_id = ?",
                (row["id"],),
            )

            conn.execute(
                """
                UPDATE rm_requirement
                SET title = ?,
                    text_content = ?,
                    rationale = ?,
                    source = ?,
                    source_reference = ?,
                    quality_class_id = ?,
                    status_id = ?,
                    verification_method_id = ?,
                    priority = ?,
                    criticality = ?,
                    maturity = ?,
                    stability = ?,
                    owner = ?,
                    author = ?,
                    version_major = ?,
                    version_minor = ?,
                    version_label = ?,
                    change_summary = ?,
                    updated_at = ?
                WHERE id = ?
                """,
                (
                    new_title,
                    new_text_content,
                    new_rationale,
                    new_source,
                    new_source_reference,
                    quality_id,
                    status_id,
                    verification_id,
                    new_priority,
                    new_criticality,
                    new_maturity,
                    new_stability,
                    new_owner,
                    new_author,
                    new_major,
                    new_minor,
                    new_version_label,
                    summary.strip(),
                    now,
                    row["id"],
                ),
            )

            snapshot = {
                "title": new_title,
                "text_content": new_text_content,
                "rationale": new_rationale,
                "source": new_source,
                "source_reference": new_source_reference,
                "kind_id": row["kind_id"],
                "quality_class_id": quality_id,
                "status_id": status_id,
                "verification_method_id": verification_id,
                "priority": new_priority,
                "criticality": new_criticality,
                "maturity": new_maturity,
                "stability": new_stability,
                "owner": new_owner,
                "author": new_author,
            }

            conn.execute(
                """
                INSERT INTO rm_requirement_version(
                    requirement_id, version_major, version_minor, version_label,
                    change_type, change_summary, snapshot_json, created_at, created_by, is_current
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 1)
                """,
                (
                    row["id"],
                    new_major,
                    new_minor,
                    new_version_label,
                    change_type,
                    summary.strip(),
                    json.dumps(snapshot, ensure_ascii=False, sort_keys=True),
                    now,
                    author,
                ),
            )

            return new_version_label

    def show_requirement(self, req_key: str) -> dict[str, Any]:
        with self.connect() as conn:
            row = self._get_requirement_row(conn, req_key)
            versions = conn.execute(
                """
                SELECT version_label, change_type, change_summary, created_at, created_by, is_current
                FROM rm_requirement_version
                WHERE requirement_id = ?
                ORDER BY version_major DESC, version_minor DESC
                """,
                (row["id"],),
            ).fetchall()

            return {
                "req_key": row["req_key"],
                "project_code": row["project_code"],
                "domain_code": row["domain_code"],
                "title": row["title"],
                "text_content": row["text_content"],
                "version_label": row["version_label"],
                "change_summary": row["change_summary"],
                "created_at": row["created_at"],
                "updated_at": row["updated_at"],
                "versions": [dict(v) for v in versions],
            }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Gestionnaire SQLite3 d'exigences avec règle de nommage et gestion de versions."
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {APP_VERSION}")

    subparsers = parser.add_subparsers(dest="command", required=True)

    p_migrate = subparsers.add_parser("migrate", help="Ajoute le schéma RM à une base SQLite existante.")
    p_migrate.add_argument("--db", required=True, help="Chemin vers la base SQLite.")
    p_migrate.add_argument("--project", required=True, help="Code projet, ex. MONPROJ.")

    p_create = subparsers.add_parser("create", help="Crée une nouvelle exigence.")
    p_create.add_argument("--db", required=True, help="Chemin vers la base SQLite.")
    p_create.add_argument("--project", required=True, help="Code projet.")
    p_create.add_argument("--domain", required=True, help="Code domaine, ex. SYS, HMI, SW.")
    p_create.add_argument("--kind", required=True, help="Code type d'exigence, ex. functional, interface.")
    p_create.add_argument("--title", required=True, help="Titre de l'exigence.")
    p_create.add_argument("--text", required=True, help="Texte complet de l'exigence.")
    p_create.add_argument("--author", help="Auteur.")
    p_create.add_argument("--owner", help="Responsable.")
    p_create.add_argument("--source", help="Source.")
    p_create.add_argument("--source-reference", help="Référence source.")
    p_create.add_argument("--rationale", help="Justification.")
    p_create.add_argument("--quality", help="Classe qualité, ex. performance_efficiency, security.")
    p_create.add_argument("--status", default="draft", help="Statut, ex. draft, proposed, approved.")
    p_create.add_argument("--verification", help="Méthode de vérification, ex. test, analysis.")
    p_create.add_argument("--priority", type=int, choices=range(1, 6), help="Priorité 1..5.")
    p_create.add_argument("--criticality", type=int, choices=range(1, 6), help="Criticité 1..5.")
    p_create.add_argument("--maturity", type=int, choices=range(1, 6), help="Maturité 1..5.")
    p_create.add_argument("--stability", type=int, choices=range(1, 6), help="Stabilité 1..5.")

    p_revise = subparsers.add_parser("revise", help="Crée une nouvelle version d'une exigence existante.")
    p_revise.add_argument("--db", required=True, help="Chemin vers la base SQLite.")
    p_revise.add_argument("--req-key", required=True, help="Identifiant de l'exigence.")
    p_revise.add_argument("--change-type", required=True, choices=["major", "minor"], help="Type de changement.")
    p_revise.add_argument("--summary", required=True, help="Résumé de changement.")
    p_revise.add_argument("--author", help="Auteur de la révision.")
    p_revise.add_argument("--title", help="Nouveau titre.")
    p_revise.add_argument("--text", help="Nouveau texte.")
    p_revise.add_argument("--rationale", help="Nouvelle justification.")
    p_revise.add_argument("--source", help="Nouvelle source.")
    p_revise.add_argument("--source-reference", help="Nouvelle référence source.")
    p_revise.add_argument("--quality", help="Nouvelle classe qualité.")
    p_revise.add_argument("--status", help="Nouveau statut.")
    p_revise.add_argument("--verification", help="Nouvelle méthode de vérification.")
    p_revise.add_argument("--priority", type=int, choices=range(1, 6), help="Nouvelle priorité 1..5.")
    p_revise.add_argument("--criticality", type=int, choices=range(1, 6), help="Nouvelle criticité 1..5.")
    p_revise.add_argument("--maturity", type=int, choices=range(1, 6), help="Nouvelle maturité 1..5.")
    p_revise.add_argument("--stability", type=int, choices=range(1, 6), help="Nouvelle stabilité 1..5.")
    p_revise.add_argument("--owner", help="Nouveau responsable.")

    p_show = subparsers.add_parser("show", help="Affiche une exigence et ses versions.")
    p_show.add_argument("--db", required=True, help="Chemin vers la base SQLite.")
    p_show.add_argument("--req-key", required=True, help="Identifiant de l'exigence.")

    return parser


def ensure_db_parent_exists(db_path: str) -> None:
    parent = Path(db_path).resolve().parent
    parent.mkdir(parents=True, exist_ok=True)


def main(argv: Optional[list[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    ensure_db_parent_exists(args.db)
    rm = RMDatabase(args.db)

    try:
        if args.command == "migrate":
            rm.migrate(project_code=args.project)
            print(f"[OK] Migration terminée pour la base : {args.db}")
            print(f"[OK] Règle de nommage activée pour le projet : {slug_code(args.project, 20)}")
            print("Format d'identifiant : REQ-<PROJET>-<DOMAINE>-<TYPE>-<NNNN>")
            print("Gestion de version : major.minor")
            return 0

        if args.command == "create":
            req_key = rm.create_requirement(
                project_code=args.project,
                domain_code=args.domain,
                kind_code=args.kind,
                title=args.title,
                text_content=args.text,
                author=args.author,
                owner=args.owner,
                source=args.source,
                source_reference=args.source_reference,
                rationale=args.rationale,
                quality_code=args.quality,
                status_code=args.status,
                verification_code=args.verification,
                priority=args.priority,
                criticality=args.criticality,
                maturity=args.maturity,
                stability=args.stability,
            )
            print(f"[OK] Exigence créée : {req_key}")
            print("Version initiale : 1.0")
            return 0

        if args.command == "revise":
            new_version = rm.revise_requirement(
                req_key=args.req_key,
                change_type=args.change_type,
                summary=args.summary,
                author=args.author,
                title=args.title,
                text_content=args.text,
                rationale=args.rationale,
                source=args.source,
                source_reference=args.source_reference,
                quality_code=args.quality,
                status_code=args.status,
                verification_code=args.verification,
                priority=args.priority,
                criticality=args.criticality,
                maturity=args.maturity,
                stability=args.stability,
                owner=args.owner,
            )
            print(f"[OK] Exigence mise à jour : {args.req_key}")
            print(f"[OK] Nouvelle version : {new_version}")
            return 0

        if args.command == "show":
            data = rm.show_requirement(args.req_key)
            print(json.dumps(data, ensure_ascii=False, indent=2))
            return 0

        parser.error("Commande inconnue.")
        return 2

    except Exception as exc:
        print(f"[ERREUR] {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
