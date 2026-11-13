"""Comandi da terminale.

python -m app.cli reset-admin-password admin@example.com
"""

from __future__ import annotations

import argparse
import getpass
import sys

from app.core.config import get_settings
from app.db.base import Base
from app.db.session import Database
from app.services.admins import set_password
from app.services.retention import purge_expired


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m app.cli")
    commands = parser.add_subparsers(dest="command", required=True)
    reset = commands.add_parser("reset-admin-password", help="imposta una nuova password per l'admin")
    reset.add_argument("email")
    commands.add_parser("purge-expired", help="elimina subito le conversazioni oltre RETENTION_DAYS")
    args = parser.parse_args(argv)

    if args.command == "purge-expired":
        settings = get_settings()
        db = Database(settings)
        Base.metadata.create_all(db.engine)
        print(f"Conversazioni eliminate: {purge_expired(db, settings.retention_days)}")
        return 0

    if args.command == "reset-admin-password":
        password = getpass.getpass("Nuova password (min. 12 caratteri): ")
        if password != getpass.getpass("Ripeti la password: "):
            print("Le password non coincidono", file=sys.stderr)
            return 1
        db = Database(get_settings())
        Base.metadata.create_all(db.engine)
        try:
            with db.session() as session:
                if not set_password(session, args.email, password):
                    print("Admin non trovato", file=sys.stderr)
                    return 1
        except ValueError as exc:
            print(exc, file=sys.stderr)
            return 1
        print("Password aggiornata")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
