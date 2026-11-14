"""Grant the admin role to an existing verified account from a trusted operator shell.

Usage: python scripts/grant_admin.py --email verified-user@example.com
"""

from __future__ import annotations

import argparse

from sqlalchemy.orm import Session

from backend.app.core.config import get_settings
from backend.app.database.session import create_database_engine
from backend.app.services.auth.admin_bootstrap import promote_verified_account


def main() -> None:
    """Promote one existing account; role changes are deliberately not self-service."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--email", required=True, help="Email of an existing verified account")
    args = parser.parse_args()

    engine = create_database_engine(get_settings().database_url)
    try:
        with Session(engine) as db:
            promote_verified_account(db, args.email)
        print("Admin role granted to the verified account.")
    except ValueError as exc:
        parser.error(str(exc))
    finally:
        engine.dispose()


if __name__ == "__main__":
    main()
