"""Offline runner safeguards; mock orchestration is not PostgreSQL locking."""

from contextlib import contextmanager
import io
import json
from pathlib import Path
from queue import Queue
import unittest
from unittest.mock import MagicMock, patch

import psycopg

from backend.auth_store import StorageUnavailable
from backend.tests import topic_vote_concurrency as runner


def manifest():
    return {"version": 1, "database": runner.TEST_DB, "namespace": "spms-vc-" + "a" * 32,
            "users": {key: str(index) for index, key in enumerate(runner.USER_ROLES, 1)},
            "teams": {"main": "1", "revision": "2"}, "projects": {"main": "1", "revision": "2"},
            "submissions": {"main": "1", "revision": "2"},
            "assignments": {"main": {"b": "1", "c": "2", "d": "3"}, "revision": {"b": "4", "c": "5", "d": "6"}}}


class TopicConcurrencySafetyTests(unittest.TestCase):
    def setUp(self):
        for target in ("backend.auth_store.dotenv_values", "backend.auth_store.psycopg.connect"):
            blocker = patch(target, side_effect=AssertionError("REAL_CONFIG_OR_DB_FORBIDDEN"))
            blocker.start()
            self.addCleanup(blocker.stop)

    def test_default_plan_and_fixture_argument_alone_are_offline(self):
        for args in ([], ["--fixture", "missing.json"]):
            with patch("sys.stdout", new_callable=io.StringIO) as output, patch.object(runner.VoteFixture, "load") as load:
                self.assertEqual(runner.main(args), 0)
            result = json.loads(output.getvalue())
            self.assertFalse(result["database_connected"])
            self.assertEqual(len(result["cases"]), 8)
            self.assertNotIn('"PASS"', output.getvalue())
            load.assert_not_called()

    def test_runtime_modes_require_explicit_manifest_and_apply_is_absent(self):
        for flag in ("--preflight", "--run-rollback"):
            with patch("sys.stdout", new_callable=io.StringIO) as output:
                self.assertEqual(runner.main([flag]), 1)
            self.assertEqual(json.loads(output.getvalue())["reason"], "EXPLICIT_MANIFEST_REQUIRED")
        with patch("sys.stderr", new_callable=io.StringIO), self.assertRaises(SystemExit):
            runner.main(["--apply"])

    def test_manifest_rejects_main_database_secrets_invalid_ids_and_duplicate_entities(self):
        variants = []
        for key, value in (("database", "student_project_management"), ("namespace", "existing-team"),
                           ("password", "SyntheticPrivateValue"), ("version", True)):
            data = manifest()
            data[key] = value
            variants.append(data)
        for value in (0, "0", "01", "-1", "1; SELECT 1", "9223372036854775808", None, True):
            data = manifest()
            data["projects"]["main"] = value
            variants.append(data)
        for field, key in (("users", "leader_main"), ("teams", "main"), ("projects", "main"), ("submissions", "main")):
            data = manifest()
            data[field][key] = list(data[field].values())[-1]
            variants.append(data)
        data = manifest()
        data["assignments"]["revision"]["b"] = data["assignments"]["main"]["b"]
        variants.append(data)
        data = manifest()
        data["assignments"]["revision"]["extra"] = "99"
        variants.append(data)
        for data in variants:
            with self.assertRaises(runner.CheckFailed):
                runner.VoteFixture.parse(data)

    def test_bigint_precision_and_manifest_are_copied(self):
        data = manifest()
        data["projects"]["main"] = "9223372036854775807"
        fixture = runner.VoteFixture.parse(data)
        data["assignments"]["main"]["b"] = "999"
        self.assertEqual(fixture.projects["main"], "9223372036854775807")
        self.assertEqual(fixture.assignments["main"]["b"], "1")

    def test_placeholder_example_and_oversized_file_are_rejected_without_db_access(self):
        path = Path(__file__).with_name("fixtures") / "topic_vote_concurrency.example.json"
        with self.assertRaises(runner.CheckFailed):
            runner.VoteFixture.load(path)
        with patch.object(Path, "stat") as stat, patch.object(Path, "read_text") as read:
            stat.return_value.st_size = 8193
            with self.assertRaises(runner.CheckFailed):
                runner.VoteFixture.load("large.json")
            read.assert_not_called()

    def fixture_connection(self):
        fixture = runner.VoteFixture.parse(manifest())
        u, ns = fixture.users, fixture.namespace
        rows = [(f"{ns}.{key}@example.test", role) for key, role in runner.USER_ROLES.items()]
        rows.append([(int(fixture.teams[label]), int(u["leader_" + label]), "leader") for label in runner.PROJECT_LABELS])
        for label in runner.PROJECT_LABELS:
            project, submission, leader = int(fixture.projects[label]), int(fixture.submissions[label]), int(u["leader_" + label])
            rows.extend([(f"{ns}.{label}",), [(project, leader, f"{ns}.{label}.project", None)],
                         [(int(u["advisor"]), leader, "accepted")],
                         [(submission, leader, "approved", f"{ns}.{label}.project", None)],
                         [(runner.FILE_BYTES, "phase.pdf", "application/pdf")],
                         [(int(fixture.assignments[label][member]), int(u[member]), int(u["coordinator"])) for member in runner.COMMITTEE_LABELS],
                         [(submission, int(value), "revision_requested", runner.REVISION_COMMENT) for value in fixture.assignments[label].values()] if label == "revision" else [],
                         ("revision_requested" if label == "revision" else None,), (False,), (False,)])
        rows.append((False,))
        conn = MagicMock()
        cursors = []
        for row in rows:
            cursor = MagicMock()
            cursor.fetchone.return_value = row
            cursor.fetchall.return_value = row
            cursors.append(cursor)
        conn.execute.side_effect = cursors
        return conn, fixture, cursors

    def test_preflight_checks_full_graph_with_selects_only(self):
        conn, fixture, _ = self.fixture_connection()
        with patch.object(runner, "assert_auth_connection"):
            runner.validate_fixture(conn, fixture)
        self.assertTrue(all(call.args[0].lstrip().startswith("SELECT") for call in conn.execute.call_args_list))

    def test_preflight_rejects_real_account_bad_membership_file_and_existing_votes(self):
        for cursor_index, invalid in ((0, ("existing@example.test", "student")), (8, []),
                                      (13, [(b"wrong", "phase.pdf", "application/pdf")]),
                                      (15, [(1, 1, "approved", None)])):
            conn, fixture, cursors = self.fixture_connection()
            cursors[cursor_index].fetchone.return_value = invalid
            cursors[cursor_index].fetchall.return_value = invalid
            with patch.object(runner, "assert_auth_connection"), self.assertRaises(runner.CheckFailed):
                runner.validate_fixture(conn, fixture)

    def test_preflight_never_starts_workers(self):
        with patch.object(runner.VoteFixture, "load", return_value=runner.VoteFixture.parse(manifest())), \
                patch.object(runner, "rollback_connection") as connection, patch.object(runner, "validate_fixture") as validate, \
                patch.object(runner, "run_case") as run, patch("sys.stdout", new_callable=io.StringIO):
            self.assertEqual(runner.main(["--preflight", "--fixture", "local.json"]), 0)
        connection.assert_called_once_with(readonly=True)
        validate.assert_called_once()
        run.assert_not_called()

    def test_unknown_action_stops_before_business_work(self):
        conn = MagicMock()
        for case, side in (("VC99", "A"), ("VC01", "C")):
            with self.assertRaises(runner.CheckFailed):
                runner.action(conn, runner.VoteFixture.parse(manifest()), case, side)
        conn.execute.assert_not_called()

    def test_permission_sqlstate_is_preserved_without_secret_exception_text(self):
        try:
            try:
                raise psycopg.errors.InsufficientPrivilege("SyntheticPrivateDSN")
            except psycopg.Error:
                raise StorageUnavailable() from None
        except StorageUnavailable as exc:
            result = runner.diagnostic(exc)
        self.assertEqual(result["sqlstate"], "42501")
        self.assertNotIn("SyntheticPrivateDSN", json.dumps(result))

    def test_worker_failure_exits_outer_rollback_before_report(self):
        ready, done = Queue(), Queue()
        events, conn = [], MagicMock()
        @contextmanager
        def connection():
            try:
                yield conn
            finally:
                events.append("rollback")
        with patch.object(runner, "rollback_connection", connection), patch.object(runner, "validate_fixture"), \
                patch.object(runner, "action", side_effect=psycopg.errors.LockNotAvailable("SyntheticSQL")):
            runner.worker(runner.VoteFixture.parse(manifest()), "VC01", ready, done)
        self.assertEqual(events, ["rollback"])
        self.assertEqual(done.get_nowait()["sqlstate"], "55P03")

    def orchestration(self, *, blocked=True, drift=False, worker_ok=True):
        observer, first, second = MagicMock(), MagicMock(), MagicMock()
        observer.execute.return_value.fetchone.return_value = (10,)
        first.execute.return_value.fetchone.return_value = (20,)
        first_closed = False
        @contextmanager
        def connection(**kwargs):
            nonlocal first_closed
            if kwargs.get("readonly"):
                yield observer
            else:
                try:
                    yield first
                finally:
                    first_closed = True
        def start_thread(*, target, args, daemon):
            self.assertTrue(daemon)
            self.assertIs(target, runner.worker)
            _, _, ready, done = args
            thread = MagicMock()
            def start():
                ready.put((second, 30))
                done.put({"ok": True, "sqlstate": None} if worker_ok else {"ok": False, "sqlstate": "42501", "reason": "WORKER_FAILED"})
            thread.start.side_effect = start
            return thread
        def finish(*args):
            self.assertTrue(first_closed, "Must release A before awaiting B")
        with patch.object(runner, "rollback_connection", connection), patch.object(runner, "validate_fixture"), \
                patch.object(runner, "action"), patch.object(runner, "Thread", side_effect=start_thread), \
                patch.object(runner, "fingerprint", side_effect=["before", "changed" if drift else "before"]), \
                patch.object(runner, "wait_for_block", side_effect=None if blocked else runner.CheckFailed("NO_BLOCK")) as wait, \
                patch.object(runner, "finish_worker", side_effect=finish) as cleanup:
            try:
                return runner.run_case(runner.VoteFixture.parse(manifest()), "VC01")
            finally:
                wait.assert_called_once_with(observer, 20, 30)
                cleanup.assert_called_once()

    def test_pair_requires_observed_block_and_releases_first_before_join(self):
        self.assertTrue(self.orchestration()["wait_observed"])

    def test_missing_block_never_becomes_pass_and_still_cleans_up(self):
        with self.assertRaisesRegex(runner.CheckFailed, "NO_BLOCK"):
            self.orchestration(blocked=False)

    def test_baseline_drift_never_becomes_pass(self):
        with self.assertRaisesRegex(runner.CheckFailed, "BASELINE_NOT_RESTORED"):
            self.orchestration(drift=True)

    def test_worker_error_propagates_only_fixed_reason_and_sqlstate(self):
        with self.assertRaises(runner.CheckFailed) as error:
            self.orchestration(worker_ok=False)
        self.assertEqual(error.exception.sqlstate, "42501")
        self.assertEqual(str(error.exception), "VOTE_UNEXPECTED_WORKER_RESULT")


if __name__ == "__main__":
    unittest.main()
