from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional

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

    def __init__(self, db: DatabaseManager) -> None:
        self._db = db

    def config_ready(self) -> bool:
        engine = self._db.engine
        if engine is None:
            return False
        return self._table_exists(engine, self.RULES_TABLE)

    def has_persisted_rules(self) -> bool:
        engine = self._db.engine
        if engine is None or not self.config_ready():
            return False
        try:
            with engine.connect() as conn:
                count = conn.execute(
                    text(f'SELECT COUNT(*) FROM {self._q(self.RULES_TABLE)}')
                ).scalar_one()
            return int(count or 0) > 0
        except Exception:
            return False

    def get_all_rules_raw(self) -> list[dict[str, Any]]:
        engine = self._db.engine
        if engine is None or not self.config_ready():
            return []

        sql = text(
            f"SELECT id, family, subfamily, enabled, priority, "
            f"regex_pattern, contains_any, not_contains_any "
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
                        "id": int(row[0]),
                        "family": "" if row[1] is None else str(row[1]).strip(),
                        "subfamily": "" if row[2] is None else str(row[2]).strip(),
                        "enabled": int(row[3] or 0),
                        "priority": int(row[4] or 0),
                        "criteria": {
                            "regex_pattern": "" if row[5] is None else str(row[5]).strip(),
                            "contains_any": self._csv_to_list(row[6]),
                            "not_contains_any": self._csv_to_list(row[7]),
                        },
                    }
                )

            if out:
                return out

            return self.build_default_rules_from_articles()
        except Exception:
            return []

    def save_rule(
        self,
        *,
        rule_id: int | None,
        family: str,
        subfamily: str,
        enabled: bool,
        priority: int,
        regex_pattern: str,
        contains_any: list[str],
        not_contains_any: list[str],
    ) -> tuple[bool, str]:
        engine = self._db.engine
        if engine is None:
            return False, "Aucune base DATA configurée."
        if not self.config_ready():
            return False, "Table de configuration PHC non disponible."

        family = family.strip()
        subfamily = subfamily.strip()
        regex_pattern = regex_pattern.strip()

        if not family:
            return False, "Le champ Famille est obligatoire."
        if not regex_pattern:
            return False, "Le champ Expression régulière est obligatoire."

        try:
            re.compile(regex_pattern)
        except re.error as e:
            return False, f"Expression régulière invalide : {e}"

        payload = {
            "family": family,
            "subfamily": subfamily,
            "enabled": 1 if enabled else 0,
            "priority": int(priority),
            "regex_pattern": regex_pattern,
            "contains_any": self._list_to_csv(contains_any),
            "not_contains_any": self._list_to_csv(not_contains_any),
        }

        try:
            with engine.begin() as conn:
                if rule_id is None:
                    conn.execute(
                        text(
                            f"INSERT INTO {self._q(self.RULES_TABLE)} "
                            f"(family, subfamily, enabled, priority, regex_pattern, contains_any, not_contains_any) "
                            f"VALUES (:family, :subfamily, :enabled, :priority, :regex_pattern, :contains_any, :not_contains_any)"
                        ),
                        payload,
                    )
                    return True, "Règle créée."
                conn.execute(
                    text(
                        f"UPDATE {self._q(self.RULES_TABLE)} "
                        f"SET family = :family, "
                        f"subfamily = :subfamily, "
                        f"enabled = :enabled, "
                        f"priority = :priority, "
                        f"regex_pattern = :regex_pattern, "
                        f"contains_any = :contains_any, "
                        f"not_contains_any = :not_contains_any, "
                        f"updated_at = CURRENT_TIMESTAMP "
                        f"WHERE id = :rule_id"
                    ),
                    {**payload, "rule_id": int(rule_id)},
                )
            return True, "Règle mise à jour."
        except Exception as e:
            return False, f"Erreur enregistrement règle : {e}"

    def delete_rule(self, rule_id: int) -> tuple[bool, str]:
        engine = self._db.engine
        if engine is None:
            return False, "Aucune base DATA configurée."
        if not self.config_ready():
            return False, "Table de configuration PHC non disponible."

        try:
            with engine.begin() as conn:
                conn.execute(
                    text(f"DELETE FROM {self._q(self.RULES_TABLE)} WHERE id = :rule_id"),
                    {"rule_id": int(rule_id)},
                )
            return True, "Règle supprimée."
        except Exception as e:
            return False, f"Erreur suppression règle : {e}"

    def build_default_rules_from_articles(self) -> list[dict[str, Any]]:
        engine = self._db.engine
        if engine is None:
            return []

        ok, _msg = self.is_available()
        if not ok:
            return []

        try:
            available_cols = self._get_table_columns(engine, self.TABLE)
            if self.COL_ARTICLE not in available_cols or self.COL_SOURCE not in available_cols:
                return []

            src_expr = f"TRIM(UPPER(CAST({self._q(self.COL_SOURCE)} AS TEXT) || ''))"
            sql = text(
                f"SELECT {self._q(self.COL_ARTICLE)} AS article "
                f"FROM {self._q(self.TABLE)} "
                f"WHERE {src_expr} = :src"
            )

            seen: set[str] = set()
            rules: list[dict[str, Any]] = []

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
                        if not fam or fam in seen:
                            continue
                        seen.add(fam)
                        rules.append(
                            {
                                "id": None,
                                "family": fam,
                                "subfamily": "",
                                "enabled": 1,
                                "priority": self._default_priority_for(fam, ""),
                                "criteria": self._default_criteria_for(fam, ""),
                            }
                        )

            rules.sort(
                key=lambda r: (
                    -int(r.get("priority", 0)),
                    str(r.get("family", "")).upper(),
                    str(r.get("subfamily", "")).upper(),
                )
            )
            return rules
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
            out_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
            return True, f"Bundle JSON exporté : {out_path}"
        except Exception as e:
            return False, f"Erreur export bundle JSON : {e}"

    def export_family_diagnostic_json(self, filepath: str | Path) -> tuple[bool, str]:
        engine = self._db.engine
        if engine is None:
            return False, "Aucune base DATA configurée."
        ok, msg = self.is_available()
        if not ok:
            return False, msg

        try:
            available_cols = self._get_table_columns(engine, self.TABLE)
            if self.COL_ARTICLE not in available_cols or self.COL_SOURCE not in available_cols:
                return False, "Colonnes Article/source_table manquantes."

            src_expr = f"TRIM(UPPER(CAST({self._q(self.COL_SOURCE)} AS TEXT) || ''))"
            sql = text(
                f"SELECT {self._q(self.COL_ARTICLE)} AS article "
                f"FROM {self._q(self.TABLE)} "
                f"WHERE {src_expr} = :src"
            )

            rules = self.get_all_rules_raw()
            article_families: dict[str, dict[str, Any]] = {}
            unmatched_article_families: dict[str, dict[str, Any]] = {}

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

                        match = self._find_best_rule_for_article(a, rules)
                        if match is not None:
                            fam = str(match.get("family", "")).strip()
                            if not fam:
                                continue
                            entry = article_families.setdefault(
                                fam,
                                {
                                    "family_root": fam,
                                    "count": 0,
                                    "examples": [],
                                },
                            )
                            entry["count"] += 1
                            if len(entry["examples"]) < 20 and a not in entry["examples"]:
                                entry["examples"].append(a)
                        else:
                            raw_fam = self._family_f1(a)
                            if not raw_fam:
                                continue
                            entry = unmatched_article_families.setdefault(
                                raw_fam,
                                {
                                    "family_root": raw_fam,
                                    "count": 0,
                                    "examples": [],
                                },
                            )
                            entry["count"] += 1
                            if len(entry["examples"]) < 20 and a not in entry["examples"]:
                                entry["examples"].append(a)

            rule_families = sorted(
                {str(rule.get("family", "")).strip() for rule in rules if str(rule.get("family", "")).strip()},
                key=str.upper,
            )

            ok_opts, options, msg_opts = self.get_family_subfamily_options()
            combo_options: list[dict[str, str]] = []
            if ok_opts:
                for display, fam, sub in options:
                    combo_options.append(
                        {
                            "display": display,
                            "family": fam,
                            "subfamily": sub,
                        }
                    )

            article_family_names = sorted(article_families.keys(), key=str.upper)
            families_from_articles_not_in_rules = [f for f in article_family_names if f not in rule_families]
            families_from_rules_not_in_articles = [f for f in rule_families if f not in article_family_names]

            payload = {
                "table": self.TABLE,
                "source_table_value": self.SOURCE_TABLE_VALUE,
                "rules_table": self.RULES_TABLE,
                "rules_count": len(rules),
                "combo_options_count": len(combo_options),
                "article_families_count": len(article_families),
                "combo_options_status": msg_opts if not ok_opts else "OK",
                "rule_families": rule_families,
                "combo_options": combo_options,
                "rules": rules,
                "article_families": sorted(
                    list(article_families.values()),
                    key=lambda x: str(x.get("family_root", "")).upper(),
                ),
                "unmatched_article_families": sorted(
                    list(unmatched_article_families.values()),
                    key=lambda x: str(x.get("family_root", "")).upper(),
                ),
                "families_from_articles_not_in_rules": families_from_articles_not_in_rules,
                "families_from_rules_not_in_articles": families_from_rules_not_in_articles,
            }

            out_path = Path(filepath)
            out_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
            return True, f"Diagnostic familles exporté : {out_path}"
        except Exception as e:
            return False, f"Erreur export diagnostic familles : {e}"

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
                criteria = self._normalize_criteria(rule.get("criteria", {}))
                regex_pattern = str(criteria.get("regex_pattern", "")).strip()
                if not regex_pattern:
                    regex_pattern = self._legacy_prefixes_to_regex(criteria.get("startswith_any", []))
                if not str(rule.get("family", "")).strip():
                    continue
                cleaned_rules.append(
                    {
                        "family": str(rule.get("family", "")).strip(),
                        "subfamily": str(rule.get("subfamily", "")).strip(),
                        "enabled": int(rule.get("enabled", 1) or 0),
                        "priority": int(rule.get("priority", 0) or 0),
                        "regex_pattern": regex_pattern,
                        "contains_any": criteria.get("contains_any", []),
                        "not_contains_any": criteria.get("not_contains_any", []),
                    }
                )

            with engine.begin() as conn:
                conn.execute(text(f"DELETE FROM {self._q(self.RULES_TABLE)}"))
                for rule in cleaned_rules:
                    conn.execute(
                        text(
                            f"INSERT INTO {self._q(self.RULES_TABLE)} "
                            f"(family, subfamily, enabled, priority, regex_pattern, contains_any, not_contains_any) "
                            f"VALUES (:family, :subfamily, :enabled, :priority, :regex_pattern, :contains_any, :not_contains_any)"
                        ),
                        {
                            "family": rule["family"],
                            "subfamily": rule["subfamily"],
                            "enabled": rule["enabled"],
                            "priority": rule["priority"],
                            "regex_pattern": rule["regex_pattern"],
                            "contains_any": self._list_to_csv(rule["contains_any"]),
                            "not_contains_any": self._list_to_csv(rule["not_contains_any"]),
                        },
                    )

            return True, f"Bundle JSON importé : {src}"
        except json.JSONDecodeError as e:
            return False, f"JSON invalide : {e}"
        except Exception as e:
            return False, f"Erreur import bundle JSON : {e}"

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

            rules = self.get_all_rules_raw()
            src_expr = f"TRIM(UPPER(CAST({self._q(self.COL_SOURCE)} AS TEXT) || ''))"
            sql = text(
                f"SELECT {self._q(self.COL_ARTICLE)} AS article "
                f"FROM {self._q(self.TABLE)} "
                f"WHERE {src_expr} = :src"
            )

            fam_to_subs: dict[str, set[str]] = {}
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

                        match = self._find_best_rule_for_article(a, rules)
                        if match is None:
                            continue

                        fam = str(match.get("family", "")).strip()
                        sub = str(match.get("subfamily", "")).strip()

                        if not fam:
                            continue

                        fam_seen.add(fam)
                        if sub:
                            fam_to_subs.setdefault(fam, set()).add(sub)

            for rule in rules:
                fam = str(rule.get("family", "")).strip()
                sub = str(rule.get("subfamily", "")).strip()
                if fam:
                    fam_seen.add(fam)
                if fam and sub:
                    fam_to_subs.setdefault(fam, set()).add(sub)

            families = sorted(fam_seen, key=str.upper)
            options: list[tuple[str, str, str]] = [("(Toutes familles)", "", "")]
            for fam in families:
                options.append((fam, fam, ""))
                for sub in sorted(list(fam_to_subs.get(fam, set())), key=str.upper):
                    options.append((f"    └ {sub}", fam, sub))

            return True, options, f"{len(families)} familles"
        except SQLAlchemyError as e:
            return False, [], f"Erreur SQLAlchemy: {e}"
        except Exception as e:
            return False, [], f"Erreur inattendue: {e}"

    def list_distinct_years_for_selection(
        self,
        date_column: str,
        family_root: str,
        subfamily: str,
    ) -> tuple[bool, list[str], str]:
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
            if self.COL_ARTICLE not in available_cols:
                return False, [], f"Colonne introuvable : {self.COL_ARTICLE}"

            rules = self.get_all_rules_raw()
            sql = text(
                f"SELECT {self._q(self.COL_ARTICLE)} AS article, {self._q(date_column)} AS date_value "
                f"FROM {self._q(self.TABLE)} "
                f"WHERE TRIM(UPPER(CAST({self._q(self.COL_SOURCE)} AS TEXT) || '')) = :src"
            )

            years_found: set[str] = set()
            with engine.connect() as conn:
                rows = conn.execute(sql, {"src": self.SOURCE_TABLE_VALUE}).fetchall()

            selected_family = (family_root or "").strip()
            selected_subfamily = (subfamily or "").strip()

            for article, date_value in rows:
                a = "" if article is None else str(article).strip()
                if selected_family:
                    match = self._find_best_rule_for_article(a, rules)
                    if match is None:
                        continue
                    if str(match.get("family", "")).strip() != selected_family:
                        continue
                    if selected_subfamily and str(match.get("subfamily", "")).strip() != selected_subfamily:
                        continue

                year = self._extract_year(date_value)
                if year:
                    years_found.add(year)

            years = sorted(years_found, reverse=True)
            return True, years, f"{len(years)} année(s)"
        except Exception as e:
            return False, [], f"Erreur inattendue: {e}"

    def list_lines(
        self,
        filters: PHCFilters,
        limit: int = 200,
        offset: int = 0,
        order_desc: bool = True,
    ) -> tuple[bool, Optional[PageResult], str]:
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

            if self.COL_ARTICLE not in cols_to_select:
                return False, None, "Colonne Article indisponible."

            select_parts = [self._q(c) for c in cols_to_select]
            sql = text(
                f"SELECT {', '.join(select_parts)} "
                f"FROM {self._q(self.TABLE)} "
                f"WHERE TRIM(UPPER(CAST({self._q(self.COL_SOURCE)} AS TEXT) || '')) = :src"
            )

            with engine.connect() as conn:
                rows = conn.execute(sql, {"src": self.SOURCE_TABLE_VALUE}).fetchall()

            raw_rows = [list(r) for r in rows]
            date_idx = cols_to_select.index(date_col)
            article_idx = cols_to_select.index(self.COL_ARTICLE)
            qty_idx = cols_to_select.index(self.COL_QTY) if self.COL_QTY in cols_to_select else -1
            price_idx = cols_to_select.index(self.COL_PRICE_NET) if self.COL_PRICE_NET in cols_to_select else -1

            filtered_rows: list[list[Any]] = []
            selected_years = {y.strip() for y in (filters.years or []) if y and y.strip()}
            selected_family = (filters.family_root or "").strip()
            selected_subfamily = (filters.subfamily or "").strip()
            rules = self.get_all_rules_raw()

            for row in raw_rows:
                article = "" if row[article_idx] is None else str(row[article_idx]).strip()

                if selected_family:
                    match = self._find_best_rule_for_article(article, rules)
                    if match is None:
                        continue
                    if str(match.get("family", "")).strip() != selected_family:
                        continue
                    if selected_subfamily and str(match.get("subfamily", "")).strip() != selected_subfamily:
                        continue

                row_year = self._extract_year(row[date_idx])
                if selected_years and row_year not in selected_years:
                    continue

                out_row = list(row)
                if qty_idx >= 0 and price_idx >= 0:
                    qty = self._safe_float(row[qty_idx])
                    price = self._safe_float(row[price_idx])
                    out_row.append(qty * price)

                filtered_rows.append(out_row)

            filtered_rows.sort(
                key=lambda row: self._sortable_value(row[date_idx]),
                reverse=order_desc,
            )

            page_rows = filtered_rows[offset:offset + max(1, limit)]
            out_columns = list(cols_to_select)
            if qty_idx >= 0 and price_idx >= 0:
                out_columns.append(self.CALC_COL_HEADER)

            return True, PageResult(columns=out_columns, rows=page_rows, message=f"{len(filtered_rows)} ligne(s)"), "OK"
        except SQLAlchemyError as e:
            return False, None, f"Erreur SQLAlchemy: {e}"
        except Exception as e:
            return False, None, f"Erreur inattendue: {e}"

    @staticmethod
    def _normalize_criteria(criteria: Any) -> dict[str, Any]:
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
            "regex_pattern": str(criteria.get("regex_pattern", "")).strip(),
            "startswith_any": _norm_list("startswith_any"),
            "contains_any": _norm_list("contains_any"),
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

    @staticmethod
    def _legacy_prefixes_to_regex(prefixes: list[str]) -> str:
        tokens = [re.escape(str(v).strip()) for v in prefixes if str(v).strip()]
        if not tokens:
            return ""
        if len(tokens) == 1:
            return f"^{tokens[0]}"
        return "^(?:" + "|".join(tokens) + ")"

    def _default_priority_for(self, family: str, subfamily: str) -> int:
        return 200 if subfamily else 10

    def _default_criteria_for(self, family: str, subfamily: str) -> dict[str, Any]:
        token = (subfamily or family).strip()
        return {
            "regex_pattern": f"^{re.escape(token)}" if token else "",
            "contains_any": [],
            "not_contains_any": [],
        }

    def _find_best_rule_for_article(
        self,
        article: str,
        rules: list[dict[str, Any]],
    ) -> dict[str, Any] | None:
        a = (article or "").strip()
        if not a:
            return None

        best_rule: dict[str, Any] | None = None
        best_score: tuple[int, int, int, str, str] | None = None

        for rule in rules:
            if int(rule.get("enabled", 1) or 0) != 1:
                continue

            criteria = self._normalize_criteria(rule.get("criteria", {}))
            if not self._rule_matches_article(a, criteria):
                continue

            priority = int(rule.get("priority", 0) or 0)
            regex_pattern = str(criteria.get("regex_pattern", "")).strip()
            regex_len = len(regex_pattern)
            contains_count = len(criteria.get("contains_any", []) or [])
            family = str(rule.get("family", "")).strip().upper()
            subfamily = str(rule.get("subfamily", "")).strip().upper()

            score = (priority, regex_len, contains_count, family, subfamily)
            if best_score is None or score > best_score:
                best_score = score
                best_rule = rule

        return best_rule

    def _rule_matches_article(self, article: str, criteria: dict[str, Any]) -> bool:
        a = (article or "").strip()
        if not a:
            return False

        regex_pattern = str(criteria.get("regex_pattern", "")).strip()
        if regex_pattern:
            try:
                if re.search(regex_pattern, a, flags=re.IGNORECASE) is None:
                    return False
            except re.error:
                return False

        contains_any = [str(v).strip() for v in criteria.get("contains_any", []) if str(v).strip()]
        if contains_any:
            article_upper = a.upper()
            if not any(token.upper() in article_upper for token in contains_any):
                return False

        not_contains_any = [str(v).strip() for v in criteria.get("not_contains_any", []) if str(v).strip()]
        if not_contains_any:
            article_upper = a.upper()
            if any(token.upper() in article_upper for token in not_contains_any):
                return False

        return bool(regex_pattern or contains_any or not_contains_any)

    def _table_exists(self, engine: Engine, table: str) -> bool:
        return table in inspect(engine).get_table_names()

    def _get_table_columns(self, engine: Engine, table: str) -> list[str]:
        cols = inspect(engine).get_columns(table)
        return [str(c.get("name", "")) for c in cols if c.get("name")]

    @staticmethod
    def _q(identifier: str) -> str:
        safe = identifier.replace('"', '""')
        return f'"{safe}"'

    @staticmethod
    def _extract_year(value: Any) -> str:
        text_value = "" if value is None else str(value).strip()
        if len(text_value) >= 4 and text_value[:4].isdigit():
            return text_value[:4]
        if len(text_value) >= 4 and text_value[-4:].isdigit():
            return text_value[-4:]
        return ""

    @staticmethod
    def _sortable_value(value: Any) -> str:
        return "" if value is None else str(value)

    @staticmethod
    def _safe_float(value: Any) -> float:
        if value is None:
            return 0.0
        try:
            return float(str(value).replace(",", "."))
        except Exception:
            return 0.0

    def _family_f1(self, article: str) -> str:
        s = (article or "").strip()
        if not s:
            return ""
        for i, ch in enumerate(s):
            if ch.isdigit():
                return s[:i] if i > 0 else "<Débute par chiffre>"
        return s