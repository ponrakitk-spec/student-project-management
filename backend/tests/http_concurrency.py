"""Real loopback HTTP requests waiting on a concurrent repository transaction.

Default is OFFLINE. Explicit manifests identify the existing dedicated fixtures.
A and observer authenticate directly as app. B prepares ONE temporary credential
as non-superuser owner, then serves every HTTP request as effective project_app.
Real Login/session/CSRF and real TCP are used; all writes always ROLLBACK.
This is repository A versus HTTP B, not two HTTP clients or winner-COMMIT.
"""

import argparse
from contextlib import contextmanager
from dataclasses import dataclass
from functools import lru_cache
import json
from pathlib import Path
from queue import Empty, Queue
import socket
from threading import Thread
import time

import httpx
import uvicorn

from backend.auth_api import CSRF_COOKIE, CSRF_HEADER, get_auth_uow
from backend.auth_security import hash_password
from backend.auth_store import assert_auth_connection, transaction_on
from backend.committee_api import get_committee_uow
from backend.committee_store import committee_transaction_on
from backend.invitation_api import get_invitation_uow
from backend.invitation_store import invitation_transaction_on
from backend.main import create_app
from backend.project_api import get_project_uow
from backend.project_store import project_transaction_on
from backend.team_api import get_team_uow
from backend.team_store import team_transaction_on
from backend.topic_vote_api import get_topic_vote_uow
from backend.topic_vote_store import topic_vote_transaction_on
from backend.evaluation_api import get_evaluation_uow
from backend.evaluation_store import evaluation_transaction_on
from backend.tests import team_project_concurrency as team_cases, topic_vote_concurrency as vote_cases
from backend.tests.team_project_concurrency import (
    CheckFailed, fingerprint, finish_worker, require, rollback_connection, wait_for_block,
)
from database.tests.Auth_Regression import switch
from database.tests.Team_Create_Installed_Regression import baseline
from database.tools.Test_Database import TEST_DB, connect_test_database

PASSWORD = "HttpConcurrencyFixtureA1"  # Synthetic test-only password, never persisted.
ORIGIN = {"Origin": "http://localhost:3000"}
MANAGERS = {
    get_auth_uow: transaction_on, get_team_uow: team_transaction_on,
    get_project_uow: project_transaction_on, get_invitation_uow: invitation_transaction_on,
    get_committee_uow: committee_transaction_on, get_topic_vote_uow: topic_vote_transaction_on,
    get_evaluation_uow: evaluation_transaction_on,
}
CASES = {**{"H" + key: value for key, value in team_cases.CASES.items()},
         **{"H" + key: value for key, value in vote_cases.CASES.items()}}
CASES["HRC06"] = "HTTP Team update times out with sanitized 500/55P03 while A holds Team lock"


@dataclass(frozen=True)
class RequestPlan:
    actor: str
    method: str
    path: str
    body: dict | None
    status: int


def request_plan(fixture, case):
    require(case in CASES, "UNKNOWN_HTTP_CASE")
    users = fixture.users
    if case.startswith("HRC"):
        actor = users["member_b" if case == "HRC02" else "leader_c" if case in ("HRC04", "HRC05") else "leader_a"]
        if case == "HRC02":
            return RequestPlan(actor, "POST", "/api/v1/teams/me/leave", {}, 204)
        if case == "HRC04":
            return RequestPlan(actor, "POST", "/api/v1/projects", {"name": fixture.namespace + ".http-project"}, 201)
        if case == "HRC05":
            return RequestPlan(actor, "POST", "/api/v1/teams/me/members",
                               {"email": fixture.namespace + ".free_student@example.test"}, 201)
        path = "/api/v1/projects/me" if case == "HRC03" else "/api/v1/teams/me"
        return RequestPlan(actor, "PATCH", path, {"name": fixture.namespace + ".http-update"}, 500 if case == "HRC06" else 200)
    project = fixture.projects["main"]
    if case in ("HVC01", "HVC02", "HVC03"):
        path = f"/api/v1/coordinator/projects/{project}/committee"
        if case == "HVC01":
            return RequestPlan(users["coordinator"], "POST", path, {"advisor_id": users["spare"]}, 201)
        path += "/" + fixture.assignments["main"]["c"]
        if case == "HVC03":
            return RequestPlan(users["coordinator"], "POST", path + "/remove", {}, 204)
        return RequestPlan(users["coordinator"], "PATCH", path, {"advisor_id": users["spare"]}, 200)
    if case == "HVC07":
        return RequestPlan(users["leader_revision"], "GET", "/api/v1/projects/me/committee", None, 200)
    return RequestPlan(users["c" if case == "HVC06" else "b"], "POST",
                       f"/api/v1/committee/projects/{project}/topic-votes",
                       {"submission_id": fixture.submissions["main"], "vote": "approved", "comment": "HTTP concurrency fixture"}, 201)


def validate(conn, fixture, case):
    return (team_cases.validate_fixture if case.startswith("HRC") else vote_cases.validate_fixture)(conn, fixture)


@lru_cache(maxsize=1)
def encoded_password():
    return hash_password(PASSWORD)


@contextmanager
def http_connection(fixture, case, *, connector=None, actor=None):
    """Owner only prepares the credential; never retries a failed app operation."""
    require(case in CASES, "UNKNOWN_HTTP_CASE")
    selected_actor = request_plan(fixture, case).actor if actor is None else actor
    require(selected_actor in fixture.users.values(), "HTTP_ACTOR_NOT_IN_FIXTURE")
    conn = (connector or connect_test_database)()
    try:
        conn.rollback()  # End the connector's identity-only implicit transaction.
        with conn.transaction(force_rollback=True):
            conn.execute("SET TRANSACTION ISOLATION LEVEL READ COMMITTED")
            conn.execute("SELECT set_config('statement_timeout','10000ms',true)")
            conn.execute("SELECT set_config('lock_timeout',%s,true)", ("1000ms" if case == "HRC06" else "5000ms",))
            with conn.cursor() as cur:
                switch(cur, "project_app")
                assert_auth_connection(conn)
                validate(conn, fixture, case)
                switch(cur, "project_owner")
                cur.execute("SELECT current_user,rolsuper FROM pg_roles WHERE rolname=current_user")
                require(cur.fetchone() == ("project_owner", False), "NON_SUPERUSER_OWNER_REQUIRED")
                cur.execute("SELECT EXISTS(SELECT 1 FROM auth.credentials WHERE user_id=%s)", (selected_actor,))
                require(cur.fetchone() == (False,), "FIXTURE_CREDENTIAL_ALREADY_EXISTS")
                cur.execute("INSERT INTO auth.credentials(user_id,password_hash) VALUES (%s,%s)", (selected_actor, encoded_password()))
                switch(cur, "project_app")
            assert_auth_connection(conn)
            require(conn.execute("SELECT current_database(),current_user,current_setting('transaction_isolation')").fetchone() ==
                    (TEST_DB, "project_app", "read committed"), "HTTP_CONNECTION_IDENTITY")
            yield conn
    finally:
        try:
            conn.rollback()
        finally:
            conn.close()


def request_app(conn, sqlstates, *, on_complete=None):
    app = create_app()
    def manager_for(manager):
        @contextmanager
        def unit():
            try:
                with manager(conn) as store:
                    yield store
                    if on_complete is not None:
                        on_complete(manager)
            except Exception as exc:
                state = vote_cases.diagnostic(exc)["sqlstate"]
                if state is not None:
                    sqlstates.append(state)
                raise
        return unit
    for dependency, manager in MANAGERS.items():
        app.dependency_overrides[dependency] = lambda manager=manager: manager_for(manager)
    def dependencies(dependant):
        if dependant is None:
            return set()
        call = dependant.call
        found = {call} if callable(call) and getattr(call, "__name__", "").startswith("get_") and call.__name__.endswith("_uow") else set()
        for child in dependant.dependencies:
            found.update(dependencies(child))
        return found
    required, visited = set(), set()
    def inspect_routes(routes):
        for route in routes:
            if id(route) in visited:
                continue
            visited.add(id(route))
            required.update(dependencies(getattr(route, "dependant", None)))
            # This installed FastAPI retains included routers as wrappers.
            included = getattr(route, "original_router", None)
            if included is not None:
                inspect_routes(included.routes)
    inspect_routes(app.routes)
    require(required == set(MANAGERS), "HTTP_UOW_OVERRIDE_SET_CHANGED")
    return app


@contextmanager
def live_client(app):
    """An owned ephemeral loopback socket; never touches normal app ports."""
    listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server, thread = None, None
    try:
        listener.bind(("127.0.0.1", 0))
        listener.listen(64)
        port = listener.getsockname()[1]
        server = uvicorn.Server(uvicorn.Config(app, log_level="critical", access_log=False,
                                             timeout_graceful_shutdown=2, ws="none"))
        thread = Thread(target=server.run, kwargs={"sockets": [listener]}, daemon=True)
        thread.start()
        deadline = time.monotonic() + 5
        while not server.started and thread.is_alive() and time.monotonic() < deadline:
            time.sleep(0.01)
        require(server.started, "HTTP_SERVER_NOT_READY")
        with httpx.Client(base_url=f"http://127.0.0.1:{port}", timeout=12, trust_env=False, follow_redirects=False) as client:
            yield client
    finally:
        if server is not None:
            server.should_exit = True
        if thread is not None:
            thread.join(timeout=5)
            if thread.is_alive():
                server.force_exit = True
                thread.join(timeout=3)
        listener.close()
        require(thread is None or not thread.is_alive(), "HTTP_SERVER_DID_NOT_STOP")


def http_call(client, method, path, *, body=None, status=200):
    headers = {**ORIGIN, **({CSRF_HEADER: client.cookies.get(CSRF_COOKIE, "")} if method != "GET" else {})}
    response = client.request(method, path, headers=headers, **({"json": body} if body is not None else {}))
    require(response.status_code == status, "HTTP_STATUS_MISMATCH")
    require(response.headers.get("cache-control") == "no-store", "HTTP_CACHE_POLICY")
    require(response.content == b"" if status == 204 else isinstance(response.json(), dict), "HTTP_BODY_SHAPE")
    return response


def authenticate(client, conn, actor):
    email, role = conn.execute("SELECT email,role FROM public.users WHERE id=%s", (actor,)).fetchone()
    http_call(client, "POST", "/api/v1/auth/login", body={"email": email, "password": PASSWORD})
    user = http_call(client, "GET", "/api/v1/auth/me").json()["data"]
    require(user["id"] == actor and user["role"] == role, "HTTP_SESSION_IDENTITY")
    require(bool(client.cookies.get(CSRF_COOKIE)), "HTTP_CSRF_COOKIE_REQUIRED")


def verify_response(client, conn, fixture, case, state, response, sqlstates):
    if case == "HRC06":
        require(response.json()["error"]["code"] == "INTERNAL_ERROR" and sqlstates == ["55P03"], "HTTP_TIMEOUT_TRANSLATION")
        require(set(response.json()) == {"error"} and set(response.json()["error"]) == {"code", "message"}, "HTTP_TIMEOUT_LEAK")
        return
    require(not sqlstates, "UNEXPECTED_HTTP_SQL_FAILURE")
    data = response.json()["data"] if response.status_code != 204 else None
    users = fixture.users
    if case == "HRC01":
        require(data["membership"]["role"] == "leader" and data["name"] == fixture.namespace + ".http-update", "HTTP_TRANSFER_ROLLBACK_AUTHORITY")
    elif case == "HRC02":
        require(conn.execute("SELECT count(*) FROM public.team_members WHERE user_id=%s", (users["member_b"],)).fetchone() == (0,), "HTTP_EXIT_NOT_APPLIED")
    elif case == "HRC03":
        require(data["id"] == fixture.project_id and data["name"] == fixture.namespace + ".http-update" and
                data["description"] == state["project_description"], "HTTP_PROJECT_OMITTED_FIELD")
    elif case == "HRC04":
        require(data["team_id"] == fixture.teams["empty"] and data["created_by"] == users["leader_c"], "HTTP_PROJECT_TARGET")
    elif case == "HRC05":
        require(data["user_id"] == users["free_student"] and data["role"] == "member" and
                conn.execute("SELECT team_id FROM public.team_members WHERE user_id=%s", (users["free_student"],)).fetchone() ==
                (int(fixture.teams["empty"]),), "HTTP_MEMBER_TARGET")
    elif case in ("HVC01", "HVC02", "HVC03"):
        project = fixture.projects["main"]
        count = conn.execute("SELECT count(*) FROM public.committee_assignments WHERE project_id=%s", (project,)).fetchone()[0]
        require(count == {"HVC01": 4, "HVC02": 3, "HVC03": 2}[case], "HTTP_ROSTER_COUNT")
        if data is not None:
            require(data["advisor"]["id"] == users["spare"], "HTTP_ROSTER_TARGET")
            if case == "HVC02":
                require(data["id"] == fixture.assignments["main"]["c"], "HTTP_REPLACEMENT_ID")
    elif case == "HVC07":
        require(len(data["rounds"]) == 1 and data["rounds"][0]["submission"]["id"] == fixture.submissions["revision"], "HTTP_UNCOMMITTED_ROUND_LEAK")
        require(data["rounds"][0]["decision"] == "revision_requested" and
                data["rounds"][0]["comments"] == [vote_cases.REVISION_COMMENT] * 3, "HTTP_READER_RESULT")
        require(set(data["rounds"][0]) == {"submission", "decision", "comments"} and
                all(set(row) == {"full_name"} for row in data["committee"]), "HTTP_READER_PRIVACY")
    else:
        member = "c" if case == "HVC06" else "b"
        submission, project = fixture.submissions["main"], fixture.projects["main"]
        require(data["submission_id"] == submission and data["vote"] == "approved", "HTTP_VOTE_RESULT")
        require(conn.execute("SELECT committee_assignment_id FROM public.committee_topic_votes WHERE submission_id=%s", (submission,)).fetchall() ==
                [(int(fixture.assignments["main"][member]),)], "HTTP_VOTE_NOT_SINGLE_OWN")
        context = http_call(client, "GET", f"/api/v1/committee/projects/{project}/topic-votes").json()["data"]
        require(context["rounds"][0]["own_vote"] == data and context["rounds"][0]["decision"] is None, "HTTP_OWN_VOTE_CONTEXT")


def worker(fixture, case, state, ready, done):
    try:
        with http_connection(fixture, case) as conn:
            sqlstates = []
            plan = request_plan(fixture, case)
            with live_client(request_app(conn, sqlstates)) as client:
                authenticate(client, conn, plan.actor)
                ready.put((conn, conn.execute("SELECT pg_backend_pid()").fetchone()[0]))
                response = http_call(client, plan.method, plan.path, body=plan.body, status=plan.status)
                verify_response(client, conn, fixture, case, state, response, sqlstates)
        done.put({"ok": True, "http_status": plan.status, "sqlstate": "55P03" if case == "HRC06" else None})
    except Exception as exc:
        done.put(vote_cases.diagnostic(exc))


def run_case(fixture, case):
    require(case in CASES, "UNKNOWN_HTTP_CASE")
    ready, done = Queue(), Queue()
    thread, worker_conn, failure, outcome = None, None, None, None
    auth_before = baseline()
    with rollback_connection(readonly=True) as observer:
        state = validate(observer, fixture, case)
        before = fingerprint(observer)
        try:
            with rollback_connection() as first:
                require(validate(first, fixture, case) == state, "HTTP_FIXTURE_CHANGED")
                first_pid = first.execute("SELECT pg_backend_pid()").fetchone()[0]
                observer_pid = observer.execute("SELECT pg_backend_pid()").fetchone()[0]
                if case.startswith("HRC"):
                    team_cases.action(first, fixture, state, case[1:], "A")
                else:
                    vote_cases.action(first, fixture, case[1:], "A")
                thread = Thread(target=worker, args=(fixture, case, state, ready, done), daemon=True)
                thread.start()
                try:
                    worker_conn, worker_pid = ready.get(timeout=10)
                except Empty:
                    result = done.get_nowait() if not done.empty() else {}
                    raise CheckFailed("HTTP_WORKER_NOT_READY", result.get("sqlstate")) from None
                require(len({first_pid, worker_pid, observer_pid}) == 3, "SESSIONS_NOT_DISTINCT")
                wait_for_block(observer, first_pid, worker_pid)
                if case == "HRC06":
                    try:
                        outcome = done.get(timeout=6)
                    except Empty:
                        raise CheckFailed("HTTP_TIMEOUT_NOT_RETURNED") from None
        except Exception as exc:
            failure = exc
        finally:
            if thread is not None:
                finish_worker(thread, worker_conn)
        require(fingerprint(observer) == before, "HTTP_PUBLIC_BASELINE_NOT_RESTORED")
    require(baseline() == auth_before, "HTTP_AUTH_METADATA_COUNTS_NOT_RESTORED")
    if failure is not None:
        raise failure
    if outcome is None:
        try:
            outcome = done.get_nowait()
        except Empty:
            raise CheckFailed("HTTP_WORKER_RESULT_MISSING") from None
    expected = {"ok": True, "http_status": request_plan(fixture, case).status, "sqlstate": "55P03" if case == "HRC06" else None}
    if outcome != expected:
        raise CheckFailed("HTTP_UNEXPECTED_WORKER_RESULT", outcome.get("sqlstate"))
    return {"case": case, "result": "PASS", "transport": "LOOPBACK_TCP", "real_login": True,
            "wait_observed": True, "http_status": outcome["http_status"], "sqlstate": outcome["sqlstate"],
            "both_workers_rolled_back": True, "public_rows_auth_counts_metadata_restored": True}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--team-fixture", type=Path)
    parser.add_argument("--vote-fixture", type=Path)
    parser.add_argument("--run-rollback", action="store_true")
    args = parser.parse_args(argv)
    try:
        if not args.run_rollback:
            print(json.dumps({"mode": "OFFLINE_PLAN", "database_connected": False, "cases": CASES,
                              "new_persistent_fixture_required": False, "winner_commit": "NOT_IMPLEMENTED_NOT_AUTHORIZED"}))
            return 0
        require(args.team_fixture is not None and args.vote_fixture is not None, "BOTH_MANIFESTS_REQUIRED")
        fixtures = {"HRC": team_cases.Fixture.load(args.team_fixture), "HVC": vote_cases.VoteFixture.load(args.vote_fixture)}
        with rollback_connection(readonly=True) as conn:
            require(conn.execute("SELECT count(*) FROM pg_stat_activity WHERE datname=current_database() "
                                 "AND pid<>pg_backend_pid() AND backend_type='client backend'").fetchone() == (0,), "OTHER_CLIENTS_CONNECTED")
            team_cases.validate_fixture(conn, fixtures["HRC"])
            vote_cases.validate_fixture(conn, fixtures["HVC"])
        for case in CASES:
            print(json.dumps(run_case(fixtures[case[:3]], case)))
        return 0
    except Exception as exc:
        print(json.dumps({"result": "FAIL", **vote_cases.diagnostic(exc)}))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
