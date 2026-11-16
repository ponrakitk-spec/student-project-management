"""Offline error-boundary tests; no DB configuration or connection is read."""
from types import SimpleNamespace
import unittest
from unittest.mock import MagicMock, patch
import psycopg
from backend.auth_store import StorageUnavailable
from backend.task_store import TaskError, task_transaction_on


class DatabaseFailure(psycopg.Error):
    def __init__(self, state, message="Synthetic database failure", constraint=None):
        self.state = state
        self.diagnostic = SimpleNamespace(message_primary=message, constraint_name=constraint)

    @property
    def sqlstate(self):
        return self.state

    @property
    def diag(self):
        return self.diagnostic


class TaskStorageBoundaryTests(unittest.TestCase):
    def error(self, error, expected):
        conn = MagicMock()
        with patch("backend.task_store.assert_auth_connection"), self.assertRaises(expected) as caught:
            with task_transaction_on(conn):
                raise error
        conn.transaction.assert_called_once_with()
        return caught.exception

    def test_permission_timeout_and_unknown_database_errors_are_not_business_conflicts(self):
        for state in ("42501", "55P03", "40001", "23503"):
            self.error(DatabaseFailure(state), StorageUnavailable)

    def test_unknown_trigger_error_is_not_labeled_as_input_error(self):
        self.error(DatabaseFailure("P0001", "An unrelated trigger failed"), StorageUnavailable)

    def test_deferred_last_assignee_error_is_recognized_without_exposing_task_id(self):
        error = self.error(DatabaseFailure("P0001", "In-progress Task 123 must have an assignee at COMMIT"), TaskError)
        self.assertEqual(error.code, "TASK_ASSIGNEE_REQUIRED")
        self.error(DatabaseFailure("P0001", "In-progress Task unsafe must have an assignee at COMMIT"), StorageUnavailable)

    def test_only_exact_unique_constraints_are_recognized(self):
        for constraint, code in (("uq_tasks_milestone_name_ci", "TASK_NAME_CONFLICT"), ("uq_task_assignees_task_member", "ASSIGNEE_ALREADY_ASSIGNED")):
            self.assertEqual(self.error(DatabaseFailure("23505", constraint=constraint), TaskError).code, code)
        self.error(DatabaseFailure("23505", constraint="unrelated_unique"), StorageUnavailable)

    def test_date_and_phase_guards_use_known_trigger_messages_only(self):
        for message, code in (("Invalid Task due_date", "TASK_DUE_DATE_INVALID"), ("Tasks locked after first committee evaluation", "TASK_LOCKED")):
            self.assertEqual(self.error(DatabaseFailure("P0001", message), TaskError).code, code)


if __name__ == "__main__":
    unittest.main()
