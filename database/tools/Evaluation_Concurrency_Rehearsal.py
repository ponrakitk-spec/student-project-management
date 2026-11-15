"""Prepare Evaluation race scenarios in one session and ALWAYS ROLLBACK.

Default is an offline plan. --dry-run rehearses commands and ordered pairs;
it does NOT test concurrent sessions, waits, HTTP, or winner-COMMIT. No apply,
manifest export, Login accounts, DDL, grants, or changes to existing fixtures.
"""

import argparse
import json
from uuid import uuid4

import psycopg

from backend.auth_store import assert_auth_connection
from backend.evaluation_store import EvaluationError, evaluation_transaction_on
from backend.tests.team_project_concurrency import fingerprint, require
from backend.tests.topic_vote_concurrency import diagnostic, vote_call
from database.tests.Auth_Regression import snapshot, switch
from database.tools.Test_Database import TEST_DB, connect_test_database
from database.tools.Topic_Vote_Concurrency_Fixture import COUNTS as TOPIC_COUNTS, create_fixture as create_topic_fixture
from database.tools.V1_Baseline_Prepare import inventory


CASES = {
    "EC01": "First evaluation / Task metadata update",
    "EC02": "First evaluation / Milestone metadata update",
    "EC03": "First evaluation / Task assignee removal",
    "EC04": "Reopen the only completed Task / Evaluation eligibility recheck",
    "EC05": "Same committee assignment / Duplicate evaluation",
    "EC06": "Different committees / Partial score privacy",
    "EC07": "Final evaluation / Team, Advisor, Coordinator result readers",
    "EC08": "Team reader / Final evaluation",
}
COUNTS = {**TOPIC_COUNTS, "public.committee_topic_votes": TOPIC_COUNTS["public.committee_topic_votes"] + 3,
          "public.milestones": 2, "public.tasks": 2, "public.task_assignees": 2}
COMMENT = "Evaluation rehearsal feedback"


def evaluation_call(conn, method, *args):
    with evaluation_transaction_on(conn) as store:
        return getattr(store, method)(*args)


def actor(conn, user):
    assert_auth_connection(conn)
    conn.execute("SELECT set_config('app.actor_user_id',%s,true)", (user,))


def create_fixture(conn):
    # The existing helper validates a fresh UUID namespace before any writes.
    fixture = create_topic_fixture(conn, "spms-vc-" + uuid4().hex)
    project, users = fixture.projects["main"], fixture.users
    for member in ("b", "c", "d"):
        vote_call(conn, "cast", users[member], project, fixture.submissions["main"], "approved", COMMENT)
    actor(conn, users["leader_main"])
    due = conn.execute("SELECT (NOW() AT TIME ZONE 'Asia/Bangkok')::date+7").fetchone()[0]
    milestone = conn.execute("SELECT public.v1_create_milestone(%s,'Evaluation rehearsal',NULL,%s)", (project, due)).fetchone()[0]
    task = conn.execute("SELECT public.v1_create_task(%s,'Evaluation rehearsal task',NULL,%s)", (milestone, due)).fetchone()[0]
    member = conn.execute("SELECT id FROM public.team_members WHERE user_id=%s", (users["leader_main"],)).fetchone()[0]
    conn.execute("SELECT public.v1_assign_task(%s,%s)", (task, member))
    conn.execute("SELECT public.v1_set_task_status(%s,'completed')", (task,))
    conn.execute("SET CONSTRAINTS ALL IMMEDIATE")
    require(conn.execute("SELECT status FROM public.milestones WHERE id=%s", (milestone,)).fetchone() == ("completed",),
            "DERIVED_COMPLETED_MILESTONE_REQUIRED")
    # Completed Tasks already reject metadata/assignee edits before Evaluation.
    # Use a separate not_started Task to isolate the first-score lock itself.
    editable_milestone = conn.execute("SELECT public.v1_create_milestone(%s,'Editable rehearsal',NULL,%s)",
                                     (project, due)).fetchone()[0]
    editable_task = conn.execute("SELECT public.v1_create_task(%s,'Editable rehearsal task',NULL,%s)",
                                (editable_milestone, due)).fetchone()[0]
    conn.execute("SELECT public.v1_assign_task(%s,%s)", (editable_task, member))
    conn.execute("SET CONSTRAINTS ALL IMMEDIATE")
    require(evaluation_call(conn, "committee_context", users["b"], project)["can_evaluate"], "EVALUATION_NOT_ELIGIBLE")
    return {"base": fixture, "milestone": milestone, "task": task, "editable_task": editable_task,
            "member": member, "due": due}


def verify_counts(conn, before):
    with conn.cursor() as cur:
        switch(cur, "project_owner")
        during = snapshot(cur)
        require(during[0] == before[0], "METADATA_CHANGED_DURING_FIXTURE")
        require(during[1] == {table: count + COUNTS.get(table, 0) for table, count in before[1].items()},
                "UNEXPECTED_EVALUATION_FIXTURE_ROW_DELTA")
        switch(cur, "project_app")
    assert_auth_connection(conn)


def record(conn, state, member, score):
    fixture = state["base"]
    result = evaluation_call(conn, "record", fixture.users[member], fixture.projects["main"], score, COMMENT)
    require(result["score"] == score and result["comment"] == COMMENT, "EVALUATION_RECORD_RESULT")


def reader(conn, state, complete):
    fixture = state["base"]
    project, users = fixture.projects["main"], fixture.users
    expected = {"total_score": "210", "average_score": 70} if complete else None
    team = evaluation_call(conn, "team_context", users["leader_main"])
    advisor = evaluation_call(conn, "advisor_context", users["advisor"], project)
    coordinator = evaluation_call(conn, "coordinator_context", users["coordinator"], project)
    require(set(team) == set(advisor) == {"project", "summary"}, "READER_DTO_PRIVACY")
    require(team["summary"] == advisor["summary"] == coordinator["summary"] == expected, "READER_SUMMARY")
    require(len(coordinator["evaluations"]) == (3 if complete else 0), "COORDINATOR_EVALUATION_PRIVACY")


def prepare_case(conn, state, case):
    if case in ("EC07", "EC08"):
        record(conn, state, "b", 60)
        record(conn, state, "c", 70)
        reader(conn, state, False)


def action(conn, state, case, side, *, after_first=False):
    require(case in CASES and side in ("A", "B"), "UNKNOWN_EVALUATION_ACTION")
    fixture = state["base"]
    users, project = fixture.users, fixture.projects["main"]
    if side == "A":
        if case == "EC04":
            actor(conn, users["leader_main"])
            conn.execute("SELECT public.v1_set_task_status(%s,'in_progress')", (state["task"],))
            require(conn.execute("SELECT status FROM public.milestones WHERE id=%s", (state["milestone"],)).fetchone() ==
                    ("in_progress",), "REOPEN_DID_NOT_DERIVE_MILESTONE")
        elif case == "EC08":
            reader(conn, state, False)
        else:
            record(conn, state, "d" if case == "EC07" else "b", 80)
    elif case in ("EC01", "EC02", "EC03"):
        actor(conn, users["leader_main"])
        if case == "EC01":
            conn.execute("SELECT public.v1_update_task_metadata(%s,'Updated rehearsal task',NULL,%s)", (state["editable_task"], state["due"]))
            require(conn.execute("SELECT name FROM public.tasks WHERE id=%s", (state["editable_task"],)).fetchone() ==
                    ("Updated rehearsal task",), "TASK_METADATA_NOT_CHANGED")
        elif case == "EC02":
            conn.execute("SELECT public.v1_update_milestone(%s,'Updated rehearsal milestone',NULL,%s)", (state["milestone"], state["due"]))
            require(conn.execute("SELECT name FROM public.milestones WHERE id=%s", (state["milestone"],)).fetchone() ==
                    ("Updated rehearsal milestone",), "MILESTONE_METADATA_NOT_CHANGED")
        else:
            conn.execute("SELECT public.v1_unassign_task(%s,%s)", (state["editable_task"], state["member"]))
            require(conn.execute("SELECT count(*) FROM public.task_assignees WHERE task_id=%s", (state["editable_task"],)).fetchone() == (0,),
                    "ASSIGNEE_NOT_REMOVED")
            require(conn.execute("SELECT count(*) FROM public.task_assignment_history WHERE task_id=%s", (state["editable_task"],)).fetchone() == (1,),
                    "ASSIGNEE_HISTORY_REQUIRED")
    elif case == "EC07":
        reader(conn, state, after_first)
    else:
        record(conn, state, "c" if case == "EC06" else "d" if case == "EC08" else "b", 80 if case == "EC08" else 90)
        if case == "EC06":
            reader(conn, state, False)
        elif case == "EC08":
            reader(conn, state, True)
    conn.execute("SET CONSTRAINTS ALL IMMEDIATE")


def ordered_pair(conn, state, case):
    action(conn, state, case, "A")
    if case in ("EC01", "EC02", "EC03"):
        try:
            with conn.transaction():
                action(conn, state, case, "B", after_first=True)
        except psycopg.errors.RaiseException:
            return {"expected_sqlstate": "P0001"}
        require(False, "FIRST_EVALUATION_DID_NOT_LOCK_WORK")
    elif case in ("EC04", "EC05"):
        expected = "COMPLETED_MILESTONE_REQUIRED" if case == "EC04" else "EVALUATION_ALREADY_RECORDED"
        try:
            action(conn, state, case, "B", after_first=True)
        except EvaluationError as exc:
            require(exc.code == expected, "UNEXPECTED_EVALUATION_CONFLICT")
            return {"expected_code": expected}
        require(False, "EXPECTED_EVALUATION_CONFLICT_MISSING")
    else:
        action(conn, state, case, "B", after_first=True)
        return {"expected_code": None}


def rehearse(*, connector=None):
    conn, before, before_rows, error = None, None, None, None
    stage, restored, sequential, pairs = "CONNECT_TEST_DATABASE", False, [], []
    try:
        conn = (connector or connect_test_database)()
        stage = "CHECK_TEST_DATABASE"
        require(conn.execute("SELECT current_database()").fetchone() == (TEST_DB,), "TEST_DATABASE_REQUIRED")
        with conn.cursor() as cur:
            switch(cur, "project_owner")
            stage = "CHECK_INSTALLED_BASELINE"
            require(inventory(cur) == (52, []), "INSTALLED_BASELINE_REQUIRED")
            before, before_rows = snapshot(cur), fingerprint(conn)
        with conn.transaction(force_rollback=True):
            stage = "CREATE_38_ROW_EVALUATION_FIXTURE"
            state = create_fixture(conn)
            verify_counts(conn, before)
            fixture_rows = fingerprint(conn)
            for case in CASES:
                with conn.transaction(force_rollback=True):
                    stage = f"PREPARE_{case}"
                    prepare_case(conn, state, case)
                    case_rows = fingerprint(conn)
                    for side in ("A", "B"):
                        stage = f"ISOLATED_{case}_{side}"
                        with conn.transaction(force_rollback=True):
                            action(conn, state, case, side)
                        require(fingerprint(conn) == case_rows, "ACTION_BASELINE_NOT_RESTORED")
                        sequential.append({"case": case, "side": side, "result": "PASS"})
                    stage = f"ORDERED_{case}_A_THEN_B"
                    with conn.transaction(force_rollback=True):
                        outcome = ordered_pair(conn, state, case)
                    require(fingerprint(conn) == case_rows, "PAIR_BASELINE_NOT_RESTORED")
                    pairs.append({"case": case, "result": "PASS", **outcome})
                require(fingerprint(conn) == fixture_rows, "CASE_BASELINE_NOT_RESTORED")
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
    result = {"mode": "DRY_RUN", "result": "FAIL" if error else "PASS", "database": TEST_DB,
              "baseline_restored": restored, "committed": False, "manifest_exported": False,
              "multisession_tested": False, "blocking_tested": False, "http_tested": False,
              "identity_sequence_values_excluded": True}
    if error:
        return {**result, "diagnostic": error}
    require(restored, "POSTFLIGHT_REQUIRED")
    return {**result, "fixture_row_delta": COUNTS, "fixture_rows_total": sum(COUNTS.values()),
            "isolated_actions": sequential, "ordered_pairs": pairs}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)
    try:
        result = rehearse() if args.dry_run else {"mode": "OFFLINE_PLAN", "database": TEST_DB,
            "database_connected": False, "fixture_row_delta": COUNTS, "fixture_rows_total": sum(COUNTS.values()),
            "cases": CASES, "apply_mode_available": False, "manifest_export_available": False,
            "multisession_tested": False, "blocking_tested": False}
        print(json.dumps(result))
        return 1 if result.get("result") == "FAIL" else 0
    except Exception as exc:
        print(json.dumps({"result": "FAIL", **diagnostic(exc), "committed": False}))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
