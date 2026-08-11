#!/usr/bin/env python3
"""Query journal metrics from the bundled SQLite index."""

from __future__ import annotations

import argparse
import difflib
import json
import re
import sqlite3
import unicodedata
from collections import defaultdict
from pathlib import Path
from typing import Any, Iterable


DEFAULT_DB = Path(__file__).resolve().parent.parent / "assets" / "journal-metrics.sqlite"
REPOSITORY_URL = "https://github.com/hiDaDeng/journal-metrics"


def normalize_name(value: str) -> str:
    text = unicodedata.normalize("NFKC", value.strip()).casefold()
    return "".join(char for char in text if char.isalnum())


def normalize_issn(value: str) -> str:
    return re.sub(r"[^0-9X]", "", value.upper())


def unique(values: Iterable[str]) -> list[str]:
    return sorted({value.strip() for value in values if value and value.strip()})


def unique_issns(values: Iterable[str]) -> list[str]:
    return [value for value in unique(values) if len(normalize_issn(value)) == 8]


def category_indexes(values: Iterable[str]) -> list[str]:
    indexes: set[str] = set()
    for value in values:
        indexes.update(
            match.upper()
            for match in re.findall(r"\((SCI|SCIE|SSCI|ESCI|AHCI)\)", value or "", re.I)
        )
    return sorted(indexes)


def latest_jcr_years(connection: sqlite3.Connection) -> list[int]:
    row = connection.execute(
        "SELECT value FROM metadata WHERE key = 'latest_three_jcr_years'"
    ).fetchone()
    return json.loads(row[0]) if row else []


def optional_text(value: str | None) -> str | None:
    return value if value else None


def optional_bool(value: int | None) -> bool | None:
    return bool(value) if value is not None else None


def doaj_record(row: sqlite3.Row) -> dict[str, Any]:
    return {
        "doaj_id": row["doaj_id"],
        "title": row["journal_title"],
        "alternative_title": optional_text(row["alternative_title"]),
        "issns": unique_issns([row["print_issn"], row["online_issn"]]),
        "journal_url": row["journal_url"],
        "doaj_url": row["doaj_url"],
        "publisher": {
            "name": row["publisher"],
            "country": row["publisher_country"],
            "other_organization": optional_text(row["other_organization"]),
            "other_organization_country": optional_text(
                row["other_organization_country"]
            ),
        },
        "open_access": {
            "open_license_since": optional_text(row["open_license_since"]),
            "license": row["journal_license"],
            "license_attributes": optional_text(row["license_attributes"]),
            "license_terms_url": optional_text(row["license_terms_url"]),
            "machine_readable_cc": optional_bool(row["machine_readable_cc"]),
            "author_holds_copyright": optional_bool(
                row["author_holds_copyright"]
            ),
            "copyright_url": optional_text(row["copyright_url"]),
            "complies_with_doaj_definition": optional_bool(
                row["complies_with_doaj_oa"]
            ),
        },
        "fees": {
            "apc": optional_bool(row["apc"]),
            "apc_amount_raw": optional_text(row["apc_amount_raw"]),
            "apc_info_url": optional_text(row["apc_info_url"]),
            "waiver_policy": optional_bool(row["waiver_policy"]),
            "waiver_policy_url": optional_text(row["waiver_policy_url"]),
            "has_other_fees": optional_bool(row["has_other_fees"]),
            "other_fees_url": optional_text(row["other_fees_url"]),
            "subscribe_to_open": optional_bool(row["subscribe_to_open"]),
        },
        "editorial": {
            "review_process": row["review_process"],
            "review_process_url": optional_text(row["review_process_url"]),
            "plagiarism_screening": optional_bool(row["plagiarism_screening"]),
            "submission_to_publication_weeks": row[
                "submission_to_publication_weeks"
            ],
            "aims_scope_url": optional_text(row["aims_scope_url"]),
            "editorial_board_url": optional_text(row["editorial_board_url"]),
            "author_instructions_url": optional_text(
                row["author_instructions_url"]
            ),
        },
        "archiving": {
            "preservation_services": optional_text(row["preservation_services"]),
            "preservation_national_library": optional_text(
                row["preservation_national_library"]
            ),
            "preservation_url": optional_text(row["preservation_url"]),
            "deposit_policy_directory": optional_text(
                row["deposit_policy_directory"]
            ),
            "deposit_policy_url": optional_text(row["deposit_policy_url"]),
            "persistent_article_identifiers": optional_text(
                row["persistent_article_identifiers"]
            ),
        },
        "discovery": {
            "keywords": optional_text(row["keywords"]),
            "subjects": optional_text(row["subjects"]),
            "lcc_codes": optional_text(row["lcc_codes"]),
            "accepted_languages": optional_text(row["accepted_languages"]),
        },
        "continuity": {
            "continues": optional_text(row["continues"]),
            "continued_by": optional_text(row["continued_by"]),
            "mirror_journal": optional_bool(row["mirror_journal"]),
            "open_journals_collective": optional_bool(
                row["open_journals_collective"]
            ),
        },
        "freshness": {
            "added_at": row["added_at"],
            "last_updated_at": row["last_updated_at"],
            "last_full_review_date": optional_text(row["last_full_review_date"]),
            "article_records_in_doaj": row["article_records"],
            "most_recent_article_added_at": optional_text(
                row["most_recent_article_added_at"]
            ),
        },
    }


def query_doaj(
    core_db_path: Path,
    query: str,
    names: Iterable[str] = (),
    issns: Iterable[str] = (),
) -> dict[str, Any] | None:
    path = core_db_path.parent / "doaj.sqlite"
    if not path.exists():
        return None
    name_keys = {normalize_name(query), *(normalize_name(name) for name in names)}
    name_keys.discard("")
    issn_keys = {normalize_issn(query), *(normalize_issn(issn) for issn in issns)}
    issn_keys = {value for value in issn_keys if len(value) == 8}

    connection = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    connection.row_factory = sqlite3.Row
    try:
        if issn_keys:
            placeholders = ",".join("?" for _ in issn_keys)
            params = tuple(sorted(issn_keys))
            rows = list(
                connection.execute(
                    f"SELECT * FROM journals WHERE print_issn_norm IN ({placeholders}) "
                    f"OR online_issn_norm IN ({placeholders})",
                    params + params,
                )
            )
        elif name_keys:
            placeholders = ",".join("?" for _ in name_keys)
            params = tuple(sorted(name_keys))
            rows = list(
                connection.execute(
                    f"SELECT * FROM journals WHERE title_norm IN ({placeholders}) "
                    f"OR alternative_title_norm IN ({placeholders})",
                    params + params,
                )
            )
        else:
            rows = []
    finally:
        connection.close()

    if len(rows) == 1:
        return {"status": "found", "record": doaj_record(rows[0])}
    if len(rows) > 1:
        exact_name_rows = [row for row in rows if row["title_norm"] in name_keys]
        if len(exact_name_rows) == 1:
            return {"status": "found", "record": doaj_record(exact_name_rows[0])}
        return {
            "status": "ambiguous",
            "candidates": [
                {
                    "doaj_id": row["doaj_id"],
                    "title": row["journal_title"],
                    "issns": unique_issns([row["print_issn"], row["online_issn"]]),
                    "publisher": row["publisher"],
                }
                for row in rows
            ],
        }
    return None


def query_wiley(
    core_db_path: Path,
    query: str,
    names: Iterable[str] = (),
    issns: Iterable[str] = (),
) -> dict[str, Any] | None:
    path = core_db_path.parent / "publishers" / "wiley.sqlite"
    if not path.exists():
        return None
    name_keys = {normalize_name(query), *(normalize_name(name) for name in names)}
    issn_keys = {normalize_issn(query), *(normalize_issn(issn) for issn in issns)}
    name_keys.discard("")
    issn_keys = {value for value in issn_keys if len(value) == 8}

    clauses: list[str] = []
    params: list[str] = []
    if name_keys:
        placeholders = ",".join("?" for _ in name_keys)
        clauses.append(f"title_norm IN ({placeholders})")
        params.extend(sorted(name_keys))
    if issn_keys:
        placeholders = ",".join("?" for _ in issn_keys)
        clauses.append(f"REPLACE(inferred_issn, '-', '') IN ({placeholders})")
        params.extend(sorted(issn_keys))
    if not clauses:
        return None

    connection = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    connection.row_factory = sqlite3.Row
    try:
        rows = list(
            connection.execute(
                "SELECT * FROM journals WHERE " + " OR ".join(clauses), params
            )
        )
    finally:
        connection.close()
    if len(rows) != 1:
        return None
    row = rows[0]
    return {
        "publisher_group": "Wiley",
        "title": row["title"],
        "issn": row["inferred_issn"],
        "journal_url": optional_text(row["journal_url"]),
        "first_decision_days": row["first_decision_days"],
        "first_decision_raw": row["first_decision_raw"],
        "acceptance_rate_percent": row["acceptance_rate_percent"],
        "acceptance_rate_raw": row["acceptance_rate_raw"],
        "submission_to_acceptance_days": None,
        "acceptance_to_online_days": row["acceptance_to_online_days"],
        "acceptance_to_online_raw": row["acceptance_to_online_raw"],
        "oa_model": row["revenue_model"],
        "apc_amount": row["apc_amount"],
        "apc_currency": row["apc_currency"],
        "apc_raw": row["apc_raw"],
        "journal_ranking": optional_text(row["cas_journal_ranking"]),
        "peer_review_model": optional_text(row["peer_review_model"]),
        "article_count_total": None,
        "article_views_total": None,
        "article_downloads_total": None,
        "cite_score": None,
        "publisher_jif": row["journal_impact_factor"],
        "observed_at_utc": row["observed_at_utc"],
        "source_url": row["source_url"],
    }


def query_frontiers(
    core_db_path: Path,
    query: str,
    names: Iterable[str] = (),
    issns: Iterable[str] = (),
) -> dict[str, Any] | None:
    path = core_db_path.parent / "publishers" / "frontiers.sqlite"
    if not path.exists():
        return None
    name_keys = {normalize_name(query), *(normalize_name(name) for name in names)}
    issn_keys = {normalize_issn(query), *(normalize_issn(issn) for issn in issns)}
    name_keys.discard("")
    issn_keys = {value for value in issn_keys if len(value) == 8}

    clauses: list[str] = []
    params: list[str] = []
    if name_keys:
        placeholders = ",".join("?" for _ in name_keys)
        clauses.append(f"title_norm IN ({placeholders})")
        params.extend(sorted(name_keys))
    if issn_keys:
        placeholders = ",".join("?" for _ in issn_keys)
        clauses.append(f"issn_norm IN ({placeholders})")
        params.extend(sorted(issn_keys))
    if not clauses:
        return None

    connection = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    connection.row_factory = sqlite3.Row
    try:
        rows = list(
            connection.execute(
                "SELECT * FROM journals WHERE " + " OR ".join(clauses), params
            )
        )
    finally:
        connection.close()
    if len(rows) != 1:
        return None
    row = rows[0]
    return {
        "publisher_group": "Frontiers",
        "title": row["title"],
        "issn": row["issn"],
        "journal_url": optional_text(row["source_url"]),
        "first_decision_days": None,
        "first_decision_raw": None,
        "acceptance_rate_percent": None,
        "acceptance_rate_raw": None,
        "submission_to_acceptance_days": None,
        "acceptance_to_online_days": None,
        "acceptance_to_online_raw": None,
        "oa_model": "Gold Open Access",
        "apc_amount": None,
        "apc_currency": None,
        "apc_raw": None,
        "journal_ranking": None,
        "peer_review_model": None,
        "article_count_total": row["article_count_total"],
        "article_views_total": row["article_views_total"],
        "article_downloads_total": row["article_downloads_total"],
        "cite_score": row["cite_score"],
        "publisher_jif": row["publisher_jif"],
        "observed_at_utc": row["observed_at_utc"],
        "source_url": row["source_url"],
    }


def query_publisher(
    core_db_path: Path,
    query: str,
    names: Iterable[str] = (),
    issns: Iterable[str] = (),
    doaj: dict[str, Any] | None = None,
) -> tuple[dict[str, Any] | None, str | None]:
    lookups = (
        ("wiley.sqlite", query_wiley),
        ("frontiers.sqlite", query_frontiers),
    )
    if doaj:
        publisher = normalize_name(doaj["publisher"]["name"])
        if "wiley" in publisher:
            lookups = (("wiley.sqlite", query_wiley),)
        elif publisher in {"frontiersmedia", "frontiersmediasa"}:
            lookups = (("frontiers.sqlite", query_frontiers),)
        else:
            return None, None
    for database_name, lookup in lookups:
        result = lookup(core_db_path, query, names, issns)
        if result:
            return result, database_name
    return None, None


def rows_for_exact_query(connection: sqlite3.Connection, query: str) -> list[dict[str, Any]]:
    name = normalize_name(query)
    issn = normalize_issn(query)
    looks_like_issn = len(issn) == 8
    rows: list[dict[str, Any]] = []

    if looks_like_issn:
        for row in connection.execute(
            """
            SELECT 'jcr' AS source, journal, journal_norm, issn_norm AS id1,
                   eissn_norm AS id2
            FROM jcr_metrics WHERE issn_norm = ? OR eissn_norm = ?
            UNION ALL
            SELECT 'emerging', journal, journal_norm, issn1_norm, issn2_norm
            FROM emerging_quartiles WHERE issn1_norm = ? OR issn2_norm = ?
            """,
            (issn, issn, issn, issn),
        ):
            rows.append(dict(row))
    else:
        for row in connection.execute(
            """
            SELECT 'jcr' AS source, journal, journal_norm, issn_norm AS id1,
                   eissn_norm AS id2
            FROM jcr_metrics WHERE journal_norm = ?
            UNION ALL
            SELECT 'emerging', journal, journal_norm, issn1_norm, issn2_norm
            FROM emerging_quartiles WHERE journal_norm = ?
            """,
            (name, name),
        ):
            rows.append(dict(row))
    return rows


def identity_groups(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    groups: list[dict[str, Any]] = []
    for row in rows:
        identifiers = {value for value in (row["id1"], row["id2"]) if value}
        touching = [group for group in groups if identifiers & group["identifiers"]]
        if not identifiers and groups:
            touching = [groups[0]]
        if not touching:
            groups.append(
                {"identifiers": set(identifiers), "names": {row["journal"]}, "rows": [row]}
            )
            continue
        target = touching[0]
        target["identifiers"].update(identifiers)
        target["names"].add(row["journal"])
        target["rows"].append(row)
        for other in touching[1:]:
            target["identifiers"].update(other["identifiers"])
            target["names"].update(other["names"])
            target["rows"].extend(other["rows"])
            groups.remove(other)
    return groups


def fetch_identity_rows(
    connection: sqlite3.Connection, identifiers: set[str], journal_norms: set[str]
) -> tuple[list[sqlite3.Row], list[sqlite3.Row]]:
    if identifiers:
        placeholders = ",".join("?" for _ in identifiers)
        params = tuple(sorted(identifiers))
        jcr = list(
            connection.execute(
                f"SELECT * FROM jcr_metrics WHERE issn_norm IN ({placeholders}) "
                f"OR eissn_norm IN ({placeholders})",
                params + params,
            )
        )
        emerging = list(
            connection.execute(
                f"SELECT * FROM emerging_quartiles WHERE issn1_norm IN ({placeholders}) "
                f"OR issn2_norm IN ({placeholders})",
                params + params,
            )
        )
        return jcr, emerging

    placeholders = ",".join("?" for _ in journal_norms)
    params = tuple(sorted(journal_norms))
    return (
        list(connection.execute(f"SELECT * FROM jcr_metrics WHERE journal_norm IN ({placeholders})", params)),
        list(
            connection.execute(
                f"SELECT * FROM emerging_quartiles WHERE journal_norm IN ({placeholders})", params
            )
        ),
    )


def suggestions(
    connection: sqlite3.Connection, db_path: Path, query: str, limit: int = 5
) -> list[str]:
    names = [
        row[0]
        for row in connection.execute(
            """
            SELECT journal FROM jcr_metrics
            UNION
            SELECT journal FROM emerging_quartiles
            """
        )
    ]
    doaj_path = db_path.parent / "doaj.sqlite"
    if doaj_path.exists():
        doaj_connection = sqlite3.connect(f"file:{doaj_path}?mode=ro", uri=True)
        try:
            names.extend(
                row[0]
                for row in doaj_connection.execute(
                    "SELECT journal_title FROM journals "
                    "UNION SELECT alternative_title FROM journals "
                    "WHERE alternative_title <> ''"
                )
            )
        finally:
            doaj_connection.close()
    normalized_to_names: dict[str, list[str]] = defaultdict(list)
    for name in names:
        normalized_to_names[normalize_name(name)].append(name)
    matches = difflib.get_close_matches(
        normalize_name(query), normalized_to_names.keys(), n=limit, cutoff=0.62
    )
    return [sorted(normalized_to_names[match], key=len)[0] for match in matches]


def query_database(
    db_path: Path, query: str, allow_suggestion_fallback: bool = True
) -> dict[str, Any]:
    connection = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    connection.row_factory = sqlite3.Row
    try:
        exact_rows = rows_for_exact_query(connection, query)
        if not exact_rows:
            doaj_result = query_doaj(db_path, query)
            if doaj_result and doaj_result["status"] == "ambiguous":
                return {
                    "status": "ambiguous",
                    "query": query,
                    "message": "DOAJ 名称或 ISSN 对应多个期刊，请指定更准确的 ISSN",
                    "candidates": doaj_result["candidates"],
                    "source": ["doaj.sqlite"],
                }
            doaj = doaj_result["record"] if doaj_result else None
            doaj_names = (
                unique([doaj["title"], doaj["alternative_title"]]) if doaj else []
            )
            doaj_issns = doaj["issns"] if doaj else []
            publisher, publisher_source = query_publisher(
                db_path, query, doaj_names, doaj_issns, doaj
            )
            if doaj:
                sources = ["doaj.sqlite"]
                if publisher_source:
                    sources.append(publisher_source)
                return {
                    "status": "found",
                    "query": query,
                    "journal": {
                        "name": doaj["title"],
                        "aliases": doaj_names,
                        "issns": doaj_issns,
                    },
                    "jcr_history": [
                        {
                            "year": year,
                            "jif": [],
                            "jcr_quartile": [],
                            "indexes": [],
                            "rankings": [],
                            "categories": [],
                        }
                        for year in latest_jcr_years(connection)
                    ],
                    "emerging_2026": {"quartile": [], "major_categories": []},
                    "doaj": doaj,
                    "publisher_metrics": publisher,
                    "source": sources,
                }
            if publisher:
                return {
                    "status": "found",
                    "query": query,
                    "journal": {
                        "name": publisher["title"],
                        "aliases": [publisher["title"]],
                        "issns": unique_issns([publisher["issn"]]),
                    },
                    "jcr_history": [
                        {
                            "year": year,
                            "jif": [],
                            "jcr_quartile": [],
                            "indexes": [],
                            "rankings": [],
                            "categories": [],
                        }
                        for year in latest_jcr_years(connection)
                    ],
                    "emerging_2026": {"quartile": [], "major_categories": []},
                    "doaj": None,
                    "publisher_metrics": publisher,
                    "source": [db_path.name, publisher_source],
                }
            suggestion_list = suggestions(connection, db_path, query)
            if allow_suggestion_fallback and suggestion_list:
                selected = suggestion_list[0]
                fallback_result = query_database(
                    db_path, selected, allow_suggestion_fallback=False
                )
                if fallback_result["status"] == "found":
                    fallback_result["fallback"] = {
                        "original_query": query,
                        "selected_suggestion": selected,
                        "remaining_suggestions": suggestion_list[1:],
                    }
                    return fallback_result
            return {
                "status": "not_found",
                "query": query,
                "message": "本地数据未收录",
                "suggestions": suggestion_list,
            }

        groups = identity_groups(exact_rows)
        if len(groups) > 1:
            return {
                "status": "ambiguous",
                "query": query,
                "message": "名称对应多个 ISSN 身份，请指定 ISSN",
                "candidates": [
                    {
                        "names": sorted(group["names"]),
                        "issns": sorted(group["identifiers"]),
                    }
                    for group in groups
                ],
            }

        group = groups[0]
        journal_norms = {row["journal_norm"] for row in group["rows"]}
        jcr_rows, emerging_rows = fetch_identity_rows(
            connection, group["identifiers"], journal_norms
        )
        years = latest_jcr_years(connection)

        history = []
        for year in years:
            rows = [row for row in jcr_rows if row["year"] == year]
            categories = unique(row["category"] for row in rows)
            history.append(
                {
                    "year": year,
                    "jif": unique(row["jif"] for row in rows),
                    "jcr_quartile": unique(row["jcr_quartile"] for row in rows),
                    "indexes": category_indexes(categories),
                    "rankings": [],
                    "categories": categories,
                }
            )

        names = unique(
            [row["journal"] for row in jcr_rows]
            + [row["journal"] for row in emerging_rows]
        )
        display_name = min(names, key=len) if names else query
        issns = unique_issns(
            [row["issn"] for row in jcr_rows]
            + [row["eissn"] for row in jcr_rows]
            + [row["issn1"] for row in emerging_rows]
            + [row["issn2"] for row in emerging_rows]
        )
        doaj_result = query_doaj(db_path, query, names, issns)
        doaj = (
            doaj_result["record"]
            if doaj_result and doaj_result["status"] == "found"
            else None
        )
        if doaj:
            names = unique(names + [doaj["title"], doaj["alternative_title"]])
            issns = unique_issns(issns + doaj["issns"])
        publisher_metrics, publisher_source = query_publisher(
            db_path, query, names, issns, doaj
        )
        sources = [db_path.name]
        if doaj:
            sources.append("doaj.sqlite")
        if publisher_metrics:
            sources.append(publisher_source)
        return {
            "status": "found",
            "query": query,
            "journal": {"name": display_name, "aliases": names, "issns": issns},
            "jcr_history": history,
            "emerging_2026": {
                "quartile": unique(row["emerging_quartile"] for row in emerging_rows),
                "major_categories": unique(row["major_category"] for row in emerging_rows),
            },
            "doaj": doaj,
            "doaj_candidates": (
                doaj_result["candidates"]
                if doaj_result and doaj_result["status"] == "ambiguous"
                else []
            ),
            "publisher_metrics": publisher_metrics,
            "source": sources,
        }
    finally:
        connection.close()


def format_values(values: list[str]) -> str:
    return " / ".join(values) if values else "本地数据未收录"


def format_optional(value: object, suffix: str = "") -> str:
    if value is None or value == "":
        return "本地数据未收录"
    if isinstance(value, float) and value.is_integer():
        value = int(value)
    return f"{value}{suffix}"


def format_boolean(value: bool | None) -> str:
    if value is None:
        return "本地数据未收录"
    return "是" if value else "否"


def compact_values(values: list[str]) -> str:
    return " / ".join(values) if values else "—"


def escape_markdown_table_text(value: str) -> str:
    return value.replace("|", "\\|").replace("\n", "<br>")


def render_inline_code(value: str) -> str:
    escaped = value.replace("\\", "\\\\").replace("`", "\\`")
    return f"`{escaped}`"


def render_issns(issns: list[str]) -> str:
    return render_inline_code(" / ".join(issns)) if issns else "—"


def compact_optional(value: object, suffix: str = "") -> str:
    if value is None or value == "":
        return "—"
    if isinstance(value, float) and value.is_integer():
        value = int(value)
    return f"{value}{suffix}"


def compact_boolean(value: bool | None) -> str:
    if value is None:
        return "—"
    return "Yes" if value else "No"


def display_categories(values: list[str]) -> str:
    if not values:
        return "—"
    rendered = []
    for value in values:
        rendered.append(value.replace(";", ";<br>"))
    return "<br>".join(rendered)


def latest_nonempty(history: list[dict[str, Any]], key: str) -> tuple[int | None, list[str]]:
    for item in reversed(history):
        values = item.get(key, [])
        if values:
            return item["year"], values
    return None, []


def aggregate_jcr_summary(history: list[dict[str, Any]]) -> dict[str, str]:
    jif_year, jif_values = latest_nonempty(history, "jif")
    quartile_year, quartile_values = latest_nonempty(history, "jcr_quartile")
    ranking_year, ranking_values = latest_nonempty(history, "rankings")

    index_values = sorted(
        {value for item in history for value in item.get("indexes", []) if value}
    )

    category_year = None
    category_values: list[str] = []
    for item in reversed(history):
        values = item.get("categories", [])
        if not values:
            continue
        if values != ["Multiple"]:
            category_year = item["year"]
            category_values = values
            break
    if not category_values:
        category_year, category_values = latest_nonempty(history, "categories")

    return {
        "jif": compact_values(jif_values),
        "jif_year": str(jif_year) if jif_year else "—",
        "quartile": compact_values(quartile_values),
        "quartile_year": str(quartile_year) if quartile_year else "—",
        "indexes": compact_values(index_values),
        "categories": display_categories(category_values),
        "category_year": str(category_year) if category_year else "—",
        "rankings": compact_values(ranking_values),
        "ranking_year": str(ranking_year) if ranking_year else "—",
    }


def format_text(result: dict[str, Any]) -> str:
    if result["status"] != "found":
        return json.dumps(result, ensure_ascii=False, indent=2)
    lines = []
    fallback = result.get("fallback")
    if fallback:
        lines.extend(
            [
                f"> Original query: {fallback['original_query']}",
                f"> Auto-selected suggestion #1: {fallback['selected_suggestion']}",
                "",
            ]
        )

    history = result["jcr_history"]
    emerging = result["emerging_2026"]
    summary = aggregate_jcr_summary(history)
    doaj = result.get("doaj")
    publisher = result.get("publisher_metrics")
    journal_link = None
    if doaj and doaj.get("journal_url"):
        journal_link = doaj["journal_url"]
    elif publisher and publisher.get("journal_url"):
        journal_link = publisher["journal_url"]
    journal_name = escape_markdown_table_text(result["journal"]["name"])
    journal_label = (
        f"[**{journal_name}**](<{journal_link}>)"
        if journal_link
        else f"**{journal_name}**"
    )
    rows: list[tuple[str, str] | None] = [
        ("Journal", journal_label),
        ("ISSN", render_issns(result["journal"]["issns"])),
        ("JIF", f"**{summary['jif']}**"),
        ("JCR Quartile", f"**{summary['quartile']}**"),
        (
            "2026 新锐分区",
            compact_values(emerging["quartile"])
            + " · "
            + compact_values(emerging["major_categories"]),
        ),
        ("Indexing", summary["indexes"]),
        ("JCR Categories", summary["categories"]),
        ("Ranking", summary["rankings"]) if summary["rankings"] != "—" else None,
    ]

    if doaj:
        fees = doaj["fees"]
        editorial = doaj["editorial"]
        open_access = doaj["open_access"]
        archiving = doaj["archiving"]
        freshness = doaj["freshness"]
        apc = compact_boolean(fees["apc"])
        if fees["apc_amount_raw"]:
            apc += f"（{fees['apc_amount_raw']}）"
        rows.extend(
            [
                ("DOAJ · Publisher", compact_optional(doaj["publisher"]["name"])),
                ("DOAJ · Country", compact_optional(doaj["publisher"]["country"])),
                ("DOAJ · License", compact_optional(open_access["license"])),
                ("DOAJ · License Since", compact_optional(open_access["open_license_since"])),
                ("DOAJ · Author Holds Copyright", compact_boolean(open_access["author_holds_copyright"])),
                ("DOAJ · APC", apc),
                ("DOAJ · Waiver Policy", compact_boolean(fees["waiver_policy"])),
                ("DOAJ · Other Fees", compact_boolean(fees["has_other_fees"])),
                ("DOAJ · Review Process", compact_optional(editorial["review_process"])),
                ("DOAJ · Plagiarism Screening", compact_boolean(editorial["plagiarism_screening"])),
                ("DOAJ · Submission to Publication", compact_optional(editorial["submission_to_publication_weeks"], " weeks")),
                ("DOAJ · Preservation Services", compact_optional(archiving["preservation_services"])),
                ("DOAJ · DOI/PID", compact_optional(archiving["persistent_article_identifiers"])),
                ("DOAJ · Last Full Review", compact_optional(freshness["last_full_review_date"])),
                ("DOAJ · Article Records", compact_optional(freshness["article_records_in_doaj"])),
            ]
        )
    if publisher:
        rows.extend(
            [
                ("Publisher · Name", compact_optional(publisher["publisher_group"])),
                ("Publisher · Directory Ranking", compact_optional(publisher.get("journal_ranking"))),
                ("Publisher · Submission to First Decision", compact_optional(publisher["first_decision_days"], " days")),
                ("Publisher · Acceptance Rate", compact_optional(publisher["acceptance_rate_percent"], "%")),
                ("Publisher · Submission to Acceptance", compact_optional(publisher["submission_to_acceptance_days"], " days")),
                ("Publisher · Acceptance to Online", compact_optional(publisher["acceptance_to_online_days"], " days")),
                ("Publisher · OA Model", compact_optional(publisher["oa_model"])),
                ("Publisher · APC", compact_optional(publisher["apc_raw"])),
                ("Publisher · Peer Review Model", compact_optional(publisher.get("peer_review_model"))),
                ("Publisher · Article Count", compact_optional(publisher.get("article_count_total"))),
                ("Publisher · Article Views", compact_optional(publisher.get("article_views_total"))),
                ("Publisher · Article Downloads", compact_optional(publisher.get("article_downloads_total"))),
                ("Publisher · Directory IF", compact_optional(publisher.get("publisher_jif"))),
                ("Publisher · CiteScore", compact_optional(publisher.get("cite_score"))),
                ("Publisher · Observed At", compact_optional(publisher["observed_at_utc"])),
            ]
        )

    lines.extend(
        [
            "**Overview**",
            "",
            "| Field | Value |",
            "|---|---|",
        ]
    )
    lines.extend(
        f"| {label} | {value} |"
        for row in rows
        if row is not None
        for label, value in [row]
        if value != "—"
    )
    lines.extend(
        [
            "",
            f"[hiDaDeng/journal-metrics]({REPOSITORY_URL}) Please re-check critical details before submission.",
        ]
    )
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("query", help="期刊名、ISSN 或 eISSN")
    parser.add_argument("--db", type=Path, default=DEFAULT_DB)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    result = query_database(args.db, args.query)
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print(format_text(result))


if __name__ == "__main__":
    main()
