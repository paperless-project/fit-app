"""Importacion masiva de la carpeta Activities/ a la BD.

Uso (desde el contenedor api):

    python -m scripts.bulk_import --user-email tu@email.com --path /activities

Recorre todos los .fit del directorio, parsea cada uno y persiste la actividad
asociada al usuario indicado. Hace dedupe por (user_id, file_hash).
"""
from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

from sqlalchemy import select

from fitapp.db import SessionLocal
from fitapp.models.user import User
from fitapp.services.activity_service import persist_activity
from fitapp.services.fit_parser import parse_fit


async def import_folder(user_email: str, folder: Path) -> None:
    if not folder.is_dir():
        print(f"error: {folder} no es un directorio", file=sys.stderr)
        sys.exit(1)

    fit_files = sorted(folder.glob("*.fit"))
    if not fit_files:
        print(f"warning: no hay ficheros .fit en {folder}", file=sys.stderr)
        return

    async with SessionLocal() as db:
        result = await db.execute(select(User).where(User.email == user_email))
        user = result.scalar_one_or_none()
        if user is None:
            print(f"error: no existe el usuario {user_email}", file=sys.stderr)
            sys.exit(1)

        print(f"Importando {len(fit_files)} ficheros para {user.email}…")
        imported = skipped = errors = 0

        for i, path in enumerate(fit_files, 1):
            try:
                parsed = parse_fit(path)
                _, is_dup = await persist_activity(db, user.id, parsed)
                if is_dup:
                    print(f"  [{i:3d}/{len(fit_files)}] SKIP {path.name} (duplicado)")
                    skipped += 1
                else:
                    print(f"  [{i:3d}/{len(fit_files)}] OK   {path.name}  {parsed.distance_m or 0:.0f}m")
                    imported += 1
            except Exception as exc:
                print(f"  [{i:3d}/{len(fit_files)}] ERR  {path.name}: {exc}", file=sys.stderr)
                errors += 1

    print(f"\nResumen: {imported} importadas, {skipped} omitidas, {errors} errores.")


def main() -> None:
    parser = argparse.ArgumentParser(description="Importa ficheros FIT a la BD")
    parser.add_argument("--user-email", required=True, help="Email del usuario destino")
    parser.add_argument(
        "--path", default="/activities", help="Carpeta con ficheros .fit (default: /activities)"
    )
    args = parser.parse_args()
    asyncio.run(import_folder(args.user_email, Path(args.path)))


if __name__ == "__main__":
    main()
