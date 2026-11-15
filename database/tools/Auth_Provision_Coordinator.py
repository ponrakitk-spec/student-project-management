"""Owner-only NEW coordinator provisioning in the test DB. Default ROLLBACK.

Same validation, hashing, hidden TTY password and owner guard as advisor CLI.
No role option, existing-account changes, password arguments/files/env, DDL
or additional grants. --apply is for a separately authorized named account.
"""

import json
import sys

import psycopg

from backend.auth_security import hash_password
from backend.auth_validation import validate_new_password
from database.tools.Auth_Provision_Advisor import (
    ProvisionError, SafeParser, check, guard_owner, insert_credentials,
    prompt_password, validate_account,
)
from database.tools.Test_Database import TEST_DB, connect_test_database


def create_coordinator_on(conn, full_name, email, password):
    name, address = validate_account(full_name, email)
    try:
        encoded = hash_password(password)
    except ValueError:
        raise ProvisionError("INVALID_PASSWORD_POLICY") from None
    try:
        with conn.transaction():
            guard_owner(conn)
            if conn.execute("SELECT EXISTS(SELECT 1 FROM public.users WHERE email=lower(%s))",
                            (address,)).fetchone()[0]:
                raise ProvisionError("ACCOUNT_ALREADY_EXISTS")
            row = conn.execute("""INSERT INTO public.users(full_name,email,role)
                VALUES (%s,%s,'coordinator') RETURNING id,full_name,email,role""", (name, address)).fetchone()
            insert_credentials(conn, row[0], encoded)
            return {"id": str(row[0]), "full_name": row[1], "email": row[2], "role": row[3]}
    except psycopg.Error as exc:
        if (exc.sqlstate == "23505" and exc.diag.schema_name == "public" and
                exc.diag.table_name == "users" and exc.diag.constraint_name == "users_email_key"):
            raise ProvisionError("ACCOUNT_ALREADY_EXISTS") from None
        raise ProvisionError("DATABASE_OPERATION_FAILED") from None


def provision(full_name, email, password, *, apply=False):
    validate_account(full_name, email)
    try:
        validate_new_password(password)
    except ValueError:
        raise ProvisionError("INVALID_PASSWORD_POLICY") from None
    conn = connect_test_database()
    try:
        conn.rollback()
        with conn.transaction(force_rollback=not apply):
            user = create_coordinator_on(conn, full_name, email, password)
        return {"result": "PASS", "mode": "APPLIED" if apply else "DRY_RUN", "database": TEST_DB,
                "effective_role": "project_owner", "persisted": apply, "user": user}
    finally:
        try:
            conn.rollback()
        finally:
            conn.close()


def main(argv=None):
    try:
        parser = SafeParser(description=__doc__)
        modes = parser.add_mutually_exclusive_group()
        modes.add_argument("--check", action="store_true")
        modes.add_argument("--dry-run", action="store_true")
        modes.add_argument("--apply", action="store_true")
        parser.add_argument("--confirm-database")
        parser.add_argument("--full-name")
        parser.add_argument("--email")
        args = parser.parse_args(argv)
        if args.confirm_database not in (None, TEST_DB) or (args.apply and args.confirm_database != TEST_DB):
            raise ProvisionError("TEST_DATABASE_CONFIRMATION_REQUIRED")
        if args.check:
            result = check()
        else:
            if (args.full_name is None or args.email is None) and not sys.stdin.isatty():
                raise ProvisionError("ACCOUNT_INPUT_TTY_REQUIRED")
            name = args.full_name if args.full_name is not None else input("Coordinator full name: ")
            email = args.email if args.email is not None else input("Coordinator email: ")
            validate_account(name, email)
            password = prompt_password()
            try:
                result = provision(name, email, password, apply=args.apply)
            finally:
                del password
        print(json.dumps(result, ensure_ascii=True))
        return 0
    except ProvisionError as exc:
        print(json.dumps({"result": "FAIL", "code": exc.code}))
    except (KeyboardInterrupt, EOFError):
        print(json.dumps({"result": "FAIL", "code": "CANCELLED"}))
    except Exception:
        print(json.dumps({"result": "FAIL", "code": "INTERNAL_ERROR"}))
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
