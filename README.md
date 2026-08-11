# journal-metrics

[English](./README.md) | [中文](./README-zh.md)

**Journal Metrics**

A local agent skill for concise journal lookups across JIF, JCR quartiles, indexing, DOAJ, and selected publisher submission metrics.

## Overview

- Query multiple local SQLite indexes through one entrypoint.
- Return a compact table focused on the fields most relevant to journal selection.
- Keep source boundaries explicit instead of filling missing fields by guesswork.

## Installation

In an agent chat window (Codex, OpenCode, Claude Code, Kimi Code, etc.), run the following command:

```text
Install GitHub repo hiDaDeng/journal-metrics.
```

## Usage

Typical agent prompt:

```text
$journal-metrics Computers in Human Behavior
```

Direct command-line usage:

```bash
python3 scripts/query.py "Computers in Human Behavior"
python3 scripts/query.py "Computers in Human Behavior" --json
```

## Output

The default response is a single summary table, usually including:

- Journal and ISSN
- JIF
- JCR Quartile
- 2026 新锐分区
- Indexing (`SCI` / `SCIE` / `SSCI` / `ESCI` / `AHCI`)
- JCR Categories
- Ranking, if locally available
- DOAJ fields, if matched
- Publisher metrics, if matched

Status handling:

- `found`: return the result directly
- `ambiguous`: return candidates and wait for a narrower journal identity
- `not_found`: auto-apply suggestion #1 when available; otherwise report that local data is unavailable

## Project Structure

```text
journal-metrics/
├── SKILL.md
├── README.md
├── README-zh.md
├── agents/
│   └── openai.yaml
├── scripts/
│   ├── query.py
│   ├── build_index.py
│   ├── build_doaj.py
│   ├── sync_publishers.py
│   ├── sync_wiley.py
│   └── sync_frontiers.py
└── assets/
    ├── journal-metrics.sqlite
    ├── doaj.sqlite
    └── publishers/
        ├── wiley.sqlite
        └── frontiers.sqlite
```

## File Guide

- `SKILL.md`  
  Core operating instructions for the skill.

- `README.md`  
  English project overview.

- `README-zh.md`  
  Chinese project overview.

- `agents/openai.yaml`  
  UI metadata for display name, short description, and default prompt.

- `scripts/query.py`  
  Main query entrypoint for lookup, aggregation, and output formatting.

- `scripts/build_index.py`  
  Builds `journal-metrics.sqlite` from local JCR workbooks and the 2026 emerging-quartile workbook.

- `scripts/build_doaj.py`  
  Builds `doaj.sqlite` from an official DOAJ CSV snapshot.

- `scripts/sync_wiley.py`  
  Syncs public Wiley directory metrics.

- `scripts/sync_frontiers.py`  
  Syncs public Frontiers directory metrics.

- `scripts/sync_publishers.py`  
  Batch sync entrypoint for supported publisher datasets.

- `assets/journal-metrics.sqlite`  
  Main lookup database built from local JCR and emerging-quartile source tables.

- `assets/doaj.sqlite`  
  Fast lookup database generated from the DOAJ CSV snapshot.

- `assets/publishers/wiley.sqlite`  
  Generated from public Wiley directory data.

- `assets/publishers/frontiers.sqlite`  
  Generated from public Frontiers directory data.

## Notes

- The repository is still under active construction.
- Please re-check critical details before submission.
