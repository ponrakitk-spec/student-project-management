"""Rehearse the reviewed 10-row Team/Project fixture, then ALWAYS ROLLBACK.

Default invocation is an offline plan. --dry-run uses only the pinned test DB.
No apply/COMMIT mode, manifest export, auth account, DDL or privilege changes.
Sequential action rehearsals do not establish cross-connection concurrency.
"""

import argparse
import json
from uuid import uuid4

from backend.auth_store import assert_auth_connection
from backend.tests.team_project_concurrency import (
    CASES, CheckFailed, Fixture, action, fingerprint, project_call, require,
    sanitized_failure, team_call, validate_fixture,
)
from database.tests.Auth_Regression import snapshot, switch
from database.tools.Test_Database import TEST_DB, connect_test_database
from database.tools.V1_Baseline_Prepare import inventory

COUNTS = {"public.users": 4, "public.teams": 2, "public.team_members": 3, "public.projects": 1}


def create_fixture(conn, namespace):
    # Validate names before any DML, using the same manifest rules as the runner.
    Fixture.parse({"version": 1, "database": TEST_DB, "namespace": namespace,
                   "users": dict(zip(("leader_a", "member_b", "leader_c", "free_student"),
                                     ("1", "2", "3", "4"))),
                   "teams": {"main": "1", "empty": "2"}, "project_id": "1"})
    users = {}
    with conn.cursor() as cur:
        switch(cur, "project_owner")
        for label in ("leader_a", "member_b", "leader_c", "free_student"):
            cur.execute("""INSERT INTO public.users(full_name,email,role)
                VALUES (%s,%s,'student') RETURNING id""",
                ("Concurrency fixture " + label, f"{namespace}.{label}@example.test"))
            users[label] = str(cur.fetchone()[0])
        switch(cur, "project_app")
    assert_auth_connection(conn)
    main = team_call(conn, "create", f"{namespace}.main", None, users["leader_a"])
    team_call(conn, "add_member", users["leader_a"], f"{namespace}.member_b@example.test")
    empty = team_call(conn, "create", f"{namespace}.empty", None, users["leader_c"])
    project = project_call(conn, "create", f"{namespace}.project", None, users["leader_a"])
    fixture = Fixture.parse({"version": 1, "database": TEST_DB, "namespace": namespace,
                             "users": users, "teams": {"main": main["id"], "empty": empty["id"]},
                             "project_id": project["id"]})
    conn.execute("SET CONSTRAINTS ALL IMMEDIATE")
    validate_fixture(conn, fixture)
    return fixture


def verify_fixture_counts(conn, before):
    with conn.cursor() as cur:
        switch(cur, "project_owner")
        during = snapshot(cur)
        require(during[0] == before[0], "METADATA_CHANGED_DURING_FIXTURE")
        require(during[1] == {table: count + COUNTS.get(table, 0) for table, count in before[1].items()},
                "UNEXPECTED_FIXTURE_ROW_DELTA")
        switch(cur, "project_app")
    assert_auth_connection(conn)


def safe_diagnostic(exc):
    # UOW sanitizes psycopg failures for HTTP. Inspect the context only for a
    # SQLSTATE; never print context text, SQL/parameters or connection details.
    result = sanitized_failure(exc)
    seen = set()
    context = exc
    while result["sqlstate"] is None and context is not None and id(context) not in seen:
        seen.add(id(context))
        state = sanitized_failure(context)["sqlstate"]
        if state is not None:
            result["sqlstate"] = state
        context = context.__context__
    return result


def rehearse(*, connector=None):
    conn = None
    before = None
    before_rows = None
    diagnostic = None
    stage = "CONNECT_TEST_DATABASE"
    sequential = []
    restored = False
    try:
        conn = (connector or connect_test_database)()
        with conn.cursor() as cur:
            stage = "CHECK_INSTALLED_BASELINE"
            switch(cur, "project_owner")
            require(inventory(cur) == (52, []), "INSTALLED_BASELINE_REQUIRED")
            before = snapshot(cur)
            before_rows = fingerprint(conn)
        stage = "CREATE_TEN_ROW_FIXTURE"
        # connect_test_database already opened an outer transaction. This is a
        # rollback-only savepoint; final rollback also ends that outer tx.
        with conn.transaction(force_rollback=True):
            fixture = create_fixture(conn, "spms-ct-" + uuid4().hex)
            stage = "VERIFY_EXACT_ROW_DELTA"
            verify_fixture_counts(conn, before)
            fixture_rows = fingerprint(conn)
            state = validate_fixture(conn, fixture)
            for case in CASES:
                for side in ("A", "B"):
                    stage = f"SEQUENTIAL_{case}_{side}"
                    with conn.transaction(force_rollback=True):
                        action(conn, fixture, state, case, side)
                    require(fingerprint(conn) == fixture_rows, "ACTION_BASELINE_NOT_RESTORED")
                    require(validate_fixture(conn, fixture) == state, "ACTION_FIXTURE_CHANGED")
                    sequential.append({"case": case, "side": side, "result": "PASS",
                                       "blocking_tested": False})
            # RC06 B acquires an uncontended lock here; it must NOT time out.
            # 55P03 remains untested until the actual two-session runner runs.
    except Exception as exc:
        diagnostic = {"stage": stage, **safe_diagnostic(exc)}
    finally:
        if conn is not None:
            try:
                conn.rollback()
                if before is not None and before_rows is not None:
                    stage = "POSTFLIGHT_READONLY"
                    conn.execute("SET TRANSACTION READ ONLY")
                    with conn.cursor() as cur:
                        switch(cur, "project_owner")
                        restored = snapshot(cur) == before and fingerprint(conn) == before_rows
                    require(restored, "BASELINE_NOT_RESTORED")
            except Exception as exc:
                diagnostic = {"stage": stage, **safe_diagnostic(exc)}
                restored = False
            finally:
                try:
                    conn.rollback()
                finally:
                    conn.close()
    if diagnostic is not None:
        return {"mode": "DRY_RUN", "result": "FAIL", "diagnostic": diagnostic,
                "baseline_restored": restored, "committed": False}
    require(restored, "POSTFLIGHT_REQUIRED")
    return {"mode": "DRY_RUN", "result": "PASS", "database": TEST_DB,
            "fixture_row_delta": COUNTS, "sequential_actions": sequential,
            "baseline_restored": True, "committed": False, "manifest_exported": False,
            "multisession_tested": False, "identity_sequence_values_excluded": True}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)
    try:
        result = rehearse() if args.dry_run else {
            "mode": "OFFLINE_PLAN", "database_connected": False, "database": TEST_DB,
            "fixture_row_delta": COUNTS, "fixture_rows_total": sum(COUNTS.values()),
            "apply_mode_available": False, "manifest_export_available": False}
        print(json.dumps(result))
        return 0 if result.get("result") != "FAIL" else 1
    except Exception as exc:
        print(json.dumps({"result": "FAIL", **safe_diagnostic(exc), "committed": False}))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
