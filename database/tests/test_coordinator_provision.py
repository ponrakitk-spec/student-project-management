"""New coordinator tool boundaries and PostgreSQL fixtures; never --apply."""

import io
import json
import unittest
from unittest.mock import patch
from uuid import uuid4

from backend.auth_security import verify_password
from backend.auth_store import assert_auth_connection, open_auth_connection
from backend.tests import test_team_api as base
from database.tests.Auth_Regression import switch
from database.tools import Auth_Provision_Coordinator as tool


class CoordinatorProvisionBoundaryTests(unittest.TestCase):
    def invoke(self, args):
        with patch("sys.stdout", new_callable=io.StringIO) as output:
            status = tool.main(args)
        return status, json.loads(output.getvalue())

    def test_default_is_dry_run_and_explicit_apply_requires_test_db(self):
        for args, apply in (([], False), (["--apply", "--confirm-database", tool.TEST_DB], True)):
            with patch.object(tool, "prompt_password", return_value=base.PASSWORD), \
                    patch.object(tool, "provision", return_value={"result": "PASS"}) as provision:
                status, _ = self.invoke([*args, "--full-name", "Coordinator fixture", "--email", "coord@example.test"])
            self.assertEqual(status, 0)
            self.assertEqual(provision.call_args.kwargs, {"apply": apply})

    def test_unknown_password_and_role_arguments_are_redacted(self):
        for args in (["--password", "PrivateSyntheticValueA1"], ["--role", "advisor"]):
            with patch.object(tool, "connect_test_database") as connect:
                status, result = self.invoke(args)
            self.assertEqual((status, result["code"]), (1, "ARGUMENT_ERROR"))
            self.assertNotIn("PrivateSyntheticValueA1", str(result))
            connect.assert_not_called()

    def test_bad_apply_confirmation_never_prompts_or_connects(self):
        for args in (["--apply"], ["--apply", "--confirm-database", "student_project_management"]):
            with patch.object(tool, "prompt_password") as prompt, patch.object(tool, "connect_test_database") as connect:
                status, result = self.invoke(args)
            self.assertEqual((status, result["code"]), (1, "TEST_DATABASE_CONFIRMATION_REQUIRED"))
            prompt.assert_not_called()
            connect.assert_not_called()

    def test_check_has_no_password_or_account_prompts(self):
        with patch.object(tool, "check", return_value={"result": "PASS"}), \
                patch.object(tool, "prompt_password") as password, patch("builtins.input") as account:
            self.assertEqual(self.invoke(["--check"])[0], 0)
        password.assert_not_called()
        account.assert_not_called()

    def test_invalid_account_or_password_stops_before_config_or_connection(self):
        with patch.object(tool, "connect_test_database") as connect:
            for name, email, password in ((" ", "coord@example.test", base.PASSWORD),
                                           ("Coord", "invalid", base.PASSWORD),
                                           ("Coord", "coord@example.test", "lowercase")):
                with self.assertRaises(tool.ProvisionError):
                    tool.provision(name, email, password)
        connect.assert_not_called()


class CoordinatorProvisionIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        base.TeamAPIIntegrationTests.setUpClass.__func__(cls)

    @classmethod
    def tearDownClass(cls):
        base.TeamAPIIntegrationTests.tearDownClass.__func__(cls)

    def setUp(self):
        base.TeamAPIIntegrationTests.setUp(self)
        self.email = "coordinator-provision-" + uuid4().hex + "@example.test"

    tearDown = base.TeamAPIIntegrationTests.tearDown

    def test_atomic_creation_normalizes_identity_hashes_password_and_never_returns_hash(self):
        user = tool.create_coordinator_on(self.conn, " \tCoordinator fixture\n", " " + self.email.upper(), base.PASSWORD)
        self.assertEqual((user["role"], user["full_name"], user["email"]), ("coordinator", "Coordinator fixture", self.email))
        encoded = self.conn.execute("SELECT password_hash FROM auth.credentials WHERE user_id=%s", (user["id"],)).fetchone()[0]
        self.assertTrue(verify_password(base.PASSWORD, encoded))
        self.assertFalse(verify_password(" " + base.PASSWORD, encoded))
        self.assertNotIn(encoded, json.dumps(user))
        self.assertNotIn(base.PASSWORD, json.dumps(user))

    def test_existing_email_is_never_activated_changed_or_reassigned(self):
        user = tool.create_coordinator_on(self.conn, "Original", self.email, base.PASSWORD)
        before = self.conn.execute("SELECT u.full_name,u.role,c.password_hash FROM public.users u JOIN auth.credentials c ON c.user_id=u.id WHERE u.id=%s", (user["id"],)).fetchone()
        with self.assertRaises(tool.ProvisionError) as caught:
            tool.create_coordinator_on(self.conn, "Replacement", self.email.upper(), "AnotherFixtureA1")
        self.assertEqual(caught.exception.code, "ACCOUNT_ALREADY_EXISTS")
        self.assertEqual(self.conn.execute("SELECT u.full_name,u.role,c.password_hash FROM public.users u JOIN auth.credentials c ON c.user_id=u.id WHERE u.id=%s", (user["id"],)).fetchone(), before)

    def test_credential_failure_also_removes_new_user(self):
        def invalid(conn, user, encoded):
            conn.execute("INSERT INTO auth.credentials(user_id,password_hash) VALUES (%s,'invalid')", (user,))
        with patch.object(tool, "insert_credentials", invalid), self.assertRaises(tool.ProvisionError):
            tool.create_coordinator_on(self.conn, "Coordinator", self.email, base.PASSWORD)
        self.assertEqual(self.conn.execute("SELECT count(*) FROM public.users WHERE email=%s", (self.email,)).fetchone(), (0,))

    def test_service_default_and_nested_helper_leave_no_persistent_account(self):
        result = tool.provision("Coordinator dry run", self.email, base.PASSWORD)
        self.assertEqual(result["mode"], "DRY_RUN")
        self.assertFalse(result["persisted"])
        with self.conn.transaction(force_rollback=True):
            tool.create_coordinator_on(self.conn, "Coordinator nested", self.email, base.PASSWORD)
        self.assertEqual(self.conn.execute("SELECT count(*) FROM public.users WHERE email=%s", (self.email,)).fetchone(), (0,))

    def test_provisioned_coordinator_can_login_and_student_routes_still_deny(self):
        tool.create_coordinator_on(self.conn, "Coordinator", self.email, base.PASSWORD)
        with self.conn.cursor() as cur:
            switch(cur, "project_app")
        self.assertEqual(self.client.post("/api/v1/auth/login", headers=base.ORIGIN, json={"email": self.email, "password": base.PASSWORD}).status_code, 200)
        self.assertEqual(self.client.get("/api/v1/auth/me").json()["data"]["role"], "coordinator")
        # Committee UOW is deliberately not called here: it must not escape
        # the borrowed fixture connection before override in Committee tests.
        self.assertEqual(self.client.get("/api/v1/teams/me").status_code, 403)

    def test_direct_application_login_cannot_create_a_coordinator(self):
        conn = open_auth_connection()
        try:
            with conn.transaction(force_rollback=True):
                assert_auth_connection(conn)
                with self.assertRaises(tool.ProvisionError) as caught:
                    tool.create_coordinator_on(conn, "Coordinator", self.email, base.PASSWORD)
                self.assertEqual(caught.exception.code, "DATABASE_OPERATION_FAILED")
                assert_auth_connection(conn)
        finally:
            try:
                conn.rollback()
            finally:
                conn.close()


if __name__ == "__main__":
    unittest.main()
