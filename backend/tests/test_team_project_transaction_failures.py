"""Offline safeguards only; mocked tests do not establish actual deadlocks."""

from contextlib import contextmanager
import io
import json
from queue import Queue
import unittest
from unittest.mock import MagicMock, patch

import psycopg

from backend.tests import team_project_transaction_failures as runner
from backend.tests.team_project_concurrency import CheckFailed, Fixture
from backend.tests.test_team_project_concurrency_harness import manifest


class TransactionFailureSafetyTests(unittest.TestCase):
    def setUp(self):
        for target in ("backend.auth_store.dotenv_values", "backend.auth_store.psycopg.connect"):
            blocker = patch(target, side_effect=AssertionError("REAL_ENV_OR_DB_FORBIDDEN"))
            blocker.start()
            self.addCleanup(blocker.stop)
        self.fixture = Fixture.parse(manifest())
        self.success = {"ok": True, "sqlstate": None}
        self.deadlock = {"ok": False, "sqlstate": "40P01", "reason": "WORKER_FAILED"}

    def test_default_is_offline_and_does_not_report_runtime_pass(self):
        with patch("sys.stdout", new_callable=io.StringIO) as output:
            self.assertEqual(runner.main([]), 0)
        result = json.loads(output.getvalue())
        self.assertFalse(result["database_connected"])
        self.assertEqual(set(result["cases"]), {"RC07", "RC08"})
        self.assertNotIn('"PASS"', output.getvalue())

    def test_real_run_requires_manifest_before_connection(self):
        with patch("sys.stdout", new_callable=io.StringIO) as output:
            self.assertEqual(runner.main(["--run-rollback"]), 1)
        self.assertEqual(json.loads(output.getvalue())["reason"], "EXPLICIT_MANIFEST_REQUIRED")

    def test_deadlock_either_worker_may_be_victim(self):
        for first, second in ((self.deadlock, self.success), (self.success, self.deadlock)):
            with self.subTest(first=first):
                self.assertEqual(runner.verify_outcomes("RC08", first, second), "40P01")

    def test_deadlock_requires_one_victim_and_one_success_not_timeout_or_fake_error(self):
        for first, second in ((self.success, self.success), (self.deadlock, self.deadlock),
                              (self.success, {"ok": False, "sqlstate": "55P03", "reason": "WORKER_FAILED"}),
                              (self.success, {"ok": False, "sqlstate": "40P01", "reason": "OTHER"})):
            with self.subTest(first=first, second=second), self.assertRaises(CheckFailed):
                runner.verify_outcomes("RC08", first, second)

    def test_project_lock_requires_both_successes(self):
        self.assertIsNone(runner.verify_outcomes("RC07", self.success, self.success))
        with self.assertRaises(CheckFailed):
            runner.verify_outcomes("RC07", self.success, self.deadlock)

    def test_project_lock_holder_only_sets_actor_and_locks_project_without_team_lock(self):
        conn = MagicMock()
        runner.prepare(conn, self.fixture, "RC07", "A")
        self.assertEqual(conn.execute.call_count, 2)
        self.assertEqual(conn.execute.call_args.args,
                         ("SELECT public.v1_lock_project(%s)", (self.fixture.project_id,)))

    def test_injected_deadlock_uses_authorized_repository_write_for_each_actor(self):
        with patch.object(runner, "team_call") as call:
            for side, actor, team in (("A", "leader_a", "main"), ("B", "leader_c", "empty")):
                call.return_value = {"id": self.fixture.teams[team], "name": f"{self.fixture.namespace}.deadlock-{side}"}
                runner.prepare(MagicMock(), self.fixture, "RC08", side)
                self.assertEqual(call.call_args.args[2], self.fixture.users[actor])

    def test_survivor_requires_earlier_victim_write_to_have_rolled_back(self):
        conn = MagicMock()
        conn.execute.return_value.fetchone.return_value = ("still changed by victim",)
        with self.assertRaisesRegex(CheckFailed, "DEADLOCK_VICTIM_WRITE_NOT_RESTORED"):
            runner.complete(conn, self.fixture, {}, "RC08", "A")

    def test_project_update_checks_omitted_field_and_target_identity(self):
        with patch.object(runner, "project_call", return_value={
                "id": self.fixture.project_id, "name": f"{self.fixture.namespace}.project-lock-B",
                "description": "wrong"}), self.assertRaises(CheckFailed):
            runner.complete(MagicMock(), self.fixture, {"project_description": "baseline"}, "RC07", "B")

    def test_worker_reports_failure_only_after_rollback_and_without_private_error(self):
        conn, ready, done = MagicMock(), Queue(), Queue()

        @contextmanager
        def session(**kwargs):
            self.assertEqual(kwargs, {"lock_ms": 8000})
            try:
                yield conn
            finally:
                self.assertTrue(done.empty())

        with patch.object(runner, "rollback_connection", side_effect=session), \
                patch.object(runner, "validate_fixture", return_value={}), patch.object(runner, "prepare"), \
                patch.object(runner, "complete", side_effect=psycopg.errors.DeadlockDetected("private SQL")):
            runner.worker(self.fixture, "RC08", {}, ready, done)
        self.assertEqual(done.get_nowait(), self.deadlock)

    def test_bad_case_is_rejected_before_db_access(self):
        with self.assertRaisesRegex(CheckFailed, "UNKNOWN_CASE"):
            runner.run_case(self.fixture, "RC99")

    def test_orchestrator_always_checks_wait_and_cleanup_before_pass(self):
        observer, first, second = MagicMock(), MagicMock(), MagicMock()
        observer.execute.return_value.fetchone.side_effect = [(0,), (10,)]
        first.execute.return_value.fetchone.return_value = (20,)
        thread = MagicMock()

        @contextmanager
        def connection(**kwargs):
            yield observer if kwargs.get("readonly") else first

        def thread_factory(**kwargs):
            _, _, _, ready, done = kwargs["args"]
            thread.start.side_effect = lambda: (ready.put((second, 30)), done.put(self.success))
            return thread

        with patch.object(runner, "rollback_connection", side_effect=connection), \
                patch.object(runner, "validate_fixture", return_value={}), \
                patch.object(runner, "fingerprint", return_value="baseline"), \
                patch.object(runner, "prepare"), patch.object(runner, "Thread", side_effect=thread_factory), \
                patch.object(runner, "wait_for_block") as wait, patch.object(runner, "finish_worker") as finish:
            result = runner.run_case(self.fixture, "RC07")
        self.assertEqual(result["result"], "PASS")
        wait.assert_called_once_with(observer, 20, 30)
        finish.assert_called_once_with(thread, second)

    def test_first_worker_victim_rolls_back_before_survivor_cleanup(self):
        observer, first, second = MagicMock(), MagicMock(), MagicMock()
        observer.execute.return_value.fetchone.side_effect = [(0,), (1000,), (10,)]
        first.execute.return_value.fetchone.return_value = (20,)
        thread = MagicMock()
        first_exited = []

        @contextmanager
        def connection(**kwargs):
            if kwargs.get("readonly"):
                yield observer
            else:
                try:
                    yield first
                finally:
                    first_exited.append(True)

        def thread_factory(**kwargs):
            _, _, _, ready, done = kwargs["args"]
            thread.start.side_effect = lambda: (ready.put((second, 30)), done.put(self.success))
            return thread

        def cleanup(*args):
            self.assertEqual(first_exited, [True], "Victim still holds its failed transaction")

        with patch.object(runner, "rollback_connection", side_effect=connection), \
                patch.object(runner, "validate_fixture", return_value={}), \
                patch.object(runner, "fingerprint", return_value="baseline"), \
                patch.object(runner, "prepare"), patch.object(runner, "Thread", side_effect=thread_factory), \
                patch.object(runner, "complete", side_effect=psycopg.errors.DeadlockDetected("private SQL")), \
                patch.object(runner, "wait_for_block"), \
                patch.object(runner, "finish_worker", side_effect=cleanup):
            result = runner.run_case(self.fixture, "RC08")
        self.assertEqual(result["sqlstate"], "40P01")
        self.assertTrue(result["both_workers_rolled_back"])

    def test_excessive_deadlock_detection_time_is_not_changed_or_bypassed(self):
        observer = MagicMock()
        observer.execute.return_value.fetchone.side_effect = [(0,), (5000,)]

        @contextmanager
        def connection(**kwargs):
            self.assertEqual(kwargs, {"readonly": True})
            yield observer

        with patch.object(runner, "rollback_connection", side_effect=connection), \
                patch.object(runner, "validate_fixture", return_value={}), \
                patch.object(runner, "Thread") as thread, \
                self.assertRaisesRegex(CheckFailed, "DEADLOCK_DETECTION_EXCEEDS_TEST_DEADLINE"):
            runner.run_case(self.fixture, "RC08")
        thread.assert_not_called()
        self.assertTrue(all(c.args[0].lstrip().startswith("SELECT") for c in observer.execute.call_args_list))


if __name__ == "__main__":
    unittest.main()
