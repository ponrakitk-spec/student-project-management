"""Offline safeguards for two overlapping HTTP clients; no real network/PG."""

from contextlib import contextmanager
import io
import json
from queue import Empty, Queue
from threading import Event
import unittest
from unittest.mock import MagicMock, patch

import psycopg

from backend.tests import dual_http_concurrency as runner
from backend.tests.test_team_project_concurrency_harness import manifest as team_manifest
from backend.tests.test_topic_vote_concurrency import manifest as vote_manifest


class DualHttpSafetyTests(unittest.TestCase):
    def setUp(self):
        for target in ("backend.auth_store.psycopg.connect", "backend.auth_store.dotenv_values",
                       "database.tools.Test_Database.dotenv_values", "backend.tests.http_concurrency.socket.socket"):
            blocker = patch(target, side_effect=AssertionError("REAL_NETWORK_OR_CONFIG_FORBIDDEN"))
            blocker.start()
            self.addCleanup(blocker.stop)
        self.team = runner.shared.team_cases.Fixture.parse(team_manifest())
        self.vote = runner.shared.vote_cases.VoteFixture.parse(vote_manifest())
        self.state = {"member_id": "20", "project_description": None}

    def test_default_and_manifest_arguments_alone_are_offline(self):
        for args in ([], ["--team-fixture", "missing.json", "--vote-fixture", "missing2.json"]):
            with patch("sys.stdout", new_callable=io.StringIO) as output:
                self.assertEqual(runner.main(args), 0)
            result = json.loads(output.getvalue())
            self.assertFalse(result["database_connected"])
            self.assertFalse(result["new_persistent_fixture_required"])
            self.assertEqual(len(result["cases"]), 9)
            self.assertNotIn('"PASS"', output.getvalue())

    def test_runtime_requires_both_manifests_before_loading(self):
        with patch.object(runner.shared.team_cases.Fixture, "load") as load, patch("sys.stdout", new_callable=io.StringIO) as output:
            self.assertEqual(runner.main(["--run-rollback"]), 1)
        load.assert_not_called()
        self.assertEqual(json.loads(output.getvalue())["reason"], "BOTH_MANIFESTS_REQUIRED")

    def test_bad_manifest_stops_before_connecting(self):
        with patch.object(runner.shared.team_cases.Fixture, "load", side_effect=runner.CheckFailed("MANIFEST_DATABASE")), \
                patch.object(runner, "rollback_connection") as connect, patch("sys.stdout", new_callable=io.StringIO):
            self.assertEqual(runner.main(["--run-rollback", "--team-fixture", "bad.json", "--vote-fixture", "bad2.json"]), 1)
        connect.assert_not_called()

    def test_every_plan_has_distinct_real_fixture_actors_and_known_uow(self):
        for case, (source, _) in runner.CASES.items():
            fixture = self.team if source.startswith("HRC") else self.vote
            plan = runner.plans(fixture, case, self.state)
            self.assertNotEqual(plan.first.actor, plan.second.actor)
            self.assertIn(plan.first.actor, fixture.users.values())
            self.assertIn(plan.second.actor, fixture.users.values())
            self.assertIn(plan.manager, runner.shared.MANAGERS.values())
            for request in (plan.first, plan.second):
                self.assertNotIn("actor_user_id", request.body or {})
                self.assertTrue(request.path.startswith("/api/v1/"))

    def test_transfer_competes_with_member_leave_and_both_votes_have_different_users(self):
        transfer = runner.plans(self.team, "DH01", self.state)
        self.assertEqual(transfer.first.path, "/api/v1/teams/me/leader")
        self.assertEqual(transfer.second.path, "/api/v1/teams/me/leave")
        votes = runner.plans(self.vote, "DH08", self.state)
        self.assertEqual(votes.first.actor, self.vote.users["b"])
        self.assertEqual(votes.second.actor, self.vote.users["c"])

    def test_invalid_actor_is_rejected_before_connection_or_dml(self):
        connect = MagicMock()
        with self.assertRaisesRegex(runner.CheckFailed, "HTTP_ACTOR_NOT_IN_FIXTURE"):
            with runner.shared.http_connection(self.team, "HRC02", connector=connect, actor="999999"):
                pass
        connect.assert_not_called()

    def test_gate_ignores_auth_and_unarmed_callbacks(self):
        manager = object()
        gate = runner.RequestGate(manager)
        gate(manager)
        gate.armed.set()
        gate(object())
        self.assertFalse(gate.held.is_set())

    def test_gate_holds_only_matching_business_uow_once_and_is_bounded(self):
        manager = object()
        gate = runner.RequestGate(manager)
        gate.armed.set()
        gate.release = MagicMock()
        gate.release.wait.return_value = True
        gate(manager)
        gate(manager)
        self.assertTrue(gate.held.is_set())
        gate.release.wait.assert_called_once_with(timeout=12)

    def test_gate_timeout_is_an_error_not_silent_success(self):
        manager = object()
        gate = runner.RequestGate(manager)
        gate.armed.set()
        gate.release = MagicMock()
        gate.release.wait.return_value = False
        with self.assertRaisesRegex(runner.CheckFailed, "DUAL_HTTP_GATE_TIMEOUT"):
            gate(manager)

    def test_callback_occurs_before_uow_exit_without_replacing_repository(self):
        events = []
        @contextmanager
        def manager(conn):
            events.append("uow_enter")
            yield "repository"
            events.append("uow_exit")
        def callback(actual):
            self.assertIs(actual, manager)
            events.append("callback")
        with patch.dict(runner.shared.MANAGERS, {key: manager for key in runner.shared.MANAGERS}):
            app = runner.shared.request_app(MagicMock(), [], on_complete=callback)
            with app.dependency_overrides[runner.shared.get_team_uow]()() as store:
                self.assertEqual(store, "repository")
                events.append("operation")
        self.assertEqual(events, ["uow_enter", "operation", "callback", "uow_exit"])

    def test_ready_failure_preserves_only_fixed_reason_and_sqlstate(self):
        ready, done = MagicMock(), Queue()
        ready.get.side_effect = Empty
        done.put({"ok": False, "sqlstate": "42501", "reason": "WORKER_FAILED"})
        with self.assertRaises(runner.CheckFailed) as error:
            runner.ready_worker(ready, done)
        self.assertEqual(error.exception.sqlstate, "42501")
        self.assertEqual(str(error.exception), "DUAL_HTTP_WORKER_NOT_READY")

    def test_result_requires_expected_status_and_preserves_worker_sqlstate(self):
        for result in ({"ok": True, "http_status": 200, "sqlstate": None},
                       {"ok": False, "sqlstate": "55P03", "reason": "WORKER_FAILED"}):
            queue = Queue()
            queue.put(result)
            with self.assertRaises(runner.CheckFailed):
                runner.result_worker(queue, 201)
        with self.assertRaisesRegex(runner.CheckFailed, "DUAL_HTTP_RESULT_MISSING"):
            runner.result_worker(Queue(), 201)

    def test_worker_reports_after_server_and_outer_rollback(self):
        conn, done, ready, returned, events = MagicMock(), Queue(), Queue(), Event(), []
        selected = runner.plans(self.team, "DH01", self.state)
        gate = runner.RequestGate(selected.manager)
        @contextmanager
        def connection(*args, **kwargs):
            self.assertEqual(kwargs["actor"], selected.first.actor)
            try:
                yield conn
            finally:
                self.assertTrue(done.empty())
                events.append("rollback")
        @contextmanager
        def client(*args):
            try:
                yield MagicMock()
            finally:
                events.append("server_closed")
        with patch.object(runner.shared, "http_connection", connection), patch.object(runner.shared, "live_client", client), \
                patch.object(runner.shared, "request_app"), patch.object(runner.shared, "authenticate"), \
                patch.object(runner.shared, "http_call"), patch.object(runner, "verify_first"):
            runner.worker(self.team, "DH01", self.state, selected.first, "A", gate, ready, done, returned)
        self.assertEqual(events, ["server_closed", "rollback"])
        self.assertTrue(returned.is_set())
        self.assertFalse(gate.armed.is_set())
        self.assertTrue(done.get_nowait()["ok"])

    def test_worker_failure_never_exposes_password_or_sql(self):
        done = Queue()
        plan = runner.plans(self.team, "DH01", self.state)
        with patch.object(runner.shared, "http_connection", side_effect=psycopg.OperationalError("SyntheticPrivatePassword")):
            runner.worker(self.team, "DH01", self.state, plan.first, "A", runner.RequestGate(plan.manager), Queue(), done, Event())
        result = done.get_nowait()
        self.assertFalse(result["ok"])
        self.assertNotIn("SyntheticPrivatePassword", json.dumps(result))

    def orchestration(self, *, wait=True, early_first=False, early_second=False,
                      public_drift=False, auth_drift=False, cleanup_error=False, worker_ok=True):
        observer = MagicMock()
        observer.execute.return_value.fetchone.return_value = (30,)
        created, cleaned, gates = [], [], []
        fixture = self.team
        selected = runner.plans(fixture, "DH01", self.state)
        channels = {}
        def thread_factory(*, target, args, daemon):
            self.assertIs(target, runner.worker)
            self.assertTrue(daemon)
            _, _, _, plan, side, gate, ready, done, returned = args
            thread = MagicMock()
            thread.side = side
            created.append(side)
            gates.append(gate)
            channels[side] = (plan, done, returned)
            def start():
                ready.put((MagicMock(), 10 if side == "A" else 20))
                if side == "A":
                    gate.held.set()
                if (side == "A" and early_first) or (side == "B" and early_second):
                    returned.set()
            thread.start.side_effect = start
            return thread
        def finish(thread, conn):
            self.assertTrue(gates[0].release.is_set(), "Always release gate before joining")
            cleaned.append(thread.side)
            if cleanup_error and thread.side == "A":
                raise runner.CheckFailed("CLEANUP_FAILED")
            plan, done, returned = channels[thread.side]
            returned.set()
            done.put({"ok": True, "http_status": plan.status, "sqlstate": None} if worker_ok else
                     {"ok": False, "sqlstate": "42501", "reason": "WORKER_FAILED"})
        with patch.object(runner, "baseline", side_effect=["before", "after" if auth_drift else "before"]), \
                patch.object(runner, "rollback_connection") as connection, patch.object(runner.shared, "validate", return_value=self.state), \
                patch.object(runner, "fingerprint", side_effect=["before", "after" if public_drift else "before"]), \
                patch.object(runner, "Thread", side_effect=thread_factory), \
                patch.object(runner, "wait_for_block", side_effect=None if wait else runner.CheckFailed("NO_DATABASE_BLOCK")) as observed, \
                patch.object(runner, "finish_worker", side_effect=finish):
            connection.return_value.__enter__.return_value = observer
            try:
                return runner.run_case(fixture, "DH01")
            finally:
                self.assertEqual(cleaned, created)
                if not early_first:
                    observed.assert_called_once_with(observer, 10, 20)

    def test_two_pending_responses_and_database_block_are_required(self):
        result = self.orchestration()
        self.assertTrue(result["http_requests_overlap_observed"])
        self.assertTrue(result["database_wait_observed"])
        self.assertEqual(result["http_statuses"], [200, 204])

    def test_early_response_is_never_reported_as_overlap(self):
        for options in ({"early_first": True}, {"early_second": True}):
            with self.assertRaises(runner.CheckFailed):
                self.orchestration(**options)

    def test_missing_database_block_fails_and_still_releases_both_workers(self):
        with self.assertRaisesRegex(runner.CheckFailed, "NO_DATABASE_BLOCK"):
            self.orchestration(wait=False)

    def test_public_or_auth_baseline_drift_never_becomes_pass(self):
        for options in ({"public_drift": True}, {"auth_drift": True}):
            with self.assertRaises(runner.CheckFailed):
                self.orchestration(**options)

    def test_both_cleanups_are_attempted_even_if_first_cleanup_fails(self):
        with self.assertRaisesRegex(runner.CheckFailed, "CLEANUP_FAILED"):
            self.orchestration(cleanup_error=True)

    def test_worker_error_preserves_sqlstate_and_fixed_reason(self):
        with self.assertRaises(runner.CheckFailed) as error:
            self.orchestration(worker_ok=False)
        self.assertEqual(error.exception.sqlstate, "42501")

    def test_unknown_case_stops_before_database_snapshot(self):
        with patch.object(runner, "baseline") as snapshot, self.assertRaises(runner.CheckFailed):
            runner.run_case(self.team, "UNKNOWN")
        snapshot.assert_not_called()


if __name__ == "__main__":
    unittest.main()
