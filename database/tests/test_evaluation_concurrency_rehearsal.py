"""Offline safety checks; these mocks do not prove PostgreSQL concurrency."""

from contextlib import contextmanager
import io
import json
import unittest
from unittest.mock import MagicMock, patch

import psycopg

from backend.evaluation_store import EvaluationError
from backend.tests.team_project_concurrency import CheckFailed
from database.tools import Evaluation_Concurrency_Rehearsal as tool


class EvaluationRehearsalSafetyTests(unittest.TestCase):
    def setUp(self):
        for target in ("database.tools.Test_Database.dotenv_values", "database.tools.Test_Database.psycopg.connect"):
            blocker = patch(target, side_effect=AssertionError("REAL_CONFIG_OR_DB_FORBIDDEN"))
            blocker.start()
            self.addCleanup(blocker.stop)

    def test_default_plan_is_offline_without_apply_or_export(self):
        with patch("sys.stdout", new_callable=io.StringIO) as output, patch.object(tool, "connect_test_database") as connect:
            self.assertEqual(tool.main([]), 0)
        result = json.loads(output.getvalue())
        connect.assert_not_called()
        self.assertEqual(result["fixture_rows_total"], 38)
        self.assertEqual(len(result["cases"]), 8)
        self.assertNotIn("result", result)
        for key in ("database_connected", "apply_mode_available", "manifest_export_available", "multisession_tested", "blocking_tested"):
            self.assertFalse(result[key])

    def test_unknown_mutating_or_export_options_are_rejected(self):
        for flag in ("--apply", "--run-rollback", "--manifest", "--database"):
            with patch("sys.stderr", new_callable=io.StringIO), self.assertRaises(SystemExit):
                tool.main([flag])

    def test_action_rejects_unknown_case_or_side_before_database_access(self):
        conn = MagicMock()
        for case, side in (("EC99", "A"), ("EC01", "C")):
            with self.assertRaises(CheckFailed):
                tool.action(conn, {}, case, side)
        conn.execute.assert_not_called()

    def test_counts_protect_auth_rows_metadata_and_existing_data(self):
        before = ("metadata", {**dict.fromkeys(tool.COUNTS, 10), "auth.credentials": 3, "auth.sessions": 2})
        during = ("metadata", {key: count + tool.COUNTS.get(key, 0) for key, count in before[1].items()})
        for current, valid in ((during, True), (("changed", during[1]), False),
                               (("metadata", {**during[1], "auth.sessions": 3}), False)):
            with patch.object(tool, "switch"), patch.object(tool, "assert_auth_connection"), patch.object(tool, "snapshot", return_value=current):
                if valid:
                    tool.verify_counts(MagicMock(), before)
                else:
                    with self.assertRaises(CheckFailed):
                        tool.verify_counts(MagicMock(), before)

    def rehearsal(self, *, wrong_db=False, drift=False, bad_inventory=False, fail_action=False, fail_role=False):
        conn, events = MagicMock(), []
        conn.execute.return_value.fetchone.return_value = ("student_project_management" if wrong_db else tool.TEST_DB,)
        baseline = ("metadata", {"public.users": 2})

        @contextmanager
        def transaction(**kwargs):
            self.assertEqual(kwargs, {"force_rollback": True})
            events.append("enter")
            try:
                yield
            finally:
                events.append("rollback")
        conn.transaction.side_effect = transaction
        failure = psycopg.errors.InsufficientPrivilege("SyntheticPrivateSQL") if fail_action else None
        with patch.object(tool, "switch", side_effect=CheckFailed("ROLE_GUARD") if fail_role else None), \
                patch.object(tool, "inventory", return_value=(52, ["drift"]) if bad_inventory else (52, [])), \
                patch.object(tool, "snapshot", side_effect=[baseline, ("changed", baseline[1]) if drift else baseline]), \
                patch.object(tool, "fingerprint", return_value="digest"), patch.object(tool, "create_fixture") as create, \
                patch.object(tool, "verify_counts"), patch.object(tool, "prepare_case"), \
                patch.object(tool, "action", side_effect=failure) as action, \
                patch.object(tool, "ordered_pair", return_value={"expected_code": None}) as pair:
            result = tool.rehearse(connector=lambda: conn)
        conn.commit.assert_not_called()
        conn.rollback.assert_called()
        conn.close.assert_called_once()
        self.assertEqual(events.count("enter"), events.count("rollback"))
        return result, create, action, pair

    def test_rehearses_actions_and_pairs_without_claiming_multisession(self):
        result, create, action, pair = self.rehearsal()
        self.assertEqual(result["result"], "PASS")
        self.assertTrue(result["baseline_restored"])
        self.assertEqual(len(result["isolated_actions"]), 16)
        self.assertEqual(action.call_count, 16)
        self.assertEqual(len(result["ordered_pairs"]), 8)
        self.assertEqual(pair.call_count, 8)
        create.assert_called_once()
        for key in ("committed", "manifest_exported", "multisession_tested", "blocking_tested", "http_tested"):
            self.assertFalse(result[key])

    def test_wrong_database_stops_before_role_changes_or_fixture_writes(self):
        result, create, action, _ = self.rehearsal(wrong_db=True)
        self.assertEqual(result["result"], "FAIL")
        self.assertEqual(result["diagnostic"]["reason"], "TEST_DATABASE_REQUIRED")
        create.assert_not_called()
        action.assert_not_called()

    def test_metadata_drift_prevents_fixture_creation(self):
        result, create, _, _ = self.rehearsal(bad_inventory=True)
        self.assertEqual(result["diagnostic"]["reason"], "INSTALLED_BASELINE_REQUIRED")
        create.assert_not_called()

    def test_role_guard_stops_before_fixture_creation(self):
        result, create, _, _ = self.rehearsal(fail_role=True)
        self.assertEqual(result["result"], "FAIL")
        create.assert_not_called()

    def test_permission_failure_rolls_back_and_redacts_exception_text(self):
        result, _, action, pair = self.rehearsal(fail_action=True)
        self.assertEqual(result["result"], "FAIL")
        self.assertTrue(result["baseline_restored"])
        self.assertEqual(result["diagnostic"]["sqlstate"], "42501")
        self.assertNotIn("SyntheticPrivateSQL", json.dumps(result))
        action.assert_called_once()
        pair.assert_not_called()

    def test_postflight_drift_fails_even_if_all_actions_passed(self):
        result, _, _, _ = self.rehearsal(drift=True)
        self.assertEqual(result["result"], "FAIL")
        self.assertFalse(result["baseline_restored"])

    def test_connection_failure_has_no_fallback_or_secret_output(self):
        connect = MagicMock(side_effect=psycopg.OperationalError("SyntheticPrivatePassword"))
        result = tool.rehearse(connector=connect)
        connect.assert_called_once_with()
        self.assertEqual(result["result"], "FAIL")
        self.assertNotIn("SyntheticPrivatePassword", json.dumps(result))

    def test_ordered_pair_does_not_accept_unexpected_sql_failure(self):
        conn = MagicMock()
        for failure in (psycopg.errors.InsufficientPrivilege("private"), psycopg.errors.ForeignKeyViolation("private")):
            with patch.object(tool, "action", side_effect=[None, failure]), self.assertRaises(type(failure)):
                tool.ordered_pair(conn, {}, "EC01")
        with patch.object(tool, "action", side_effect=[None, EvaluationError("WRONG_CODE")]), self.assertRaises(CheckFailed):
            tool.ordered_pair(conn, {}, "EC04")

    def test_expected_conflicts_are_required_instead_of_accepting_any_success(self):
        for case in ("EC01", "EC02", "EC03", "EC04", "EC05"):
            with patch.object(tool, "action"), self.assertRaises(CheckFailed):
                tool.ordered_pair(MagicMock(), {}, case)


if __name__ == "__main__":
    unittest.main()
