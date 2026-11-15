"""Offline rehearsal-tool safeguards; never reads .env or connects to PG."""

from contextlib import contextmanager
import io
import json
import unittest
from unittest.mock import MagicMock, patch

import psycopg

from backend.auth_store import StorageUnavailable
from backend.tests.team_project_concurrency import CheckFailed
from database.tools import Team_Project_Concurrency_Fixture as tool


class ConcurrencyFixtureSafetyTests(unittest.TestCase):
    def setUp(self):
        for target in ("database.tools.Test_Database.dotenv_values", "database.tools.Test_Database.psycopg.connect"):
            blocker = patch(target, side_effect=AssertionError("REAL_CONFIG_OR_DB_FORBIDDEN"))
            blocker.start()
            self.addCleanup(blocker.stop)

    def test_default_plan_is_offline_ten_rows_and_has_no_apply(self):
        with patch("sys.stdout", new_callable=io.StringIO) as output:
            self.assertEqual(tool.main([]), 0)
        result = json.loads(output.getvalue())
        self.assertFalse(result["database_connected"])
        self.assertFalse(result["apply_mode_available"])
        self.assertFalse(result["manifest_export_available"])
        self.assertEqual(result["fixture_rows_total"], 10)

    def test_apply_flag_is_rejected_before_database_access(self):
        with patch("sys.stderr", new_callable=io.StringIO), self.assertRaises(SystemExit) as raised:
            tool.main(["--apply"])
        self.assertEqual(raised.exception.code, 2)

    def test_invalid_namespace_stops_before_any_dml(self):
        conn = MagicMock()
        with self.assertRaises(CheckFailed):
            tool.create_fixture(conn, "ordinary-user-team")
        conn.cursor.assert_not_called()
        conn.execute.assert_not_called()

    def test_sqlstate_survives_uow_sanitization_without_raw_exception_text(self):
        try:
            try:
                raise psycopg.errors.InsufficientPrivilege("SyntheticPrivateDSN")
            except psycopg.Error:
                raise StorageUnavailable() from None
        except StorageUnavailable as exc:
            result = tool.safe_diagnostic(exc)
        self.assertEqual(result["sqlstate"], "42501")
        self.assertNotIn("SyntheticPrivateDSN", json.dumps(result))

    def test_create_fixture_uses_owner_only_for_four_users_then_app_repositories(self):
        conn = MagicMock()
        cur = conn.cursor.return_value.__enter__.return_value
        cur.fetchone.side_effect = [(10,), (20,), (30,), (40,)]
        with patch.object(tool, "switch") as switch, patch.object(tool, "assert_auth_connection"), \
                patch.object(tool, "team_call", side_effect=[{"id": "50"}, {}, {"id": "60"}]) as teams, \
                patch.object(tool, "project_call", return_value={"id": "70"}) as projects, \
                patch.object(tool, "validate_fixture"):
            fixture = tool.create_fixture(conn, "spms-ct-" + "a" * 32)
        self.assertEqual([c.args[1] for c in switch.call_args_list], ["project_owner", "project_app"])
        self.assertEqual(cur.execute.call_count, 4)
        self.assertTrue(all("INSERT INTO public.users" in c.args[0] for c in cur.execute.call_args_list))
        self.assertEqual([c.args[1] for c in teams.call_args_list], ["create", "add_member", "create"])
        self.assertEqual(projects.call_args.args[1], "create")
        self.assertEqual(fixture.users["free_student"], "40")
        conn.commit.assert_not_called()

    def test_row_delta_requires_exactly_four_users_two_teams_three_members_one_project(self):
        before = ("metadata", {**dict.fromkeys(tool.COUNTS, 0), "auth.credentials": 2, "auth.sessions": 1})
        expected = ("metadata", {**tool.COUNTS, "auth.credentials": 2, "auth.sessions": 1})
        conn = MagicMock()
        with patch.object(tool, "switch"), patch.object(tool, "assert_auth_connection"), \
                patch.object(tool, "snapshot", return_value=expected):
            tool.verify_fixture_counts(conn, before)
        unexpected = ("metadata", {**expected[1], "auth.credentials": 3})
        with patch.object(tool, "switch"), patch.object(tool, "assert_auth_connection"), \
                patch.object(tool, "snapshot", return_value=unexpected), self.assertRaises(CheckFailed):
            tool.verify_fixture_counts(conn, before)

    def rehearsal(self, *, fail_action=False, drift=False, bad_inventory=False, fail_role=False):
        conn = MagicMock()
        baseline = ("metadata", {"public.users": 2})
        after = ("metadata changed", {"public.users": 2}) if drift else baseline
        fixture, state = MagicMock(), {"member_id": "2", "project_description": None}
        action_calls = []

        @contextmanager
        def transaction(**kwargs):
            self.assertEqual(kwargs, {"force_rollback": True})
            try:
                yield
            finally:
                pass

        conn.transaction.side_effect = transaction

        def action(*args):
            action_calls.append(args[-2:])
            if fail_action:
                raise psycopg.errors.InsufficientPrivilege("private SQL parameters")

        with patch.object(tool, "switch", side_effect=CheckFailed("ROLE_GUARD") if fail_role else None), \
                patch.object(tool, "inventory", return_value=(52, ["drift"]) if bad_inventory else (52, [])), \
                patch.object(tool, "snapshot", side_effect=[baseline, after]), \
                patch.object(tool, "fingerprint", return_value="full row values hash"), \
                patch.object(tool, "create_fixture", return_value=fixture) as create, \
                patch.object(tool, "verify_fixture_counts"), \
                patch.object(tool, "validate_fixture", return_value=state), \
                patch.object(tool, "action", side_effect=action):
            result = tool.rehearse(connector=lambda: conn)
        conn.commit.assert_not_called()
        conn.rollback.assert_called()
        conn.close.assert_called_once()
        return result, action_calls, create

    def test_success_rehearses_twelve_actions_and_never_claims_concurrency(self):
        result, calls, _ = self.rehearsal()
        self.assertEqual(result["result"], "PASS")
        self.assertTrue(result["baseline_restored"])
        self.assertFalse(result["committed"])
        self.assertFalse(result["manifest_exported"])
        self.assertFalse(result["multisession_tested"])
        self.assertEqual(len(calls), 12)
        self.assertTrue(all(not c["blocking_tested"] for c in result["sequential_actions"]))

    def test_permission_failure_rolls_back_stops_and_preserves_sqlstate(self):
        result, calls, _ = self.rehearsal(fail_action=True)
        self.assertEqual(result["result"], "FAIL")
        self.assertEqual(result["diagnostic"]["sqlstate"], "42501")
        self.assertTrue(result["baseline_restored"])
        self.assertEqual(len(calls), 1)
        self.assertNotIn("private SQL parameters", json.dumps(result))

    def test_postflight_drift_is_never_reported_as_pass(self):
        result, _, _ = self.rehearsal(drift=True)
        self.assertEqual(result["result"], "FAIL")
        self.assertFalse(result["baseline_restored"])
        self.assertEqual(result["diagnostic"]["reason"], "BASELINE_NOT_RESTORED")

    def test_wrong_installed_baseline_prevents_fixture_creation(self):
        result, calls, create = self.rehearsal(bad_inventory=True)
        self.assertEqual(result["result"], "FAIL")
        self.assertEqual(result["diagnostic"]["reason"], "INSTALLED_BASELINE_REQUIRED")
        create.assert_not_called()
        self.assertEqual(calls, [])

    def test_role_guard_failure_prevents_fixture_creation_and_closes(self):
        result, calls, create = self.rehearsal(fail_role=True)
        self.assertEqual(result["result"], "FAIL")
        create.assert_not_called()
        self.assertEqual(calls, [])

    def test_connection_failure_is_sanitized_and_has_no_fallback(self):
        connector = MagicMock(side_effect=psycopg.OperationalError("private DB password"))
        result = tool.rehearse(connector=connector)
        self.assertEqual(result["result"], "FAIL")
        self.assertFalse(result["baseline_restored"])
        connector.assert_called_once_with()
        self.assertNotIn("private DB password", json.dumps(result))


if __name__ == "__main__":
    unittest.main()
