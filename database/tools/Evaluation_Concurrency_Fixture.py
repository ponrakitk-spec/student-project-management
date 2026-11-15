"""Rehearse a dedicated 42-row Evaluation fixture, always ROLLBACK.

Default is offline. No apply/manifest export, Auth accounts, DDL or grants.
Single-session actions and ordered pairs do not prove database lock waits.
"""

import argparse
import json
from uuid import uuid4

from backend.auth_store import assert_auth_connection
from backend.tests.evaluation_concurrency import (
    CASES, COMMENT, COUNTS, FILE_BYTES, MEMBERS, PROJECTS, USER_ROLES,
    EvaluationFixture, action, case_state, diagnostic, validate_fixture,
)
from backend.tests.team_project_concurrency import fingerprint, project_call, require, team_call
from backend.tests.topic_vote_concurrency import vote_call
from backend.committee_store import committee_transaction_on
from database.tests.Auth_Regression import snapshot, switch
from database.tools.Evaluation_Concurrency_Rehearsal import actor, evaluation_call, ordered_pair
from database.tools.Test_Database import TEST_DB, connect_test_database
from database.tools.V1_Baseline_Prepare import inventory


def placeholder(namespace):
    return {"version": 1, "database": TEST_DB, "namespace": namespace,
            "users": {key: str(i) for i, key in enumerate(USER_ROLES, 1)},
            "teams": {"main": "1", "final": "2"}, "projects": {"main": "1", "final": "2"},
            "submissions": {"main": "1", "final": "2"},
            "assignments": {"main": {"b": "1", "c": "2", "d": "3"}, "final": {"b": "4", "c": "5", "d": "6"}},
            "work": {"main": {"milestone": "1", "task": "1", "member": "1"},
                     "editable": {"milestone": "2", "task": "2", "member": "1"},
                     "final": {"milestone": "3", "task": "3", "member": "2"}}}


def create_fixture(conn, namespace):
    data = placeholder(namespace)
    EvaluationFixture.parse(data)  # Reject unsafe namespace before any writes.
    users, teams, projects, submissions, assignments, work = {}, {}, {}, {}, {}, {}
    with conn.cursor() as cur:
        switch(cur, "project_owner")
        for label, role in USER_ROLES.items():
            cur.execute("INSERT INTO public.users(full_name,email,role) VALUES (%s,%s,%s) RETURNING id",
                        ("Evaluation concurrency " + label, f"{namespace}.{label}@example.test", role))
            users[label] = str(cur.fetchone()[0])
        switch(cur, "project_app")
    assert_auth_connection(conn)
    due = conn.execute("SELECT (NOW() AT TIME ZONE 'Asia/Bangkok')::date+7").fetchone()[0]
    for label in PROJECTS:
        leader = users["leader_" + label]
        teams[label] = team_call(conn, "create", f"{namespace}.{label}", None, leader)["id"]
        projects[label] = project_call(conn, "create", f"{namespace}.{label}.project", None, leader)["id"]
        invitation = conn.execute("INSERT INTO public.advisor_invitations(project_id,advisor_id,sent_by) VALUES (%s,%s,%s) RETURNING id",
                                  (projects[label], users["advisor"], leader)).fetchone()[0]
        actor(conn, users["advisor"])
        conn.execute("SELECT public.v1_resolve_invitation(%s,'accepted')", (invitation,))
        actor(conn, leader)
        conn.execute("SET CONSTRAINTS public.c_submission_requires_file DEFERRED")
        submission = conn.execute("INSERT INTO public.project_submissions(project_id,submitted_by) VALUES (%s,%s) RETURNING id",
                                  (projects[label], leader)).fetchone()[0]
        submissions[label] = str(submission)
        conn.execute("INSERT INTO public.project_submission_files(submission_id,file_data,original_filename,mime_type) "
                     "VALUES (%s,%s,'phase.pdf','application/pdf')", (submission, FILE_BYTES))
        conn.execute("SET CONSTRAINTS ALL IMMEDIATE")
        actor(conn, users["advisor"])
        conn.execute("SELECT public.v1_review_submission(%s,'approved',NULL)", (submission,))
        assignments[label] = {}
        for member in MEMBERS:
            with committee_transaction_on(conn) as store:
                assignments[label][member] = store.mutate(users["coordinator"], projects[label], operation="add", advisor=users[member])["id"]
        for member in MEMBERS:
            vote_call(conn, "cast", users[member], projects[label], submissions[label], "approved", COMMENT)
        for work_label in (("main", "editable") if label == "main" else ("final",)):
            actor(conn, leader)
            milestone = conn.execute("SELECT public.v1_create_milestone(%s,%s,NULL,%s)",
                                     (projects[label], f"{namespace}.{work_label}.milestone", due)).fetchone()[0]
            task = conn.execute("SELECT public.v1_create_task(%s,%s,NULL,%s)",
                                (milestone, f"{namespace}.{work_label}.task", due)).fetchone()[0]
            membership = conn.execute("SELECT id FROM public.team_members WHERE user_id=%s", (leader,)).fetchone()[0]
            conn.execute("SELECT public.v1_assign_task(%s,%s)", (task, membership))
            if work_label != "editable":
                conn.execute("SELECT public.v1_set_task_status(%s,'completed')", (task,))
            work[work_label] = {"milestone": str(milestone), "task": str(task), "member": str(membership)}
    for member, score in (("b", 60), ("c", 70)):
        evaluation_call(conn, "record", users[member], projects["final"], score, COMMENT)
    conn.execute("SET CONSTRAINTS ALL IMMEDIATE")
    fixture = EvaluationFixture.parse({**data, "users": users, "teams": teams, "projects": projects,
                                       "submissions": submissions, "assignments": assignments, "work": work})
    validate_fixture(conn, fixture)
    return fixture


def verify_counts(conn, before):
    with conn.cursor() as cur:
        switch(cur, "project_owner")
        during = snapshot(cur)
        require(during[0] == before[0], "METADATA_CHANGED_DURING_FIXTURE")
        require(during[1] == {table: count + COUNTS.get(table, 0) for table, count in before[1].items()},
                "UNEXPECTED_EVALUATION_FIXTURE_ROW_DELTA")
        switch(cur, "project_app")
    assert_auth_connection(conn)


def rehearse(*, connector=None):
    conn, before, before_rows, error = None, None, None, None
    stage, restored, actions, pairs = "CONNECT_TEST_DATABASE", False, [], []
    try:
        conn = (connector or connect_test_database)()
        require(conn.execute("SELECT current_database()").fetchone() == (TEST_DB,), "TEST_DATABASE_REQUIRED")
        with conn.cursor() as cur:
            stage = "CHECK_INSTALLED_BASELINE"
            switch(cur, "project_owner")
            require(inventory(cur) == (52, []), "INSTALLED_BASELINE_REQUIRED")
            before, before_rows = snapshot(cur), fingerprint(conn)
        with conn.transaction(force_rollback=True):
            stage = "CREATE_42_ROW_FIXTURE"
            fixture = create_fixture(conn, "spms-ec-" + uuid4().hex)
            verify_counts(conn, before)
            baseline = fingerprint(conn)
            dates = validate_fixture(conn, fixture)
            for case in CASES:
                for side in ("A", "B"):
                    stage = f"ISOLATED_{case}_{side}"
                    with conn.transaction(force_rollback=True):
                        action(conn, fixture, dates, case, side)
                    require(fingerprint(conn) == baseline, "ACTION_BASELINE_NOT_RESTORED")
                    validate_fixture(conn, fixture)
                    actions.append({"case": case, "side": side, "result": "PASS"})
                stage = f"ORDERED_{case}"
                with conn.transaction(force_rollback=True):
                    result = ordered_pair(conn, case_state(fixture, dates, case), case)
                require(fingerprint(conn) == baseline, "PAIR_BASELINE_NOT_RESTORED")
                pairs.append({"case": case, "result": "PASS", **result})
    except Exception as exc:
        error = {"stage": stage, **diagnostic(exc)}
    finally:
        if conn is not None:
            try:
                conn.rollback()
                if before is not None and before_rows is not None:
                    conn.execute("SET TRANSACTION READ ONLY")
                    with conn.cursor() as cur:
                        switch(cur, "project_owner")
                        restored = snapshot(cur) == before and fingerprint(conn) == before_rows
                    require(restored, "BASELINE_NOT_RESTORED")
            except Exception as exc:
                error, restored = {"stage": "POSTFLIGHT", **diagnostic(exc)}, False
            finally:
                try:
                    conn.rollback()
                finally:
                    conn.close()
    result = {"mode": "DRY_RUN", "result": "FAIL" if error else "PASS", "database": TEST_DB,
              "fixture_rows_total": sum(COUNTS.values()), "baseline_restored": restored,
              "committed": False, "manifest_exported": False, "multisession_tested": False,
              "identity_sequence_values_excluded": True}
    if error:
        return {**result, "diagnostic": error}
    require(restored, "POSTFLIGHT_REQUIRED")
    return {**result, "fixture_row_delta": COUNTS, "isolated_actions": actions, "ordered_pairs": pairs}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)
    try:
        result = rehearse() if args.dry_run else {"mode": "OFFLINE_PLAN", "database_connected": False,
            "database": TEST_DB, "fixture_rows_total": sum(COUNTS.values()), "fixture_row_delta": COUNTS,
            "apply_mode_available": False, "manifest_export_available": False}
        print(json.dumps(result))
        return 1 if result.get("result") == "FAIL" else 0
    except Exception as exc:
        print(json.dumps({"result": "FAIL", **diagnostic(exc), "committed": False}))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
