"""Prepared Topic/Committee two-session tests; default invocation is OFFLINE.

Requires a dedicated, already-visible fixture manifest. Never seeds/commits
shared data, uses an existing user's project, or changes Schema/RBAC. Both
workers always ROLLBACK. Winner-COMMIT and HTTP concurrency remain untested.
"""

import argparse
from dataclasses import dataclass
import json
from pathlib import Path
from queue import Empty, Queue
import re
from threading import Thread

from backend.auth_store import APP_ROLE, TEST_DB, assert_auth_connection
from backend.committee_store import committee_transaction_on
from backend.topic_vote_store import topic_vote_transaction_on
from backend.tests.team_project_concurrency import (
    CheckFailed, fingerprint, finish_worker, positive_id, require,
    rollback_connection, sanitized_failure, wait_for_block,
)

CASES = {
    "VC01": "First Vote blocks committee add; add succeeds after Vote rollback",
    "VC02": "First Vote blocks committee replacement; replacement succeeds after rollback",
    "VC03": "First Vote blocks committee removal; removal succeeds after rollback",
    "VC04": "Uncommitted voter removal blocks own Vote; rollback restores assignment",
    "VC05": "Same committee's second Vote waits; exactly one remains inside B after A rollback",
    "VC06": "Different committee Votes serialize; B cannot see A's rolled-back Vote",
    "VC07": "Uncommitted new round blocks reader; reader sees only baseline history after rollback",
    "VC08": "Reader holds Project lock; Vote waits and proceeds after reader rollback",
}
USER_ROLES = {
    "leader_main": "student", "leader_revision": "student", "advisor": "advisor",
    "b": "advisor", "c": "advisor", "d": "advisor", "spare": "advisor",
    "coordinator": "coordinator",
}
PROJECT_LABELS = ("main", "revision")
COMMITTEE_LABELS = ("b", "c", "d")
REVISION_COMMENT = "Concurrency revision fixture"
FILE_BYTES = b"DB-only topic concurrency phase fixture"


def diagnostic(exc):
    result, seen, current = sanitized_failure(exc), set(), exc
    while result["sqlstate"] is None and current is not None and id(current) not in seen:
        seen.add(id(current))
        result["sqlstate"] = sanitized_failure(current)["sqlstate"]
        current = current.__context__
    return result


@dataclass(frozen=True)
class VoteFixture:
    namespace: str
    users: dict
    teams: dict
    projects: dict
    submissions: dict
    assignments: dict

    @classmethod
    def parse(cls, data):
        require(isinstance(data, dict) and set(data) == {
            "version", "database", "namespace", "users", "teams", "projects", "submissions", "assignments"},
            "VOTE_MANIFEST_SHAPE")
        require(type(data["version"]) is int and data["version"] == 1, "VOTE_MANIFEST_VERSION")
        require(data["database"] == TEST_DB, "VOTE_MANIFEST_DATABASE")
        require(isinstance(data["namespace"], str) and
                re.fullmatch(r"spms-vc-[0-9a-f]{32}", data["namespace"]), "VOTE_MANIFEST_NAMESPACE")
        for field, labels in (("users", USER_ROLES), ("teams", PROJECT_LABELS),
                              ("projects", PROJECT_LABELS), ("submissions", PROJECT_LABELS)):
            values = data[field]
            require(isinstance(values, dict) and set(values) == set(labels), "VOTE_MANIFEST_KEYS")
            require(all(positive_id(value) for value in values.values()), "VOTE_MANIFEST_IDS")
            require(len(set(values.values())) == len(values), "VOTE_MANIFEST_DUPLICATE_IDS")
        assignments = data["assignments"]
        require(isinstance(assignments, dict) and set(assignments) == set(PROJECT_LABELS), "VOTE_MANIFEST_KEYS")
        for values in assignments.values():
            require(isinstance(values, dict) and set(values) == set(COMMITTEE_LABELS), "VOTE_MANIFEST_KEYS")
            require(all(positive_id(value) for value in values.values()), "VOTE_MANIFEST_IDS")
        require(len({value for values in assignments.values() for value in values.values()}) == 6,
                "VOTE_MANIFEST_DUPLICATE_IDS")
        return cls(data["namespace"], dict(data["users"]), dict(data["teams"]), dict(data["projects"]),
                   dict(data["submissions"]), {key: dict(value) for key, value in assignments.items()})

    @classmethod
    def load(cls, path):
        try:
            require(Path(path).stat().st_size <= 8192, "VOTE_MANIFEST_TOO_LARGE")
            return cls.parse(json.loads(Path(path).read_text(encoding="utf-8-sig")))
        except (OSError, ValueError):
            raise CheckFailed("VOTE_MANIFEST_READ") from None


def validate_fixture(conn, fixture):
    """SELECT-only checks; exact dedicated graph, no auto-picking real rows."""
    assert_auth_connection(conn)
    users, ns = fixture.users, fixture.namespace
    for label, role in USER_ROLES.items():
        require(conn.execute("SELECT email,role FROM public.users WHERE id=%s", (users[label],)).fetchone() ==
                (f"{ns}.{label}@example.test", role), "VOTE_FIXTURE_USER_MISMATCH")
    team_ids = [int(value) for value in fixture.teams.values()]
    user_ids = [int(value) for value in users.values()]
    members = conn.execute("SELECT team_id,user_id,role FROM public.team_members "
                           "WHERE team_id=ANY(%s) OR user_id=ANY(%s)", (team_ids, user_ids)).fetchall()
    expected_members = {(int(fixture.teams[label]), int(users["leader_" + label]), "leader") for label in PROJECT_LABELS}
    require(len(members) == 2 and set(members) == expected_members, "VOTE_FIXTURE_MEMBERSHIP")
    for label in PROJECT_LABELS:
        project, team, submission = fixture.projects[label], fixture.teams[label], fixture.submissions[label]
        leader = users["leader_" + label]
        require(conn.execute("SELECT name FROM public.teams WHERE id=%s", (team,)).fetchone() ==
                (f"{ns}.{label}",), "VOTE_FIXTURE_TEAM_MISMATCH")
        require(conn.execute("SELECT id,created_by,name,description FROM public.projects WHERE team_id=%s", (team,)).fetchall() ==
                [(int(project), int(leader), f"{ns}.{label}.project", None)], "VOTE_FIXTURE_PROJECT_MISMATCH")
        require(conn.execute("SELECT advisor_id,sent_by,status FROM public.advisor_invitations WHERE project_id=%s", (project,)).fetchall() ==
                [(int(users["advisor"]), int(leader), "accepted")], "VOTE_FIXTURE_INVITATION")
        require(conn.execute("SELECT id,submitted_by,status,snapshot_name,snapshot_description FROM public.project_submissions "
                             "WHERE project_id=%s", (project,)).fetchall() ==
                [(int(submission), int(leader), "approved", f"{ns}.{label}.project", None)], "VOTE_FIXTURE_SUBMISSION")
        require(conn.execute("SELECT file_data,original_filename,mime_type FROM public.project_submission_files WHERE submission_id=%s", (submission,)).fetchall() ==
                [(FILE_BYTES, "phase.pdf", "application/pdf")], "VOTE_FIXTURE_FILE")
        assignments = conn.execute("SELECT id,advisor_id,assigned_by FROM public.committee_assignments WHERE project_id=%s", (project,)).fetchall()
        require(len(assignments) == 3 and set(assignments) == {
            (int(fixture.assignments[label][member]), int(users[member]), int(users["coordinator"]))
            for member in COMMITTEE_LABELS}, "VOTE_FIXTURE_ASSIGNMENTS")
        votes = conn.execute("SELECT v.submission_id,v.committee_assignment_id,v.vote,v.comment "
                              "FROM public.committee_topic_votes v JOIN public.committee_assignments a "
                              "ON a.id=v.committee_assignment_id WHERE a.project_id=%s", (project,)).fetchall()
        expected = {(int(submission), int(assignment), "revision_requested", REVISION_COMMENT)
                    for assignment in fixture.assignments[label].values()} if label == "revision" else set()
        require(len(votes) == len(expected) and set(votes) == expected, "VOTE_FIXTURE_VOTES")
        require(conn.execute("SELECT public.v1_topic_decision(%s)", (submission,)).fetchone() ==
                ("revision_requested" if label == "revision" else None,), "VOTE_FIXTURE_DECISION")
        require(not conn.execute("SELECT EXISTS(SELECT 1 FROM public.milestones WHERE project_id=%s)", (project,)).fetchone()[0],
                "VOTE_FIXTURE_MILESTONES")
        require(not conn.execute("SELECT EXISTS(SELECT 1 FROM public.committee_evaluations e JOIN public.committee_assignments a "
                                 "ON a.id=e.committee_assignment_id WHERE a.project_id=%s)", (project,)).fetchone()[0],
                "VOTE_FIXTURE_EVALUATIONS")
    require(not conn.execute("SELECT EXISTS(SELECT 1 FROM public.task_assignment_history WHERE user_id=ANY(%s))", (user_ids,)).fetchone()[0],
            "VOTE_FIXTURE_TASK_HISTORY")


def vote_call(conn, method, *args):
    with topic_vote_transaction_on(conn) as store:
        return getattr(store, method)(*args)


def committee_call(conn, fixture, operation, **kwargs):
    with committee_transaction_on(conn) as store:
        return store.mutate(fixture.users["coordinator"], fixture.projects["main"], operation=operation, **kwargs)


def new_round(conn, fixture):
    """DB-only phase setup; does not implement peer Submission/file APIs."""
    conn.execute("SELECT set_config('app.actor_user_id',%s,true)", (fixture.users["leader_revision"],))
    conn.execute("SELECT public.v1_lock_project(%s)", (fixture.projects["revision"],))
    conn.execute("SET CONSTRAINTS public.c_submission_requires_file DEFERRED")
    identifier = conn.execute("INSERT INTO public.project_submissions(project_id,submitted_by) VALUES (%s,%s) RETURNING id",
                              (fixture.projects["revision"], fixture.users["leader_revision"])).fetchone()[0]
    conn.execute("INSERT INTO public.project_submission_files(submission_id,file_data,original_filename,mime_type) "
                 "VALUES (%s,%s,'phase.pdf','application/pdf')", (identifier, FILE_BYTES))
    conn.execute("SET CONSTRAINTS ALL IMMEDIATE")
    return str(identifier)


def action(conn, fixture, case, side):
    require(case in CASES and side in ("A", "B"), "UNKNOWN_VOTE_ACTION")
    first, users = side == "A", fixture.users
    project, submission = fixture.projects["main"], fixture.submissions["main"]
    if case in ("VC01", "VC02", "VC03") and not first:
        operation = {"VC01": "add", "VC02": "replace", "VC03": "remove"}[case]
        kwargs = {} if operation == "remove" else {"advisor": users["spare"]}
        if operation != "add":
            kwargs["assignment"] = fixture.assignments["main"]["c"]
        result = committee_call(conn, fixture, operation, **kwargs)
        count = conn.execute("SELECT count(*) FROM public.committee_assignments WHERE project_id=%s", (project,)).fetchone()[0]
        require(count == {"add": 4, "replace": 3, "remove": 2}[operation], "VOTE_ROSTER_RESULT")
        require((result is None) if operation == "remove" else result["advisor"]["id"] == users["spare"], "VOTE_ROSTER_TARGET")
    elif case == "VC04" and first:
        committee_call(conn, fixture, "remove", assignment=fixture.assignments["main"]["b"])
    elif case == "VC07":
        if first:
            require(new_round(conn, fixture) != fixture.submissions["revision"], "VOTE_NEW_ROUND_MISSING")
        else:
            context = vote_call(conn, "team_context", users["leader_revision"])
            require(len(context["rounds"]) == 1 and context["rounds"][0]["submission"]["id"] == fixture.submissions["revision"],
                    "VOTE_READER_SAW_UNCOMMITTED_ROUND")
            require(context["rounds"][0]["decision"] == "revision_requested" and
                    context["rounds"][0]["comments"] == [REVISION_COMMENT] * 3, "VOTE_READER_BASELINE_RESULT")
    elif case == "VC08" and first:
        context = vote_call(conn, "team_context", users["leader_main"])
        require(context["rounds"][0]["decision"] is None and context["rounds"][0]["comments"] == [], "VOTE_READER_PRIVACY")
    else:
        member = "c" if case == "VC06" and not first else "b"
        result = vote_call(conn, "cast", users[member], project, submission, "approved", "Concurrency approved fixture")
        require(result["submission_id"] == submission and result["vote"] == "approved", "VOTE_CAST_RESULT")
        rows = conn.execute("SELECT committee_assignment_id FROM public.committee_topic_votes WHERE submission_id=%s", (submission,)).fetchall()
        require(rows == [(int(fixture.assignments["main"][member]),)], "VOTE_NOT_EXACTLY_ONE_OWN_ROW")
        context = vote_call(conn, "committee_context", users[member], project)
        require(context["rounds"][0]["own_vote"] == result and context["rounds"][0]["decision"] is None, "VOTE_OWN_RESULT")
    conn.execute("SET CONSTRAINTS ALL IMMEDIATE")


def worker(fixture, case, ready, done):
    try:
        with rollback_connection() as conn:
            validate_fixture(conn, fixture)
            ready.put((conn, conn.execute("SELECT pg_backend_pid()").fetchone()[0]))
            action(conn, fixture, case, "B")
        done.put({"ok": True, "sqlstate": None})
    except Exception as exc:
        done.put(diagnostic(exc))


def run_case(fixture, case):
    require(case in CASES, "UNKNOWN_VOTE_ACTION")
    ready, done = Queue(), Queue()
    thread, worker_conn, failure = None, None, None
    with rollback_connection(readonly=True) as observer:
        validate_fixture(observer, fixture)
        before = fingerprint(observer)
        try:
            with rollback_connection() as first:
                validate_fixture(first, fixture)
                first_pid = first.execute("SELECT pg_backend_pid()").fetchone()[0]
                observer_pid = observer.execute("SELECT pg_backend_pid()").fetchone()[0]
                action(first, fixture, case, "A")
                thread = Thread(target=worker, args=(fixture, case, ready, done), daemon=True)
                thread.start()
                try:
                    worker_conn, worker_pid = ready.get(timeout=10)
                except Empty:
                    diagnostic = done.get_nowait() if not done.empty() else {}
                    raise CheckFailed("VOTE_WORKER_NOT_READY", diagnostic.get("sqlstate")) from None
                require(len({first_pid, worker_pid, observer_pid}) == 3, "SESSIONS_NOT_DISTINCT")
                wait_for_block(observer, first_pid, worker_pid)
            # A must ROLLBACK before B is awaited; its changes never persist.
        except Exception as exc:
            failure = exc
        finally:
            if thread is not None:
                finish_worker(thread, worker_conn)
        require(fingerprint(observer) == before, "BASELINE_NOT_RESTORED")
        if failure is not None:
            raise failure
        try:
            outcome = done.get_nowait()
        except Empty:
            raise CheckFailed("VOTE_WORKER_RESULT_MISSING") from None
        if outcome != {"ok": True, "sqlstate": None}:
            raise CheckFailed("VOTE_UNEXPECTED_WORKER_RESULT", outcome.get("sqlstate"))
        return {"case": case, "result": "PASS", "wait_observed": True,
                "both_workers_rolled_back": True, "public_rows_metadata_restored": True}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fixture", type=Path)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--preflight", action="store_true")
    mode.add_argument("--run-rollback", action="store_true")
    args = parser.parse_args(argv)
    try:
        if not (args.preflight or args.run_rollback):
            print(json.dumps({"mode": "OFFLINE_PLAN", "database_connected": False, "cases": CASES,
                              "winner_commit_cases": "NOT_IMPLEMENTED_NOT_AUTHORIZED"}))
            return 0
        require(args.fixture is not None, "EXPLICIT_MANIFEST_REQUIRED")
        fixture = VoteFixture.load(args.fixture)
        with rollback_connection(readonly=True) as conn:
            validate_fixture(conn, fixture)
        print(json.dumps({"preflight": "PASS", "database": TEST_DB, "role": APP_ROLE,
                          "readonly": True, "shared_fixture_created": False}))
        if args.run_rollback:
            for case in CASES:
                print(json.dumps(run_case(fixture, case)))
        return 0
    except Exception as exc:
        print(json.dumps({"result": "FAIL", **diagnostic(exc)}))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
