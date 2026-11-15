"""Offline safeguards only; mocked orchestration is not live HTTP/PG evidence."""

from contextlib import contextmanager
import io
import json
from queue import Queue
from threading import Event
import unittest
from unittest.mock import MagicMock, patch

import psycopg

from backend.tests import evaluation_http_concurrency as runner
from backend.tests.test_evaluation_concurrency import manifest


class EvaluationHttpSafetyTests(unittest.TestCase):
    def setUp(self):
        for target in ("backend.auth_store.psycopg.connect", "backend.auth_store.dotenv_values",
                       "database.tools.Test_Database.dotenv_values", "backend.tests.http_concurrency.socket.socket"):
            blocker = patch(target, side_effect=AssertionError("REAL_NETWORK_OR_CONFIG_FORBIDDEN"))
            blocker.start()
            self.addCleanup(blocker.stop)
        self.fixture = runner.database_cases.EvaluationFixture.parse(manifest())

    def test_default_and_manifest_argument_alone_are_offline(self):
        for args in ([], ["--fixture", "missing.json"]):
            with patch("sys.stdout", new_callable=io.StringIO) as output:
                self.assertEqual(runner.main(args), 0)
            result = json.loads(output.getvalue())
            self.assertFalse(result["database_connected"])
            self.assertFalse(result["new_persistent_fixture_required"])
            self.assertFalse(result["winner_commit_available"])
            self.assertEqual(len(result["cases"]), 10)

    def test_runtime_requires_manifest_before_connection(self):
        with patch.object(runner.database_cases.EvaluationFixture, "load") as load, patch("sys.stdout", new_callable=io.StringIO) as output:
            self.assertEqual(runner.main(["--run-rollback"]), 1)
        load.assert_not_called()
        self.assertEqual(json.loads(output.getvalue())["reason"], "EXPLICIT_MANIFEST_REQUIRED")

    def test_bad_manifest_stops_before_connection(self):
        with patch.object(runner.database_cases.EvaluationFixture, "load", side_effect=runner.CheckFailed("WRONG_DATABASE")), \
                patch.object(runner, "rollback_connection") as connect, patch("sys.stdout", new_callable=io.StringIO):
            self.assertEqual(runner.main(["--run-rollback", "--fixture", "bad.json"]), 1)
        connect.assert_not_called()

    def test_apply_and_winner_commit_options_do_not_exist(self):
        for option in ("--apply", "--commit"):
            with patch("sys.stderr", new_callable=io.StringIO), self.assertRaises(SystemExit):
                runner.main([option])

    def test_plans_cover_five_mixed_and_five_distinct_actor_http_pairs(self):
        counts = {1: 0, 2: 0}
        for case in runner.CASES:
            plans = runner.plans(self.fixture, case)
            http = [p for p in (plans.first, plans.second) if p]
            counts[len(http)] += 1
            if len(http) == 2:
                self.assertNotEqual(http[0].actor, http[1].actor)
            for plan in http:
                self.assertIn(plan.actor, self.fixture.users.values())
                self.assertNotIn("actor_user_id", plan.body or {})
                self.assertTrue(plan.path.endswith("/evaluations"))
                self.assertEqual(plan.status, 201 if plan.method == "POST" else 200)
        self.assertEqual(counts, {1: 5, 2: 5})
        for case, actor in (("EH07", "leader_final"), ("EH08", "advisor"), ("EH09", "coordinator")):
            self.assertEqual(runner.plans(self.fixture, case).second.actor, self.fixture.users[actor])

    def test_unknown_case_and_external_actor_stop_before_connections(self):
        with self.assertRaises(runner.CheckFailed):
            runner.plans(self.fixture, "UNKNOWN")
        connector = MagicMock()
        with self.assertRaises(runner.CheckFailed):
            with runner.http_connection(self.fixture, "999", connector=connector):
                pass
        connector.assert_not_called()

    def test_http_credential_fixture_always_rolls_back_and_restores_app_role(self):
        conn, events = MagicMock(), []
        conn.execute.return_value.fetchone.return_value = (runner.TEST_DB, "project_app", "read committed")
        cur = conn.cursor.return_value.__enter__.return_value
        cur.fetchone.side_effect = [("project_owner", False), (False,)]
        @contextmanager
        def transaction(**kwargs):
            self.assertEqual(kwargs, {"force_rollback": True})
            try:
                yield
            finally:
                events.append("rollback")
        conn.transaction.side_effect = transaction
        with patch.object(runner, "switch") as switch, patch.object(runner, "assert_auth_connection"), \
                patch.object(runner.database_cases, "validate_fixture"), patch.object(runner.shared, "encoded_password", return_value="test hash"):
            with self.assertRaisesRegex(RuntimeError, "operation failed"):
                with runner.http_connection(self.fixture, self.fixture.users["b"], connector=lambda: conn):
                    self.assertEqual(switch.call_args.args[1], "project_app")
                    raise RuntimeError("operation failed")
        self.assertEqual(events, ["rollback"])
        conn.commit.assert_not_called()
        conn.rollback.assert_called()
        conn.close.assert_called_once()

    def test_existing_credential_is_not_overwritten_or_used_as_fallback(self):
        conn = MagicMock()
        cur = conn.cursor.return_value.__enter__.return_value
        cur.fetchone.side_effect = [("project_owner", False), (True,)]
        with patch.object(runner, "switch"), patch.object(runner, "assert_auth_connection"), \
                patch.object(runner.database_cases, "validate_fixture"), self.assertRaises(runner.CheckFailed):
            with runner.http_connection(self.fixture, self.fixture.users["b"], connector=lambda: conn):
                self.fail("Must not serve")
        self.assertFalse(any("INSERT INTO" in str(c.args[0]) for c in cur.execute.call_args_list))
        conn.close.assert_called_once()

    def test_readers_reject_partial_score_or_individual_leaks(self):
        plan = runner.plans(self.fixture, "EH09").second
        for data in ({"project": {"id": self.fixture.projects["final"]}, "summary": None, "evaluations": [{"score": 60}]},
                     {"project": {"id": self.fixture.projects["final"]}, "summary": {"total_score": "130"}, "evaluations": []}):
            response = MagicMock()
            response.json.return_value = {"data": data}
            with self.assertRaises(runner.CheckFailed):
                runner.verify_response(None, None, self.fixture, "EH09", "B", plan, response, [])

    def test_post_response_rejects_wrong_actor_score_and_extra_fields(self):
        plan = runner.plans(self.fixture, "EH06").second
        for data in ({"id": "10", "score": 80, "comment": runner.database_cases.COMMENT, "created_at": "now"},
                     {"id": "10", "score": 90, "comment": runner.database_cases.COMMENT, "created_at": "now", "advisor_id": "1"}):
            response = MagicMock()
            response.json.return_value = {"data": data}
            with self.assertRaises(runner.CheckFailed):
                runner.verify_response(None, None, self.fixture, "EH06", "B", plan, response, [])

    def test_http_worker_closes_server_before_outer_rollback_and_result(self):
        conn, ready, done, returned, events = MagicMock(), Queue(), Queue(), Event(), []
        plan = runner.plans(self.fixture, "EH06").first
        gate = runner.RequestGate(runner.shared.evaluation_transaction_on)
        @contextmanager
        def connection(*args):
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
        with patch.object(runner, "http_connection", connection), patch.object(runner.shared, "live_client", client), \
                patch.object(runner.shared, "request_app"), patch.object(runner.shared, "authenticate"), \
                patch.object(runner.shared, "http_call"), patch.object(runner, "verify_response"):
            runner.worker(self.fixture, None, "EH06", "A", plan, gate, ready, done, returned)
        self.assertEqual(events, ["server_closed", "rollback"])
        self.assertTrue(returned.is_set())
        self.assertFalse(gate.armed.is_set())
        self.assertTrue(done.get_nowait()["ok"])

    def test_repository_worker_uses_no_http_and_rolls_back(self):
        ready, done, returned = Queue(), Queue(), Event()
        gate = runner.RequestGate(runner.shared.evaluation_transaction_on)
        with patch.object(runner, "rollback_connection") as connection, patch.object(runner.database_cases, "validate_fixture", return_value=None), \
                patch.object(runner.database_cases, "action") as action, patch.object(runner.shared, "live_client") as http:
            runner.worker(self.fixture, None, "EH01", "B", None, gate, ready, done, returned)
        connection.assert_called_once_with()
        action.assert_called_once()
        http.assert_not_called()
        self.assertEqual(done.get_nowait(), {"ok": True, "http_status": None, "sqlstate": None})

    def test_worker_failure_redacts_private_error(self):
        plan = runner.plans(self.fixture, "EH06").first
        done = Queue()
        with patch.object(runner, "http_connection", side_effect=psycopg.OperationalError("SyntheticPrivatePassword")):
            runner.worker(self.fixture, None, "EH06", "A", plan, None, Queue(), done, Event())
        result = done.get_nowait()
        self.assertFalse(result["ok"])
        self.assertNotIn("SyntheticPrivatePassword", json.dumps(result))

    def orchestration(self, *, case="EH06", blocked=True, early=False, public_drift=False, auth_drift=False, fail_cleanup=False):
        observer = MagicMock()
        observer.execute.return_value.fetchone.return_value = (30,)
        channels, gates, clean = {}, [], []
        def thread_factory(*, target, args, daemon):
            self.assertIs(target, runner.worker)
            _, _, _, side, plan, gate, ready, done, returned = args
            gates.append(gate)
            channels[side] = returned
            thread = MagicMock()
            def start():
                ready.put((MagicMock(), 10 if side == "A" else 20))
                done.put({"ok": True, "http_status": plan.status if plan else None, "sqlstate": None})
                if side == "A":
                    gate.held.set()
                if early:
                    returned.set()
            thread.start.side_effect = start
            thread.side = side
            return thread
        def finish(thread, conn):
            self.assertTrue(gates[0].release.is_set())
            clean.append(thread.side)
            channels[thread.side].set()
            if fail_cleanup and thread.side == "A":
                raise runner.CheckFailed("CLEANUP_FAILED")
        try:
            with patch.object(runner, "baseline", side_effect=["before", "changed" if auth_drift else "before"]), \
                    patch.object(runner, "rollback_connection") as connection, \
                    patch.object(runner.database_cases, "validate_fixture", return_value=None), \
                    patch.object(runner, "fingerprint", side_effect=["before", "changed" if public_drift else "before"]), \
                    patch.object(runner, "Thread", side_effect=thread_factory), \
                    patch.object(runner, "finish_worker", side_effect=finish), \
                    patch.object(runner, "wait_for_block", side_effect=None if blocked else runner.CheckFailed("NO_BLOCK")) as wait:
                connection.return_value.__enter__.return_value = observer
                result = runner.run_case(self.fixture, case)
                wait.assert_called_once_with(observer, 10, 20)
                return result
        finally:
            self.assertEqual(clean, ["A"] if early else ["A", "B"])

    def test_distinct_pids_observed_wait_and_two_pending_requests_required(self):
        self.assertEqual(self.orchestration()["transport"], "TWO_LOOPBACK_TCP_CLIENTS")

    def test_mixed_pair_counts_only_one_http_login(self):
        self.assertEqual(self.orchestration(case="EH01")["real_login_http_workers"], 1)

    def test_missing_database_wait_is_fail(self):
        with self.assertRaisesRegex(runner.CheckFailed, "NO_BLOCK"):
            self.orchestration(blocked=False)

    def test_early_response_cannot_be_reported_as_overlap(self):
        with self.assertRaisesRegex(runner.CheckFailed, "FIRST_RETURNED_EARLY"):
            self.orchestration(early=True)

    def test_public_or_auth_drift_is_fail(self):
        for options in ({"public_drift": True}, {"auth_drift": True}):
            with self.assertRaises(runner.CheckFailed):
                self.orchestration(**options)

    def test_cleanup_error_still_attempts_both_workers(self):
        with self.assertRaisesRegex(runner.CheckFailed, "CLEANUP_FAILED"):
            self.orchestration(fail_cleanup=True)


if __name__ == "__main__":
    unittest.main()
