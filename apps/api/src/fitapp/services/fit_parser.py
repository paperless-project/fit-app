"""Parseo de ficheros FIT. (esqueleto - se completa en Fase 2)

Convierte un fichero FIT en un dict con los bloques `session`, `records` y `laps`
listos para mapear a los modelos SQLAlchemy.
"""
from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any


@dataclass
class ParsedFit:
    file_hash: str
    file_name: str
    started_at: datetime | None = None
    sport: str | None = None
    session: dict[str, Any] = field(default_factory=dict)
    records: list[dict[str, Any]] = field(default_factory=list)
    laps: list[dict[str, Any]] = field(default_factory=list)


def file_sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def parse_fit(path: Path) -> ParsedFit:
    """Parsea un fichero FIT con `fitparse` y devuelve un `ParsedFit`."""
    # TODO Fase 2: implementar usando fitparse.FitFile
    # - extraer session (totales)
    # - extraer records (serie temporal)
    # - extraer laps
    return ParsedFit(file_hash=file_sha256(path), file_name=path.name)
