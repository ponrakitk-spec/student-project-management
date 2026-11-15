"""Two overlapping, authenticated loopback HTTP requests; ALWAYS ROLLBACK.

Default OFFLINE. Existing dedicated manifests only, no persistent Auth fixtures.
Both API workers prepare distinct temporary credentials as non-superuser owner
and serve as effective project_app. An in-process UOW gate holds A BEFORE its
response; observer must prove B's database wait while BOTH responses are pending.
No production route, authentication, HTTP status or SQL operation is mocked.
"""

import argparse
from dataclasses import dataclass
import json
from pathlib import Path
from queue import Empty, Queue
from threading import Event, Thread

from backend.tests import http_concurrency as shared
from backend.tests.team_project_concurrency import (
    CheckFailed, fingerprint, finish_worker, require, rollback_connection, wait_for_block,
)
from database.tests.Team_Create_Installed_Regression import baseline

CASES = {
    "DH01": ("HRC02", "Leader transfer versus the next leader's member leave (A rollback)"),
    "DH02": ("HRC02", "Leader removes member versus that member leaving"),
    "DH03": ("HRC05", "Two leaders add the same free student to different teams"),
    "DH04": ("HVC01", "First Vote versus Coordinator adding committee"),
    "DH05": ("HVC02", "First Vote versus Coordinator replacing committee"),
    "DH06": ("HVC03", "First Vote versus Coordinator removing committee"),
    "DH07": ("HVC04", "Coordinator removes voter versus that voter's Vote"),
    "DH08": ("HVC06", "Different committee members Vote concurrently"),
    "DH09": ("HVC08", "Team result reader versus committee Vote"),
}


@dataclass(frozen=True)
class Plans:
    first: shared.RequestPlan
    second: shared.RequestPlan
    manager: object


def plans(fixture, case, state):
    require(case in CASES, "UNKNOWN_DUAL_HTTP_CASE")
    source = CASES[case][0]
    second = shared.request_plan(fixture, source)
    users = fixture.users
    if case == "DH01":
        first = shared.RequestPlan(users["leader_a"], "POST", "/api/v1/teams/me/leader",
                                   {"team_member_id": state["member_id"]}, 200)
        manager = shared.team_transaction_on
    elif case == "DH02":
        first = shared.RequestPlan(users["leader_a"], "POST", f"/api/v1/teams/me/members/{state['member_id']}/remove", {}, 204)
        manager = shared.team_transaction_on
    elif case == "DH03":
        first = shared.RequestPlan(users["leader_a"], "POST", "/api/v1/teams/me/members",
                                   {"email": fixture.namespace + ".free_student@example.test"}, 201)
        manager = shared.team_transaction_on
    elif case == "DH07":
        project, assignment = fixture.projects["main"], fixture.assignments["main"]["b"]
        first = shared.RequestPlan(users["coordinator"], "POST",
                                   f"/api/v1/coordinator/projects/{project}/committee/{assignment}/remove", {}, 204)
        manager = shared.committee_transaction_on
    elif case == "DH09":
        first = shared.RequestPlan(users["leader_main"], "GET", "/api/v1/projects/me/committee", None, 200)
        manager = shared.topic_vote_transaction_on
    else:
        first = shared.request_plan(fixture, "HVC05")  # Appointed advisor b.
        manager = shared.topic_vote_transaction_on
    require(first.actor != second.actor, "DUAL_HTTP_ACTORS_MUST_DIFFER")
    require(first.actor in users.values() and second.actor in users.values(), "HTTP_ACTOR_NOT_IN_FIXTURE")
    return Plans(first, second, manager)


class RequestGate:
    def __init__(self, manager):
        self.manager = manager
        self.armed, self.held, self.release = Event(), Event(), Event()

    def __call__(self, manager):
        if manager is self.manager and self.armed.is_set() and not self.held.is_set():
            self.held.set()
            require(self.release.wait(timeout=12), "DUAL_HTTP_GATE_TIMEOUT")


def verify_first(client, conn, fixture, case, response, sqlstates):
    require(not sqlstates, "UNEXPECTED_HTTP_SQL_FAILURE")
    if case == "DH01":
        data = response.json()["data"]
        require(data["id"] == fixture.teams["main"] and data["membership"]["role"] == "member", "DUAL_HTTP_TRANSFER_RESULT")
        require(conn.execute("SELECT role FROM public.team_members WHERE user_id=%s", (fixture.users["member_b"],)).fetchone() ==
                ("leader",), "DUAL_HTTP_NEXT_LEADER")
    elif case == "DH02":
        require(conn.execute("SELECT count(*) FROM public.team_members WHERE user_id=%s", (fixture.users["member_b"],)).fetchone() ==
                (0,), "DUAL_HTTP_REMOVAL_RESULT")
    elif case == "DH03":
        require(response.json()["data"]["user_id"] == fixture.users["free_student"] and
                conn.execute("SELECT team_id FROM public.team_members WHERE user_id=%s", (fixture.users["free_student"],)).fetchone() ==
                (int(fixture.teams["main"]),), "DUAL_HTTP_ADDITION_TARGET")
    elif case == "DH07":
        require(conn.execute("SELECT count(*) FROM public.committee_assignments WHERE id=%s", (fixture.assignments["main"]["b"],)).fetchone() ==
                (0,), "DUAL_HTTP_VOTER_REMOVAL")
    elif case == "DH09":
        data = response.json()["data"]
        require(len(data["rounds"]) == 1 and data["rounds"][0]["submission"]["id"] == fixture.submissions["main"], "DUAL_HTTP_READER_ROUND")
        require(data["rounds"][0]["decision"] is None and data["rounds"][0]["comments"] == [] and
                set(data["rounds"][0]) == {"submission", "decision", "comments"} and
                all(set(row) == {"full_name"} for row in data["committee"]), "DUAL_HTTP_READER_PRIVACY")
    else:
        shared.verify_response(client, conn, fixture, "HVC05", None, response, sqlstates)


def worker(fixture, case, state, plan, side, gate, ready, done, returned):
    try:
        source = CASES[case][0]
        with shared.http_connection(fixture, source, actor=plan.actor) as conn:
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
                    verify_first(client, conn, fixture, case, response, sqlstates)
                else:
                    shared.verify_response(client, conn, fixture, source, state, response, sqlstates)
        done.put({"ok": True, "http_status": plan.status, "sqlstate": None})
    except Exception as exc:
        done.put(shared.vote_cases.diagnostic(exc))


def ready_worker(queue, done):
    try:
        return queue.get(timeout=10)
    except Empty:
        result = done.get_nowait() if not done.empty() else {}
        raise CheckFailed("DUAL_HTTP_WORKER_NOT_READY", result.get("sqlstate")) from None


def result_worker(queue, status):
    try:
        result = queue.get_nowait()
    except Empty:
        raise CheckFailed("DUAL_HTTP_RESULT_MISSING") from None
    if result != {"ok": True, "http_status": status, "sqlstate": None}:
        raise CheckFailed("DUAL_HTTP_UNEXPECTED_RESULT", result.get("sqlstate"))
    return status


def run_case(fixture, case):
    require(case in CASES, "UNKNOWN_DUAL_HTTP_CASE")
    source = CASES[case][0]
    before_auth = baseline()
    channels = {side: (Queue(), Queue(), Event()) for side in ("A", "B")}
    threads, connections, failure, gate = {}, {}, None, None
    with rollback_connection(readonly=True) as observer:
        state = shared.validate(observer, fixture, source)
        before = fingerprint(observer)
        selected = plans(fixture, case, state)
        gate = RequestGate(selected.manager)
        observer_pid = observer.execute("SELECT pg_backend_pid()").fetchone()[0]
        try:
            ready_a, done_a, returned_a = channels["A"]
            threads["A"] = Thread(target=worker, args=(fixture, case, state, selected.first, "A", gate, ready_a, done_a, returned_a), daemon=True)
            threads["A"].start()
            connections["A"], first_pid = ready_worker(ready_a, done_a)
            require(gate.held.wait(timeout=10), "DUAL_HTTP_FIRST_REQUEST_NOT_HELD")
            require(not returned_a.is_set(), "DUAL_HTTP_FIRST_RESPONSE_ALREADY_RETURNED")
            ready_b, done_b, returned_b = channels["B"]
            threads["B"] = Thread(target=worker, args=(fixture, case, state, selected.second, "B", gate, ready_b, done_b, returned_b), daemon=True)
            threads["B"].start()
            connections["B"], second_pid = ready_worker(ready_b, done_b)
            require(len({first_pid, second_pid, observer_pid}) == 3, "SESSIONS_NOT_DISTINCT")
            wait_for_block(observer, first_pid, second_pid)
            require(not returned_a.is_set() and not returned_b.is_set(), "DUAL_HTTP_REQUESTS_NOT_OVERLAPPING")
        except Exception as exc:
            failure = exc
        finally:
            if gate is not None:
                gate.release.set()
            # Finish/rollback A BEFORE waiting for B, including error paths.
            cleanup_failure = None
            for side in ("A", "B"):
                if side in threads:
                    try:
                        finish_worker(threads[side], connections.get(side))
                    except Exception as exc:
                        cleanup_failure = cleanup_failure or exc
            if cleanup_failure is not None:
                failure = failure or cleanup_failure
        require(fingerprint(observer) == before, "DUAL_HTTP_PUBLIC_BASELINE_NOT_RESTORED")
    require(baseline() == before_auth, "DUAL_HTTP_AUTH_BASELINE_NOT_RESTORED")
    if failure is not None:
        raise failure
    statuses = [result_worker(channels[side][1], plan.status) for side, plan in (("A", selected.first), ("B", selected.second))]
    require(all(channels[side][2].is_set() for side in ("A", "B")), "DUAL_HTTP_RESPONSE_NOT_OBSERVED")
    return {"case": case, "result": "PASS", "transport": "TWO_LOOPBACK_TCP_CLIENTS", "real_login_both": True,
            "http_requests_overlap_observed": True, "database_wait_observed": True, "http_statuses": statuses,
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
        team = shared.team_cases.Fixture.load(args.team_fixture)
        vote = shared.vote_cases.VoteFixture.load(args.vote_fixture)
        with rollback_connection(readonly=True) as conn:
            require(conn.execute("SELECT count(*) FROM pg_stat_activity WHERE datname=current_database() AND "
                                 "pid<>pg_backend_pid() AND backend_type='client backend'").fetchone() == (0,), "OTHER_CLIENTS_CONNECTED")
            shared.team_cases.validate_fixture(conn, team)
            shared.vote_cases.validate_fixture(conn, vote)
        for case, (source, _) in CASES.items():
            print(json.dumps(run_case(team if source.startswith("HRC") else vote, case)))
        return 0
    except Exception as exc:
        print(json.dumps({"result": "FAIL", **shared.vote_cases.diagnostic(exc)}))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
