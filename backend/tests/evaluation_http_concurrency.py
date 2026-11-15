"""Real authenticated Evaluation HTTP races on the existing 42-row fixture.

Default OFFLINE. Five mixed HTTP/repository and five dual-HTTP cases; all
credentials/sessions/actions ROLLBACK. No seed, DDL, grants, or winner-COMMIT.
HTTP workers use a borrowed owner fixture connection with effective app role;
repository workers/observer use direct LOGIN project_app. No peer Task API.
"""

import argparse
from contextlib import contextmanager
from dataclasses import dataclass
import json
from pathlib import Path
from queue import Queue
from threading import Event, Thread

from backend.auth_store import assert_auth_connection
from backend.tests import evaluation_concurrency as database_cases, http_concurrency as shared
from backend.tests.dual_http_concurrency import RequestGate, ready_worker, result_worker
from backend.tests.team_project_concurrency import (
    CheckFailed, fingerprint, finish_worker, positive_id, require, rollback_connection, wait_for_block,
)
from database.tests.Auth_Regression import switch
from database.tests.Team_Create_Installed_Regression import baseline
from database.tools.Test_Database import TEST_DB, connect_test_database


CASES = {
    "EH01": ("EC01", "HTTP", "REPOSITORY", None),
    "EH02": ("EC02", "HTTP", "REPOSITORY", None),
    "EH03": ("EC03", "HTTP", "REPOSITORY", None),
    "EH04": ("EC04", "REPOSITORY", "HTTP", None),
    "EH05": ("EC05", "REPOSITORY", "HTTP", None),
    "EH06": ("EC06", "HTTP", "HTTP", None),
    "EH07": ("EC07", "HTTP", "HTTP", "team"),
    "EH08": ("EC07", "HTTP", "HTTP", "advisor"),
    "EH09": ("EC07", "HTTP", "HTTP", "coordinator"),
    "EH10": ("EC08", "HTTP", "HTTP", None),
}


@dataclass(frozen=True)
class Plans:
    first: shared.RequestPlan | None
    second: shared.RequestPlan | None


def plans(fixture, case):
    require(case in CASES, "UNKNOWN_EVALUATION_HTTP_CASE")
    source, mode_a, mode_b, reader_role = CASES[case]
    final = source in ("EC07", "EC08")
    project = fixture.projects["final" if final else "main"]
    users = fixture.users

    def make(side, mode):
        if mode == "REPOSITORY":
            return None
        reader = (source == "EC07" and side == "B") or (source == "EC08" and side == "A")
        if reader:
            role = reader_role if side == "B" else "team"
            actor = users["leader_final"] if role == "team" else users[role]
            path = "/api/v1/projects/me/evaluations" if role == "team" else f"/api/v1/{role}/projects/{project}/evaluations"
            return shared.RequestPlan(actor, "GET", path, None, 200)
        member = "d" if final else "c" if source == "EC06" and side == "B" else "b"
        score = 80 if final or side == "A" else 90
        return shared.RequestPlan(users[member], "POST", f"/api/v1/committee/projects/{project}/evaluations",
                                  {"score": score, "comment": database_cases.COMMENT}, 201)
    result = Plans(make("A", mode_a), make("B", mode_b))
    if result.first and result.second:
        require(result.first.actor != result.second.actor, "HTTP_ACTORS_MUST_DIFFER")
    return result


@contextmanager
def http_connection(fixture, actor, *, connector=None):
    require(actor in fixture.users.values(), "HTTP_ACTOR_NOT_IN_FIXTURE")
    conn = (connector or connect_test_database)()
    try:
        conn.rollback()
        with conn.transaction(force_rollback=True):
            conn.execute("SET TRANSACTION ISOLATION LEVEL READ COMMITTED")
            conn.execute("SELECT set_config('statement_timeout','10000ms',true)")
            conn.execute("SELECT set_config('lock_timeout','5000ms',true)")
            with conn.cursor() as cur:
                switch(cur, "project_app")
                assert_auth_connection(conn)
                database_cases.validate_fixture(conn, fixture)
                switch(cur, "project_owner")
                cur.execute("SELECT current_user,rolsuper FROM pg_roles WHERE rolname=current_user")
                require(cur.fetchone() == ("project_owner", False), "NON_SUPERUSER_OWNER_REQUIRED")
                cur.execute("SELECT EXISTS(SELECT 1 FROM auth.credentials WHERE user_id=%s)", (actor,))
                require(cur.fetchone() == (False,), "FIXTURE_CREDENTIAL_ALREADY_EXISTS")
                cur.execute("INSERT INTO auth.credentials(user_id,password_hash) VALUES (%s,%s)", (actor, shared.encoded_password()))
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


def verify_response(client, conn, fixture, case, side, plan, response, sqlstates):
    require(not sqlstates, "UNEXPECTED_EVALUATION_HTTP_SQL_FAILURE")
    body = response.json()
    require(set(body) == {"data"}, "EVALUATION_HTTP_ENVELOPE")
    data = body["data"]
    source = CASES[case][0]
    label = "final" if source in ("EC07", "EC08") else "main"
    project = fixture.projects[label]
    if plan.method == "POST":
        require(set(data) == {"id", "score", "comment", "created_at"} and positive_id(data["id"]) and
                type(data["score"]) is int and data["score"] == plan.body["score"] and data["comment"] == plan.body["comment"],
                "EVALUATION_HTTP_RECORD_DTO")
        context = shared.http_call(client, "GET", plan.path).json()["data"]
        require(set(context) == {"project", "can_evaluate", "blocking_reason", "own_evaluation", "summary"} and
                context["project"]["id"] == project and context["own_evaluation"] == data and
                context["can_evaluate"] is False and context["blocking_reason"] == "ALREADY_EVALUATED",
                "EVALUATION_HTTP_OWN_RESULT")
        expected = {"total_score": "210", "average_score": 70} if label == "final" else None
        require(context["summary"] == expected, "EVALUATION_HTTP_SCORE_PRIVACY")
        member = next(k for k in database_cases.MEMBERS if fixture.users[k] == plan.actor)
        rows = conn.execute("SELECT committee_assignment_id,score FROM public.committee_evaluations WHERE committee_assignment_id=ANY(%s)",
                            ([int(v) for v in fixture.assignments[label].values()],)).fetchall()
        expected_rows = {(int(fixture.assignments[label][member]), plan.body["score"])}
        if label == "final":
            expected_rows |= {(int(fixture.assignments[label][k]), score) for k, score in (("b", 60), ("c", 70))}
        require(len(rows) == len(expected_rows) and set(rows) == expected_rows, "EVALUATION_HTTP_ROLLED_BACK_SCORE_VISIBLE")
    else:
        coordinator = plan.actor == fixture.users["coordinator"]
        keys = {"project", "summary", "evaluations"} if coordinator else {"project", "summary"}
        require(set(data) == keys and data["project"]["id"] == project and data["summary"] is None,
                "EVALUATION_HTTP_READER_PRIVACY")
        if coordinator:
            require(data["evaluations"] == [], "EVALUATION_HTTP_INDIVIDUAL_SCORE_LEAK")


def worker(fixture, dates, case, side, plan, gate, ready, done, returned):
    try:
        source = CASES[case][0]
        if plan is None:
            with rollback_connection() as conn:
                require(database_cases.validate_fixture(conn, fixture) == dates, "EVALUATION_FIXTURE_CHANGED")
                ready.put((conn, conn.execute("SELECT pg_backend_pid()").fetchone()[0]))
                database_cases.action(conn, fixture, dates, source, side)
                if side == "A":
                    gate.held.set()
                    require(gate.release.wait(timeout=12), "EVALUATION_REPOSITORY_GATE_TIMEOUT")
                returned.set()
        else:
            with http_connection(fixture, plan.actor) as conn:
                sqlstates = []
                app = shared.request_app(conn, sqlstates, on_complete=gate if side == "A" else None)
                with shared.live_client(app) as client:
                    shared.authenticate(client, conn, plan.actor)
                    ready.put((conn, conn.execute("SELECT pg_backend_pid()").fetchone()[0]))
                    if side == "A":
                        gate.armed.set()
                    response = shared.http_call(client, plan.method, plan.path, body=plan.body, status=plan.status)
                    returned.set()
                    if side == "A":
                        gate.armed.clear()
                    verify_response(client, conn, fixture, case, side, plan, response, sqlstates)
        done.put({"ok": True, "http_status": plan.status if plan else None, "sqlstate": None})
    except Exception as exc:
        done.put(database_cases.diagnostic(exc))


def run_case(fixture, case):
    require(case in CASES, "UNKNOWN_EVALUATION_HTTP_CASE")
    selected = plans(fixture, case)
    before_auth = baseline()
    channels = {side: (Queue(), Queue(), Event()) for side in ("A", "B")}
    threads, connections, failure = {}, {}, None
    gate = RequestGate(shared.evaluation_transaction_on)
    with rollback_connection(readonly=True) as observer:
        dates = database_cases.validate_fixture(observer, fixture)
        before = fingerprint(observer)
        observer_pid = observer.execute("SELECT pg_backend_pid()").fetchone()[0]
        try:
            ready_a, done_a, returned_a = channels["A"]
            threads["A"] = Thread(target=worker, args=(fixture, dates, case, "A", selected.first, gate, ready_a, done_a, returned_a), daemon=True)
            threads["A"].start()
            connections["A"], first_pid = ready_worker(ready_a, done_a)
            require(gate.held.wait(timeout=10), "EVALUATION_HTTP_FIRST_NOT_HELD")
            require(not returned_a.is_set(), "EVALUATION_HTTP_FIRST_RETURNED_EARLY")
            ready_b, done_b, returned_b = channels["B"]
            threads["B"] = Thread(target=worker, args=(fixture, dates, case, "B", selected.second, gate, ready_b, done_b, returned_b), daemon=True)
            threads["B"].start()
            connections["B"], second_pid = ready_worker(ready_b, done_b)
            require(len({first_pid, second_pid, observer_pid}) == 3, "SESSIONS_NOT_DISTINCT")
            wait_for_block(observer, first_pid, second_pid)
            require(not returned_a.is_set() and not returned_b.is_set(), "EVALUATION_HTTP_OVERLAP_NOT_OBSERVED")
        except Exception as exc:
            failure = exc
        finally:
            gate.release.set()
            for side in ("A", "B"):
                if side in threads:
                    try:
                        finish_worker(threads[side], connections.get(side))
                    except Exception as exc:
                        failure = failure or exc
        require(fingerprint(observer) == before, "EVALUATION_HTTP_PUBLIC_BASELINE_NOT_RESTORED")
        database_cases.validate_fixture(observer, fixture)
    require(baseline() == before_auth, "EVALUATION_HTTP_AUTH_BASELINE_NOT_RESTORED")
    if failure is not None:
        raise failure
    statuses = [result_worker(channels[side][1], plan.status if plan else None)
                for side, plan in (("A", selected.first), ("B", selected.second))]
    require(all(channels[side][2].is_set() for side in ("A", "B")), "EVALUATION_HTTP_RESULT_NOT_OBSERVED")
    count = sum(plan is not None for plan in (selected.first, selected.second))
    return {"case": case, "result": "PASS", "transport": "TWO_LOOPBACK_TCP_CLIENTS" if count == 2 else "HTTP_AND_REPOSITORY",
            "real_login_http_workers": count, "overlap_observed": True, "database_wait_observed": True,
            "http_statuses": statuses, "both_workers_rolled_back": True,
            "public_rows_auth_counts_metadata_restored": True}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fixture", type=Path)
    parser.add_argument("--run-rollback", action="store_true")
    args = parser.parse_args(argv)
    try:
        if not args.run_rollback:
            print(json.dumps({"mode": "OFFLINE_PLAN", "database_connected": False, "cases": CASES,
                              "new_persistent_fixture_required": False, "winner_commit_available": False}))
            return 0
        require(args.fixture is not None, "EXPLICIT_MANIFEST_REQUIRED")
        fixture = database_cases.EvaluationFixture.load(args.fixture)
        with rollback_connection(readonly=True) as conn:
            require(conn.execute("SELECT count(*) FROM pg_stat_activity WHERE datname=current_database() AND "
                                 "pid<>pg_backend_pid() AND backend_type='client backend'").fetchone() == (0,), "OTHER_CLIENTS_CONNECTED")
            database_cases.validate_fixture(conn, fixture)
        for case in CASES:
            print(json.dumps(run_case(fixture, case)))
        return 0
    except Exception as exc:
        print(json.dumps({"result": "FAIL", **database_cases.diagnostic(exc)}))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
