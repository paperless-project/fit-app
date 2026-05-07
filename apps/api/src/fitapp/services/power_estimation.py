"""Estimación de potencia ciclista y cálculo de Normalized Power (NP).

Para actividades sin medidor de potencia, estima la potencia usando un modelo
físico que combina peso total (ciclista + bicicleta), velocidad GPS y cambios
de altitud. Más preciso en subidas donde la gravedad domina sobre la aerodinámica.
"""
from __future__ import annotations

import math
from typing import Any

_G = 9.81       # m/s² (aceleración gravitatoria)
_RHO = 1.225    # kg/m³ (densidad del aire a nivel del mar, 15°C)
_CDA = 0.32     # m² (CdA: coeficiente de arrastre × área frontal, posición de manillar)
_CRR = 0.004    # coeficiente de resistencia a la rodadura (neumáticos de carretera)
_ETA = 0.98     # eficiencia de transmisión (~2% pérdida mecánica)
_NP_WINDOW = 30  # segundos de media móvil para el cálculo de NP


def estimate_power(speed_mps: float, grade: float, total_mass_kg: float) -> float:
    """Estima la potencia instantánea (W) a partir de velocidad y pendiente.

    Combina tres componentes:
    - Gravitatoria: dominante en subidas (proporcional a masa × g × v × pendiente)
    - Aerodinámica: dominante en llano a alta velocidad (proporcional a v³)
    - Rodadura: proporcional a masa × velocidad
    """
    if speed_mps <= 0.0:
        return 0.0
    angle = math.atan(grade)
    p_gravity = total_mass_kg * _G * speed_mps * math.sin(angle)
    p_air = 0.5 * _RHO * _CDA * speed_mps ** 3
    p_rolling = _CRR * total_mass_kg * _G * speed_mps * math.cos(angle)
    return max(0.0, (p_gravity + p_air + p_rolling) / _ETA)


def compute_normalized_power(powers: list[float]) -> int | None:
    """Calcula Normalized Power (NP) según el algoritmo de Allen & Coggan.

    NP = raíz cuarta de la media de (promedio_30s)^4.
    Requiere al menos 30 muestras (una por segundo).
    """
    n = len(powers)
    if n < _NP_WINDOW:
        return None
    rolling = [
        sum(powers[i : i + _NP_WINDOW]) / _NP_WINDOW
        for i in range(n - _NP_WINDOW + 1)
    ]
    mean_p4 = sum(p ** 4 for p in rolling) / len(rolling)
    return round(mean_p4 ** 0.25)


def build_power_series(
    records: list[dict[str, Any]],
    total_mass_kg: float = 85.0,
) -> list[float]:
    """Construye la serie temporal de potencia para el cálculo de NP.

    Si más del 50% de los records tienen datos de medidor de potencia, los usa
    directamente. En caso contrario, estima la potencia a partir de velocidad y altitud.

    total_mass_kg: peso total ciclista + bicicleta (por defecto 75 + 10 = 85 kg).
    """
    n = len(records)
    if n == 0:
        return []

    has_power = sum(1 for r in records if r.get("power") is not None)
    if has_power > n * 0.5:
        return [float(r["power"]) for r in records if r.get("power") is not None]

    # Estimación física: velocidad GPS + cambios de altitud
    powers: list[float] = []
    prev: dict[str, Any] | None = None
    for r in records:
        speed = r.get("speed_mps")
        grade = 0.0
        if (
            speed is not None
            and speed > 0
            and prev is not None
            and r.get("altitude_m") is not None
            and prev.get("altitude_m") is not None
            and r.get("distance_m") is not None
            and prev.get("distance_m") is not None
        ):
            dist_diff = float(r["distance_m"]) - float(prev["distance_m"])
            if dist_diff >= 0.5:  # al menos 0.5 m de avance para pendiente fiable
                alt_diff = float(r["altitude_m"]) - float(prev["altitude_m"])
                grade = alt_diff / dist_diff
                grade = max(-0.30, min(0.30, grade))  # limitar a ±30%

        powers.append(estimate_power(float(speed or 0), grade, total_mass_kg))
        prev = r

    return powers
