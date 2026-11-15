"""RC07/RC08 against the existing approved fixture; all workers ROLLBACK.

RC08 intentionally inverts two Team locks ONLY in this test. A 40P01 is an
expected injected failure, not evidence the application's lock order deadlocks.
Default invocation is offline. No seed/COMMIT/HTTP/retry behavior is added.
"""

import argparse
import json
from pathlib import Path
from queue import Empty, Queue
from threading import Thread

from backend.tests.team_project_concurrency import (
    CheckFailed, Fixture, fingerprint, finish_worker, project_call, require,
    rollback_connection, sanitized_failure, team_call, validate_fixture, wait_for_block,
)

CASES = {"RC07": "Project update waits on a directly held Project lock",
         "RC08": "Injected two-Team deadlock produces one 40P01 and rolls back both writes"}


def set_actor(conn, actor):
    conn.execute("SELECT set_config('app.actor_user_id',%s,true)", (actor,))


def prepare(conn, fixture, case, side):
    if case == "RC07":
        if side == "A":
            set_actor(conn, fixture.users["leader_a"])
            conn.execute("SELECT public.v1_lock_project(%s)", (fixture.project_id,))
    elif case == "RC08":
        team = "main" if side == "A" else "empty"
        actor = fixture.users["leader_a" if side == "A" else "leader_c"]
        result = team_call(conn, "update", actor, {"name": f"{fixture.namespace}.deadlock-{side}"})
        require(result["id"] == fixture.teams[team] and
                result["name"] == f"{fixture.namespace}.deadlock-{side}", "EARLIER_WRITE_NOT_OBSERVED")
    else:
        raise CheckFailed("UNKNOWN_CASE")


def complete(conn, fixture, state, case, side):
    if case == "RC07":
        if side == "B":
            result = project_call(conn, "update", fixture.users["leader_a"],
                                  {"name": f"{fixture.namespace}.project-lock-B"})
            require(result["id"] == fixture.project_id and
                    result["name"] == f"{fixture.namespace}.project-lock-B" and
                    result["description"] == state["project_description"], "PROJECT_UPDATE_MISMATCH")
    elif case == "RC08":
        target = "empty" if side == "A" else "main"
        # Deliberately opposite order for error injection; no raw UPDATE grant.
        conn.execute("SELECT public.v1_lock_team(%s)", (fixture.teams[target],))
        require(conn.execute("SELECT name FROM public.teams WHERE id=%s",
                             (fixture.teams[target],)).fetchone() ==
                (f"{fixture.namespace}.{target}",), "DEADLOCK_VICTIM_WRITE_NOT_RESTORED")
    else:
        raise CheckFailed("UNKNOWN_CASE")
    conn.execute("SET CONSTRAINTS ALL IMMEDIATE")


def worker(fixture, case, state, ready, done):
    try:
        with rollback_connection(lock_ms=8000) as conn:
            require(validate_fixture(conn, fixture) == state, "WORKER_BASELINE_CHANGED")
            prepare(conn, fixture, case, "B")
            ready.put((conn, conn.execute("SELECT pg_backend_pid()").fetchone()[0]))
            complete(conn, fixture, state, case, "B")
        done.put({"ok": True, "sqlstate": None})
    except Exception as exc:
        done.put(sanitized_failure(exc))


def verify_outcomes(case, first, second):
    if case == "RC07":
        require(first == second == {"ok": True, "sqlstate": None}, "PROJECT_LOCK_OUTCOME_MISMATCH")
        return None
    require(case == "RC08", "UNKNOWN_CASE")
    victims = [row for row in (first, second) if row ==
               {"ok": False, "sqlstate": "40P01", "reason": "WORKER_FAILED"}]
    successes = [row for row in (first, second) if row == {"ok": True, "sqlstate": None}]
    require(len(victims) == len(successes) == 1, "EXPECTED_EXACTLY_ONE_DEADLOCK_VICTIM")
    return "40P01"


def run_case(fixture, case):
    require(case in CASES, "UNKNOWN_CASE")
    ready, done = Queue(), Queue()
    thread = None
    worker_conn = None
    orchestration_failure = None
    first_outcome = {"ok": True, "sqlstate": None}
    with rollback_connection(readonly=True) as observer:
        state = validate_fixture(observer, fixture)
        require(observer.execute("""SELECT count(*) FROM pg_stat_activity
            WHERE datname=current_database() AND pid<>pg_backend_pid()
            AND backend_type='client backend'""").fetchone() == (0,), "OTHER_CLIENTS_CONNECTED")
        if case == "RC08":
            timeout = observer.execute("SELECT setting::int FROM pg_settings "
                                       "WHERE name='deadlock_timeout' AND unit='ms'").fetchone()
            require(timeout is not None and 0 < timeout[0] < 4000, "DEADLOCK_DETECTION_EXCEEDS_TEST_DEADLINE")
        before = fingerprint(observer)
        try:
            try:
                with rollback_connection(lock_ms=8000) as first:
                    require(validate_fixture(first, fixture) == state, "FIRST_BASELINE_CHANGED")
                    first_pid = first.execute("SELECT pg_backend_pid()").fetchone()[0]
                    observer_pid = observer.execute("SELECT pg_backend_pid()").fetchone()[0]
                    prepare(first, fixture, case, "A")
                    thread = Thread(target=worker, args=(fixture, case, state, ready, done), daemon=True)
                    thread.start()
                    try:
                        worker_conn, worker_pid = ready.get(timeout=10)
                    except Empty:
                        raise CheckFailed("WORKER_NOT_READY") from None
                    require(len({first_pid, worker_pid, observer_pid}) == 3, "SESSIONS_NOT_DISTINCT")
                    wait_for_block(observer, first_pid, worker_pid)
                    # RC07 releases A's sole Project lock via ROLLBACK here.
                    # RC08 asks for B's Team lock, completing the injected cycle.
                    if case == "RC08":
                        try:
                            complete(first, fixture, state, case, "A")
                        except Exception as exc:
                            first_outcome = sanitized_failure(exc)
                            raise
            except Exception:
                if first_outcome["ok"]:
                    raise
                # A's failed root transaction has now ROLLBACKed. Never keep
                # the victim open while waiting for the other worker to finish.
        except Exception as exc:
            orchestration_failure = exc
        finally:
            if thread is not None:
                finish_worker(thread, worker_conn)
        require(fingerprint(observer) == before, "BASELINE_NOT_RESTORED")
        require(validate_fixture(observer, fixture) == state, "FIXTURE_NOT_RESTORED")
        if orchestration_failure is not None:
            raise orchestration_failure
        try:
            second_outcome = done.get_nowait()
        except Empty:
            raise CheckFailed("WORKER_RESULT_MISSING") from None
        sqlstate = verify_outcomes(case, first_outcome, second_outcome)
        return {"case": case, "result": "PASS", "wait_observed": True,
                "distinct_connections": 3, "both_workers_rolled_back": True,
                "public_rows_metadata_restored": True, "sqlstate": sqlstate,
                "automatic_retry": False}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-rollback", action="store_true")
    parser.add_argument("--fixture", type=Path)
    args = parser.parse_args(argv)
    try:
        if not args.run_rollback:
            print(json.dumps({"mode": "OFFLINE_PLAN", "database_connected": False, "cases": CASES}))
            return 0
        require(args.fixture is not None, "EXPLICIT_MANIFEST_REQUIRED")
        fixture = Fixture.load(args.fixture)
        for case in CASES:
            print(json.dumps(run_case(fixture, case)))
        return 0
    except Exception as exc:
        print(json.dumps({"result": "FAIL", **sanitized_failure(exc)}))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
