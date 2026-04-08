from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from typing import Any, Optional

from sqlalchemy import text, Row
from sqlalchemy.engine import Engine
from sqlalchemy.exc import SQLAlchemyError

from app.database_manager import DatabaseManager


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


class RMRepository:
    """
    Repository pour la gestion des exigences (Requirements Management).
    Implémente le schéma ISO 29148 + OSLC RM + ReqIF.
    """

    def __init__(self, db: DatabaseManager) -> None:
        self._db = db

    def migrate(self, project_code: str) -> tuple[bool, str]:
        """
        Initialise le schéma rm_* dans la base de données.
        """
        engine = self._db.engine
        if engine is None:
            return False, "Aucun engine configuré."

        sql_script = """
        -- 1) Tables de référence
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

        -- 2) Configuration du projet
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

        -- 3) Exigences
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

        CREATE INDEX IF NOT EXISTS idx_rm_requirement_kind ON rm_requirement(kind_id);
        CREATE INDEX IF NOT EXISTS idx_rm_requirement_status ON rm_requirement(status_id);
        CREATE INDEX IF NOT EXISTS idx_rm_requirement_project_domain ON rm_requirement(project_code, domain_code);

        -- 4) Historique des versions
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

        CREATE UNIQUE INDEX IF NOT EXISTS uq_rm_requirement_version_label ON rm_requirement_version(requirement_id, version_label);
        CREATE INDEX IF NOT EXISTS idx_rm_requirement_version_current ON rm_requirement_version(requirement_id, is_current);

        -- 5) Traçabilité et Collections
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
        """

        try:
            with engine.connect() as conn:
                # Exécution du script de création des tables
                for statement in sql_script.split(";"):
                    if statement.strip():
                        conn.execute(text(statement))
                
                # Naming rule
                now = utc_now_iso()
                conn.execute(
                    text("""
                    INSERT INTO rm_naming_rule(project_code, prefix, separator, seq_padding, version_scheme, created_at, updated_at)
                    VALUES (:proj, 'REQ', '-', 4, 'major.minor', :now, :now)
                    ON CONFLICT(project_code) DO UPDATE SET updated_at = excluded.updated_at
                    """),
                    {"proj": project_code, "now": now}
                )

                self._seed_reference_tables(conn)
                conn.commit()

            return True, "Migration RM réussie."
        except Exception as e:
            return False, f"Erreur de migration RM : {e}"

    def _seed_reference_tables(self, conn: Any) -> None:
        """Remplit les tables de référence (kinds, quality classes, statuses, etc.)."""
        # (Les données de seed sont identiques à celles de rm_sqlite_app.py)
        
        # Kinds
        kinds = [
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
        for c, s, l, d in kinds:
            conn.execute(
                text("INSERT INTO rm_requirement_kind(code, short_code, label, description) VALUES (:c, :s, :l, :d) ON CONFLICT(code) DO NOTHING"),
                {"c": c, "s": s, "l": l, "d": d}
            )

        # Quality classes
        qclasses = [
            ("functional_suitability", "FSU", "Adéquation fonctionnelle", "Couverture correcte des fonctions attendues."),
            ("performance_efficiency", "PER", "Efficience de performance", "Temps, ressources, capacité."),
            ("compatibility", "COM", "Compatibilité", "Interopérabilité et coexistence."),
            ("usability", "USA", "Utilisabilité", "Ergonomie et facilité d'utilisation."),
            ("reliability", "REL", "Fiabilité", "Disponibilité, tolérance aux fautes, maturité."),
            ("security", "SEC", "Sécurité", "Confidentialité, intégrité, traçabilité, authenticité."),
            ("maintainability", "MAI", "Maintenabilité", "Testabilité, modularité, analysabilité."),
            ("portability", "POR", "Portabilité", "Adaptation à divers environnements."),
        ]
        for c, s, l, d in qclasses:
            conn.execute(
                text("INSERT INTO rm_quality_class(code, short_code, label, description) VALUES (:c, :s, :l, :d) ON CONFLICT(code) DO NOTHING"),
                {"c": c, "s": s, "l": l, "d": d}
            )

        # Statuses
        statuses = [
            ("draft", "Brouillon", 0),
            ("proposed", "Proposée", 0),
            ("approved", "Approuvée", 0),
            ("implemented", "Implémentée", 0),
            ("verified", "Vérifiée", 1),
            ("rejected", "Rejetée", 1),
            ("obsolete", "Obsolète", 1),
        ]
        for c, l, cl in statuses:
            conn.execute(
                text("INSERT INTO rm_status(code, label, is_closed) VALUES (:c, :l, :cl) ON CONFLICT(code) DO NOTHING"),
                {"c": c, "l": l, "cl": cl}
            )

        # Verification methods
        vmethods = [
            ("test", "TST", "Test", "Vérification par essai ou test."),
            ("analysis", "ANL", "Analyse", "Vérification par analyse."),
            ("inspection", "INSP", "Inspection", "Vérification par inspection."),
            ("demonstration", "DEMO", "Démonstration", "Vérification par démonstration."),
        ]
        for c, s, l, d in vmethods:
            conn.execute(
                text("INSERT INTO rm_verification_method(code, short_code, label, description) VALUES (:c, :s, :l, :d) ON CONFLICT(code) DO NOTHING"),
                {"c": c, "s": s, "l": l, "d": d}
            )

    def get_naming_rule(self, project_code: str) -> Optional[dict[str, Any]]:
        engine = self._db.engine
        if engine is None: return None
        with engine.connect() as conn:
            row = conn.execute(
                text("SELECT * FROM rm_naming_rule WHERE project_code = :p"),
                {"p": project_code}
            ).fetchone()
            return dict(row._mapping) if row else None

    def get_next_sequence_value(self, sequence_key: str) -> int:
        engine = self._db.engine
        if engine is None: return 0
        with engine.connect() as conn:
            row = conn.execute(
                text("SELECT current_value FROM rm_sequence WHERE sequence_key = :k"),
                {"k": sequence_key}
            ).fetchone()
            
            now = utc_now_iso()
            if row is None:
                conn.execute(
                    text("INSERT INTO rm_sequence(sequence_key, current_value, updated_at) VALUES (:k, 1, :n)"),
                    {"k": sequence_key, "n": now}
                )
                conn.commit()
                return 1
            
            next_val = int(row[0]) + 1
            conn.execute(
                text("UPDATE rm_sequence SET current_value = :v, updated_at = :n WHERE sequence_key = :k"),
                {"v": next_val, "n": now, "k": sequence_key}
            )
            conn.commit()
            return next_val

    def list_requirements(self, project_code: str) -> list[dict[str, Any]]:
        engine = self._db.engine
        if engine is None: return []
        with engine.connect() as conn:
            rows = conn.execute(
                text("SELECT * FROM rm_requirement WHERE project_code = :p AND is_deleted = 0 ORDER BY req_key"),
                {"p": project_code}
            ).fetchall()
            return [dict(r._mapping) for r in rows]

    def create_requirement(self, data: dict[str, Any]) -> str:
        engine = self._db.engine
        if engine is None: raise ValueError("Engine non configuré")
        
        now = utc_now_iso()
        data["uuid"] = str(uuid.uuid4())
        data["created_at"] = now
        data["updated_at"] = now
        
        # On extrait les IDs des codes si fournis
        with engine.connect() as conn:
            # On insère l'exigence
            cols = ", ".join(data.keys())
            placeholders = ", ".join([f":{k}" for k in data.keys()])
            conn.execute(text(f"INSERT INTO rm_requirement ({cols}) VALUES ({placeholders})"), data)
            
            # On récupère l'ID pour la version
            req_id = conn.execute(text("SELECT last_insert_rowid()")).scalar()
            
            # Version initiale
            snapshot = {k: v for k, v in data.items() if k not in ("uuid", "req_key", "created_at", "updated_at")}
            conn.execute(
                text("""
                INSERT INTO rm_requirement_version(requirement_id, version_major, version_minor, version_label, change_type, change_summary, snapshot_json, created_at, created_by, is_current)
                VALUES (:rid, 1, 0, '1.0', 'initial', 'Création initiale', :snap, :now, :auth, 1)
                """),
                {"rid": req_id, "snap": json.dumps(snapshot, ensure_ascii=False), "now": now, "auth": data.get("author")}
            )
            conn.commit()
            return str(data["req_key"])
