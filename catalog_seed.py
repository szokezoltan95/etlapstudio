"""Bundled starter catalogue refreshed from the October 2026 restaurant database."""
from __future__ import annotations
import csv
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class StarterDish:
    category: str
    name: str
    price: int


def starter_dishes() -> list[StarterDish]:
    source = Path(__file__).resolve().parent / "data" / "alap_eteladatbazis.csv"
    with source.open(encoding="utf-8-sig", newline="") as stream:
        rows = csv.DictReader(stream)
        return [StarterDish(row["kategoria"], row["etel"], int(row["ar_ft"] or 0))
                for row in rows]

