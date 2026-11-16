"""Offline destination/security tests. Synthetic URLs; never open a socket."""

from types import SimpleNamespace
import unittest
from unittest.mock import MagicMock, patch

from backend.db_target import database_target, InvalidDatabaseTarget
from backend.auth_store import AuthRepository, StorageUnavailable, assert_auth_connection, open_auth_connection


REF = "abcdefghijklmnopqrst"
DIRECT = f"postgresql://project_app:FixturePass1@db.{REF}.supabase.co:5432/postgres?sslmode=require"
SESSION = f"postgresql://project_app.{REF}:FixturePass1@aws-0-ap-southeast-1.pooler.supabase.com:5432/postgres?sslmode=require"


def cloud(url=DIRECT):
    return {"AUTH_DB_TARGET": "supabase_test", "SUPABASE_PROJECT_REF": REF, "AUTH_DATABASE_URL": url}


class DatabaseTargetTests(unittest.TestCase):
    def test_local_default_is_unchanged_and_admin_config_is_ignored(self):
        target = database_target({"AUTH_DB_PASSWORD": "FixturePass1", "DB_NAME": "student_project_management", "DB_USER": "postgres"})
        self.assertEqual((target.mode, target.database, target.auth_schema), ("local_test", "student_project_management_v1_test", "auth"))
        self.assertEqual(target.connect_kwargs["user"], "project_app")

    def test_local_requires_application_password(self):
        for config in ({}, {"DB_PASSWORD": "FixturePass1"}):
            with self.assertRaises(InvalidDatabaseTarget):
                database_target(config)

    def test_cloud_url_requires_explicit_profile_and_ref(self):
        for config in ({"AUTH_DATABASE_URL": DIRECT, "AUTH_DB_PASSWORD": "FixturePass1"}, {**cloud(), "SUPABASE_PROJECT_REF": ""}, {**cloud(), "AUTH_DB_TARGET": "production"}):
            with self.assertRaises(InvalidDatabaseTarget):
                database_target(config)

    def test_accepts_direct_and_session_pooler_only(self):
        for url in (DIRECT, SESSION):
            target = database_target(cloud(url))
            self.assertEqual((target.database, target.auth_schema), ("postgres", "spms_auth"))
            self.assertEqual(target.connect_kwargs["port"], 5432)

    def test_rejects_admin_or_wrong_application_role(self):
        for url in (DIRECT.replace("project_app:", "postgres:"), DIRECT.replace("project_app:", "project_owner:"), SESSION.replace("project_app.", "postgres.")):
            with self.assertRaises(InvalidDatabaseTarget):
                database_target(cloud(url))

    def test_rejects_database_overrides_and_unsafe_libpq_options(self):
        for url in (DIRECT.replace("/postgres?", "/student_project_management?"), DIRECT+"&options=-c%20role=postgres", DIRECT+"&hostaddr=127.0.0.1", DIRECT+"&service=other", DIRECT+"&user=postgres"):
            with self.assertRaises(InvalidDatabaseTarget):
                database_target(cloud(url))

    def test_rejects_missing_tls_and_password(self):
        for url in (DIRECT.split("?")[0], DIRECT.replace("require", "disable"), DIRECT.replace("FixturePass1", "")):
            with self.assertRaises(InvalidDatabaseTarget):
                database_target(cloud(url))

    def test_rejects_wrong_project_host_and_transaction_pooler(self):
        for url in (DIRECT.replace(REF, "x"*20), SESSION.replace(REF, "x"*20), SESSION.replace(":5432/", ":6543/"), DIRECT.replace(f"db.{REF}.supabase.co", "localhost"), DIRECT.replace("postgresql://", "https://")):
            with self.assertRaises(InvalidDatabaseTarget):
                database_target(cloud(url))

    def test_percent_encoded_password_and_verify_full(self):
        url = DIRECT.replace("FixturePass1", "Fixture%40Pass%3A1").replace("sslmode=require", "sslmode=verify-full&sslrootcert=C%3A%2Fcert.pem")
        target = database_target(cloud(url))
        self.assertEqual(target.connect_kwargs["password"], "Fixture@Pass:1")
        self.assertEqual(target.connect_kwargs["sslrootcert"], "C:/cert.pem")
        self.assertNotIn("Fixture", repr(target))

    def test_bad_config_never_connects_or_discloses_url(self):
        with patch.dict("os.environ", cloud(DIRECT+"&options=unsafe"), clear=True), patch("backend.auth_store.dotenv_values", return_value={}), patch("backend.auth_store.psycopg.connect") as connect:
            with self.assertRaises(StorageUnavailable) as error:
                open_auth_connection()
            connect.assert_not_called()
            self.assertNotIn("FixturePass1", str(error.exception))

    def test_cloud_opener_uses_only_validated_kwargs(self):
        with patch.dict("os.environ", cloud(SESSION), clear=True), patch("backend.auth_store.dotenv_values", return_value={}), patch("backend.auth_store.psycopg.connect") as connect:
            open_auth_connection()
            settings = connect.call_args.kwargs
            self.assertEqual(settings["user"], f"project_app.{REF}")
            self.assertEqual(settings["dbname"], "postgres")
            self.assertFalse(settings["autocommit"])
            self.assertEqual(settings["sslmode"], "require")

    def test_readonly_opener_sets_server_side_readonly_before_queries(self):
        with patch.dict("os.environ", cloud(), clear=True), patch("backend.auth_store.dotenv_values", return_value={}), patch("backend.auth_store.psycopg.connect") as connect:
            open_auth_connection(readonly=True)
            self.assertIn("default_transaction_read_only=on", connect.call_args.kwargs["options"])

    def test_local_preview_refuses_cloud_mode_before_opening_connection(self):
        from backend.tests import auth_browser_server as preview
        with patch.dict("os.environ", {"SPMS_AUTH_BROWSER_ROLLBACK": "1"}), patch.object(preview, "runtime_target", return_value=SimpleNamespace(mode="supabase_test")), patch.object(preview, "open_auth_connection") as app, patch.object(preview, "connect_test_database") as owner:
            with self.assertRaises(StorageUnavailable):
                preview.run_fixture()
            app.assert_not_called()
            owner.assert_not_called()

    def test_cloud_guard_requires_physical_app_login(self):
        good = ("postgres", "project_app", False, False, False, False, False, "origin", False, False, False)
        with patch.dict("os.environ", cloud(), clear=True), patch("backend.auth_store.dotenv_values", return_value={}):
            conn = MagicMock()
            cursor = conn.cursor.return_value.__enter__.return_value
            cursor.fetchone.side_effect = [good, (True,)]
            assert_auth_connection(conn)
            cursor.fetchone.side_effect = [good, (False,)]
            with self.assertRaises(StorageUnavailable):
                assert_auth_connection(conn)
            cursor.fetchone.side_effect = [("student_project_management",)+good[1:]]
            with self.assertRaises(StorageUnavailable):
                assert_auth_connection(conn)

    def test_profile_guard_fails_closed_before_reading_remote_connection(self):
        with patch.dict("os.environ", {"AUTH_DB_TARGET": "supabase_test"}, clear=True), patch("backend.auth_store.dotenv_values", return_value={}):
            conn = MagicMock()
            with self.assertRaises(StorageUnavailable):
                assert_auth_connection(conn)
            conn.cursor.assert_not_called()

    def test_repository_selects_only_fixed_schema_and_keeps_parameters_bound(self):
        for db, expected in (("postgres", "spms_auth"), ("student_project_management_v1_test", "auth")):
            conn = MagicMock()
            conn.info = SimpleNamespace(dbname=db)
            repository = AuthRepository(conn)
            repository.credentials("someone@example.test")
            query, params = conn.cursor.return_value.__enter__.return_value.execute.call_args.args
            self.assertIn(expected+".lookup_credentials", query)
            self.assertEqual(params, ("someone@example.test",))


if __name__ == "__main__":
    unittest.main()
