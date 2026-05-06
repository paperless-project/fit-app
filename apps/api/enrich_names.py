"""Enriquece los nombres de actividades con name IS NULL mediante geocodificacion inversa.

Uso (desde el contenedor api):

    python enrich_names.py --user-email EMAIL
    python enrich_names.py --all-users
    python enrich_names.py --user-email EMAIL --force   # re-geocodifica aunque ya tenga nombre

El script respeta el rate-limit de Nominatim (1 req/s maximo) y muestra progreso
en tiempo real. Para las 114 actividades importadas en bulk son ~8-10 llamadas cada
una, por lo que puede tardar 15-20 minutos en total.
"""
from __future__ import annotations

import argparse
import asyncio
import sys

from sqlalchemy import select

from fitapp.db import SessionLocal
from fitapp.models.activity import Activity
from fitapp.models.user import User
from fitapp.services.activity_service import enrich_activity_name


async def enrich_user(user_email: str, force: bool) -> tuple[int, int, int]:
    """Enriquece actividades de un usuario. Devuelve (updated, skipped, errors)."""
    async with SessionLocal() as db:
        user_result = await db.execute(select(User).where(User.email == user_email))
        user = user_result.scalar_one_or_none()
        if user is None:
            print(f"  error: no existe el usuario {user_email}", file=sys.stderr)
            return 0, 0, 0

        if force:
            ids_result = await db.execute(
                select(Activity.id, Activity.file_name)
                .where(Activity.user_id == user.id)
                .order_by(Activity.started_at)
            )
        else:
            ids_result = await db.execute(
                select(Activity.id, Activity.file_name)
                .where(Activity.user_id == user.id, Activity.name.is_(None))
                .order_by(Activity.started_at)
            )
        rows = ids_result.all()

        if not rows:
            print(f"  {user_email}: sin actividades pendientes.")
            return 0, 0, 0

        print(f"  {user_email}: {len(rows)} actividades a enriquecer…")
        updated = skipped = errors = 0

        for i, (activity_id, file_name) in enumerate(rows, 1):
            prefix = f"    [{i:3d}/{len(rows)}]"
            try:
                # Necesitamos una sesion fresca por cada actividad porque enrich_activity_name
                # hace commit. Reutilizar la misma sesion despues de un commit es seguro
                # con expire_on_commit=False, pero creamos una nueva para mayor claridad.
                async with SessionLocal() as session:
                    changed = await enrich_activity_name(session, activity_id, force=force)

                if changed:
                    # Leer el nombre resultante para mostrarlo en el log
                    async with SessionLocal() as session:
                        act = await session.get(Activity, activity_id)
                        name = act.name if act else "?"
                    print(f"{prefix} OK       {file_name} → \"{name}\"")
                    updated += 1
                else:
                    print(f"{prefix} SKIP     {file_name} (sin GPS o geocoding fallido)")
                    skipped += 1
            except Exception as exc:
                print(f"{prefix} ERR      {file_name}: {exc}", file=sys.stderr)
                errors += 1

        return updated, skipped, errors


async def main_async(args: argparse.Namespace) -> None:
    if args.all_users:
        async with SessionLocal() as db:
            users_result = await db.execute(select(User.email))
            emails = [row[0] for row in users_result.all()]
        if not emails:
            print("No hay usuarios en la base de datos.")
            return
        print(f"Enriqueciendo actividades para {len(emails)} usuario(s)…")
        total_u = total_s = total_e = 0
        for email in emails:
            u, s, e = await enrich_user(email, args.force)
            total_u += u
            total_s += s
            total_e += e
        print(f"\nTotal: {total_u} actualizadas, {total_s} omitidas, {total_e} errores.")
    else:
        print(f"Enriqueciendo actividades para {args.user_email}…")
        u, s, e = await enrich_user(args.user_email, args.force)
        print(f"\nResumen: {u} actualizadas, {s} omitidas, {e} errores.")


def main() -> None:
    parser = argparse.ArgumentParser(description="Geocodifica nombres de actividades con name IS NULL")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--user-email", help="Email del usuario a enriquecer")
    group.add_argument("--all-users", action="store_true", help="Enriquecer todos los usuarios")
    parser.add_argument(
        "--force",
        action="store_true",
        help="Re-geocodificar aunque la actividad ya tenga nombre",
    )
    args = parser.parse_args()
    asyncio.run(main_async(args))


if __name__ == "__main__":
    main()
