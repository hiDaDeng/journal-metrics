#!/usr/bin/env python3
"""Refresh all supported publisher-level journal databases."""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path


SCRIPTS = {
    "wiley": "sync_wiley.py",
    "frontiers": "sync_frontiers.py",
}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "sources",
        nargs="*",
        choices=sorted(SCRIPTS),
        help="Defaults to every supported source",
    )
    args = parser.parse_args()
    selected = args.sources or list(SCRIPTS)
    scripts_directory = Path(__file__).resolve().parent
    failures: list[str] = []

    for source in selected:
        print(f"Updating {source}...")
        completed = subprocess.run(
            [sys.executable, str(scripts_directory / SCRIPTS[source])], check=False
        )
        if completed.returncode:
            failures.append(source)

    if failures:
        raise SystemExit("Publisher updates failed: " + ", ".join(failures))


if __name__ == "__main__":
    main()
