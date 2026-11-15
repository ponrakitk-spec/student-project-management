"""Offline safeguards for the prepared 42-row installation; no real DB connections."""

from contextlib import contextmanager
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import MagicMock, patch

import psycopg

from backend.tests.evaluation_concurrency import CheckFailed, EvaluationFixture
from backend.tests.test_evaluation_concurrency import manifest
from database.tools import Evaluation_Concurrency_Fixture_Install as tool


class EvaluationInstallSafetyTests(unittest.TestCase):
    def setUp(self):
        for target in ("database.tools.Test_Database.dotenv_values", "database.tools.Test_Database.psycopg.connect"):
            blocker = patch(target, side_effect=AssertionError("REAL_CONFIG_OR_DB_FORBIDDEN"))
            blocker.start()
            self.addCleanup(blocker.stop)
        self.directory = tempfile.TemporaryDirectory(prefix="spms-topic-installer-test-")
        self.addCleanup(self.directory.cleanup)
        self.path = Path(self.directory.name) / "topic.json"

    def test_default_does_not_connect_create_file_or_install(self):
        with patch("sys.stdout", new_callable=io.StringIO) as output, patch.object(tool, "install") as install:
            self.assertEqual(tool.main([]), 0)
        self.assertEqual(json.loads(output.getvalue())["fixture_rows_total"], 42)
        install.assert_not_called()
        self.assertFalse(self.path.exists())

    def test_apply_requires_exact_database_before_file_access(self):
        for database in (None, "student_project_management"):
            args = ["--apply", "--manifest", str(self.path)]
            if database:
                args += ["--confirm-database", database]
            with patch("sys.stdout", new_callable=io.StringIO), patch.object(tool, "install") as install:
                self.assertEqual(tool.main(args), 1)
            install.assert_not_called()
            self.assertFalse(self.path.exists())

    def test_direct_install_rejects_repository_path_and_non_json(self):
        connector = MagicMock()
        for path in (tool.BASE / "fixture.json", self.path.with_suffix(".txt")):
            with self.assertRaises(CheckFailed):
                tool.install(path, connector=connector)
        connector.assert_not_called()

    def test_existing_manifest_is_verified_without_overwrite_or_new_connection(self):
        content = json.dumps(manifest())
        self.path.write_text(content, encoding="utf-8")
        connector = MagicMock()
        with patch.object(tool, "check", return_value={"result": "PASS"}) as check:
            result = tool.install(self.path, connector=connector)
        self.assertEqual(result["mode"], "ALREADY_INSTALLED")
        self.assertEqual(result["additional_rows"], 0)
        connector.assert_not_called()
        check.assert_called_once_with(self.path)
        self.assertEqual(self.path.read_text(encoding="utf-8"), content)

    def test_partial_manifest_never_triggers_reseed(self):
        self.path.write_text("incomplete artifact", encoding="utf-8")
        connector = MagicMock()
        with self.assertRaises(CheckFailed):
            tool.install(self.path, connector=connector)
        connector.assert_not_called()

    def simulate(self, *, fail_prepare=False, fail_commit=False, fail_post=False,
                 existing_changed=False, existing_fixture=False, other_clients=False, wrong_database=False):
        conn, fixture = MagicMock(), EvaluationFixture.parse(manifest())
        def execute(query, parameters=None):
            cursor = MagicMock()
            cursor.fetchone.return_value = (("student_project_management" if wrong_database else tool.TEST_DB,)
                if query == "SELECT current_database()" else
                (existing_fixture,) if "WHERE email LIKE" in query else (1 if other_clients else 0,))
            return cursor
        conn.execute.side_effect = execute
        @contextmanager
        def root_transaction():
            yield
            self.assertEqual(EvaluationFixture.load(self.path), fixture)
            if fail_commit:
                raise psycopg.OperationalError("SyntheticPrivateCommitMessage")
        conn.transaction.side_effect = root_transaction
        with patch.object(tool, "switch"), patch.object(tool, "inventory", return_value=(52, [])), \
                patch.object(tool, "snapshot", return_value=("metadata", {})), \
                patch.object(tool, "public_rows_hash", side_effect=["original", "changed" if existing_changed else "original"]), \
                patch.object(tool, "fingerprint", return_value="fixture hash"), \
                patch.object(tool, "create_fixture", return_value=fixture,
                             side_effect=psycopg.errors.InsufficientPrivilege("SyntheticPrivateSQL") if fail_prepare else None), \
                patch.object(tool, "verify_fixture_counts"), patch.object(tool, "validate_fixture"), \
                patch.object(tool, "postflight", side_effect=CheckFailed("POSTCHECK") if fail_post else None) as post:
            result = tool.install(self.path, connector=lambda: conn)
        conn.close.assert_called_once()
        conn.rollback.assert_called()
        return result, post

    def test_manifest_is_saved_before_root_commit_then_postflight_runs(self):
        result, post = self.simulate()
        self.assertTrue(result["committed"])
        self.assertEqual(result["fixture_rows_total"], 42)
        EvaluationFixture.load(self.path)
        post.assert_called_once()

    def test_wrong_database_guard_stops_before_fixture_creation(self):
        result, post = self.simulate(wrong_database=True)
        self.assertEqual(result["diagnostic"]["reason"], "TEST_DATABASE_REQUIRED")
        self.assertEqual(result["commit_status"], "NOT_ATTEMPTED")
        post.assert_not_called()

    def test_precommit_failure_rolls_back_retains_reservation_and_hides_secrets(self):
        result, post = self.simulate(fail_prepare=True)
        self.assertEqual(result["commit_status"], "NOT_ATTEMPTED")
        self.assertEqual(result["diagnostic"]["sqlstate"], "42501")
        self.assertFalse(result["automatic_retry_allowed"])
        post.assert_not_called()
        self.assertTrue(self.path.exists())
        self.assertNotIn("SyntheticPrivateSQL", json.dumps(result))

    def test_uncertain_commit_retains_valid_manifest_and_never_claims_rollback(self):
        result, post = self.simulate(fail_commit=True)
        self.assertEqual(result["commit_status"], "COMMIT_PENDING")
        self.assertNotIn("committed", result)
        self.assertFalse(result["automatic_retry_allowed"])
        EvaluationFixture.load(self.path)
        post.assert_not_called()
        self.assertNotIn("SyntheticPrivateCommitMessage", json.dumps(result))

    def test_failed_postflight_is_marked_committed(self):
        result, _ = self.simulate(fail_post=True)
        self.assertEqual(result["result"], "FAIL")
        self.assertEqual(result["commit_status"], "COMMITTED")

    def test_changed_original_rows_prevent_commit(self):
        result, post = self.simulate(existing_changed=True)
        self.assertEqual(result["commit_status"], "NOT_ATTEMPTED")
        self.assertEqual(result["diagnostic"]["reason"], "EXISTING_ROWS_CHANGED")
        post.assert_not_called()

    def test_existing_fixture_or_other_clients_prevent_new_seed(self):
        for kwargs, expected in (({"existing_fixture": True}, "EXISTING_FIXTURE_REQUIRES_ORIGINAL_MANIFEST"),
                                 ({"other_clients": True}, "OTHER_CLIENTS_CONNECTED")):
            # A failed reservation is intentionally retained by the installer.
            self.path = self.path.with_name(expected.lower() + ".json")
            result, post = self.simulate(**kwargs)
            self.assertEqual(result["commit_status"], "NOT_ATTEMPTED")
            self.assertEqual(result["diagnostic"]["reason"], expected)
            post.assert_not_called()

    def test_hash_excludes_only_exact_fixture_rows_and_detects_existing_value_change(self):
        fixture, conn = EvaluationFixture.parse(manifest()), MagicMock()
        original = "original user"
        def execute(query, parameters=None):
            text = query if isinstance(query, str) else query.as_string()
            cursor = MagicMock()
            if text.startswith("SELECT id"):
                count = next(tool.COUNTS["public." + table] for table in ("team_members", "advisor_invitations", "project_submission_files", "committee_topic_votes", "milestones", "tasks", "task_assignees", "committee_evaluations") if '"' + table + '"' in text)
                cursor.fetchall.return_value = [(100 + index,) for index in range(count)]
            elif '"users"' in text:
                cursor.fetchall.return_value = [({"id": 1, "name": "fixture user"},), ({"id": 999, "name": original},)]
            else:
                cursor.fetchall.return_value = []
            return cursor
        conn.execute.side_effect = execute
        before = tool.public_rows_hash(conn, fixture)
        original = "changed existing user"
        self.assertNotEqual(before, tool.public_rows_hash(conn, fixture))

    def test_check_is_direct_app_readonly_and_creates_no_rows(self):
        self.path.write_text(json.dumps(manifest()), encoding="utf-8")
        with patch.object(tool, "rollback_connection") as connection, patch.object(tool, "validate_fixture"):
            result = tool.check(self.path)
        connection.assert_called_once_with(readonly=True)
        self.assertTrue(result["direct_app_login"])
        self.assertFalse(result["written"])


if __name__ == "__main__":
    unittest.main()
