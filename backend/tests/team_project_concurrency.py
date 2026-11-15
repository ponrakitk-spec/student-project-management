"""Prepared two-session repository tests. Default invocation is OFFLINE.

--run-rollback requires an explicitly supplied, dedicated, already-visible
fixture manifest. This tool never creates/commits shared fixtures. All worker
transactions are forced to ROLLBACK, including success and timeout paths.
These cases exercise winner-ROLLBACK, not winner-COMMIT or HTTP concurrency.
"""

from contextlib import contextmanager
from dataclasses import dataclass
import argparse
import hashlib
import json
from pathlib import Path
from queue import Empty, Queue
import re
from threading import Thread
import time

import psycopg
from psycopg import sql

from backend.auth_store import APP_ROLE, TEST_DB, assert_auth_connection, open_auth_connection
from backend.project_store import project_transaction_on
from backend.team_store import team_transaction_on

TABLES = (
    "users", "teams", "team_members", "projects", "advisor_invitations",
    "project_submissions", "project_submission_files", "committee_assignments",
    "committee_topic_votes", "committee_evaluations", "milestones", "tasks",
    "task_assignees", "task_assignment_history",
)
CASES = {
    "RC01": "Uncommitted leader transfer blocks old leader's Team update; rollback restores authority",
    "RC02": "Uncommitted removal blocks the same member's leave; rollback restores membership",
    "RC03": "Project partial update waits and preserves the baseline omitted field after rollback",
    "RC04": "Duplicate Project creation waits; second create succeeds after first rollback",
    "RC05": "Two teams add the same student; UNIQUE conflict waits until first rollback",
    "RC06": "55P03 lock timeout rolls back an earlier write in the same worker transaction",
}


class CheckFailed(Exception):
    """Only fixed, non-sensitive reason codes may be exposed by the CLI."""

    def __init__(self, code, sqlstate=None):
        super().__init__(code)
        self.sqlstate = sqlstate


def require(condition, code):
    if not condition:
        raise CheckFailed(code)


def positive_id(value):
    return (isinstance(value, str) and re.fullmatch(r"[1-9][0-9]{0,18}", value)
            and int(value) <= 9223372036854775807)


@dataclass(frozen=True)
class Fixture:
    namespace: str
    users: dict
    teams: dict
    project_id: str

    @classmethod
    def parse(cls, data):
        require(isinstance(data, dict) and set(data) == {
            "version", "database", "namespace", "users", "teams", "project_id"}, "MANIFEST_SHAPE")
        require(type(data["version"]) is int and data["version"] == 1, "MANIFEST_VERSION")
        require(data["database"] == TEST_DB, "MANIFEST_DATABASE")
        namespace = data["namespace"]
        require(isinstance(namespace, str) and re.fullmatch(r"spms-ct-[0-9a-f]{32}", namespace),
                "MANIFEST_NAMESPACE")
        users, teams = data["users"], data["teams"]
        require(isinstance(users, dict) and set(users) == {
            "leader_a", "member_b", "leader_c", "free_student"}, "MANIFEST_USERS")
        require(isinstance(teams, dict) and set(teams) == {"main", "empty"}, "MANIFEST_TEAMS")
        require(all(positive_id(v) for v in [*users.values(), *teams.values(), data["project_id"]]),
                "MANIFEST_IDS")
        require(len(set(users.values())) == 4 and len(set(teams.values())) == 2, "MANIFEST_DUPLICATE_IDS")
        return cls(namespace, dict(users), dict(teams), data["project_id"])

    @classmethod
    def load(cls, path):
        # No fallback to environment IDs, arbitrary SQL, or auto-selected rows.
        try:
            require(Path(path).stat().st_size <= 4096, "MANIFEST_TOO_LARGE")
            return cls.parse(json.loads(Path(path).read_text(encoding="utf-8-sig")))
        except (OSError, ValueError):
            raise CheckFailed("MANIFEST_READ") from None


@contextmanager
def rollback_connection(*, readonly=False, lock_ms=5000, connector=None):
    conn = (connector or open_auth_connection)()
    try:
        require(not conn.autocommit and conn.info.transaction_status == psycopg.pq.TransactionStatus.IDLE,
                "CONNECTION_NOT_IDLE")
        with conn.transaction(force_rollback=True):
            conn.execute("SET TRANSACTION ISOLATION LEVEL READ COMMITTED " +
                         ("READ ONLY" if readonly else "READ WRITE"))
            assert_auth_connection(conn)
            require(conn.execute("SELECT session_user,current_setting('transaction_isolation'),"
                                 "current_setting('transaction_read_only')").fetchone() ==
                    (APP_ROLE, "read committed", "on" if readonly else "off"), "CONNECTION_IDENTITY")
            conn.execute("SELECT set_config('lock_timeout',%s,true)", (f"{lock_ms}ms",))
            conn.execute("SELECT set_config('statement_timeout','10000ms',true)")
            yield conn
    finally:
        try:
            conn.rollback()
        finally:
            conn.close()


def validate_fixture(conn, fixture):
    """Read-only validation: dedicated namespace, exact roster, no phase children."""
    assert_auth_connection(conn)
    users, teams, ns = fixture.users, fixture.teams, fixture.namespace
    for label, user in users.items():
        require(conn.execute("SELECT email,role FROM public.users WHERE id=%s", (user,)).fetchone() ==
                (f"{ns}.{label}@example.test", "student"), "FIXTURE_USER_MISMATCH")
    for label, team in teams.items():
        require(conn.execute("SELECT name FROM public.teams WHERE id=%s", (team,)).fetchone() ==
                (f"{ns}.{label}",), "FIXTURE_TEAM_MISMATCH")
    expected = {(int(teams["main"]), int(users["leader_a"]), "leader"),
                (int(teams["main"]), int(users["member_b"]), "member"),
                (int(teams["empty"]), int(users["leader_c"]), "leader")}
    members = conn.execute("""SELECT team_id,user_id,role FROM public.team_members
        WHERE team_id=ANY(%s) OR user_id=ANY(%s)""",
        ([int(v) for v in teams.values()], [int(v) for v in users.values()])).fetchall()
    require(set(members) == expected and len(members) == 3, "FIXTURE_ROSTER_MISMATCH")
    project = conn.execute("SELECT id,team_id,created_by,name,description FROM public.projects "
                           "WHERE team_id=ANY(%s)", ([int(v) for v in teams.values()],)).fetchall()
    require(len(project) == 1 and project[0][:4] ==
            (int(fixture.project_id), int(teams["main"]), int(users["leader_a"]), f"{ns}.project"),
            "FIXTURE_PROJECT_MISMATCH")
    for table in ("advisor_invitations", "project_submissions", "committee_assignments", "milestones"):
        require(not conn.execute(sql.SQL("SELECT EXISTS(SELECT 1 FROM public.{} WHERE project_id=%s)")
                                 .format(sql.Identifier(table)), (fixture.project_id,)).fetchone()[0],
                "FIXTURE_HAS_WORKFLOW_CHILDREN")
    require(not conn.execute("SELECT EXISTS(SELECT 1 FROM public.task_assignment_history "
                             "WHERE user_id=ANY(%s))", ([int(v) for v in users.values()],)).fetchone()[0],
            "FIXTURE_HAS_HISTORY")
    target = conn.execute("SELECT id FROM public.team_members WHERE user_id=%s",
                          (users["member_b"],)).fetchone()[0]
    return {"member_id": str(target), "project_description": project[0][4]}


def fingerprint(conn):
    """Hash full public row values and public/auth metadata; never print values.

    Auth credential/session row values and identity sequence state are excluded.
    The runner never invokes Auth operations. Run on a quiet local test DB.
    """
    digest = hashlib.sha256()
    for table in TABLES:
        rows = conn.execute(sql.SQL("SELECT to_jsonb(t) FROM public.{} t ORDER BY id")
                            .format(sql.Identifier(table))).fetchall()
        digest.update(json.dumps([table, rows], default=str, sort_keys=True).encode())
    queries = (
        """SELECT nspname,pg_get_userbyid(nspowner),nspacl::text FROM pg_namespace
            WHERE nspname IN ('public','auth') ORDER BY 1""",
        """SELECT n.nspname,c.relname,c.relkind,pg_get_userbyid(c.relowner),c.relacl::text
            FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace
            WHERE n.nspname IN ('public','auth') ORDER BY 1,2""",
        """SELECT p.oid::regprocedure::text,pg_get_userbyid(p.proowner),p.proacl::text,
            pg_get_functiondef(p.oid) FROM pg_proc p JOIN pg_namespace n ON n.oid=p.pronamespace
            WHERE n.nspname IN ('public','auth') AND p.prokind='f' ORDER BY 1""",
        """SELECT n.nspname,c.relname,x.conname,pg_get_constraintdef(x.oid)
            FROM pg_constraint x JOIN pg_class c ON c.oid=x.conrelid
            JOIN pg_namespace n ON n.oid=c.relnamespace
            WHERE n.nspname IN ('public','auth') ORDER BY 1,2,3""",
        """SELECT n.nspname,c.relname,a.attnum,a.attname,format_type(a.atttypid,a.atttypmod),
            a.attnotnull,a.attacl::text,pg_get_expr(d.adbin,d.adrelid)
            FROM pg_attribute a JOIN pg_class c ON c.oid=a.attrelid
            JOIN pg_namespace n ON n.oid=c.relnamespace
            LEFT JOIN pg_attrdef d ON d.adrelid=a.attrelid AND d.adnum=a.attnum
            WHERE n.nspname IN ('public','auth') AND c.relkind='r'
            AND a.attnum>0 AND NOT a.attisdropped ORDER BY 1,2,3""",
        """SELECT n.nspname,c.relname,t.tgname,pg_get_triggerdef(t.oid),t.tgenabled
            FROM pg_trigger t JOIN pg_class c ON c.oid=t.tgrelid
            JOIN pg_namespace n ON n.oid=c.relnamespace
            WHERE n.nspname IN ('public','auth') ORDER BY 1,2,3""",
        """SELECT rolname,rolsuper,rolcreatedb,rolcreaterole,rolbypassrls,rolcanlogin
            FROM pg_roles WHERE rolname IN ('project_owner','project_app') ORDER BY 1""",
        "SELECT datacl::text FROM pg_database WHERE datname=current_database()",
    )
    for query in queries:
        digest.update(json.dumps(conn.execute(query).fetchall(), default=str).encode())
    return digest.hexdigest()


def team_call(conn, method, *args):
    with team_transaction_on(conn) as repository:
        return getattr(repository, method)(*args)


def project_call(conn, method, *args):
    with project_transaction_on(conn) as repository:
        return getattr(repository, method)(*args)


def action(conn, fixture, state, case, side):
    """Use existing repository transactions/controlled SQL; no grants or raw DML."""
    users, ns = fixture.users, fixture.namespace
    first = side == "A"
    if case == "RC01":
        if first:
            result = team_call(conn, "transfer_leader", users["leader_a"], state["member_id"])
            require(result["membership"]["role"] == "member", "TRANSFER_DID_NOT_CHANGE_ROLE")
        else:
            result = team_call(conn, "update", users["leader_a"], {"name": f"{ns}.worker"})
            require(result["membership"]["role"] == "leader", "AUTHORITY_NOT_RESTORED")
    elif case == "RC02":
        team_call(conn, "exit_member", users["leader_a"] if first else users["member_b"],
                  state["member_id"] if first else None)
        require(conn.execute("SELECT count(*) FROM public.team_members WHERE id=%s",
                             (state["member_id"],)).fetchone() == (0,), "MEMBER_NOT_REMOVED")
    elif case == "RC03":
        result = project_call(conn, "update", users["leader_a"],
                              {"description": f"{ns}.uncommitted"} if first else {"name": f"{ns}.worker"})
        if first:
            require(result["description"] == f"{ns}.uncommitted", "FIRST_UPDATE_DID_NOT_CHANGE_FIELD")
        else:
            require(result["name"] == f"{ns}.worker" and
                    result["description"] == state["project_description"], "OMITTED_FIELD_NOT_RESTORED")
    elif case == "RC04":
        result = project_call(conn, "create", f"{ns}.{side}", None, users["leader_c"])
        require(result["team_id"] == fixture.teams["empty"] and result["created_by"] == users["leader_c"]
                and result["name"] == f"{ns}.{side}", "WRONG_PROJECT_TEAM")
    elif case == "RC05":
        result = team_call(conn, "add_member", users["leader_a"] if first else users["leader_c"],
                           f"{ns}.free_student@example.test")
        require(result["user_id"] == users["free_student"], "WRONG_ADDED_MEMBER")
        require(conn.execute("SELECT team_id FROM public.team_members WHERE user_id=%s",
                             (users["free_student"],)).fetchone() ==
                (int(fixture.teams["main" if first else "empty"]),), "WRONG_MEMBER_TEAM")
    elif case == "RC06":
        result = team_call(conn, "update", users["leader_a"] if first else users["leader_c"],
                           {"name": f"{ns}.{side}"})
        require(result["name"] == f"{ns}.{side}", "TIMEOUT_CASE_EARLIER_WRITE_MISSING")
        if not first:
            # An earlier legitimate write exists in B. Raw lock helper retains
            # 55P03 for this harness; HTTP/UOW sanitization is tested elsewhere.
            conn.execute("SELECT public.v1_lock_team(%s)", (fixture.teams["main"],))
    else:
        raise CheckFailed("UNKNOWN_CASE")
    conn.execute("SET CONSTRAINTS ALL IMMEDIATE")


def wait_for_block(observer, blocker, blocked, *, timeout=2.0):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        pids = observer.execute("SELECT pg_blocking_pids(%s)", (blocked,)).fetchone()[0]
        if blocker in pids:
            return
        time.sleep(0.02)
    raise CheckFailed("EXPECTED_DATABASE_BLOCK_NOT_OBSERVED")


def sanitized_failure(exc):
    # No exception message/traceback, query, DSN, fixture ID or account data.
    state = getattr(exc, "sqlstate", None)
    if not isinstance(state, str) or not re.fullmatch(r"[0-9A-Z]{5}", state):
        state = None
    return {"ok": False, "sqlstate": state, "reason":
            exc.args[0] if isinstance(exc, CheckFailed) else "WORKER_FAILED"}


def worker(fixture, case, state, ready, done):
    try:
        with rollback_connection(lock_ms=1500 if case == "RC06" else 5000) as conn:
            require(validate_fixture(conn, fixture) == state, "WORKER_BASELINE_CHANGED")
            ready.put((conn, conn.execute("SELECT pg_backend_pid()").fetchone()[0]))
            action(conn, fixture, state, case, "B")
        done.put({"ok": True, "sqlstate": None})
    except Exception as exc:
        done.put(sanitized_failure(exc))


def finish_worker(thread, conn):
    thread.join(timeout=3)
    if thread.is_alive() and conn is not None:
        try:
            conn.cancel()
        except psycopg.Error:
            pass
    thread.join(timeout=12)  # statement_timeout also bounds the worker query.
    require(not thread.is_alive(), "WORKER_DID_NOT_STOP")


def run_case(fixture, case):
    ready, done = Queue(), Queue()
    thread = None
    worker_conn = None
    outcome = None
    failure = None
    with rollback_connection(readonly=True) as observer:
        state = validate_fixture(observer, fixture)
        before = fingerprint(observer)
        try:
            with rollback_connection() as first:
                require(validate_fixture(first, fixture) == state, "FIXTURE_CHANGED")
                first_pid = first.execute("SELECT pg_backend_pid()").fetchone()[0]
                observer_pid = observer.execute("SELECT pg_backend_pid()").fetchone()[0]
                action(first, fixture, state, case, "A")
                thread = Thread(target=worker, args=(fixture, case, state, ready, done), daemon=True)
                thread.start()
                try:
                    worker_conn, worker_pid = ready.get(timeout=10)
                except Empty:
                    diagnostic = done.get_nowait() if not done.empty() else {}
                    raise CheckFailed("WORKER_NOT_READY", diagnostic.get("sqlstate")) from None
                require(len({first_pid, worker_pid, observer_pid}) == 3, "SESSIONS_NOT_DISTINCT")
                wait_for_block(observer, first_pid, worker_pid)
                if case == "RC06":
                    try:
                        outcome = done.get(timeout=5)
                    except Empty:
                        raise CheckFailed("LOCK_TIMEOUT_NOT_RETURNED") from None
            # A has now ROLLBACKed, so B can continue on the committed baseline.
        except Exception as exc:
            failure = exc
        finally:
            if thread is not None:
                finish_worker(thread, worker_conn)
        require(fingerprint(observer) == before, "BASELINE_NOT_RESTORED")
        if failure is not None:
            raise failure
        if outcome is None:
            try:
                outcome = done.get_nowait()
            except Empty:
                raise CheckFailed("WORKER_RESULT_MISSING") from None
        expected = ({"ok": False, "sqlstate": "55P03", "reason": "WORKER_FAILED"}
                    if case == "RC06" else {"ok": True, "sqlstate": None})
        if outcome != expected:
            raise CheckFailed("UNEXPECTED_WORKER_RESULT", outcome.get("sqlstate"))
        return {"case": case, "result": "PASS", "wait_observed": True,
                "both_workers_rolled_back": True, "public_rows_metadata_restored": True,
                "sqlstate": outcome["sqlstate"]}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fixture", type=Path)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--preflight", action="store_true", help="Read-only manifest/DB validation")
    mode.add_argument("--run-rollback", action="store_true", help="Execute prepared rollback-only cases")
    args = parser.parse_args(argv)
    try:
        if not (args.preflight or args.run_rollback):
            print(json.dumps({"mode": "OFFLINE_PLAN", "database_connected": False,
                              "cases": CASES, "winner_commit_cases": "NOT_IMPLEMENTED_NOT_AUTHORIZED"}))
            return 0
        require(args.fixture is not None, "EXPLICIT_MANIFEST_REQUIRED")
        fixture = Fixture.load(args.fixture)
        with rollback_connection(readonly=True) as conn:
            validate_fixture(conn, fixture)
        print(json.dumps({"preflight": "PASS", "database": TEST_DB, "role": APP_ROLE,
                          "readonly": True, "shared_fixture_created": False}))
        if args.run_rollback:
            for case in CASES:
                print(json.dumps(run_case(fixture, case)))
        return 0
    except Exception as exc:
        print(json.dumps({"result": "FAIL", **sanitized_failure(exc)}))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
