"""Evaluation two-session harness. Default is OFFLINE; never seed or COMMIT.

An explicitly installed dedicated fixture must be visible to both workers.
All worker actions ROLLBACK. No HTTP, owner fallback or winner-COMMIT mode.
"""

import argparse
from dataclasses import asdict, dataclass
import json
from pathlib import Path
from queue import Empty, Queue
import re
from threading import Thread
from types import SimpleNamespace

from backend.auth_store import APP_ROLE, TEST_DB, assert_auth_connection
from backend.tests.team_project_concurrency import (
    CheckFailed, fingerprint, finish_worker, positive_id, require, rollback_connection, wait_for_block,
)
from backend.tests.topic_vote_concurrency import diagnostic
from database.tools.Evaluation_Concurrency_Rehearsal import CASES, COMMENT, action as rehearsal_action


USER_ROLES = {"leader_main": "student", "leader_final": "student", "advisor": "advisor",
              "b": "advisor", "c": "advisor", "d": "advisor", "coordinator": "coordinator"}
PROJECTS = ("main", "final")
WORK = ("main", "editable", "final")
MEMBERS = ("b", "c", "d")
FILE_BYTES = b"DB-only Evaluation concurrency phase fixture"
COUNTS = {"public.users": 7, "public.teams": 2, "public.team_members": 2, "public.projects": 2,
          "public.advisor_invitations": 2, "public.project_submissions": 2, "public.project_submission_files": 2,
          "public.committee_assignments": 6, "public.committee_topic_votes": 6, "public.milestones": 3,
          "public.tasks": 3, "public.task_assignees": 3, "public.committee_evaluations": 2}


@dataclass(frozen=True)
class EvaluationFixture:
    namespace: str
    users: dict
    teams: dict
    projects: dict
    submissions: dict
    assignments: dict
    work: dict

    def payload(self):
        return {"version": 1, "database": TEST_DB, **asdict(self)}

    @classmethod
    def parse(cls, data):
        require(isinstance(data, dict) and set(data) == {
            "version", "database", "namespace", "users", "teams", "projects", "submissions", "assignments", "work"},
            "EVALUATION_MANIFEST_SHAPE")
        require(type(data["version"]) is int and data["version"] == 1, "EVALUATION_MANIFEST_VERSION")
        require(data["database"] == TEST_DB, "EVALUATION_MANIFEST_DATABASE")
        require(isinstance(data["namespace"], str) and re.fullmatch(r"spms-ec-[0-9a-f]{32}", data["namespace"]),
                "EVALUATION_MANIFEST_NAMESPACE")
        for field, keys in (("users", USER_ROLES), ("teams", PROJECTS), ("projects", PROJECTS), ("submissions", PROJECTS)):
            values = data[field]
            require(isinstance(values, dict) and set(values) == set(keys), "EVALUATION_MANIFEST_KEYS")
            require(all(positive_id(v) for v in values.values()), "EVALUATION_MANIFEST_IDS")
            require(len(set(values.values())) == len(values), "EVALUATION_MANIFEST_DUPLICATES")
        assignments, work = data["assignments"], data["work"]
        require(isinstance(assignments, dict) and set(assignments) == set(PROJECTS), "EVALUATION_MANIFEST_KEYS")
        require(isinstance(work, dict) and set(work) == set(WORK), "EVALUATION_MANIFEST_KEYS")
        for values in assignments.values():
            require(isinstance(values, dict) and set(values) == set(MEMBERS), "EVALUATION_MANIFEST_KEYS")
            require(all(positive_id(v) for v in values.values()), "EVALUATION_MANIFEST_IDS")
        require(len({v for values in assignments.values() for v in values.values()}) == 6, "EVALUATION_MANIFEST_DUPLICATES")
        for values in work.values():
            require(isinstance(values, dict) and set(values) == {"milestone", "task", "member"}, "EVALUATION_MANIFEST_KEYS")
            require(all(positive_id(v) for v in values.values()), "EVALUATION_MANIFEST_IDS")
        for key in ("milestone", "task"):
            require(len({v[key] for v in work.values()}) == 3, "EVALUATION_MANIFEST_DUPLICATES")
        require(work["main"]["member"] == work["editable"]["member"] != work["final"]["member"],
                "EVALUATION_MANIFEST_MEMBERS")
        return cls(data["namespace"], *(dict(data[k]) for k in ("users", "teams", "projects", "submissions")),
                   {k: dict(v) for k, v in assignments.items()}, {k: dict(v) for k, v in work.items()})

    @classmethod
    def load(cls, path):
        try:
            require(Path(path).stat().st_size <= 8192, "EVALUATION_MANIFEST_TOO_LARGE")
            return cls.parse(json.loads(Path(path).read_text(encoding="utf-8-sig")))
        except (OSError, ValueError):
            raise CheckFailed("EVALUATION_MANIFEST_READ") from None


def validate_fixture(conn, fixture):
    """SELECT-only exact dedicated graph; never discover arbitrary real projects."""
    assert_auth_connection(conn)
    ns, users = fixture.namespace, fixture.users
    for label, role in USER_ROLES.items():
        require(conn.execute("SELECT full_name,email,role FROM public.users WHERE id=%s", (users[label],)).fetchone() ==
                ("Evaluation concurrency " + label, f"{ns}.{label}@example.test", role), "EVALUATION_FIXTURE_USER")
    members = conn.execute("SELECT id,team_id,user_id,role FROM public.team_members WHERE team_id=ANY(%s) OR user_id=ANY(%s)",
                           ([int(v) for v in fixture.teams.values()], [int(v) for v in users.values()])).fetchall()
    require(len(members) == 2 and set(members) == {
        (int(fixture.work[label]["member"]), int(fixture.teams[label]), int(users["leader_" + label]), "leader")
        for label in PROJECTS}, "EVALUATION_FIXTURE_MEMBERSHIP")
    state = {}
    for label in PROJECTS:
        project, leader, submission = fixture.projects[label], users["leader_" + label], fixture.submissions[label]
        require(conn.execute("SELECT name FROM public.teams WHERE id=%s", (fixture.teams[label],)).fetchone() ==
                (f"{ns}.{label}",), "EVALUATION_FIXTURE_TEAM")
        require(conn.execute("SELECT id,created_by,name,description FROM public.projects WHERE team_id=%s", (fixture.teams[label],)).fetchall() ==
                [(int(project), int(leader), f"{ns}.{label}.project", None)], "EVALUATION_FIXTURE_PROJECT")
        require(conn.execute("SELECT advisor_id,sent_by,status FROM public.advisor_invitations WHERE project_id=%s", (project,)).fetchall() ==
                [(int(users["advisor"]), int(leader), "accepted")], "EVALUATION_FIXTURE_INVITATION")
        require(conn.execute("SELECT id,submitted_by,status,snapshot_name,snapshot_description FROM public.project_submissions WHERE project_id=%s",
                             (project,)).fetchall() == [(int(submission), int(leader), "approved", f"{ns}.{label}.project", None)],
                "EVALUATION_FIXTURE_SUBMISSION")
        require(conn.execute("SELECT file_data,original_filename,mime_type FROM public.project_submission_files WHERE submission_id=%s", (submission,)).fetchall() ==
                [(FILE_BYTES, "phase.pdf", "application/pdf")], "EVALUATION_FIXTURE_FILE")
        assignments = conn.execute("SELECT id,advisor_id,assigned_by FROM public.committee_assignments WHERE project_id=%s", (project,)).fetchall()
        require(len(assignments) == 3 and set(assignments) == {
            (int(fixture.assignments[label][k]), int(users[k]), int(users["coordinator"])) for k in MEMBERS}, "EVALUATION_FIXTURE_ASSIGNMENTS")
        votes = conn.execute("SELECT submission_id,committee_assignment_id,vote,comment FROM public.committee_topic_votes "
                             "WHERE submission_id=%s OR committee_assignment_id=ANY(%s)",
                             (submission, [int(v) for v in fixture.assignments[label].values()])).fetchall()
        require(len(votes) == 3 and set(votes) == {(int(submission), int(v), "approved", COMMENT)
                                                  for v in fixture.assignments[label].values()}, "EVALUATION_FIXTURE_VOTES")
        require(conn.execute("SELECT public.v1_topic_decision(%s)", (submission,)).fetchone() == ("approved",), "EVALUATION_FIXTURE_DECISION")
        evaluations = conn.execute("SELECT committee_assignment_id,score,comment FROM public.committee_evaluations "
                                   "WHERE committee_assignment_id=ANY(%s)", ([int(v) for v in fixture.assignments[label].values()],)).fetchall()
        expected = {(int(fixture.assignments[label][k]), score, COMMENT) for k, score in (("b", 60), ("c", 70))} if label == "final" else set()
        require(len(evaluations) == len(expected) and set(evaluations) == expected, "EVALUATION_FIXTURE_SCORES")
        labels = ("main", "editable") if label == "main" else ("final",)
        milestones = conn.execute("SELECT id,name,description,status,created_by,due_date FROM public.milestones WHERE project_id=%s", (project,)).fetchall()
        require(len(milestones) == len(labels), "EVALUATION_FIXTURE_MILESTONES")
        for work_label in labels:
            work = fixture.work[work_label]
            rows = [r for r in milestones if r[0] == int(work["milestone"])]
            require(len(rows) == 1, "EVALUATION_FIXTURE_WORK")
            row = rows[0]
            status = "not_started" if work_label == "editable" else "completed"
            require(row[1:5] == (f"{ns}.{work_label}.milestone", None, status, int(leader)), "EVALUATION_FIXTURE_WORK")
            require(conn.execute("SELECT id,name,description,status,created_by,due_date FROM public.tasks WHERE milestone_id=%s", (work["milestone"],)).fetchall() ==
                    [(int(work["task"]), f"{ns}.{work_label}.task", None, status, int(leader), row[5])], "EVALUATION_FIXTURE_TASK")
            require(conn.execute("SELECT team_member_id FROM public.task_assignees WHERE task_id=%s", (work["task"],)).fetchall() ==
                    [(int(work["member"]),)], "EVALUATION_FIXTURE_ASSIGNEE")
            state[work_label] = row[5]
    require(not conn.execute("SELECT EXISTS(SELECT 1 FROM public.task_assignment_history WHERE user_id=ANY(%s))",
                             ([int(v) for v in users.values()],)).fetchone()[0], "EVALUATION_FIXTURE_HISTORY")
    require(len(set(state.values())) == 1, "EVALUATION_FIXTURE_DUE_DATES")
    return state


def case_state(fixture, dates, case):
    require(case in CASES, "UNKNOWN_EVALUATION_ACTION")
    label = "final" if case in ("EC07", "EC08") else "main"
    users = {**fixture.users, "leader_main": fixture.users["leader_" + label]}
    return {"base": SimpleNamespace(users=users, projects={"main": fixture.projects[label]}),
            "milestone": fixture.work[label]["milestone"], "task": fixture.work[label]["task"],
            "editable_task": fixture.work["editable"]["task"], "member": fixture.work[label]["member"], "due": dates[label]}


def action(conn, fixture, dates, case, side):
    require(case in CASES and side in ("A", "B"), "UNKNOWN_EVALUATION_ACTION")
    rehearsal_action(conn, case_state(fixture, dates, case), case, side)
    if side == "B" and case in ("EC04", "EC05", "EC06"):
        label = "c" if case == "EC06" else "b"
        rows = conn.execute("SELECT committee_assignment_id,score FROM public.committee_evaluations WHERE committee_assignment_id=ANY(%s)",
                            ([int(v) for v in fixture.assignments["main"].values()],)).fetchall()
        require(rows == [(int(fixture.assignments["main"][label]), 90)], "EVALUATION_ROLLED_BACK_SCORE_VISIBLE")


def worker(fixture, dates, case, ready, done):
    try:
        with rollback_connection() as conn:
            require(validate_fixture(conn, fixture) == dates, "EVALUATION_FIXTURE_CHANGED")
            ready.put((conn, conn.execute("SELECT pg_backend_pid()").fetchone()[0]))
            action(conn, fixture, dates, case, "B")
        done.put({"ok": True, "sqlstate": None})
    except Exception as exc:
        done.put(diagnostic(exc))


def run_case(fixture, case):
    require(case in CASES, "UNKNOWN_EVALUATION_ACTION")
    ready, done = Queue(), Queue()
    thread, worker_conn, failure = None, None, None
    with rollback_connection(readonly=True) as observer:
        dates = validate_fixture(observer, fixture)
        before = fingerprint(observer)
        try:
            with rollback_connection() as first:
                require(validate_fixture(first, fixture) == dates, "EVALUATION_FIXTURE_CHANGED")
                first_pid = first.execute("SELECT pg_backend_pid()").fetchone()[0]
                observer_pid = observer.execute("SELECT pg_backend_pid()").fetchone()[0]
                action(first, fixture, dates, case, "A")
                thread = Thread(target=worker, args=(fixture, dates, case, ready, done), daemon=True)
                thread.start()
                try:
                    worker_conn, worker_pid = ready.get(timeout=10)
                except Empty:
                    outcome = done.get_nowait() if not done.empty() else {}
                    raise CheckFailed("EVALUATION_WORKER_NOT_READY", outcome.get("sqlstate")) from None
                require(len({first_pid, worker_pid, observer_pid}) == 3, "SESSIONS_NOT_DISTINCT")
                wait_for_block(observer, first_pid, worker_pid)
            # A is rolled back before B is awaited; both leave baseline intact.
        except Exception as exc:
            failure = exc
        finally:
            if thread is not None:
                finish_worker(thread, worker_conn)
        require(fingerprint(observer) == before, "BASELINE_NOT_RESTORED")
        validate_fixture(observer, fixture)
        if failure is not None:
            raise failure
        try:
            outcome = done.get_nowait()
        except Empty:
            raise CheckFailed("EVALUATION_WORKER_RESULT_MISSING") from None
        if outcome != {"ok": True, "sqlstate": None}:
            raise CheckFailed("EVALUATION_UNEXPECTED_WORKER_RESULT", outcome.get("sqlstate"))
    return {"case": case, "result": "PASS", "wait_observed": True, "both_workers_rolled_back": True,
            "public_rows_metadata_restored": True, "direct_app_login": True, "http_tested": False}


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
                              "fixture_rows_total": sum(COUNTS.values()), "winner_commit_available": False}))
            return 0
        require(args.fixture is not None, "EXPLICIT_MANIFEST_REQUIRED")
        fixture = EvaluationFixture.load(args.fixture)
        with rollback_connection(readonly=True) as conn:
            validate_fixture(conn, fixture)
        print(json.dumps({"preflight": "PASS", "database": TEST_DB, "role": APP_ROLE, "readonly": True}))
        if args.run_rollback:
            for case in CASES:
                print(json.dumps(run_case(fixture, case)))
        return 0
    except Exception as exc:
        print(json.dumps({"result": "FAIL", **diagnostic(exc)}))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
