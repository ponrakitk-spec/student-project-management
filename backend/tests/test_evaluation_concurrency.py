"""Offline runner safeguards; mock orchestration is not PostgreSQL locking."""

from contextlib import contextmanager
from datetime import date
import io
import json
from pathlib import Path
from queue import Queue
import unittest
from unittest.mock import MagicMock, patch

import psycopg

from backend.auth_store import StorageUnavailable
from backend.tests import evaluation_concurrency as runner
from database.tools.Evaluation_Concurrency_Fixture import placeholder


def manifest():
    return placeholder("spms-ec-" + "a" * 32)


class EvaluationConcurrencySafetyTests(unittest.TestCase):
    def setUp(self):
        for target in ("backend.auth_store.dotenv_values", "backend.auth_store.psycopg.connect"):
            blocker = patch(target, side_effect=AssertionError("REAL_CONFIG_OR_DB_FORBIDDEN"))
            blocker.start()
            self.addCleanup(blocker.stop)

    def test_default_plan_and_fixture_argument_alone_are_offline(self):
        for args in ([], ["--fixture", "missing.json"]):
            with patch("sys.stdout", new_callable=io.StringIO) as output, patch.object(runner.EvaluationFixture, "load") as load:
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
        data["assignments"]["final"]["b"] = data["assignments"]["main"]["b"]
        variants.append(data)
        data = manifest()
        data["assignments"]["final"]["extra"] = "99"
        variants.append(data)
        for data in variants:
            with self.assertRaises(runner.CheckFailed):
                runner.EvaluationFixture.parse(data)

    def test_bigint_precision_and_manifest_are_copied(self):
        data = manifest()
        data["projects"]["main"] = "9223372036854775807"
        fixture = runner.EvaluationFixture.parse(data)
        data["assignments"]["main"]["b"] = "999"
        self.assertEqual(fixture.projects["main"], "9223372036854775807")
        self.assertEqual(fixture.assignments["main"]["b"], "1")

    def test_placeholder_example_and_oversized_file_are_rejected_without_db_access(self):
        with self.assertRaises(runner.CheckFailed):
            runner.EvaluationFixture.parse(placeholder("spms-ec-REPLACE-WITH-REAL-FIXTURE"))
        with patch.object(Path, "stat") as stat, patch.object(Path, "read_text") as read:
            stat.return_value.st_size = 8193
            with self.assertRaises(runner.CheckFailed):
                runner.EvaluationFixture.load("large.json")
            read.assert_not_called()

    def test_preflight_never_starts_workers(self):
        with patch.object(runner.EvaluationFixture, "load", return_value=runner.EvaluationFixture.parse(manifest())), \
                patch.object(runner, "rollback_connection") as connection, patch.object(runner, "validate_fixture") as validate, \
                patch.object(runner, "run_case") as run, patch("sys.stdout", new_callable=io.StringIO):
            self.assertEqual(runner.main(["--preflight", "--fixture", "local.json"]), 0)
        connection.assert_called_once_with(readonly=True)
        validate.assert_called_once()
        run.assert_not_called()

    def test_work_identifiers_and_membership_shape_are_strict(self):
        variants = []
        for field in ("milestone", "task"):
            data = manifest()
            data["work"]["editable"][field] = data["work"]["main"][field]
            variants.append(data)
        data = manifest()
        data["work"]["editable"]["member"] = "99"
        variants.append(data)
        data = manifest()
        data["work"]["final"]["extra"] = "99"
        variants.append(data)
        for data in variants:
            with self.assertRaises(runner.CheckFailed):
                runner.EvaluationFixture.parse(data)

    def graph_connection(self):
        fixture = runner.EvaluationFixture.parse(manifest())
        ns, users, due = fixture.namespace, fixture.users, date(2030, 1, 1)
        rows = [("Evaluation concurrency " + k, f"{ns}.{k}@example.test", role) for k, role in runner.USER_ROLES.items()]
        rows.append([(int(fixture.work[k]["member"]), int(fixture.teams[k]), int(users["leader_" + k]), "leader") for k in runner.PROJECTS])
        slots = {}
        for k in runner.PROJECTS:
            leader = int(users["leader_" + k])
            submission = int(fixture.submissions[k])
            rows.extend([(f"{ns}.{k}",), [(int(fixture.projects[k]), leader, f"{ns}.{k}.project", None)],
                         [(int(users["advisor"]), leader, "accepted")],
                         [(submission, leader, "approved", f"{ns}.{k}.project", None)]])
            slots[k + "_file"] = len(rows)
            rows.append([(runner.FILE_BYTES, "phase.pdf", "application/pdf")])
            rows.append([(int(v), int(users[m]), int(users["coordinator"])) for m, v in fixture.assignments[k].items()])
            rows.extend([[(submission, int(v), "approved", runner.COMMENT) for v in fixture.assignments[k].values()], ("approved",)])
            slots[k + "_scores"] = len(rows)
            rows.append([(int(fixture.assignments[k][m]), score, runner.COMMENT) for m, score in (("b", 60), ("c", 70))] if k == "final" else [])
            labels = ("main", "editable") if k == "main" else ("final",)
            rows.append([(int(fixture.work[w]["milestone"]), f"{ns}.{w}.milestone", None,
                          "not_started" if w == "editable" else "completed", leader, due) for w in labels])
            for w in labels:
                rows.extend([[(int(fixture.work[w]["task"]), f"{ns}.{w}.task", None,
                               "not_started" if w == "editable" else "completed", leader, due)],
                             [(int(fixture.work[w]["member"]),)]])
        rows.append((False,))
        cursors = []
        for row in rows:
            cursor = MagicMock()
            cursor.fetchone.return_value = cursor.fetchall.return_value = row
            cursors.append(cursor)
        conn = MagicMock()
        conn.execute.side_effect = cursors
        return conn, fixture, cursors, slots

    def test_full_graph_preflight_is_select_only(self):
        conn, fixture, _, _ = self.graph_connection()
        with patch.object(runner, "assert_auth_connection"):
            self.assertEqual(set(runner.validate_fixture(conn, fixture)), set(runner.WORK))
        self.assertTrue(all(call.args[0].lstrip().startswith("SELECT") for call in conn.execute.call_args_list))

    def test_preflight_rejects_modified_file_scores_and_user(self):
        for slot in ("main_file", "final_scores", "user"):
            conn, fixture, cursors, slots = self.graph_connection()
            index = slots[slot] if slot != "user" else 0
            cursors[index].fetchone.return_value = ("Unexpected real account", "real@example.test", "student")
            cursors[index].fetchall.return_value = []
            with patch.object(runner, "assert_auth_connection"), self.assertRaises(runner.CheckFailed):
                runner.validate_fixture(conn, fixture)

    def test_unknown_action_stops_before_business_work(self):
        conn = MagicMock()
        for case, side in (("EC99", "A"), ("EC01", "C")):
            with self.assertRaises(runner.CheckFailed):
                runner.action(conn, runner.EvaluationFixture.parse(manifest()), None, case, side)
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
        with patch.object(runner, "rollback_connection", connection), patch.object(runner, "validate_fixture", return_value=None), \
                patch.object(runner, "action", side_effect=psycopg.errors.LockNotAvailable("SyntheticSQL")):
            runner.worker(runner.EvaluationFixture.parse(manifest()), None, "EC01", ready, done)
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
            _, _, _, ready, done = args
            thread = MagicMock()
            def start():
                ready.put((second, 30))
                done.put({"ok": True, "sqlstate": None} if worker_ok else {"ok": False, "sqlstate": "42501", "reason": "WORKER_FAILED"})
            thread.start.side_effect = start
            return thread
        def finish(*args):
            self.assertTrue(first_closed, "Must release A before awaiting B")
        with patch.object(runner, "rollback_connection", connection), patch.object(runner, "validate_fixture", return_value=None), \
                patch.object(runner, "action"), patch.object(runner, "Thread", side_effect=start_thread), \
                patch.object(runner, "fingerprint", side_effect=["before", "changed" if drift else "before"]), \
                patch.object(runner, "wait_for_block", side_effect=None if blocked else runner.CheckFailed("NO_BLOCK")) as wait, \
                patch.object(runner, "finish_worker", side_effect=finish) as cleanup:
            try:
                return runner.run_case(runner.EvaluationFixture.parse(manifest()), "EC01")
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
        self.assertEqual(str(error.exception), "EVALUATION_UNEXPECTED_WORKER_RESULT")


if __name__ == "__main__":
    unittest.main()
