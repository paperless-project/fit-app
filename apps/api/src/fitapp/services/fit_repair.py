"""
Reparacion de ficheros FIT corruptos.

Estrategias (en orden):
  1. check_crc=False  — ignora CRC, recupera todo lo parseable (fichero truncado o CRC malo)
  2. fix_header + fix_checksum — recalcula cabecera y CRC (desfase en data_size)
  3. trim_and_fix  — recorta bytes del final hasta encontrar un punto de parse valido,
                     inspirado en el algoritmo "drop" de andrewcooke/choochoo

El hash del fichero reparado siempre se sustituye por el del original para que
la deduplicacion (user_id, file_hash) siga funcionando correctamente.
"""
from __future__ import annotations

import struct
import tempfile
from pathlib import Path

# CRC-16 segun el protocolo FIT (tabla de lookup de 4 bits)
_CRC_TABLE = [
    0x0000, 0xCC01, 0xD801, 0x1400, 0xF001, 0x3C00, 0x2800, 0xE401,
    0xA001, 0x6C00, 0x7800, 0xB401, 0x5000, 0x9C01, 0x8801, 0x4400,
]


class FitRepairError(Exception):
    pass


def _crc16(data: bytes | bytearray) -> int:
    crc = 0
    for byte in data:
        tmp = _CRC_TABLE[crc & 0xF]
        crc = (crc >> 4) & 0x0FFF
        crc ^= tmp ^ _CRC_TABLE[byte & 0xF]
        tmp = _CRC_TABLE[crc & 0xF]
        crc = (crc >> 4) & 0x0FFF
        crc ^= tmp ^ _CRC_TABLE[(byte >> 4) & 0xF]
    return crc


def _validate_signature(data: bytes | bytearray) -> int:
    """Comprueba la firma .FIT y devuelve el header_size."""
    if len(data) < 12:
        raise FitRepairError("Fichero demasiado corto")
    if data[8:12] != b".FIT":
        raise FitRepairError("No es un fichero FIT (falta la firma .FIT)")
    hdr = data[0]
    if hdr not in (12, 14):
        raise FitRepairError(f"Header size invalido: {hdr}")
    return hdr


def _apply_fixes(data: bytearray) -> bytearray:
    """Corrige data_size en la cabecera y recalcula ambos CRCs."""
    hdr = _validate_signature(data)
    data_size = len(data) - hdr - 2
    if data_size < 0:
        raise FitRepairError("Fichero demasiado corto para tener CRC final")
    struct.pack_into("<I", data, 4, data_size)
    if hdr == 14:
        struct.pack_into("<H", data, 12, _crc16(data[:12]))
    struct.pack_into("<H", data, -2, _crc16(data[:-2]))
    return data


def _try_parse(data: bytes) -> bool:
    """Devuelve True si fitparse puede leer todos los records."""
    import fitparse
    try:
        list(fitparse.FitFile(data, check_crc=True).get_messages("record"))
        return True
    except Exception:
        return False


def repair(path: Path) -> bytes:
    """
    Intenta reparar un fichero FIT corruptto.
    Devuelve los bytes reparados, o lanza FitRepairError si no es posible.
    """
    import fitparse

    raw = path.read_bytes()
    hdr = _validate_signature(raw)  # lanza si no es FIT

    # Estrategia 1: ignorar CRC — recupera lo parseable aunque el checksum sea malo
    try:
        list(fitparse.FitFile(raw, check_crc=False).get_messages("record"))
        # Si llega aqui, el fichero se puede leer; solo necesita CRC corregido
        fixed = _apply_fixes(bytearray(raw))
        if _try_parse(bytes(fixed)):
            return bytes(fixed)
    except Exception:
        pass

    # Estrategia 2: recortar bytes del final hasta encontrar un limite valido
    # (inspirado en choochoo advance() — busqueda lineal desde el final)
    min_len = hdr + 4  # cabecera + al menos 2 bytes de datos + 2 de CRC
    for trim in range(1, min(8192, len(raw) - min_len)):
        candidate = bytearray(raw[: len(raw) - trim])
        try:
            candidate = _apply_fixes(candidate)
            if _try_parse(bytes(candidate)):
                return bytes(candidate)
        except Exception:
            continue

    raise FitRepairError(f"No se pudo reparar {path.name}")
