"""OFFLINE safeguards for the prepared runner; no .env or PostgreSQL access.

Mocked orchestration proves safety/control flow only, never PostgreSQL locking.
"""

from contextlib import contextmanager
import io
import json
from pathlib import Path
from queue import Queue
import unittest
from unittest.mock import MagicMock, patch

import psycopg

from backend.tests import team_project_concurrency as runner


def manifest():
    return {"version": 1, "database": runner.TEST_DB, "namespace": "spms-ct-" + "a" * 32,
            "users": {"leader_a": "1", "member_b": "2", "leader_c": "3", "free_student": "4"},
            "teams": {"main": "1", "empty": "2"}, "project_id": "1"}


class ConcurrencyHarnessSafetyTests(unittest.TestCase):
    def setUp(self):
        # Any unmocked attempt to open a real connection/read .env is an error.
        self.network = patch("backend.auth_store.psycopg.connect", side_effect=AssertionError("REAL_DB_FORBIDDEN"))
        self.env = patch("backend.auth_store.dotenv_values", side_effect=AssertionError("ENV_FORBIDDEN"))
        self.network.start()
        self.env.start()
        self.addCleanup(self.network.stop)
        self.addCleanup(self.env.stop)

    def test_default_plan_is_offline_and_six_cases_are_not_runtime_passes(self):
        with patch("sys.stdout", new_callable=io.StringIO) as output:
            self.assertEqual(runner.main([]), 0)
        result = json.loads(output.getvalue())
        self.assertFalse(result["database_connected"])
        self.assertEqual(set(result["cases"]), set(runner.CASES))
        self.assertEqual(len(result["cases"]), 6)
        self.assertNotIn('"PASS"', output.getvalue())

    def test_fixture_argument_alone_does_not_enable_database_execution(self):
        with patch("sys.stdout", new_callable=io.StringIO), patch.object(runner.Fixture, "load") as load:
            self.assertEqual(runner.main(["--fixture", "does-not-exist.json"]), 0)
        load.assert_not_called()

    def test_both_database_modes_require_an_explicit_manifest(self):
        for mode in ("--preflight", "--run-rollback"):
            with self.subTest(mode=mode), patch("sys.stdout", new_callable=io.StringIO) as output:
                self.assertEqual(runner.main([mode]), 1)
                self.assertEqual(json.loads(output.getvalue())["reason"], "EXPLICIT_MANIFEST_REQUIRED")

    def test_example_manifest_cannot_accidentally_target_real_ids(self):
        path = Path(__file__).with_name("fixtures") / "team_project_concurrency.example.json"
        with self.assertRaises(runner.CheckFailed):
            runner.Fixture.load(path)

    def test_manifest_rejects_main_db_extra_keys_ambiguous_and_invalid_ids(self):
        variants = []
        for key, value in (("database", "student_project_management"), ("namespace", "existing-team"),
                           ("version", True), ("password", "synthetic"), ("project_id", 1),
                           ("project_id", "9223372036854775808")):
            data = manifest()
            data[key] = value
            variants.append(data)
        for value in ("0", "-1", "1; SELECT 1", "01", "", True, None):
            data = manifest()
            data["users"]["leader_a"] = value
            variants.append(data)
        data = manifest()
        data["users"]["member_b"] = data["users"]["leader_a"]
        variants.append(data)
        data = manifest()
        data["teams"]["empty"] = data["teams"]["main"]
        variants.append(data)
        for data in variants:
            with self.subTest(data=data), self.assertRaises(runner.CheckFailed):
                runner.Fixture.parse(data)

    def test_valid_manifest_preserves_bigint_string_precision(self):
        data = manifest()
        data["project_id"] = "9223372036854775807"
        self.assertEqual(runner.Fixture.parse(data).project_id, data["project_id"])

    def fixture_connection(self, *, wrong_user=False, child=False):
        fixture = runner.Fixture.parse(manifest())
        rows = [(f"{fixture.namespace}.{label}@example.test", "student") for label in fixture.users]
        if wrong_user:
            rows[0] = ("an-existing-account@example.test", "student")
        rows += [(f"{fixture.namespace}.{label}",) for label in fixture.teams]
        rows += [[(1, 1, "leader"), (1, 2, "member"), (2, 3, "leader")],
                 [(1, 1, 1, f"{fixture.namespace}.project", "baseline description")],
                 (child,), (False,), (False,), (False,), (False,), (2,)]
        cursors = []
        for row in rows:
            cursor = MagicMock()
            cursor.fetchone.return_value = row
            cursor.fetchall.return_value = row
            cursors.append(cursor)
        conn = MagicMock()
        conn.execute.side_effect = cursors
        return conn, fixture

    def test_fixture_validation_checks_dedicated_identity_roster_and_phase_without_writes(self):
        conn, fixture = self.fixture_connection()
        with patch.object(runner, "assert_auth_connection"):
            state = runner.validate_fixture(conn, fixture)
        self.assertEqual(state, {"member_id": "2", "project_description": "baseline description"})
        for call in conn.execute.call_args_list:
            query = call.args[0]
            text = query if isinstance(query, str) else query.as_string()
            self.assertTrue(text.lstrip().startswith("SELECT"))

    def test_fixture_validation_rejects_existing_nonfixture_account_and_workflow_children(self):
        for option in ("wrong_user", "child"):
            conn, fixture = self.fixture_connection(**{option: True})
            with self.subTest(option=option), patch.object(runner, "assert_auth_connection"), \
                    self.assertRaises(runner.CheckFailed):
                runner.validate_fixture(conn, fixture)

    def test_real_fingerprint_logic_detects_changed_values_with_equal_row_counts(self):
        conn = MagicMock()
        name = "before"

        def execute(query):
            query = query if isinstance(query, str) else query.as_string()
            cursor = MagicMock()
            cursor.fetchall.return_value = [({"id": 1, "name": name},)] if "to_jsonb" in query else []
            return cursor

        conn.execute.side_effect = execute
        before = runner.fingerprint(conn)
        name = "after"
        self.assertNotEqual(before, runner.fingerprint(conn))

    def fake_connection(self):
        conn = MagicMock()
        conn.autocommit = False
        conn.info.transaction_status = psycopg.pq.TransactionStatus.IDLE
        conn.execute.return_value.fetchone.return_value = (runner.APP_ROLE, "read committed", "off")
        return conn

    def test_success_forces_rollback_and_never_calls_commit(self):
        conn = self.fake_connection()
        with patch.object(runner, "assert_auth_connection") as guard:
            with runner.rollback_connection(connector=lambda: conn) as actual:
                self.assertIs(actual, conn)
                guard.assert_called_once_with(conn)
        conn.transaction.assert_called_once_with(force_rollback=True)
        conn.rollback.assert_called_once()
        conn.close.assert_called_once()
        conn.commit.assert_not_called()

    def test_worker_exception_also_rolls_back_and_closes(self):
        conn = self.fake_connection()
        with patch.object(runner, "assert_auth_connection"), self.assertRaises(ValueError):
            with runner.rollback_connection(connector=lambda: conn):
                raise ValueError("synthetic")
        conn.rollback.assert_called_once()
        conn.close.assert_called_once()
        conn.commit.assert_not_called()

    def test_identity_mismatch_prevents_any_business_work(self):
        conn = self.fake_connection()
        conn.execute.return_value.fetchone.return_value = ("project_owner", "read committed", "off")
        with patch.object(runner, "assert_auth_connection"), self.assertRaises(runner.CheckFailed):
            with runner.rollback_connection(connector=lambda: conn):
                self.fail("Identity guard was bypassed")
        conn.rollback.assert_called_once()
        conn.close.assert_called_once()

    def test_existing_transaction_and_autocommit_are_rejected(self):
        for autocommit, status in ((True, psycopg.pq.TransactionStatus.IDLE),
                                   (False, psycopg.pq.TransactionStatus.INTRANS)):
            conn = self.fake_connection()
            conn.autocommit = autocommit
            conn.info.transaction_status = status
            with self.subTest(autocommit=autocommit), self.assertRaises(runner.CheckFailed):
                with runner.rollback_connection(connector=lambda: conn):
                    self.fail("Unsafe connection reached business work")
            conn.transaction.assert_not_called()
            conn.close.assert_called_once()

    def test_failed_rollback_still_closes_connection(self):
        conn = self.fake_connection()
        conn.rollback.side_effect = RuntimeError("synthetic cleanup failure")
        with patch.object(runner, "assert_auth_connection"), self.assertRaises(RuntimeError):
            with runner.rollback_connection(connector=lambda: conn):
                pass
        conn.close.assert_called_once()

    def test_preflight_uses_read_only_and_does_not_run_workers(self):
        conn = MagicMock()
        with patch.object(runner.Fixture, "load", return_value=runner.Fixture.parse(manifest())), \
                patch.object(runner, "rollback_connection") as sessions, \
                patch.object(runner, "validate_fixture") as validate, \
                patch.object(runner, "run_case") as run, patch("sys.stdout", new_callable=io.StringIO):
            sessions.return_value.__enter__.return_value = conn
            self.assertEqual(runner.main(["--preflight", "--fixture", "explicit.json"]), 0)
        sessions.assert_called_once_with(readonly=True)
        validate.assert_called_once()
        run.assert_not_called()

    def test_database_failure_never_prints_password_dsn_or_error_text(self):
        message = "synthetic password=DoNotPrintThis host=private"
        with patch.object(runner.Fixture, "load", side_effect=psycopg.errors.InsufficientPrivilege(message)), \
                patch("sys.stdout", new_callable=io.StringIO) as output:
            self.assertEqual(runner.main(["--preflight", "--fixture", "explicit.json"]), 1)
        self.assertNotIn(message, output.getvalue())
        self.assertEqual(json.loads(output.getvalue())["sqlstate"], "42501")

    def test_wait_requires_expected_postgresql_blocker_not_a_sleep(self):
        observer = MagicMock()
        observer.execute.return_value.fetchone.return_value = ([999],)
        with patch.object(runner.time, "monotonic", side_effect=[0, 0.01, 1]), \
                patch.object(runner.time, "sleep"), self.assertRaises(runner.CheckFailed):
            runner.wait_for_block(observer, 10, 20, timeout=0.5)
        observer.execute.assert_called_with("SELECT pg_blocking_pids(%s)", (20,))

    def test_wait_can_observe_blocker_after_a_poll(self):
        observer = MagicMock()
        observer.execute.return_value.fetchone.side_effect = [([],), ([10],)]
        with patch.object(runner.time, "sleep"):
            runner.wait_for_block(observer, 10, 20)
        self.assertEqual(observer.execute.call_count, 2)

    def test_worker_publishes_outcome_only_after_rollback_scope_exits(self):
        conn, ready, done = MagicMock(), Queue(), Queue()
        conn.execute.return_value.fetchone.return_value = (20,)

        @contextmanager
        def session(**kwargs):
            try:
                yield conn
            finally:
                self.assertTrue(done.empty(), "Outcome published before rollback")

        with patch.object(runner, "rollback_connection", side_effect=session), \
                patch.object(runner, "validate_fixture", return_value={}), \
                patch.object(runner, "action", side_effect=psycopg.errors.LockNotAvailable("private query")):
            runner.worker(runner.Fixture.parse(manifest()), "RC06", {}, ready, done)
        self.assertEqual(done.get_nowait(), {"ok": False, "sqlstate": "55P03", "reason": "WORKER_FAILED"})

    def test_cleanup_cancels_only_owned_worker_when_it_has_not_finished(self):
        thread, conn = MagicMock(), MagicMock()
        thread.is_alive.side_effect = [True, False]
        runner.finish_worker(thread, conn)
        conn.cancel.assert_called_once()
        self.assertEqual([call.kwargs["timeout"] for call in thread.join.call_args_list], [3, 12])

    def test_unstopped_worker_is_a_failure(self):
        thread = MagicMock()
        thread.is_alive.return_value = True
        with self.assertRaises(runner.CheckFailed):
            runner.finish_worker(thread, MagicMock())

    def run_stubbed_case(self, *, before="baseline", after="baseline", block_error=None, same_pid=False):
        observer, first, second = MagicMock(), MagicMock(), MagicMock()
        observer.execute.return_value.fetchone.return_value = (10,)
        first.execute.return_value.fetchone.return_value = (20,)
        fixture = runner.Fixture.parse(manifest())
        thread = MagicMock()

        @contextmanager
        def session(**kwargs):
            yield observer if kwargs.get("readonly") else first

        def construct(**kwargs):
            _, _, _, ready, done = kwargs["args"]
            thread.start.side_effect = lambda: (ready.put((second, 20 if same_pid else 30)),
                                                done.put({"ok": True, "sqlstate": None}))
            return thread

        with patch.object(runner, "rollback_connection", side_effect=session), \
                patch.object(runner, "validate_fixture", return_value={}), \
                patch.object(runner, "fingerprint", side_effect=[before, after]), \
                patch.object(runner, "action"), patch.object(runner, "Thread", side_effect=construct), \
                patch.object(runner, "wait_for_block", side_effect=block_error) as wait, \
                patch.object(runner, "finish_worker") as finish:
            try:
                return runner.run_case(fixture, "RC01")
            finally:
                finish.assert_called_once_with(thread, second)
                if not same_pid:
                    wait.assert_called_once_with(observer, 20, 30)

    def test_orchestrator_requires_wait_rollback_and_baseline_before_pass(self):
        result = self.run_stubbed_case()
        self.assertEqual(result["result"], "PASS")
        self.assertTrue(result["both_workers_rolled_back"])

    def test_orchestrator_rejects_changed_rows_even_with_same_counts(self):
        with self.assertRaisesRegex(runner.CheckFailed, "BASELINE_NOT_RESTORED"):
            self.run_stubbed_case(after="changed row content")

    def test_orchestrator_cleans_worker_and_fails_when_no_block_was_observed(self):
        with self.assertRaisesRegex(runner.CheckFailed, "NO_BLOCK"):
            self.run_stubbed_case(block_error=runner.CheckFailed("NO_BLOCK"))

    def test_orchestrator_rejects_reused_physical_session(self):
        with self.assertRaisesRegex(runner.CheckFailed, "SESSIONS_NOT_DISTINCT"):
            self.run_stubbed_case(same_pid=True)


if __name__ == "__main__":
    unittest.main()
