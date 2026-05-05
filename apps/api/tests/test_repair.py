"""Tests del modulo de reparacion de ficheros FIT."""
from __future__ import annotations

import struct
from pathlib import Path

import pytest

from fitapp.services.fit_repair import FitRepairError, _crc16, repair
from fitapp.services.fit_parser import parse_fit, parse_fit_safe

_SAMPLE_FIT = Path("/activities/240714102315.fit")


# ── Helpers para generar ficheros corruptos ──────────────────────────────────

def _corrupt_crc(data: bytes) -> bytes:
    """Invierte los ultimos 2 bytes (CRC del fichero)."""
    ba = bytearray(data)
    ba[-1] ^= 0xFF
    ba[-2] ^= 0xFF
    return bytes(ba)


def _truncate(data: bytes, n_bytes: int) -> bytes:
    """Elimina los ultimos n bytes."""
    return data[:-n_bytes]


def _write_tmp(data: bytes, tmp_path: Path) -> Path:
    p = tmp_path / "test.fit"
    p.write_bytes(data)
    return p


# ── Tests de _crc16 ──────────────────────────────────────────────────────────

def test_crc16_empty() -> None:
    assert _crc16(b"") == 0


def test_crc16_known() -> None:
    # CRC-16 del fichero original debe coincidir con sus ultimos 2 bytes
    data = _SAMPLE_FIT.read_bytes()
    expected = struct.unpack_from("<H", data, len(data) - 2)[0]
    assert _crc16(data[:-2]) == expected


# ── Tests de repair ──────────────────────────────────────────────────────────

def test_repair_bad_crc(tmp_path: Path) -> None:
    raw = _SAMPLE_FIT.read_bytes()
    corrupted = _write_tmp(_corrupt_crc(raw), tmp_path)

    repaired = repair(corrupted)

    # El fichero reparado debe parsear correctamente
    import fitparse
    records = list(fitparse.FitFile(repaired, check_crc=True).get_messages("record"))
    assert len(records) > 100


def test_repair_truncated(tmp_path: Path) -> None:
    raw = _SAMPLE_FIT.read_bytes()
    # Truncar 500 bytes del final (varios records perdidos)
    corrupted = _write_tmp(_truncate(raw, 500), tmp_path)

    repaired = repair(corrupted)

    import fitparse
    records = list(fitparse.FitFile(repaired, check_crc=True).get_messages("record"))
    assert len(records) > 100


def test_repair_not_a_fit_file(tmp_path: Path) -> None:
    bad = tmp_path / "bad.fit"
    bad.write_bytes(b"esto no es FIT")
    with pytest.raises(FitRepairError):
        repair(bad)


# ── Tests de parse_fit_safe ──────────────────────────────────────────────────

def test_parse_fit_safe_clean_file() -> None:
    parsed, repaired = parse_fit_safe(_SAMPLE_FIT)
    assert repaired is False
    assert parsed.distance_m is not None and parsed.distance_m > 0


def test_parse_fit_safe_bad_crc_returns_repaired(tmp_path: Path) -> None:
    raw = _SAMPLE_FIT.read_bytes()
    corrupted = _write_tmp(_corrupt_crc(raw), tmp_path)

    parsed, repaired = parse_fit_safe(corrupted)

    assert repaired is True
    # Hash debe ser el del fichero corrupto (original), no el reparado
    from fitapp.services.fit_parser import file_sha256
    assert parsed.file_hash == file_sha256(corrupted)
    assert parsed.distance_m is not None and parsed.distance_m > 0


def test_parse_fit_safe_truncated_preserves_original_hash(tmp_path: Path) -> None:
    raw = _SAMPLE_FIT.read_bytes()
    corrupted = _write_tmp(_truncate(raw, 200), tmp_path)

    from fitapp.services.fit_parser import file_sha256
    original_hash = file_sha256(corrupted)

    parsed, repaired = parse_fit_safe(corrupted)

    assert repaired is True
    assert parsed.file_hash == original_hash


def test_parse_fit_safe_irreparable_raises(tmp_path: Path) -> None:
    bad = tmp_path / "bad.fit"
    bad.write_bytes(b"completamente invalido")
    with pytest.raises(Exception):
        parse_fit_safe(bad)
