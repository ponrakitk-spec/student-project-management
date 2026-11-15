"""Rehearse a dedicated Topic/Committee fixture and ALWAYS ROLLBACK.

Default invocation is offline; --dry-run uses only the pinned test database.
No apply, COMMIT, manifest export, Login credentials, DDL or grant changes.
Sequential rehearsals do not prove cross-session visibility or concurrency.
"""

import argparse
import json
from uuid import uuid4

from backend.auth_store import assert_auth_connection
from backend.tests.team_project_concurrency import fingerprint, project_call, require, team_call
from backend.tests.topic_vote_concurrency import (
    CASES, COMMITTEE_LABELS, FILE_BYTES, PROJECT_LABELS, REVISION_COMMENT, USER_ROLES,
    VoteFixture, action, diagnostic, validate_fixture, vote_call,
)
from backend.committee_store import committee_transaction_on
from database.tests.Auth_Regression import snapshot, switch
from database.tools.Test_Database import TEST_DB, connect_test_database
from database.tools.V1_Baseline_Prepare import inventory

COUNTS = {"public.users": 8, "public.teams": 2, "public.team_members": 2, "public.projects": 2,
          "public.advisor_invitations": 2, "public.project_submissions": 2,
          "public.project_submission_files": 2, "public.committee_assignments": 6,
          "public.committee_topic_votes": 3}


def create_fixture(conn, namespace):
    # Validate all namespace/shape rules before any DML.
    placeholder = {"version": 1, "database": TEST_DB, "namespace": namespace,
                   "users": {key: str(index) for index, key in enumerate(USER_ROLES, 1)},
                   "teams": {"main": "1", "revision": "2"},
                   "projects": {"main": "1", "revision": "2"},
                   "submissions": {"main": "1", "revision": "2"},
                   "assignments": {"main": {"b": "1", "c": "2", "d": "3"},
                                   "revision": {"b": "4", "c": "5", "d": "6"}}}
    VoteFixture.parse(placeholder)
    users, teams, projects, submissions, assignments = {}, {}, {}, {}, {}
    with conn.cursor() as cur:
        switch(cur, "project_owner")
        cur.execute("SELECT current_user,rolsuper FROM pg_roles WHERE rolname=current_user")
        require(cur.fetchone() == ("project_owner", False), "NON_SUPERUSER_OWNER_REQUIRED")
        for label, role in USER_ROLES.items():
            cur.execute("INSERT INTO public.users(full_name,email,role) VALUES (%s,%s,%s) RETURNING id",
                        ("Topic concurrency fixture " + label, f"{namespace}.{label}@example.test", role))
            users[label] = str(cur.fetchone()[0])
        switch(cur, "project_app")
    assert_auth_connection(conn)
    for label in PROJECT_LABELS:
        leader = users["leader_" + label]
        teams[label] = team_call(conn, "create", f"{namespace}.{label}", None, leader)["id"]
        projects[label] = project_call(conn, "create", f"{namespace}.{label}.project", None, leader)["id"]
        invitation = conn.execute("INSERT INTO public.advisor_invitations(project_id,advisor_id,sent_by) VALUES (%s,%s,%s) RETURNING id",
                                  (projects[label], users["advisor"], leader)).fetchone()[0]
        conn.execute("SELECT set_config('app.actor_user_id',%s,true)", (users["advisor"],))
        conn.execute("SELECT public.v1_resolve_invitation(%s,'accepted')", (invitation,))
        conn.execute("SELECT set_config('app.actor_user_id',%s,true)", (leader,))
        conn.execute("SET CONSTRAINTS public.c_submission_requires_file DEFERRED")
        submission = conn.execute("INSERT INTO public.project_submissions(project_id,submitted_by) VALUES (%s,%s) RETURNING id",
                                  (projects[label], leader)).fetchone()[0]
        submissions[label] = str(submission)
        conn.execute("INSERT INTO public.project_submission_files(submission_id,file_data,original_filename,mime_type) "
                     "VALUES (%s,%s,'phase.pdf','application/pdf')", (submission, FILE_BYTES))
        conn.execute("SET CONSTRAINTS ALL IMMEDIATE")
        conn.execute("SELECT set_config('app.actor_user_id',%s,true)", (users["advisor"],))
        conn.execute("SELECT public.v1_review_submission(%s,'approved',NULL)", (submission,))
        assignments[label] = {}
        for member in COMMITTEE_LABELS:
            with committee_transaction_on(conn) as store:
                assignments[label][member] = store.mutate(users["coordinator"], projects[label],
                                                         operation="add", advisor=users[member])["id"]
        if label == "revision":
            for member in COMMITTEE_LABELS:
                vote_call(conn, "cast", users[member], projects[label], submissions[label], "revision_requested", REVISION_COMMENT)
    fixture = VoteFixture.parse({**placeholder, "users": users, "teams": teams, "projects": projects,
                                 "submissions": submissions, "assignments": assignments})
    conn.execute("SET CONSTRAINTS ALL IMMEDIATE")
    validate_fixture(conn, fixture)
    return fixture


def verify_fixture_counts(conn, before):
    with conn.cursor() as cur:
        switch(cur, "project_owner")
        during = snapshot(cur)
        require(during[0] == before[0], "METADATA_CHANGED_DURING_FIXTURE")
        require(during[1] == {table: count + COUNTS.get(table, 0) for table, count in before[1].items()},
                "UNEXPECTED_VOTE_FIXTURE_ROW_DELTA")
        switch(cur, "project_app")
    assert_auth_connection(conn)


def rehearse(*, connector=None):
    conn, before, before_rows, error = None, None, None, None
    stage, restored, sequential = "CONNECT_TEST_DATABASE", False, []
    try:
        conn = (connector or connect_test_database)()
        with conn.cursor() as cur:
            stage = "CHECK_INSTALLED_BASELINE"
            switch(cur, "project_owner")
            require(inventory(cur) == (52, []), "INSTALLED_BASELINE_REQUIRED")
            before, before_rows = snapshot(cur), fingerprint(conn)
        stage = "CREATE_29_ROW_VOTE_FIXTURE"
        with conn.transaction(force_rollback=True):
            fixture = create_fixture(conn, "spms-vc-" + uuid4().hex)
            stage = "VERIFY_EXACT_ROW_DELTA"
            verify_fixture_counts(conn, before)
            fixture_rows = fingerprint(conn)
            for case in CASES:
                for side in ("A", "B"):
                    stage = f"SEQUENTIAL_{case}_{side}"
                    with conn.transaction(force_rollback=True):
                        action(conn, fixture, case, side)
                    require(fingerprint(conn) == fixture_rows, "ACTION_BASELINE_NOT_RESTORED")
                    validate_fixture(conn, fixture)
                    sequential.append({"case": case, "side": side, "result": "PASS", "blocking_tested": False})
    except Exception as exc:
        error = {"stage": stage, **diagnostic(exc)}
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
                error, restored = {"stage": stage, **diagnostic(exc)}, False
            finally:
                try:
                    conn.rollback()
                finally:
                    conn.close()
    if error is not None:
        return {"mode": "DRY_RUN", "result": "FAIL", "diagnostic": error,
                "baseline_restored": restored, "committed": False}
    require(restored, "POSTFLIGHT_REQUIRED")
    return {"mode": "DRY_RUN", "result": "PASS", "database": TEST_DB, "fixture_row_delta": COUNTS,
            "fixture_rows_total": sum(COUNTS.values()), "sequential_actions": sequential,
            "baseline_restored": True, "committed": False, "manifest_exported": False,
            "multisession_tested": False, "identity_sequence_values_excluded": True}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)
    try:
        result = rehearse() if args.dry_run else {"mode": "OFFLINE_PLAN", "database_connected": False,
            "database": TEST_DB, "fixture_row_delta": COUNTS, "fixture_rows_total": sum(COUNTS.values()),
            "apply_mode_available": False, "manifest_export_available": False}
        print(json.dumps(result))
        return 0 if result.get("result") != "FAIL" else 1
    except Exception as exc:
        print(json.dumps({"result": "FAIL", **diagnostic(exc), "committed": False}))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
