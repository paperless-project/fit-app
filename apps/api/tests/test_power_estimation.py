"""Tests del servicio de estimación de potencia y cálculo de NP."""
from __future__ import annotations

import pytest

from fitapp.services.power_estimation import (
    build_power_series,
    compute_normalized_power,
    estimate_power,
)


# ── estimate_power ────────────────────────────────────────────────────────────

def test_estimate_power_flat() -> None:
    """En llano a 36 km/h (10 m/s), 85 kg → ~230 W razonable."""
    p = estimate_power(speed_mps=10.0, grade=0.0, total_mass_kg=85.0)
    assert 200 < p < 280


def test_estimate_power_uphill() -> None:
    """En subida al 8% a 5 m/s, 85 kg → más de 300 W."""
    p = estimate_power(speed_mps=5.0, grade=0.08, total_mass_kg=85.0)
    assert p > 300


def test_estimate_power_zero_speed() -> None:
    assert estimate_power(0.0, 0.0, 85.0) == 0.0


def test_estimate_power_downhill_not_negative() -> None:
    """En bajada pronunciada la potencia estimada no debe ser negativa."""
    p = estimate_power(speed_mps=12.0, grade=-0.10, total_mass_kg=85.0)
    assert p >= 0.0


# ── compute_normalized_power ─────────────────────────────────────────────────

def test_compute_np_requires_30_samples() -> None:
    assert compute_normalized_power([200.0] * 29) is None


def test_compute_np_constant_power() -> None:
    """NP de una potencia constante debe ser igual a esa potencia."""
    powers = [200.0] * 100
    np_val = compute_normalized_power(powers)
    assert np_val == 200


def test_compute_np_higher_than_avg_for_variable() -> None:
    """NP debe ser mayor que la media para potencia con bloques variables."""
    # Bloques de 60 s: 50 W / 350 W alternados → media = 200 W, NP > 200
    powers = [50.0] * 60 + [350.0] * 60
    powers = powers * 3  # 360 muestras
    np_val = compute_normalized_power(powers)
    avg = sum(powers) / len(powers)
    assert np_val is not None
    assert np_val > avg


# ── build_power_series ────────────────────────────────────────────────────────

def test_build_power_series_uses_real_power() -> None:
    """Si >50% de los records tienen power, debe usar el medidor."""
    records = [{"power": 220, "speed_mps": 8.0, "altitude_m": 100.0, "distance_m": float(i * 8)} for i in range(60)]
    series = build_power_series(records)
    assert all(p == 220.0 for p in series)


def test_build_power_series_estimates_without_power() -> None:
    """Sin medidor, debe estimar potencia positiva para velocidad > 0."""
    records = [
        {
            "power": None,
            "speed_mps": 8.0,
            "altitude_m": 100.0 + i * 0.5,  # subida constante
            "distance_m": float(i * 8),
        }
        for i in range(60)
    ]
    series = build_power_series(records, total_mass_kg=85.0)
    assert len(series) == 60
    assert all(p > 0 for p in series[1:])  # primer punto sin pendiente previa


def test_build_power_series_empty() -> None:
    assert build_power_series([]) == []
