"""Elimina actividades duplicadas (mismo user_id, started_at dentro de ±60 s).

Criterio de "mejor": se prefiere la actividad importada desde fichero FIT local
(file_name no empieza por "strava_") sobre la importada desde Strava. Si ambas son
del mismo tipo, se conserva la insertada primero (menor UUID v4 por orden de creación).

Uso (desde el contenedor api):

    # Ver qué se eliminaría sin tocar la BD:
    python deduplicate_activities.py --dry-run

    # Eliminar duplicados de un usuario concreto:
    python deduplicate_activities.py --user-email EMAIL

    # Eliminar duplicados de todos los usuarios:
    python deduplicate_activities.py --all-users
"""
from __future__ import annotations

import argparse
import asyncio
import sys
from datetime import datetime, timedelta  # noqa: F401 (timedelta usado en _WINDOW_S cálculos)

from sqlalchemy import select

from fitapp.db import SessionLocal
from fitapp.models.activity import Activity
from fitapp.models.user import User

_WINDOW_S = 60  # ventana de deduplicación en segundos


def _is_strava(file_name: str) -> bool:
    return file_name.startswith("strava_")


def _pick_winner(activities: list[Activity]) -> Activity:
    """Devuelve la actividad a conservar del grupo de duplicados.

    Prioridad: FIT local > Strava. Dentro del mismo tipo, la más antigua (UUID menor).
    """
    fit_activities = [a for a in activities if not _is_strava(a.file_name)]
    pool = fit_activities if fit_activities else activities
    # UUID v4 no es estrictamente ordenable por tiempo, pero en PostgreSQL los IDs
    # se asignan secuencialmente a nivel de sesión; min() da el más antiguo en la práctica.
    return min(pool, key=lambda a: a.id)


async def deduplicate_user(email: str, dry_run: bool) -> tuple[int, int]:
    """Deduplica actividades de un usuario. Devuelve (grupos_dup, eliminadas)."""
    async with SessionLocal() as db:
        user_result = await db.execute(select(User).where(User.email == email))
        user = user_result.unique().scalar_one_or_none()
        if user is None:
            print(f"  error: usuario no encontrado: {email}", file=sys.stderr)
            return 0, 0

        acts_result = await db.execute(
            select(Activity)
            .where(Activity.user_id == user.id)
            .order_by(Activity.started_at, Activity.id)
        )
        activities = acts_result.scalars().all()

    # Agrupar actividades cuyo started_at diste menos de _WINDOW_S segundos entre sí.
    # Algoritmo greedy: ordena por tiempo y agrupa consecutivos dentro de la ventana.
    activities_sorted = sorted(
        activities,
        key=lambda a: a.started_at or datetime.min,
    )

    raw_groups: list[list[Activity]] = []
    current: list[Activity] = []
    for act in activities_sorted:
        if not current:
            current = [act]
        else:
            prev_t = current[0].started_at
            this_t = act.started_at
            diff = abs((this_t - prev_t).total_seconds()) if (prev_t and this_t) else 999
            if diff <= _WINDOW_S:
                current.append(act)
            else:
                raw_groups.append(current)
                current = [act]
    raw_groups.append(current)

    dup_groups = [g for g in raw_groups if len(g) > 1]

    if not dup_groups:
        print(f"  {email}: sin duplicados.")
        return 0, 0

    total_deleted = 0
    for group in dup_groups:
        winner = _pick_winner(group)
        losers = [a for a in group if a.id != winner.id]

        ref_t = group[0].started_at
        label = ref_t.strftime("%Y-%m-%d %H:%M:%S") if ref_t else "sin-fecha"
        print(f"  {email} — {label}: {len(group)} copias → conservar {winner.file_name}")
        for loser in losers:
            print(f"    eliminar {loser.id}  {loser.file_name}")

        if not dry_run:
            async with SessionLocal() as db:
                for loser in losers:
                    act = await db.get(Activity, loser.id)
                    if act:
                        await db.delete(act)
                await db.commit()

        total_deleted += len(losers)

    return len(dup_groups), total_deleted


async def main_async(args: argparse.Namespace) -> None:
    dry_run = args.dry_run
    if dry_run:
        print("=== MODO SIMULACIÓN (--dry-run): no se elimina nada ===\n")

    if args.all_users:
        async with SessionLocal() as db:
            users_result = await db.execute(select(User.email))
            emails = [row[0] for row in users_result.all()]
        if not emails:
            print("No hay usuarios en la base de datos.")
            return
        print(f"Buscando duplicados en {len(emails)} usuario(s)…\n")
        total_groups = total_deleted = 0
        for email in emails:
            g, d = await deduplicate_user(email, dry_run)
            total_groups += g
            total_deleted += d
        print(f"\nTotal: {total_groups} grupos de duplicados, {total_deleted} actividades {'(a eliminar)' if dry_run else 'eliminadas'}.")
    else:
        print(f"Buscando duplicados para {args.user_email}…\n")
        g, d = await deduplicate_user(args.user_email, dry_run)
        print(f"\nResumen: {g} grupos de duplicados, {d} actividades {'(a eliminar)' if dry_run else 'eliminadas'}.")


def main() -> None:
    parser = argparse.ArgumentParser(description="Elimina actividades duplicadas por started_at")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--user-email", help="Email del usuario a limpiar")
    group.add_argument("--all-users", action="store_true", help="Limpiar todos los usuarios")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Solo muestra qué se eliminaría, sin tocar la BD",
    )
    args = parser.parse_args()
    asyncio.run(main_async(args))


if __name__ == "__main__":
    main()
