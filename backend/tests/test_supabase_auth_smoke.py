"""Offline safeguards for the cloud Auth runner, never connect to a database."""

import io
from types import SimpleNamespace
import unittest
from unittest.mock import MagicMock, patch

import psycopg
from psycopg.pq import TransactionStatus
from backend.tests import supabase_auth_smoke as smoke

REF = "abcdefghijklmnopqrst"


class SupabaseAuthSmokeSafeguards(unittest.TestCase):
    def test_default_plan_does_not_read_private_config_or_connect(self):
        with patch.object(smoke, "runtime_target") as target, patch.object(smoke, "open_auth_connection") as connect, patch("sys.stdout", new_callable=io.StringIO):
            self.assertEqual(smoke.main([]), 0)
            target.assert_not_called()
            connect.assert_not_called()

    def test_missing_reference_is_rejected_before_config_access(self):
        with patch.object(smoke, "runtime_target") as target:
            with self.assertRaises(smoke.SmokeFailed):
                smoke.validate_target(None)
            target.assert_not_called()

    def test_local_database_never_becomes_cloud_write_target(self):
        with patch.object(smoke, "runtime_target", return_value=SimpleNamespace(mode="local_test", database="student_project_management_v1_test")):
            with self.assertRaises(smoke.SmokeFailed):
                smoke.validate_target(REF)

    def test_explicit_project_must_match_direct_or_pooler_identity(self):
        for host,user,valid in ((f"db.{REF}.supabase.co", "project_app", True), ("aws-1-ap-northeast-1.pooler.supabase.com", f"project_app.{REF}", True), ("aws-1-ap-northeast-1.pooler.supabase.com", "project_app."+"x"*20, False), (f"db.{REF}.supabase.co", "postgres", False)):
            target = SimpleNamespace(mode="supabase_test", database="postgres", connect_kwargs={"host": host, "user": user})
            with patch.object(smoke, "runtime_target", return_value=target):
                if valid: self.assertIs(smoke.validate_target(REF), target)
                else:
                    with self.assertRaises(smoke.SmokeFailed): smoke.validate_target(REF)

    def test_borrowed_request_cannot_start_without_outer_transaction(self):
        conn = MagicMock()
        conn.info.transaction_status = TransactionStatus.IDLE
        with patch.object(smoke, "transaction_on") as factory:
            with self.assertRaises(smoke.SmokeFailed):
                with smoke.borrowed_auth(conn, smoke.RLock()): pass
            factory.assert_not_called()

    def test_snapshots_refuse_readwrite_transactions(self):
        conn = MagicMock()
        conn.execute.return_value.fetchone.return_value = ("off",)
        with patch.object(smoke, "inspect") as inspect:
            with self.assertRaises(smoke.SmokeFailed): smoke.fingerprint(conn)
            inspect.assert_not_called()

    def test_connection_errors_never_disclose_secrets(self):
        with patch.object(smoke, "run", side_effect=RuntimeError("PrivateConnectionFixture")), patch("sys.stdout", new_callable=io.StringIO) as output:
            self.assertEqual(smoke.main(["--run", "--project-ref", REF]), 1)
            self.assertNotIn("PrivateConnectionFixture", output.getvalue())

    def test_fixture_cleanup_checks_use_readonly_connections_and_rollback(self):
        conn = MagicMock()
        conn.execute.return_value.fetchone.return_value = (0,)
        with patch.object(smoke, "validate_target"), patch.object(smoke, "open_auth_connection", return_value=conn) as connect, patch.object(smoke, "fingerprint", return_value="baseline"), patch.object(smoke, "AuthRepository") as repository:
            repository.return_value.credentials.return_value = None
            self.assertEqual(smoke.snapshot(REF, "fixture@example.test"), "baseline")
            connect.assert_called_once_with(readonly=True)
            conn.rollback.assert_called_once()
            conn.close.assert_called_once()

    def test_persisted_fixture_credential_fails_cleanup_and_still_closes_connection(self):
        conn = MagicMock()
        with patch.object(smoke, "validate_target"), patch.object(smoke, "open_auth_connection", return_value=conn), patch.object(smoke, "fingerprint", return_value="baseline"), patch.object(smoke, "AuthRepository") as repository:
            repository.return_value.credentials.return_value = (1, "encoded-fixture")
            with self.assertRaises(smoke.SmokeFailed): smoke.snapshot(REF, "fixture@example.test")
            conn.rollback.assert_called_once()
            conn.close.assert_called_once()

    def test_failure_inside_http_exercise_still_forces_rollback_and_verifies_cleanup(self):
        conn = MagicMock()
        conn.info.transaction_status = TransactionStatus.IDLE
        conn.pgconn.ssl_in_use = True
        with patch.object(smoke, "validate_target"), patch.object(smoke, "snapshot", side_effect=["baseline", "baseline"]) as snapshot, patch.object(smoke, "open_auth_connection", return_value=conn), patch("backend.auth_store.assert_auth_connection"), patch.object(smoke, "exercise", side_effect=smoke.SmokeFailed("INJECTED_HTTP_FAILURE")):
            result = smoke.run(REF)
        self.assertEqual(result["result"], "FAIL")
        self.assertEqual(result["failed_check"], "INJECTED_HTTP_FAILURE")
        self.assertTrue(result["baseline_restored"])
        self.assertEqual(snapshot.call_count, 2)
        conn.transaction.assert_called_once_with(force_rollback=True)
        conn.commit.assert_not_called()
        conn.close.assert_called_once()

    def test_sql_diagnostics_include_state_and_function_without_private_message(self):
        class DatabaseFailure(psycopg.Error):
            @property
            def sqlstate(self): return "42501"
            @property
            def diag(self): return SimpleNamespace(context="PL/pgSQL function spms_auth.register_student(text,text,text) line 3; PrivateFixture")
        result = smoke.sql_diagnostic(DatabaseFailure("PrivateFixture"))
        self.assertEqual(result, {"sqlstate": "42501", "functions": ["spms_auth.register_student"]})
        self.assertNotIn("PrivateFixture", str(result))


if __name__ == "__main__":
    unittest.main()
