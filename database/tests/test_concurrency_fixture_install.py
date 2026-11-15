"""Offline checks for the explicitly authorized one-time fixture installer."""

from contextlib import contextmanager
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import MagicMock, patch

import psycopg

from backend.tests.team_project_concurrency import CheckFailed, Fixture
from backend.tests.test_team_project_concurrency_harness import manifest
from database.tools import Team_Project_Concurrency_Fixture_Install as tool


class ConcurrencyInstallSafetyTests(unittest.TestCase):
    def setUp(self):
        for target in ("database.tools.Test_Database.dotenv_values", "database.tools.Test_Database.psycopg.connect"):
            blocker = patch(target, side_effect=AssertionError("REAL_CONFIG_OR_DB_FORBIDDEN"))
            blocker.start()
            self.addCleanup(blocker.stop)
        self.directory = tempfile.TemporaryDirectory(prefix="spms-concurrency-installer-test-")
        self.addCleanup(self.directory.cleanup)
        self.path = Path(self.directory.name) / "fixture.json"

    def test_default_does_not_touch_file_or_database(self):
        with patch("sys.stdout", new_callable=io.StringIO), patch.object(tool, "install") as install:
            self.assertEqual(tool.main([]), 0)
        install.assert_not_called()
        self.assertFalse(self.path.exists())

    def test_apply_requires_exact_database_confirmation_before_file_access(self):
        for database in (None, "student_project_management"):
            args = ["--apply", "--manifest", str(self.path)]
            if database:
                args += ["--confirm-database", database]
            with self.subTest(database=database), patch("sys.stdout", new_callable=io.StringIO), \
                    patch.object(tool, "install") as install:
                self.assertEqual(tool.main(args), 1)
            install.assert_not_called()
            self.assertFalse(self.path.exists())

    def test_rejects_manifest_inside_repository(self):
        with self.assertRaises(CheckFailed):
            tool.manifest_path(tool.BASE / "fixture.json")

    def test_existing_manifest_is_checked_without_connecting_for_install_or_overwriting(self):
        content = json.dumps(manifest())
        self.path.write_text(content, encoding="utf-8")
        connector = MagicMock()
        with patch.object(tool, "check", return_value={"result": "PASS"}) as check:
            result = tool.install(self.path, connector=connector)
        self.assertEqual(result["mode"], "ALREADY_INSTALLED")
        check.assert_called_once_with(self.path)
        connector.assert_not_called()
        self.assertEqual(self.path.read_text(encoding="utf-8"), content)

    def test_invalid_existing_manifest_never_triggers_reseed(self):
        self.path.write_text("incomplete artifact", encoding="utf-8")
        connector = MagicMock()
        with self.assertRaises(CheckFailed):
            tool.install(self.path, connector=connector)
        connector.assert_not_called()

    def simulate(self, *, fail_prepare=False, fail_commit=False, fail_post=False,
                 existing_changed=False, existing_fixture=False):
        conn = MagicMock()
        def execute(query, parameters=None):
            cursor = MagicMock()
            cursor.fetchone.return_value = ((existing_fixture,) if "WHERE email LIKE" in query else (0,))
            return cursor
        conn.execute.side_effect = execute
        fixture = Fixture.parse(manifest())

        @contextmanager
        def root_transaction():
            yield
            # A durable valid manifest must exist before a COMMIT can happen.
            self.assertEqual(Fixture.load(self.path), fixture)
            if fail_commit:
                raise psycopg.OperationalError("SyntheticPrivateCommitMessage")

        conn.transaction.side_effect = root_transaction
        creator_error = psycopg.errors.InsufficientPrivilege("SyntheticPrivateSQL") if fail_prepare else None
        with patch.object(tool, "switch"), patch.object(tool, "inventory", return_value=(52, [])), \
                patch.object(tool, "snapshot", return_value=("metadata", {})), \
                patch.object(tool, "public_rows_hash", side_effect=["original", "changed" if existing_changed else "original"]), \
                patch.object(tool, "fingerprint", return_value="new fixture hash"), \
                patch.object(tool, "create_fixture", return_value=fixture, side_effect=creator_error), \
                patch.object(tool, "verify_fixture_counts"), patch.object(tool, "validate_fixture"), \
                patch.object(tool, "postflight", side_effect=CheckFailed("POSTCHECK") if fail_post else None) as post:
            result = tool.install(self.path, connector=lambda: conn)
        conn.close.assert_called_once()
        conn.rollback.assert_called()
        return result, post

    def test_success_saves_manifest_before_root_commit_and_checks_postflight(self):
        result, post = self.simulate()
        self.assertEqual(result["result"], "PASS")
        self.assertTrue(result["committed"])
        post.assert_called_once()
        Fixture.load(self.path)

    def test_precommit_failure_rolls_back_reports_sqlstate_and_preserves_reservation(self):
        result, post = self.simulate(fail_prepare=True)
        self.assertEqual(result["commit_status"], "NOT_ATTEMPTED")
        self.assertEqual(result["diagnostic"]["sqlstate"], "42501")
        self.assertFalse(result["automatic_retry_allowed"])
        post.assert_not_called()
        self.assertTrue(self.path.exists())
        self.assertNotIn("SyntheticPrivateSQL", json.dumps(result))

    def test_uncertain_commit_keeps_valid_manifest_and_never_claims_rollback(self):
        result, post = self.simulate(fail_commit=True)
        self.assertEqual(result["commit_status"], "COMMIT_PENDING")
        self.assertNotIn("committed", result)
        self.assertFalse(result["automatic_retry_allowed"])
        Fixture.load(self.path)
        post.assert_not_called()
        self.assertNotIn("SyntheticPrivateCommitMessage", json.dumps(result))

    def test_postcommit_check_failure_never_claims_uncommitted(self):
        result, _ = self.simulate(fail_post=True)
        self.assertEqual(result["result"], "FAIL")
        self.assertEqual(result["commit_status"], "COMMITTED")
        Fixture.load(self.path)

    def test_changed_existing_rows_prevents_commit(self):
        result, post = self.simulate(existing_changed=True)
        self.assertEqual(result["commit_status"], "NOT_ATTEMPTED")
        self.assertEqual(result["diagnostic"]["reason"], "EXISTING_ROWS_CHANGED")
        post.assert_not_called()

    def test_existing_fixture_with_a_different_manifest_path_prevents_second_seed(self):
        result, post = self.simulate(existing_fixture=True)
        self.assertEqual(result["commit_status"], "NOT_ATTEMPTED")
        self.assertEqual(result["diagnostic"]["reason"], "EXISTING_FIXTURE_REQUIRES_ORIGINAL_MANIFEST")
        post.assert_not_called()

    def test_public_hash_excludes_only_fixture_rows_and_detects_changed_existing_value(self):
        conn = MagicMock()
        old_name = "unchanged"

        def execute(query, parameters=None):
            text = query if isinstance(query, str) else query.as_string()
            cursor = MagicMock()
            if text.startswith("SELECT id FROM public.team_members"):
                cursor.fetchall.return_value = [(11,), (12,), (13,)]
            elif '"users"' in text:
                cursor.fetchall.return_value = [({"id": 1, "name": "fixture"},), ({"id": 99, "name": old_name},)]
            else:
                cursor.fetchall.return_value = []
            return cursor

        conn.execute.side_effect = execute
        fixture = Fixture.parse(manifest())
        before = tool.public_rows_hash(conn, fixture)
        old_name = "changed existing user"
        self.assertNotEqual(before, tool.public_rows_hash(conn, fixture))

    def test_check_uses_direct_app_read_only_and_creates_no_rows(self):
        self.path.write_text(json.dumps(manifest()), encoding="utf-8")
        with patch.object(tool, "rollback_connection") as connection, patch.object(tool, "validate_fixture"):
            result = tool.check(self.path)
        connection.assert_called_once_with(readonly=True)
        self.assertTrue(result["direct_app_login"])
        self.assertFalse(result["written"])


if __name__ == "__main__":
    unittest.main()
