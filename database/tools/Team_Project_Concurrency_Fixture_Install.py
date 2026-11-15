"""Install ONE explicitly approved 10-row concurrency fixture in the test DB.

Default is OFFLINE. --apply needs --confirm-database and an outside-repo
manifest path. An existing manifest is validated, never overwritten/reseeded.
Manifest is fsynced before COMMIT; uncertain COMMIT must not be retried blindly.
The rehearsal tool is unchanged and always rolls back.
"""

import argparse
import hashlib
import json
import os
from pathlib import Path
from uuid import uuid4

from psycopg import sql

from backend.tests.team_project_concurrency import (
    Fixture, TABLES, fingerprint, require, rollback_connection, validate_fixture,
)
from database.tests.Auth_Regression import snapshot, switch
from database.tools.Team_Project_Concurrency_Fixture import (
    COUNTS, create_fixture, safe_diagnostic, verify_fixture_counts,
)
from database.tools.Test_Database import BASE, TEST_DB, connect_test_database
from database.tools.V1_Baseline_Prepare import inventory


def manifest_path(value):
    path = Path(value).resolve()
    require(not path.is_relative_to(BASE.resolve()), "MANIFEST_MUST_BE_OUTSIDE_REPOSITORY")
    require(path.suffix == ".json", "MANIFEST_MUST_BE_JSON")
    return path


def payload(fixture):
    return {"version": 1, "database": TEST_DB, "namespace": fixture.namespace,
            "users": fixture.users, "teams": fixture.teams, "project_id": fixture.project_id}


def public_rows_hash(conn, fixture=None):
    excluded = {}
    if fixture is not None:
        excluded = {"users": {int(v) for v in fixture.users.values()},
                    "teams": {int(v) for v in fixture.teams.values()},
                    "projects": {int(fixture.project_id)}}
        excluded["team_members"] = {row[0] for row in conn.execute(
            "SELECT id FROM public.team_members WHERE team_id=ANY(%s)",
            ([int(v) for v in fixture.teams.values()],)).fetchall()}
        require(len(excluded["team_members"]) == 3, "FIXTURE_MEMBERSHIP_COUNT")
    digest = hashlib.sha256()
    for table in TABLES:
        rows = conn.execute(sql.SQL("SELECT to_jsonb(t) FROM public.{} t ORDER BY id")
                            .format(sql.Identifier(table))).fetchall()
        kept = [row[0] for row in rows if row[0]["id"] not in excluded.get(table, set())]
        digest.update(json.dumps([table, kept], sort_keys=True, default=str).encode())
    return digest.hexdigest()


def check(path):
    fixture = Fixture.load(path)
    with rollback_connection(readonly=True) as conn:
        validate_fixture(conn, fixture)
    return {"result": "PASS", "mode": "CHECK", "database": TEST_DB,
            "fixture_valid": True, "direct_app_login": True, "written": False}


def postflight(fixture, expected_snapshot, expected_rows, original_rows):
    conn = connect_test_database(readonly=True)
    try:
        with conn.cursor() as cur:
            switch(cur, "project_owner")
            require(snapshot(cur) == expected_snapshot, "PERSISTENT_SNAPSHOT_MISMATCH")
            require(fingerprint(conn) == expected_rows, "PERSISTENT_ROWS_MISMATCH")
            require(public_rows_hash(conn, fixture) == original_rows, "EXISTING_ROWS_CHANGED")
    finally:
        try:
            conn.rollback()
        finally:
            conn.close()
    with rollback_connection(readonly=True) as app:
        validate_fixture(app, fixture)


def install(path, *, connector=None):
    if path.exists():
        result = check(path)
        return {**result, "mode": "ALREADY_INSTALLED", "additional_rows": 0}
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = None
    phase = "NOT_ATTEMPTED"
    try:
        # Exclusive reservation precedes DB writes. Never overwrite a manifest,
        # even after a previous crash. A partial file requires status review.
        with path.open("x", encoding="utf-8", newline="\n") as artifact:
            conn = (connector or connect_test_database)()
            conn.rollback()  # End connector's identity-only implicit tx.
            with conn.transaction():  # ONLY approved fixture installation commits.
                with conn.cursor() as cur:
                    switch(cur, "project_owner")
                    require(inventory(cur) == (52, []), "INSTALLED_BASELINE_REQUIRED")
                    require(conn.execute("""SELECT count(*) FROM pg_stat_activity
                        WHERE datname=current_database() AND pid<>pg_backend_pid()
                        AND backend_type='client backend'""").fetchone() == (0,), "OTHER_CLIENTS_CONNECTED")
                    require(conn.execute("""SELECT EXISTS(SELECT 1 FROM public.users
                        WHERE email LIKE 'spms-ct-%.leader_a@example.test')""").fetchone() == (False,),
                        "EXISTING_FIXTURE_REQUIRES_ORIGINAL_MANIFEST")
                    before = snapshot(cur)
                    original_rows = public_rows_hash(conn)
                fixture = create_fixture(conn, "spms-ct-" + uuid4().hex)
                verify_fixture_counts(conn, before)
                require(public_rows_hash(conn, fixture) == original_rows, "EXISTING_ROWS_CHANGED")
                conn.execute("SET CONSTRAINTS ALL IMMEDIATE")
                validate_fixture(conn, fixture)
                with conn.cursor() as cur:
                    switch(cur, "project_owner")
                    expected_snapshot = snapshot(cur)
                    expected_rows = fingerprint(conn)
                    switch(cur, "project_app")
                artifact.write(json.dumps(payload(fixture), indent=2) + "\n")
                artifact.flush()
                os.fsync(artifact.fileno())
                phase = "COMMIT_PENDING"
            phase = "COMMITTED"
        conn.rollback()
        conn.close()
        conn = None
        postflight(fixture, expected_snapshot, expected_rows, original_rows)
        return {"result": "PASS", "mode": "APPLIED", "database": TEST_DB,
                "fixture_row_delta": COUNTS, "fixture_rows_total": sum(COUNTS.values()),
                "committed": True, "manifest_saved": True, "direct_app_login": True,
                "existing_public_rows_unchanged": True, "schema_acl_unchanged": True}
    except Exception as exc:
        # Preserve the artifact. If COMMIT's reply was lost it can identify the
        # exact rows for a read-only check; never automatically create another set.
        return {"result": "FAIL", "mode": "APPLY", "database": TEST_DB,
                "commit_status": phase, "diagnostic": safe_diagnostic(exc),
                "automatic_retry_allowed": False}
    finally:
        if conn is not None:
            try:
                conn.rollback()
            finally:
                conn.close()


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    modes = parser.add_mutually_exclusive_group()
    modes.add_argument("--check", action="store_true")
    modes.add_argument("--apply", action="store_true")
    parser.add_argument("--confirm-database")
    parser.add_argument("--manifest", type=Path)
    args = parser.parse_args(argv)
    try:
        if not (args.check or args.apply):
            result = {"mode": "OFFLINE_PLAN", "database_connected": False, "fixture_rows_total": 10}
        else:
            require(args.manifest is not None, "MANIFEST_REQUIRED")
            if args.apply:
                require(args.confirm_database == TEST_DB, "TEST_DATABASE_CONFIRMATION_REQUIRED")
            require(args.confirm_database in (None, TEST_DB), "TEST_DATABASE_CONFIRMATION_REQUIRED")
            path = manifest_path(args.manifest)
            result = install(path) if args.apply else check(path)
        print(json.dumps(result))
        return 0 if result.get("result") != "FAIL" else 1
    except Exception as exc:
        print(json.dumps({"result": "FAIL", "diagnostic": safe_diagnostic(exc)}))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
