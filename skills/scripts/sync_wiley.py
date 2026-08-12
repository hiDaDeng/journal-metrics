#!/usr/bin/env python3
"""Synchronize Wiley Journal Finder records into a publisher SQLite database."""

from __future__ import annotations

import argparse
import json
import os
import re
import sqlite3
import time
import unicodedata
from datetime import datetime, timezone
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


ENDPOINT = "https://wiley.n4.studio/search/search"
SOURCE_PAGE = "https://www.wiley.com/en-us/journal-finder/"
PAGE_SIZE = 100


def normalize_name(value: str) -> str:
    text = unicodedata.normalize("NFKC", value.strip()).casefold()
    return "".join(character for character in text if character.isalnum())


def missing_to_none(value: object) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return None if not text or text.upper() == "N/A" else text


def number(value: object) -> float | None:
    text = missing_to_none(value)
    if text is None:
        return None
    match = re.search(r"-?\d+(?:\.\d+)?", text.replace(",", ""))
    return float(match.group()) if match else None


def inferred_issn(url: str) -> str | None:
    token = url.rstrip("/").rsplit("/", 1)[-1].upper()
    if not re.fullmatch(r"\d{7}[\dX]", token):
        return None
    return f"{token[:4]}-{token[4:]}"


def fetch_page(page: int, timeout: int) -> dict[str, object]:
    payload = json.dumps(
        {
            "page": page,
            "numResultsPerPage": PAGE_SIZE,
            "filters": {},
            "sortBy": "title_a_z",
        }
    ).encode("utf-8")
    request = Request(
        ENDPOINT,
        data=payload,
        method="POST",
        headers={
            "content-type": "application/json",
            "user-agent": "journal-metrics-research/0.1",
        },
    )
    try:
        with urlopen(request, timeout=timeout) as response:
            return json.load(response)
    except HTTPError as error:
        retry_after = error.headers.get("Retry-After")
        detail = f"HTTP {error.code}"
        if retry_after:
            detail += f", Retry-After={retry_after}"
        raise RuntimeError(f"Wiley sync stopped: {detail}") from error
    except URLError as error:
        raise RuntimeError(f"Wiley sync stopped: {error.reason}") from error


def create_schema(connection: sqlite3.Connection) -> None:
    connection.executescript(
        """
        CREATE TABLE journals (
            wiley_id TEXT PRIMARY KEY,
            code TEXT,
            title TEXT NOT NULL,
            title_norm TEXT NOT NULL,
            inferred_issn TEXT,
            journal_url TEXT,
            author_guidelines_url TEXT,
            revenue_model TEXT,
            open_access_choices TEXT,
            first_decision_days REAL,
            first_decision_raw TEXT,
            acceptance_rate_percent REAL,
            acceptance_rate_raw TEXT,
            acceptance_to_online_days REAL,
            acceptance_to_online_raw TEXT,
            apc_amount REAL,
            apc_currency TEXT,
            apc_raw TEXT,
            journal_impact_factor REAL,
            journal_impact_factor_raw TEXT,
            cas_journal_ranking TEXT,
            full_text_views REAL,
            full_text_views_raw TEXT,
            peer_review_model TEXT,
            free_format_submission TEXT,
            data_sharing_policy TEXT,
            orcid_policy TEXT,
            preprints_policy TEXT,
            self_archiving_submitted_version TEXT,
            self_archiving_accepted_version TEXT,
            observed_at_utc TEXT NOT NULL,
            source_url TEXT NOT NULL,
            raw_json TEXT NOT NULL
        );

        CREATE INDEX idx_wiley_title ON journals(title_norm);
        CREATE INDEX idx_wiley_issn ON journals(inferred_issn);

        CREATE TABLE metadata (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL
        );
        """
    )


def insert_record(
    connection: sqlite3.Connection, item: dict[str, object], observed_at: str
) -> None:
    title = str(item.get("title") or "").strip()
    if not title:
        return
    journal_url = str(item.get("url") or "").strip()
    values = {
        "wiley_id": str(item.get("id") or item.get("code") or title),
        "code": missing_to_none(item.get("code")),
        "title": title,
        "title_norm": normalize_name(title),
        "inferred_issn": inferred_issn(journal_url),
        "journal_url": missing_to_none(journal_url),
        "author_guidelines_url": missing_to_none(item.get("authorGuidelinesUrl")),
        "revenue_model": missing_to_none(item.get("revenueModel")),
        "open_access_choices": missing_to_none(item.get("openAccessLicenseChoices")),
        "first_decision_days": number(item.get("submissionToFirstDecision")),
        "first_decision_raw": missing_to_none(item.get("submissionToFirstDecision")),
        "acceptance_rate_percent": number(item.get("acceptanceRate")),
        "acceptance_rate_raw": missing_to_none(item.get("acceptanceRate")),
        "acceptance_to_online_days": number(item.get("acceptanceToOnlinePublication")),
        "acceptance_to_online_raw": missing_to_none(item.get("acceptanceToOnlinePublication")),
        "apc_amount": number(item.get("publicationCharge")),
        "apc_currency": "USD" if number(item.get("publicationCharge")) is not None else None,
        "apc_raw": missing_to_none(item.get("publicationCharge")),
        "journal_impact_factor": number(item.get("journalImpactFactor")),
        "journal_impact_factor_raw": missing_to_none(item.get("journalImpactFactor")),
        "cas_journal_ranking": missing_to_none(item.get("casJournalRanking")),
        "full_text_views": number(item.get("fullTextViews")),
        "full_text_views_raw": missing_to_none(item.get("fullTextViews")),
        "peer_review_model": missing_to_none(item.get("peerReviewModel")),
        "free_format_submission": missing_to_none(item.get("freeFormatSubmission")),
        "data_sharing_policy": missing_to_none(item.get("dataSharingPolicy")),
        "orcid_policy": missing_to_none(item.get("orcidPolicy")),
        "preprints_policy": missing_to_none(item.get("preprintsPolicy")),
        "self_archiving_submitted_version": missing_to_none(
            item.get("selfArchivingSubmittedVersion")
        ),
        "self_archiving_accepted_version": missing_to_none(
            item.get("selfArchivingAcceptedVersion")
        ),
        "observed_at_utc": observed_at,
        "source_url": SOURCE_PAGE,
        "raw_json": json.dumps(item, ensure_ascii=False, sort_keys=True),
    }
    columns = ", ".join(values)
    placeholders = ", ".join("?" for _ in values)
    connection.execute(
        f"INSERT INTO journals ({columns}) VALUES ({placeholders})", tuple(values.values())
    )


def sync(output: Path, delay: float, timeout: int) -> dict[str, object]:
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.with_suffix(output.suffix + ".tmp")
    if temporary.exists():
        temporary.unlink()

    observed_at = datetime.now(timezone.utc).isoformat()
    first = fetch_page(1, timeout)
    total_pages = int(first.get("totalPages") or 1)
    expected_records = int(first.get("resultCount") or 0)
    pages = [first]
    for page_number in range(2, total_pages + 1):
        if delay:
            time.sleep(delay)
        pages.append(fetch_page(page_number, timeout))

    connection = sqlite3.connect(temporary)
    try:
        create_schema(connection)
        for page in pages:
            for item in page.get("items", []):
                insert_record(connection, item, observed_at)
        actual_records = connection.execute("SELECT COUNT(*) FROM journals").fetchone()[0]
        if expected_records and actual_records != expected_records:
            raise RuntimeError(
                f"Wiley record count mismatch: expected {expected_records}, got {actual_records}"
            )
        metadata = {
            "publisher_group": "Wiley",
            "observed_at_utc": observed_at,
            "source_url": SOURCE_PAGE,
            "endpoint": ENDPOINT,
            "record_count": str(actual_records),
            "request_count": str(total_pages),
            "page_size": str(PAGE_SIZE),
        }
        connection.executemany(
            "INSERT INTO metadata(key, value) VALUES (?, ?)", metadata.items()
        )
        connection.commit()
        integrity = connection.execute("PRAGMA integrity_check").fetchone()[0]
        if integrity != "ok":
            raise RuntimeError(f"SQLite integrity check failed: {integrity}")
    finally:
        connection.close()

    os.replace(temporary, output)
    return {
        "output": str(output),
        "records": actual_records,
        "requests": total_pages,
        "observed_at_utc": observed_at,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output",
        type=Path,
        default=Path(__file__).resolve().parent.parent
        / "assets"
        / "publishers"
        / "wiley.sqlite",
    )
    parser.add_argument("--delay", type=float, default=0.5)
    parser.add_argument("--timeout", type=int, default=60)
    args = parser.parse_args()
    print(json.dumps(sync(args.output, args.delay, args.timeout), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
