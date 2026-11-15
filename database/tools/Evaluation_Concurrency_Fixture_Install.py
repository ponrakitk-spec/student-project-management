"""Prepared installer for ONE 42-row Evaluation fixture; apply needs authorization.

Default is OFFLINE. --apply requires the exact test DB confirmation and an
outside-repository manifest. Existing manifests are verified, never replaced.
The fsynced manifest precedes COMMIT; uncertain COMMIT is never blindly retried.
The separate rehearsal tool continues to ALWAYS ROLLBACK.
"""

import argparse
import hashlib
import json
import os
from pathlib import Path
from uuid import uuid4

from psycopg import sql

from backend.tests.team_project_concurrency import TABLES, fingerprint, require, rollback_connection
from backend.tests.evaluation_concurrency import EvaluationFixture, diagnostic, validate_fixture
from database.tests.Auth_Regression import snapshot, switch
from database.tools.Test_Database import BASE, TEST_DB, connect_test_database
from database.tools.Evaluation_Concurrency_Fixture import COUNTS, create_fixture, verify_counts as verify_fixture_counts
from database.tools.V1_Baseline_Prepare import inventory


def manifest_path(value):
    path = Path(value).resolve()
    require(not path.is_relative_to(BASE.resolve()), "MANIFEST_MUST_BE_OUTSIDE_REPOSITORY")
    require(path.suffix == ".json", "MANIFEST_MUST_BE_JSON")
    return path


def payload(fixture):
    return fixture.payload()


def public_rows_hash(conn, fixture=None):
    excluded = {}
    if fixture is not None:
        excluded = {
            "users": {int(value) for value in fixture.users.values()},
            "teams": {int(value) for value in fixture.teams.values()},
            "projects": {int(value) for value in fixture.projects.values()},
            "project_submissions": {int(value) for value in fixture.submissions.values()},
            "committee_assignments": {int(value) for assignments in fixture.assignments.values() for value in assignments.values()},
        }
        for table, column, parent in (
            ("team_members", "team_id", "teams"),
            ("advisor_invitations", "project_id", "projects"),
            ("project_submission_files", "submission_id", "project_submissions"),
            ("committee_topic_votes", "committee_assignment_id", "committee_assignments"),
            ("milestones", "project_id", "projects"),
            ("tasks", "milestone_id", "milestones"),
            ("task_assignees", "task_id", "tasks"),
            ("committee_evaluations", "committee_assignment_id", "committee_assignments"),
        ):
            rows = conn.execute(sql.SQL("SELECT id FROM public.{} WHERE {}=ANY(%s)")
                                .format(sql.Identifier(table), sql.Identifier(column)),
                                (list(excluded[parent]),)).fetchall()
            excluded[table] = {row[0] for row in rows}
        require({"public." + key: len(value) for key, value in excluded.items()} == COUNTS,
                "FIXTURE_EXCLUSION_COUNTS")
    digest = hashlib.sha256()
    for table in TABLES:
        rows = conn.execute(sql.SQL("SELECT to_jsonb(t) FROM public.{} t ORDER BY id")
                            .format(sql.Identifier(table))).fetchall()
        kept = [row[0] for row in rows if row[0]["id"] not in excluded.get(table, set())]
        digest.update(json.dumps([table, kept], sort_keys=True, default=str).encode())
    return digest.hexdigest()


def check(path):
    fixture = EvaluationFixture.load(manifest_path(path))
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
    path = manifest_path(path)
    if path.exists():
        return {**check(path), "mode": "ALREADY_INSTALLED", "additional_rows": 0}
    path.parent.mkdir(parents=True, exist_ok=True)
    conn, phase = None, "NOT_ATTEMPTED"
    try:
        with path.open("x", encoding="utf-8", newline="\n") as artifact:
            conn = (connector or connect_test_database)()
            conn.rollback()
            with conn.transaction():  # ONLY the approved initial fixture commits.
                require(conn.execute("SELECT current_database()").fetchone() == (TEST_DB,), "TEST_DATABASE_REQUIRED")
                with conn.cursor() as cur:
                    switch(cur, "project_owner")
                    require(inventory(cur) == (52, []), "INSTALLED_BASELINE_REQUIRED")
                    require(conn.execute("SELECT count(*) FROM pg_stat_activity WHERE datname=current_database() "
                                         "AND pid<>pg_backend_pid() AND backend_type='client backend'").fetchone() == (0,),
                            "OTHER_CLIENTS_CONNECTED")
                    require(conn.execute("SELECT EXISTS(SELECT 1 FROM public.users "
                                         "WHERE email LIKE 'spms-ec-%.leader_main@example.test')").fetchone() == (False,),
                            "EXISTING_FIXTURE_REQUIRES_ORIGINAL_MANIFEST")
                    before, original_rows = snapshot(cur), public_rows_hash(conn)
                fixture = create_fixture(conn, "spms-ec-" + uuid4().hex)
                verify_fixture_counts(conn, before)
                validate_fixture(conn, fixture)
                require(public_rows_hash(conn, fixture) == original_rows, "EXISTING_ROWS_CHANGED")
                conn.execute("SET CONSTRAINTS ALL IMMEDIATE")
                with conn.cursor() as cur:
                    switch(cur, "project_owner")
                    expected_snapshot, expected_rows = snapshot(cur), fingerprint(conn)
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
        # Leave any reservation intact for read-only status review. Never
        # create another namespace after an uncertain COMMIT or partial file.
        return {"result": "FAIL", "mode": "APPLY", "database": TEST_DB,
                "commit_status": phase, "diagnostic": diagnostic(exc), "automatic_retry_allowed": False}
    finally:
        if conn is not None:
            try:
                conn.rollback()
            finally:
                conn.close()


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--check", action="store_true")
    mode.add_argument("--apply", action="store_true")
    parser.add_argument("--confirm-database")
    parser.add_argument("--manifest", type=Path)
    args = parser.parse_args(argv)
    try:
        if not (args.check or args.apply):
            result = {"mode": "OFFLINE_PLAN", "database_connected": False, "fixture_rows_total": sum(COUNTS.values())}
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
        print(json.dumps({"result": "FAIL", "diagnostic": diagnostic(exc)}))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
