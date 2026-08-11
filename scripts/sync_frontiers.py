#!/usr/bin/env python3
"""Build the Frontiers publisher database from its consolidated journal catalog."""

from __future__ import annotations

import argparse
import json
import os
import re
import sqlite3
import tempfile
import unicodedata
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


CATALOG_URL = "https://www.frontiersin.org/api/v3/journals/search/journal-filter"
DEFAULT_OUTPUT = (
    Path(__file__).resolve().parent.parent
    / "assets"
    / "publishers"
    / "frontiers.sqlite"
)
PAYLOAD = {
    "Skip": 0,
    "Top": 300,
    "DomainId": 0,
    "JournalIds": [],
    "Search": "",
    "FirstLetter": "",
}


def normalize_name(value: str) -> str:
    text = unicodedata.normalize("NFKC", value.strip()).casefold()
    return "".join(char for char in text if char.isalnum())


def normalize_issn(value: str | None) -> str:
    return re.sub(r"[^0-9X]", "", (value or "").upper())


def fetch_catalog(timeout: float) -> dict[str, Any]:
    request = urllib.request.Request(
        CATALOG_URL,
        data=json.dumps(PAYLOAD).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "Accept": "application/json",
            "User-Agent": "journal-metrics/1.0 (+local academic journal lookup)",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return json.load(response)
    except urllib.error.HTTPError as error:
        retry_after = error.headers.get("Retry-After")
        detail = f"HTTP {error.code}"
        if retry_after:
            detail += f"; Retry-After={retry_after}"
        raise RuntimeError(f"Frontiers catalog request stopped: {detail}") from error


def impact_value(journal: dict[str, Any], code: str) -> float | None:
    for item in journal.get("Impact") or []:
        if item.get("Code") == code:
            try:
                return float(item["Value"])
            except (KeyError, TypeError, ValueError):
                return None
    return None


def count_value(journal: dict[str, Any], key: str) -> int | None:
    value = journal.get(key)
    if not isinstance(value, dict):
        return None
    count = value.get("Count")
    return count if isinstance(count, int) else None


def validate_catalog(payload: dict[str, Any]) -> list[dict[str, Any]]:
    journals = payload.get("Journals")
    total = payload.get("TotalOnlineJournalsCount")
    if not isinstance(journals, list) or not journals:
        raise ValueError("Frontiers response did not contain a non-empty Journals list")
    if isinstance(total, int) and len(journals) != total:
        raise ValueError(
            f"Frontiers response is incomplete: received {len(journals)} of {total}"
        )
    return journals


def build_database(
    payload: dict[str, Any], output: Path, observed_at_utc: str
) -> int:
    journals = validate_catalog(payload)
    output.parent.mkdir(parents=True, exist_ok=True)
    file_descriptor, temporary_name = tempfile.mkstemp(
        prefix="frontiers-", suffix=".sqlite", dir=output.parent
    )
    os.close(file_descriptor)
    temporary = Path(temporary_name)
    try:
        connection = sqlite3.connect(temporary)
        try:
            connection.executescript(
                """
                CREATE TABLE journals (
                    journal_id INTEGER PRIMARY KEY,
                    title TEXT NOT NULL,
                    title_norm TEXT NOT NULL,
                    issn TEXT,
                    issn_norm TEXT,
                    slug TEXT NOT NULL,
                    source_url TEXT NOT NULL,
                    scope_html TEXT,
                    article_count_total INTEGER,
                    article_views_total INTEGER,
                    article_downloads_total INTEGER,
                    section_count INTEGER,
                    publisher_jif REAL,
                    cite_score REAL,
                    is_owner_frontiers INTEGER NOT NULL,
                    observed_at_utc TEXT NOT NULL,
                    raw_json TEXT NOT NULL
                );
                CREATE INDEX journals_title_norm_idx ON journals(title_norm);
                CREATE INDEX journals_issn_norm_idx ON journals(issn_norm);
                CREATE TABLE metadata (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL
                );
                """
            )
            rows = []
            for journal in journals:
                title = journal.get("AlternativeText") or " ".join(
                    part
                    for part in (journal.get("Prefix"), journal.get("Title"))
                    if part
                )
                if not title or not journal.get("Id") or not journal.get("Slug"):
                    continue
                issn = journal.get("ISSN")
                rows.append(
                    (
                        journal["Id"],
                        title,
                        normalize_name(title),
                        issn,
                        normalize_issn(issn),
                        journal["Slug"],
                        journal.get("PublicUrl")
                        or f"https://www.frontiersin.org/journals/{journal['Slug']}",
                        journal.get("Scope"),
                        count_value(journal, "ArticleCount"),
                        count_value(journal, "ArticleViewsCount"),
                        count_value(journal, "ArticleDownloadsCount"),
                        count_value(journal, "SectionCount"),
                        impact_value(journal, "ImpactFactor"),
                        impact_value(journal, "CiteScore"),
                        int(bool(journal.get("IsOwnerFrontiers"))),
                        observed_at_utc,
                        json.dumps(journal, ensure_ascii=False, separators=(",", ":")),
                    )
                )
            if len(rows) != len(journals):
                raise ValueError(
                    f"Refusing partial database: parsed {len(rows)} of {len(journals)} journals"
                )
            connection.executemany(
                "INSERT INTO journals VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                rows,
            )
            connection.executemany(
                "INSERT INTO metadata(key, value) VALUES (?, ?)",
                [
                    ("publisher_group", "Frontiers"),
                    ("catalog_url", CATALOG_URL),
                    ("observed_at_utc", observed_at_utc),
                    ("journal_count", str(len(rows))),
                    ("request_count", "1"),
                ],
            )
            connection.commit()
            result = connection.execute("PRAGMA integrity_check").fetchone()[0]
            if result != "ok":
                raise RuntimeError(f"SQLite integrity check failed: {result}")
        finally:
            connection.close()
        os.replace(temporary, output)
        return len(rows)
    except Exception:
        temporary.unlink(missing_ok=True)
        raise


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument(
        "--input-json",
        type=Path,
        help="Build from a previously downloaded response instead of using the network",
    )
    parser.add_argument("--timeout", type=float, default=30.0)
    args = parser.parse_args()

    if args.input_json:
        payload = json.loads(args.input_json.read_text(encoding="utf-8"))
    else:
        payload = fetch_catalog(args.timeout)
    observed_at_utc = datetime.now(timezone.utc).isoformat()
    count = build_database(payload, args.output, observed_at_utc)
    print(f"Frontiers: {count} journals, 1 catalog request -> {args.output}")


if __name__ == "__main__":
    main()
