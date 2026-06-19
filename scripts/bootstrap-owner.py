#!/usr/bin/env python
from __future__ import annotations

import argparse
import getpass

from backend.core.database import SessionLocal
from backend.domains.users.store import BootstrapUnavailableError, UserStore


def main() -> int:
    parser = argparse.ArgumentParser(description="Create the first 3dPrintPilot owner account.")
    parser.add_argument("--username", required=True)
    parser.add_argument("--email")
    parser.add_argument("--password", help="Owner password. Omit to prompt without echo.")
    parser.add_argument("--force-password-change", action="store_true")
    args = parser.parse_args()

    password = args.password or getpass.getpass("Owner password: ")
    with SessionLocal() as session:
        store = UserStore(session)
        try:
            result = store.bootstrap_owner(
                username=args.username,
                email=args.email,
                password=password,
                force_password_change=args.force_password_change,
            )
        except BootstrapUnavailableError as exc:
            print(str(exc))
            return 1

    print(f"Created owner account: {result.user.username}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
