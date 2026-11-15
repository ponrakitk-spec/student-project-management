"""Offline safeguards for the rollback-only Evaluation rehearsal."""

from contextlib import contextmanager
import io
import json
import unittest
from unittest.mock import MagicMock, patch

import psycopg

from backend.tests.topic_vote_concurrency import CheckFailed
from database.tools import Evaluation_Concurrency_Fixture as tool


class EvaluationFixtureSafetyTests(unittest.TestCase):
    def setUp(self):
        for target in ("database.tools.Test_Database.dotenv_values", "database.tools.Test_Database.psycopg.connect"):
            blocker = patch(target, side_effect=AssertionError("REAL_CONFIG_OR_DB_FORBIDDEN"))
            blocker.start()
            self.addCleanup(blocker.stop)

    def test_offline_plan_declares_42_rows_and_no_apply_or_export(self):
        with patch("sys.stdout", new_callable=io.StringIO) as output:
            self.assertEqual(tool.main([]), 0)
        result = json.loads(output.getvalue())
        self.assertEqual(result["fixture_rows_total"], 42)
        for key in ("database_connected", "apply_mode_available", "manifest_export_available"):
            self.assertFalse(result[key])

    def test_apply_flag_and_invalid_namespace_stop_before_db_writes(self):
        with patch("sys.stderr", new_callable=io.StringIO), self.assertRaises(SystemExit):
            tool.main(["--apply"])
        conn = MagicMock()
        with self.assertRaises(CheckFailed):
            tool.create_fixture(conn, "existing-team")
        conn.cursor.assert_not_called()
        conn.execute.assert_not_called()

    def test_fixture_deltas_include_no_auth_rows_or_metadata_changes(self):
        before = ("metadata", {**dict.fromkeys(tool.COUNTS, 10), "auth.credentials": 3, "auth.sessions": 1})
        expected = ("metadata", {table: count + tool.COUNTS.get(table, 0) for table, count in before[1].items()})
        conn = MagicMock()
        with patch.object(tool, "switch"), patch.object(tool, "assert_auth_connection"), patch.object(tool, "snapshot", return_value=expected):
            tool.verify_counts(conn, before)
        for invalid in (("changed", expected[1]), ("metadata", {**expected[1], "auth.credentials": 4})):
            with patch.object(tool, "switch"), patch.object(tool, "assert_auth_connection"), \
                    patch.object(tool, "snapshot", return_value=invalid), self.assertRaises(CheckFailed):
                tool.verify_counts(conn, before)

    def rehearsal(self, *, fail_action=False, drift=False, bad_inventory=False, fail_role=False):
        conn = MagicMock()
        conn.execute.return_value.fetchone.return_value = (tool.TEST_DB,)
        baseline = ("metadata", {"public.users": 2})
        calls = []
        @contextmanager
        def transaction(**kwargs):
            self.assertEqual(kwargs, {"force_rollback": True})
            yield
        conn.transaction.side_effect = transaction
        def action(*args):
            calls.append(args[-2:])
            if fail_action:
                raise psycopg.errors.InsufficientPrivilege("SyntheticPrivateSQL")
        with patch.object(tool, "switch", side_effect=CheckFailed("ROLE_GUARD") if fail_role else None), \
                patch.object(tool, "inventory", return_value=(52, ["drift"]) if bad_inventory else (52, [])), \
                patch.object(tool, "snapshot", side_effect=[baseline, ("changed", baseline[1]) if drift else baseline]), \
                patch.object(tool, "fingerprint", return_value="hash"), patch.object(tool, "create_fixture") as create, \
                patch.object(tool, "verify_counts"), patch.object(tool, "validate_fixture"), \
                patch.object(tool, "action", side_effect=action), patch.object(tool, "case_state"), \
                patch.object(tool, "ordered_pair", return_value={}):
            result = tool.rehearse(connector=lambda: conn)
        conn.commit.assert_not_called()
        conn.rollback.assert_called()
        conn.close.assert_called_once()
        return result, calls, create

    def test_sixteen_sequential_actions_do_not_claim_multisession(self):
        result, calls, _ = self.rehearsal()
        self.assertEqual(result["result"], "PASS")
        self.assertTrue(result["baseline_restored"])
        self.assertEqual(len(calls), 16)
        self.assertFalse(result["committed"])
        self.assertFalse(result["manifest_exported"])
        self.assertFalse(result["multisession_tested"])
        self.assertEqual(len(result["ordered_pairs"]), 8)
        self.assertEqual(len(result["isolated_actions"]), 16)

    def test_permission_failure_stops_and_rolls_back_with_sqlstate_only(self):
        result, calls, _ = self.rehearsal(fail_action=True)
        self.assertEqual(result["result"], "FAIL")
        self.assertTrue(result["baseline_restored"])
        self.assertEqual(result["diagnostic"]["sqlstate"], "42501")
        self.assertEqual(len(calls), 1)
        self.assertNotIn("SyntheticPrivateSQL", json.dumps(result))

    def test_drift_is_fail_even_when_actions_passed(self):
        result, _, _ = self.rehearsal(drift=True)
        self.assertEqual(result["result"], "FAIL")
        self.assertFalse(result["baseline_restored"])

    def test_invalid_installed_baseline_prevents_fixture_creation(self):
        result, calls, create = self.rehearsal(bad_inventory=True)
        self.assertEqual(result["result"], "FAIL")
        self.assertEqual(result["diagnostic"]["reason"], "INSTALLED_BASELINE_REQUIRED")
        self.assertEqual(calls, [])
        create.assert_not_called()

    def test_role_guard_failure_stops_before_fixture_creation(self):
        result, calls, create = self.rehearsal(fail_role=True)
        self.assertEqual(result["result"], "FAIL")
        self.assertEqual(calls, [])
        create.assert_not_called()

    def test_connect_failure_is_sanitized_and_has_no_fallback(self):
        connect = MagicMock(side_effect=psycopg.OperationalError("SyntheticPrivatePassword"))
        result = tool.rehearse(connector=connect)
        connect.assert_called_once_with()
        self.assertEqual(result["result"], "FAIL")
        self.assertFalse(result["baseline_restored"])
        self.assertNotIn("SyntheticPrivatePassword", json.dumps(result))


if __name__ == "__main__":
    unittest.main()
