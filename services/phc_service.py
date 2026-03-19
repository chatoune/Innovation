from __future__ import annotations

import csv
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Optional

from sqlalchemy import inspect, text
from sqlalchemy.engine import Engine
from sqlalchemy.exc import SQLAlchemyError

from app.database_manager import DatabaseManager


@dataclass
class PHCFilters:
    date_column: str = ""
    years: list[str] | None = None
    family_root: str = ""
    subfamily: str = ""


@dataclass
class PageResult:
    columns: list[str]
    rows: list[list[Any]]
    message: str


@dataclass
class SeriesResult:
    labels: list[str]
    values: list[float]
    message: str


class PHCService:
    TABLE = "CDV_ALL"
    SOURCE_TABLE_VALUE = "CDV_PHC"
    RULES_TABLE = "phc_family_rules"

    COL_SOURCE = "source_table"
    COL_ARTICLE = "Article"
    COL_RS = "Raison sociale"
    COL_CDV = "Commande"

    COL_QTY = "Qté"
    COL_PRICE_NET = "Prix net"

    CALC_COL_ALIAS = "Montant_Qte_PrixNet"
    CALC_COL_HEADER = "Montant (Qté×Prix net)"

    # Sous-familles RDN
    RDN_SUB_BISTABLE = "Relais bistable"
    RDN_SUB_VW = "RDN V/W"
    RDN_SUB_OTHER = "RDN autres"

    # Sous-familles BXNE
    BXNE_SUB_ALIM = "Alimentations"
    BXNE_SUB_LINEAR = "Alimentations linéaires"

    # ---- Familles fusionnées ----
    FAMILY_MERGE_LABEL_BX_LTMNT = "BXLT/MT/NT(I)"
    FAMILY_MERGE_PREFIXES_BX_LTMNT = {"BXLT", "BXMT", "BXNT", "BXLTI", "BXMTI", "BXNTI"}

    FAMILY_MERGE_LABEL_BX_NRCPRV = "BXNR/C/P/RV"
    FAMILY_MERGE_PREFIXES_BX_NRCPRV = {"BXNR", "BXNRV", "BXNC", "BXNP"}

    FAMILY_MERGE_LABEL_BX_NAI = "BXNA(I)"
    FAMILY_MERGE_PREFIXES_BX_NAI_ROOTS = {"BXNA", "BXNAI"}
    FAMILY_MERGE_SUBPREFIXES_BX_NAI = {"BXNA1", "BXNAI2"}

    def __init__(self, db: DatabaseManager) -> None:
        self._db = db

    # ---------- Config stockée dans la base DATA ----------
    def config_ready(self) -> bool:
        engine = self._db.engine
        if engine is None:
            return False
        return self._table_exists(engine, self.RULES_TABLE)

    def get_all_rules_raw(self) -> list[dict[str, Any]]:
        engine = self._db.engine
        if engine is None or not self.config_ready():
            return []

        sql = text(
            f"SELECT family, subfamily, enabled, priority, "
            f"startswith_any, contains_any, not_startswith_any, not_contains_any "
            f"FROM {self._q(self.RULES_TABLE)} "
            f"ORDER BY priority DESC, family ASC, subfamily ASC, id ASC"
        )

        try:
            with engine.connect() as conn:
                rows = conn.execute(sql).fetchall()

            out: list[dict[str, Any]] = []
            for row in rows:
                out.append(
                    {
                        "family": "" if row[0] is None else str(row[0]).strip(),
                        "subfamily": "" if row[1] is None else str(row[1]).strip(),
                        "enabled": int(row[2] or 0),
                        "priority": int(row[3] or 0),
                        "criteria": {
                            "startswith_any": self._csv_to_list(row[4]),
                            "contains_any": self._csv_to_list(row[5]),
                            "not_startswith_any": self._csv_to_list(row[6]),
                            "not_contains_any": self._csv_to_list(row[7]),
                        },
                    }
                )
            return out
        except Exception:
            return []

    def export_bundle_json(self, filepath: str | Path, date_col: str) -> tuple[bool, str]:
        if not self.config_ready():
            return False, "Table de configuration PHC non disponible dans la base DATA."

        try:
            payload = {
                "date_column": (date_col or "").strip(),
                "rules": self.get_all_rules_raw(),
            }

            out_path = Path(filepath)
            out_path.write_text(
                json.dumps(payload, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            return True, f"Bundle JSON exporté : {out_path}"
        except Exception as e:
            return False, f"Erreur export bundle JSON : {e}"

    def import_bundle_json(self, filepath: str | Path) -> tuple[bool, str]:
        engine = self._db.engine
        if engine is None:
            return False, "Aucune base DATA configurée."
        if not self.config_ready():
            return False, "Table de configuration PHC non disponible dans la base DATA."

        try:
            src = Path(filepath)
            data = json.loads(src.read_text(encoding="utf-8"))
            if not isinstance(data, dict):
                return False, "Le fichier JSON doit contenir un objet racine."

            rules = data.get("rules", [])
            if rules is None:
                rules = []
            if not isinstance(rules, list):
                return False, "Le champ 'rules' doit être une liste."

            cleaned_rules: list[dict[str, Any]] = []
            for rule in rules:
                if not isinstance(rule, dict):
                    continue
                cleaned_rules.append(
                    {
                        "family": str(rule.get("family", "")).strip(),
                        "subfamily": str(rule.get("subfamily", "")).strip(),
                        "enabled": int(rule.get("enabled", 1) or 0),
                        "priority": int(rule.get("priority", 0) or 0),
                        "criteria": self._normalize_criteria(rule.get("criteria", {})),
                    }
                )

            delete_sql = text(f"DELETE FROM {self._q(self.RULES_TABLE)}")
            insert_sql = text(
                f"INSERT INTO {self._q(self.RULES_TABLE)} "
                f"(family, subfamily, enabled, priority, startswith_any, contains_any, not_startswith_any, not_contains_any) "
                f"VALUES (:family, :subfamily, :enabled, :priority, :startswith_any, :contains_any, :not_startswith_any, :not_contains_any)"
            )

            with engine.begin() as conn:
                conn.execute(delete_sql)
                for rule in cleaned_rules:
                    criteria = rule["criteria"]
                    conn.execute(
                        insert_sql,
                        {
                            "family": rule["family"],
                            "subfamily": rule["subfamily"],
                            "enabled": rule["enabled"],
                            "priority": rule["priority"],
                            "startswith_any": self._list_to_csv(criteria.get("startswith_any", [])),
                            "contains_any": self._list_to_csv(criteria.get("contains_any", [])),
                            "not_startswith_any": self._list_to_csv(criteria.get("not_startswith_any", [])),
                            "not_contains_any": self._list_to_csv(criteria.get("not_contains_any", [])),
                        },
                    )

            return True, f"Bundle JSON importé : {src}"
        except json.JSONDecodeError as e:
            return False, f"JSON invalide : {e}"
        except Exception as e:
            return False, f"Erreur import bundle JSON : {e}"

    @staticmethod
    def _normalize_criteria(criteria: Any) -> dict[str, list[str]]:
        if not isinstance(criteria, dict):
            criteria = {}

        def _norm_list(name: str) -> list[str]:
            value = criteria.get(name, [])
            if value is None:
                return []
            if isinstance(value, str):
                value = [v.strip() for v in value.split(",")]
            if not isinstance(value, list):
                return []
            return [str(v).strip() for v in value if str(v).strip()]

        return {
            "startswith_any": _norm_list("startswith_any"),
            "contains_any": _norm_list("contains_any"),
            "not_startswith_any": _norm_list("not_startswith_any"),
            "not_contains_any": _norm_list("not_contains_any"),
        }

    @staticmethod
    def _csv_to_list(value: Any) -> list[str]:
        raw = "" if value is None else str(value)
        if not raw.strip():
            return []
        return [item.strip() for item in raw.split(",") if item.strip()]

    @staticmethod
    def _list_to_csv(values: list[str]) -> str:
        return ", ".join(str(v).strip() for v in values if str(v).strip())

    # ---------- Availability / introspection ----------
    def is_available(self) -> tuple[bool, str]:
        engine = self._db.engine
        if engine is None:
            return False, "Aucune base configurée."
        ok, msg = self._db.test_connection()
        if not ok:
            return False, msg
        if not self._table_exists(engine, self.TABLE):
            return False, f"Table introuvable : {self.TABLE}"
        return True, "OK"

    def get_timestamp_date_columns(self) -> tuple[bool, list[str], str]:
        engine = self._db.engine
        if engine is None:
            return False, [], "Aucun engine configuré."
        ok, msg = self.is_available()
        if not ok:
            return False, [], msg

        try:
            inspector = inspect(engine)
            cols = inspector.get_columns(self.TABLE)
            date_cols: list[str] = []
            for c in cols:
                name = str(c.get("name", ""))
                typ = str(c.get("type", "")).upper()
                if name and "TIMESTAMP" in typ:
                    date_cols.append(name)
            date_cols = sorted(date_cols, key=str.lower)
            if not date_cols:
                return False, [], "Aucune colonne TIMESTAMP détectée."
            return True, date_cols, f"{len(date_cols)} colonne(s) TIMESTAMP"
        except SQLAlchemyError as e:
            return False, [], f"Erreur SQLAlchemy: {e}"
        except Exception as e:
            return False, [], f"Erreur inattendue: {e}"

    # ---------- Family / subfamily options ----------
    def get_family_subfamily_options(self) -> tuple[bool, list[tuple[str, str, str]], str]:
        engine = self._db.engine
        if engine is None:
            return False, [], "Aucun engine configuré."
        ok, msg = self.is_available()
        if not ok:
            return False, [], msg

        try:
            available_cols = self._get_table_columns(engine, self.TABLE)
            if self.COL_ARTICLE not in available_cols or self.COL_SOURCE not in available_cols:
                return False, [], "Colonnes Article/source_table manquantes."

            src_expr = f"TRIM(UPPER(CAST({self._q(self.COL_SOURCE)} AS TEXT) || ''))"
            sql = text(
                f"SELECT {self._q(self.COL_ARTICLE)} AS article "
                f"FROM {self._q(self.TABLE)} "
                f"WHERE {src_expr} = :src"
            )

            fam_to_subs: Dict[str, set[str]] = {}
            fam_seen: set[str] = set()

            with engine.connect() as conn:
                result = conn.execute(sql, {"src": self.SOURCE_TABLE_VALUE})
                while True:
                    chunk = result.fetchmany(5000)
                    if not chunk:
                        break
                    for (article,) in chunk:
                        a = "" if article is None else str(article).strip()
                        if not a:
                            continue
                        fam = self._family_f1(a)
                        if not fam:
                            continue
                        fam_seen.add(fam)

                        sub = self._subfamily_for(fam, a)
                        if sub:
                            fam_to_subs.setdefault(fam, set()).add(sub)

            families = sorted(fam_seen, key=str.upper)

            options: list[tuple[str, str, str]] = []
            options.append(("(Toutes familles)", "", ""))

            for fam in families:
                options.append((fam, fam, ""))
                subs = sorted(list(fam_to_subs.get(fam, set())), key=str.upper)
                for sub in subs:
                    options.append((f"    └ {sub}", fam, sub))

            return True, options, f"{len(families)} familles"
        except SQLAlchemyError as e:
            return False, [], f"Erreur SQLAlchemy: {e}"
        except Exception as e:
            return False, [], f"Erreur inattendue: {e}"

    # ---------- Years ----------
    def list_distinct_years_for_selection(self, date_column: str, family_root: str, subfamily: str) -> tuple[bool, list[str], str]:
        engine = self._db.engine
        if engine is None:
            return False, [], "Aucun engine configuré."
        ok, msg = self.is_available()
        if not ok:
            return False, [], msg

        date_column = (date_column or "").strip()
        if not date_column:
            return False, [], "Colonne date vide."

        try:
            available_cols = self._get_table_columns(engine, self.TABLE)
            if date_column not in available_cols:
                return False, [], f"Colonne date introuvable : {date_column}"

            year_expr = self._year_expr(date_column)
            where_sql, params = self._build_where_base(
                available_cols=available_cols,
                date_col=date_column,
                years=None,
                family_root=family_root,
                subfamily=subfamily,
            )

            sql = text(
                f"SELECT DISTINCT {year_expr} AS y "
                f"FROM {self._q(self.TABLE)} "
                f"{where_sql} "
                f"AND y IS NOT NULL AND y != '' "
                f"ORDER BY y DESC"
            )

            with engine.connect() as conn:
                rows = conn.execute(sql, params).fetchall()

            years = [str(r[0]) for r in rows if r and r[0] is not None]
            years = [y for y in years if len(y) == 4 and y.isdigit()]
            return True, years, f"{len(years)} année(s)"
        except SQLAlchemyError as e:
            return False, [], f"Erreur SQLAlchemy: {e}"
        except Exception as e:
            return False, [], f"Erreur inattendue: {e}"

    # ---------- Lines ----------
    def list_lines(self, filters: PHCFilters, limit: int = 200, offset: int = 0, order_desc: bool = True) -> tuple[bool, Optional[PageResult], str]:
        engine = self._db.engine
        if engine is None:
            return False, None, "Aucun engine configuré."
        ok, msg = self.is_available()
        if not ok:
            return False, None, msg

        try:
            available_cols = self._get_table_columns(engine, self.TABLE)
            date_col = (filters.date_column or "").strip()
            if not date_col or date_col not in available_cols:
                return False, None, "Colonne date invalide/non disponible."

            cols_to_select: list[str] = []
            for c in [self.COL_CDV, date_col, self.COL_RS, self.COL_ARTICLE, self.COL_QTY, self.COL_PRICE_NET]:
                if c in available_cols:
                    cols_to_select.append(c)

            calc_expr = None
            if self.COL_QTY in available_cols and self.COL_PRICE_NET in available_cols:
                calc_expr = (
                    f"COALESCE(CAST({self._q(self.COL_QTY)} AS REAL), 0) "
                    f"* COALESCE(CAST({self._q(self.COL_PRICE_NET)} AS REAL), 0)"
                    f' AS "{self.CALC_COL_ALIAS}"'
                )

            where_sql, params = self._build_where_base(
                available_cols=available_cols,
                date_col=date_col,
                years=filters.years,
                family_root=filters.family_root,
                subfamily=filters.subfamily,
            )

            order_sql = f" ORDER BY {self._q(date_col)} {'DESC' if order_desc else 'ASC'}"
            select_parts = [self._q(c) for c in cols_to_select]
            if calc_expr is not None:
                select_parts.append(calc_expr)

            sql = text(
                f"SELECT {', '.join(select_parts)} "
                f"FROM {self._q(self.TABLE)} "
                f"{where_sql}"
                f"{order_sql} "
                f"LIMIT :limit OFFSET :offset"
            )
            params["limit"] = int(max(1, limit))
            params["offset"] = int(max(0, offset))

            with engine.connect() as conn:
                rows = conn.execute(sql, params).fetchall()

            out_columns = list(cols_to_select)
            if calc_expr is not None:
                out_columns.append(self.CALC_COL_HEADER)

            return True, PageResult(columns=out_columns, rows=[list(r) for r in rows], message=f"{len(rows)} ligne(s)"), "OK"
        except SQLAlchemyError as e:
            return False, None, f"Erreur SQLAlchemy: {e}"
        except Exception as e:
            return False, None, f"Erreur inattendue: {e}"

    def series_qty_distribution(self, filters: PHCFilters) -> tuple[bool, Optional[SeriesResult], str]:
        engine = self._db.engine
        if engine is None:
            return False, None, "Aucun engine configuré."
        ok, msg = self.is_available()
        if not ok:
            return False, None, msg

        try:
            available_cols = self._get_table_columns(engine, self.TABLE)
            if self.COL_QTY not in available_cols:
                return False, None, "Colonne Qté introuvable."

            date_col = (filters.date_column or "").strip()
            if not date_col:
                return False, None, "Colonne date vide."

            where_sql, params = self._build_where_base(
                available_cols=available_cols,
                date_col=date_col,
                years=filters.years,
                family_root=filters.family_root,
                subfamily=filters.subfamily,
            )

            qty_expr = f"CAST({self._q(self.COL_QTY)} AS REAL)"
            bucket_expr = (
                f"CASE "
                f"WHEN {qty_expr} <= 1 THEN '0-1' "
                f"WHEN {qty_expr} <= 5 THEN '2-5' "
                f"WHEN {qty_expr} <= 10 THEN '6-10' "
                f"WHEN {qty_expr} <= 20 THEN '11-20' "
                f"WHEN {qty_expr} <= 50 THEN '21-50' "
                f"WHEN {qty_expr} <= 100 THEN '51-100' "
                f"ELSE '100+' END"
            )

            sql = text(
                f"SELECT {bucket_expr} AS bucket, COUNT(*) AS n "
                f"FROM {self._q(self.TABLE)} "
                f"{where_sql} "
                f"GROUP BY bucket"
            )

            with engine.connect() as conn:
                rows = conn.execute(sql, params).fetchall()

            order = ["0-1", "2-5", "6-10", "11-20", "21-50", "51-100", "100+"]
            counts = {str(r[0]): float(r[1]) for r in rows}
            labels = [b for b in order if b in counts]
            values = [counts[b] for b in labels]
            return True, SeriesResult(labels=labels, values=values, message="OK"), "OK"

        except SQLAlchemyError as e:
            return False, None, f"Erreur SQLAlchemy: {e}"
        except Exception as e:
            return False, None, f"Erreur inattendue: {e}"

    # ================= Internals =================
    def _build_where_base(self, available_cols: list[str], date_col: str, years: list[str] | None, family_root: str, subfamily: str) -> tuple[str, dict[str, Any]]:
        clauses: list[str] = []
        params: dict[str, Any] = {}

        src_expr = f"TRIM(UPPER(CAST({self._q(self.COL_SOURCE)} AS TEXT) || ''))"
        clauses.append(f"{src_expr} = :src")
        params["src"] = self.SOURCE_TABLE_VALUE

        fam = (family_root or "").strip()
        sub = (subfamily or "").strip()
        article_text = f"CAST({self._q(self.COL_ARTICLE)} AS TEXT)"

        if fam and self.COL_ARTICLE in available_cols:
            if fam == self.FAMILY_MERGE_LABEL_BX_LTMNT:
                ors = []
                for p in sorted(self.FAMILY_MERGE_PREFIXES_BX_LTMNT):
                    key = f"bxlt_{p}"
                    params[key] = f"{p}%"
                    ors.append(f"{article_text} LIKE :{key}")
                clauses.append("(" + " OR ".join(ors) + ")")

            elif fam == self.FAMILY_MERGE_LABEL_BX_NRCPRV:
                if sub:
                    params["bxnrc_sub"] = f"{sub}%"
                    clauses.append(f"{article_text} LIKE :bxnrc_sub")
                else:
                    ors = []
                    for p in sorted(self.FAMILY_MERGE_PREFIXES_BX_NRCPRV):
                        key = f"bxnrc_{p}"
                        params[key] = f"{p}%"
                        ors.append(f"{article_text} LIKE :{key}")
                    clauses.append("(" + " OR ".join(ors) + ")")

            elif fam == self.FAMILY_MERGE_LABEL_BX_NAI:
                if sub:
                    params["bxnai_sub"] = f"{sub}%"
                    clauses.append(f"{article_text} LIKE :bxnai_sub")
                else:
                    ors = []
                    for p in sorted(self.FAMILY_MERGE_PREFIXES_BX_NAI_ROOTS):
                        key = f"bxnai_{p}"
                        params[key] = f"{p}%"
                        ors.append(f"{article_text} LIKE :{key}")
                    clauses.append("(" + " OR ".join(ors) + ")")

            elif fam == "BXNE":
                if sub == self.BXNE_SUB_ALIM:
                    ors = []
                    for d in ["0", "1", "2", "3"]:
                        key = f"bxne_a{d}"
                        params[key] = f"BXNE{d}%"
                        ors.append(f"{article_text} LIKE :{key}")
                    clauses.append("(" + " OR ".join(ors) + ")")
                elif sub == self.BXNE_SUB_LINEAR:
                    ors = []
                    for d in ["4", "5", "6", "7"]:
                        key = f"bxne_l{d}"
                        params[key] = f"BXNE{d}%"
                        ors.append(f"{article_text} LIKE :{key}")
                    clauses.append("(" + " OR ".join(ors) + ")")
                else:
                    params["famroot"] = "BXNE%"
                    clauses.append(f"{article_text} LIKE :famroot")

            else:
                params["famroot"] = f"{fam}%"
                clauses.append(f"{article_text} LIKE :famroot")

                if fam == "RDN" and sub:
                    if sub == self.RDN_SUB_BISTABLE:
                        clauses.append(f"({article_text} LIKE 'RDN310%' OR {article_text} LIKE 'RDN410%')")
                    elif sub == self.RDN_SUB_VW:
                        clauses.append(f"({article_text} LIKE 'RDN%V%' OR {article_text} LIKE 'RDN%W%')")
                    elif sub == self.RDN_SUB_OTHER:
                        clauses.append(
                            f"({article_text} LIKE 'RDN%' "
                            f"AND {article_text} NOT LIKE 'RDN310%' "
                            f"AND {article_text} NOT LIKE 'RDN410%' "
                            f"AND {article_text} NOT LIKE 'RDN%V%' "
                            f"AND {article_text} NOT LIKE 'RDN%W%')"
                        )

        years_list = years or []
        years_list = [y.strip() for y in years_list if y and y.strip()]
        if date_col and date_col in available_cols and years_list:
            year_expr = self._year_expr(date_col)
            in_params: list[str] = []
            for i, y in enumerate(years_list):
                key = f"y{i}"
                params[key] = y
                in_params.append(f":{key}")
            clauses.append(f"{year_expr} IN ({', '.join(in_params)})")

        return "WHERE " + " AND ".join(clauses), params

    def _table_exists(self, engine: Engine, table: str) -> bool:
        return table in inspect(engine).get_table_names()

    def _get_table_columns(self, engine: Engine, table: str) -> list[str]:
        cols = inspect(engine).get_columns(table)
        return [str(c.get("name", "")) for c in cols if c.get("name")]

    @staticmethod
    def _q(identifier: str) -> str:
        safe = identifier.replace('"', '""')
        return f'"{safe}"'

    def _year_expr(self, date_col: str) -> str:
        q = self._q(date_col)
        return (
            f"CASE "
            f"WHEN substr({q}, 1, 4) GLOB '[0-9][0-9][0-9][0-9]' THEN substr({q}, 1, 4) "
            f"WHEN substr({q}, -4) GLOB '[0-9][0-9][0-9][0-9]' THEN substr({q}, -4) "
            f"ELSE NULL END"
        )

    def _family_f1(self, article: str) -> str:
        s = (article or "").strip()
        if not s:
            return ""
        prefix = ""
        for i, ch in enumerate(s):
            if ch.isdigit():
                prefix = s[:i] if i > 0 else "<Débute par chiffre>"
                break
        if not prefix:
            prefix = s

        up = prefix.upper()
        if up in self.FAMILY_MERGE_PREFIXES_BX_LTMNT:
            return self.FAMILY_MERGE_LABEL_BX_LTMNT
        if up in self.FAMILY_MERGE_PREFIXES_BX_NRCPRV:
            return self.FAMILY_MERGE_LABEL_BX_NRCPRV
        if up in self.FAMILY_MERGE_PREFIXES_BX_NAI_ROOTS:
            return self.FAMILY_MERGE_LABEL_BX_NAI
        return prefix

    def _subfamily_for(self, family_root: str, article: str) -> str:
        a = (article or "").strip().upper()

        if family_root == "RDN":
            if a.startswith("RDN310") or a.startswith("RDN410"):
                return self.RDN_SUB_BISTABLE
            if a.startswith("RDN") and ("V" in a or "W" in a):
                return self.RDN_SUB_VW
            if a.startswith("RDN"):
                return self.RDN_SUB_OTHER
            return ""

        if family_root == self.FAMILY_MERGE_LABEL_BX_NRCPRV:
            pref = ""
            for i, ch in enumerate(a):
                if ch.isdigit():
                    pref = a[:i] if i > 0 else ""
                    break
            if not pref:
                pref = a
            return pref if pref in self.FAMILY_MERGE_PREFIXES_BX_NRCPRV else ""

        if family_root == self.FAMILY_MERGE_LABEL_BX_NAI:
            for sub in self.FAMILY_MERGE_SUBPREFIXES_BX_NAI:
                if a.startswith(sub):
                    return sub
            return ""

        if family_root == "BXNE":
            if any(a.startswith(f"BXNE{d}") for d in ["0", "1", "2", "3"]):
                return self.BXNE_SUB_ALIM
            if any(a.startswith(f"BXNE{d}") for d in ["4", "5", "6", "7"]):
                return self.BXNE_SUB_LINEAR
            return ""

        return ""