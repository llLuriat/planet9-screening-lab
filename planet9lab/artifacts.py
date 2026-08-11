from __future__ import annotations

import csv
import json
from collections.abc import Iterable
from pathlib import Path


def ensure_dir(path: str | Path) -> Path:
    target = Path(path)
    target.mkdir(parents=True, exist_ok=True)
    return target


def write_json(path: str | Path, data: object) -> None:
    path = Path(path)
    ensure_dir(path.parent)
    path.write_text(json.dumps(data, indent=2, sort_keys=True), encoding="utf-8")


def write_text(path: str | Path, content: str) -> None:
    path = Path(path)
    ensure_dir(path.parent)
    path.write_text(content, encoding="utf-8")


def write_csv(path: str | Path, rows: Iterable[dict], fieldnames: list[str] | None = None) -> None:
    rows = list(rows)
    path = Path(path)
    ensure_dir(path.parent)
    if fieldnames is None:
        keys: list[str] = []
        for row in rows:
            for key in row:
                if key not in keys:
                    keys.append(key)
        fieldnames = keys
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow({key: "" if row.get(key) is None else row.get(key) for key in fieldnames})


def read_csv_dicts(path: str | Path) -> list[dict[str, str]]:
    with Path(path).open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def append_csv_row(path: str | Path, row: dict, fieldnames: list[str]) -> None:
    """Append a single row to a CSV, writing the header only if the file is new.

    Used for streaming long-running integrations (energy/angular-momentum drift
    series, apsidal-longitude series) so that partial progress on a multi-hour or
    multi-day Gyr-scale integration is never held only in memory: every checkpoint
    is durable on disk immediately, which is what makes `resume` meaningful.
    """
    path = Path(path)
    ensure_dir(path.parent)
    is_new = not path.exists() or path.stat().st_size == 0
    with path.open("a", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        if is_new:
            writer.writeheader()
        writer.writerow({key: "" if row.get(key) is None else row.get(key) for key in fieldnames})
