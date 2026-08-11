#!/usr/bin/env python3
"""Build the DOAJ journal SQLite database from a DOAJ CSV export."""

from __future__ import annotations

import argparse
import csv
import json
import os
import re
import sqlite3
import tempfile
import unicodedata
from datetime import datetime, timezone
from pathlib import Path


DEFAULT_OUTPUT = Path(__file__).resolve().parent.parent / "assets" / "doaj.sqlite"


def normalize_name(value: str) -> str:
    text = unicodedata.normalize("NFKC", value.strip()).casefold()
    return "".join(char for char in text if char.isalnum())


def normalize_issn(value: str) -> str:
    normalized = re.sub(r"[^0-9X]", "", value.upper())
    return normalized if len(normalized) == 8 else ""


def doaj_id_from_url(value: str) -> str:
    match = re.search(r"/toc/([0-9a-fA-F]{32})/?$", value.strip())
    if not match:
        raise ValueError(f"Could not extract DOAJ id from {value!r}")
    return match.group(1).lower()


def yes_no(value: str) -> int | None:
    normalized = value.strip().casefold()
    if normalized == "yes":
        return 1
    if normalized == "no":
        return 0
    return None


def numeric(value: str) -> float | None:
    try:
        return float(value.strip())
    except (AttributeError, ValueError):
        return None


def integer(value: str) -> int | None:
    try:
        return int(value.strip())
    except (AttributeError, ValueError):
        return None


def build_database(source_csv: Path, output: Path) -> int:
    output.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        prefix="doaj-", suffix=".sqlite", dir=output.parent
    )
    os.close(descriptor)
    temporary = Path(temporary_name)
    imported_at = datetime.now(timezone.utc).isoformat()
    try:
        connection = sqlite3.connect(temporary)
        try:
            connection.executescript(
                """
                PRAGMA page_size = 4096;
                CREATE TABLE journals (
                    doaj_id TEXT PRIMARY KEY,
                    journal_title TEXT NOT NULL,
                    title_norm TEXT NOT NULL,
                    journal_url TEXT NOT NULL,
                    doaj_url TEXT NOT NULL UNIQUE,
                    open_license_since TEXT,
                    alternative_title TEXT,
                    alternative_title_norm TEXT,
                    print_issn TEXT,
                    print_issn_norm TEXT,
                    online_issn TEXT,
                    online_issn_norm TEXT,
                    keywords TEXT,
                    accepted_languages TEXT,
                    publisher TEXT,
                    publisher_norm TEXT,
                    publisher_country TEXT,
                    other_organization TEXT,
                    other_organization_country TEXT,
                    journal_license TEXT,
                    license_attributes TEXT,
                    license_terms_url TEXT,
                    machine_readable_cc INTEGER,
                    author_holds_copyright INTEGER,
                    copyright_url TEXT,
                    review_process TEXT,
                    review_process_url TEXT,
                    plagiarism_screening INTEGER,
                    aims_scope_url TEXT,
                    editorial_board_url TEXT,
                    author_instructions_url TEXT,
                    submission_to_publication_weeks REAL,
                    apc INTEGER,
                    apc_info_url TEXT,
                    apc_amount_raw TEXT,
                    waiver_policy INTEGER,
                    waiver_policy_url TEXT,
                    has_other_fees INTEGER,
                    other_fees_url TEXT,
                    preservation_services TEXT,
                    preservation_national_library TEXT,
                    preservation_url TEXT,
                    deposit_policy_directory TEXT,
                    deposit_policy_url TEXT,
                    persistent_article_identifiers TEXT,
                    complies_with_doaj_oa INTEGER,
                    continues TEXT,
                    continued_by TEXT,
                    lcc_codes TEXT,
                    subscribe_to_open INTEGER,
                    mirror_journal INTEGER,
                    open_journals_collective INTEGER,
                    subjects TEXT,
                    added_at TEXT,
                    last_updated_at TEXT,
                    last_full_review_date TEXT,
                    article_records INTEGER,
                    most_recent_article_added_at TEXT,
                    source_row INTEGER NOT NULL
                );
                CREATE INDEX journals_title_norm_idx ON journals(title_norm);
                CREATE INDEX journals_alt_title_norm_idx ON journals(alternative_title_norm);
                CREATE INDEX journals_print_issn_idx ON journals(print_issn_norm);
                CREATE INDEX journals_online_issn_idx ON journals(online_issn_norm);
                CREATE INDEX journals_publisher_norm_idx ON journals(publisher_norm);
                CREATE TABLE metadata (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL
                );
                """
            )

            rows = []
            with source_csv.open(encoding="utf-8-sig", newline="") as source:
                reader = csv.DictReader(source)
                for source_row, row in enumerate(reader, start=2):
                    title = row["Journal title"].strip()
                    alternative_title = row["Alternative title"].strip()
                    publisher = row["Publisher"].strip()
                    rows.append(
                        (
                            doaj_id_from_url(row["URL in DOAJ"]),
                            title,
                            normalize_name(title),
                            row["Journal URL"].strip(),
                            row["URL in DOAJ"].strip(),
                            row["When did the journal start to publish all content using an open license?"].strip(),
                            alternative_title,
                            normalize_name(alternative_title),
                            row["Journal ISSN (print version)"].strip(),
                            normalize_issn(row["Journal ISSN (print version)"]),
                            row["Journal EISSN (online version)"].strip(),
                            normalize_issn(row["Journal EISSN (online version)"]),
                            row["Keywords"].strip(),
                            row["Languages in which the journal accepts manuscripts"].strip(),
                            publisher,
                            normalize_name(publisher),
                            row["Country of publisher"].strip(),
                            row["Other organisation"].strip(),
                            row["Country of other organisation"].strip(),
                            row["Journal license"].strip(),
                            row["License attributes"].strip(),
                            row["URL for license terms"].strip(),
                            yes_no(row["Machine-readable CC licensing information embedded or displayed in articles"]),
                            yes_no(row["Author holds copyright without restrictions"]),
                            row["Copyright information URL"].strip(),
                            row["Review process"].strip(),
                            row["Review process information URL"].strip(),
                            yes_no(row["Journal plagiarism screening policy"]),
                            row["URL for journal's aims & scope"].strip(),
                            row["URL for the Editorial Board page"].strip(),
                            row["URL for journal's instructions for authors"].strip(),
                            numeric(row["Average number of weeks between article submission and publication"]),
                            yes_no(row["APC"]),
                            row["APC information URL"].strip(),
                            row["APC amount"].strip(),
                            yes_no(row["Journal waiver policy (for developing country authors etc)"]),
                            row["Waiver policy information URL"].strip(),
                            yes_no(row["Has other fees"]),
                            row["Other fees information URL"].strip(),
                            row["Preservation Services"].strip(),
                            row["Preservation Service: national library"].strip(),
                            row["Preservation information URL"].strip(),
                            row["Deposit policy directory"].strip(),
                            row["URL for deposit policy"].strip(),
                            row["Persistent article identifiers"].strip(),
                            yes_no(row["Does the journal comply to DOAJ's definition of open access?"]),
                            row["Continues"].strip(),
                            row["Continued By"].strip(),
                            row["LCC Codes"].strip(),
                            yes_no(row["Subscribe to Open"]),
                            yes_no(row["Mirror Journal"]),
                            yes_no(row["Open Journals Collective"]),
                            row["Subjects"].strip(),
                            row["Added on Date"].strip(),
                            row["Last updated Date"].strip(),
                            row["Last Full Review Date"].strip(),
                            integer(row["Number of Article Records"]),
                            row["Most Recent Article Added"].strip(),
                            source_row,
                        )
                    )

            if not rows:
                raise ValueError("Refusing to build an empty DOAJ database")
            placeholders = ", ".join("?" for _ in range(len(rows[0])))
            connection.executemany(
                f"INSERT INTO journals VALUES ({placeholders})", rows
            )
            connection.executemany(
                "INSERT INTO metadata(key, value) VALUES (?, ?)",
                [
                    ("source_file", source_csv.name),
                    ("source_size_bytes", str(source_csv.stat().st_size)),
                    ("source_modified_at", datetime.fromtimestamp(source_csv.stat().st_mtime, timezone.utc).isoformat()),
                    ("imported_at_utc", imported_at),
                    ("journal_count", str(len(rows))),
                    ("schema_version", "1"),
                ],
            )
            connection.commit()
            stored = connection.execute("SELECT COUNT(*) FROM journals").fetchone()[0]
            unique_ids = connection.execute(
                "SELECT COUNT(DISTINCT doaj_id) FROM journals"
            ).fetchone()[0]
            if stored != len(rows) or unique_ids != len(rows):
                raise RuntimeError(
                    f"DOAJ validation failed: parsed={len(rows)}, stored={stored}, ids={unique_ids}"
                )
            integrity = connection.execute("PRAGMA integrity_check").fetchone()[0]
            if integrity != "ok":
                raise RuntimeError(f"SQLite integrity check failed: {integrity}")
            connection.execute("VACUUM")
        finally:
            connection.close()
        os.replace(temporary, output)
        return len(rows)
    except Exception:
        temporary.unlink(missing_ok=True)
        raise


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source_csv", type=Path)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    count = build_database(args.source_csv, args.output)
    print(f"DOAJ: {count} journals -> {args.output}")


if __name__ == "__main__":
    main()
