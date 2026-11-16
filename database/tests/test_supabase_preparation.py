"""Offline contract/source checks. This suite does not install hosted SQL."""

from pathlib import Path
import io
import re
import unittest
from unittest.mock import MagicMock, patch

from backend.auth_store import StorageUnavailable
from database.tools import Supabase_Preflight as tool


ROOT = Path(__file__).resolve().parents[2]


def definitions(text, kind):
    if kind == "FUNCTION":
        pattern = r"CREATE(?: OR REPLACE)? FUNCTION\s+((?:public\.|auth\.|spms_auth\.)?\w+)\b[\s\S]*?\$(?:[A-Za-z_][A-Za-z0-9_]*)?\$;"
    else:
        pattern = r"CREATE TABLE\s+((?:public\.|auth\.|spms_auth\.)?\w+)\s*\([\s\S]*?\n\);"
    return {m.group(1): m.group(0) for m in re.finditer(pattern, text, re.I)}


class SupabasePackageTests(unittest.TestCase):
    def test_complete_v1_ddl_and_rbac_match_canonical_excluding_deployment_wrapper(self):
        target = (ROOT / "database/supabase/001_bootstrap.sql").read_text(encoding="utf-8")
        def normalized(text):
            return "\n".join(line.strip() for line in text.splitlines()
                             if line.strip() and not line.lstrip().startswith("--")
                             and line.strip() not in ("BEGIN;", "COMMIT;"))
        source = (ROOT / "database/schema/Database_Schema_V1_A02_A05_REVIEW_DRAFT.sql").read_text(encoding="utf-8-sig")
        ddl = target.split("-- V1 public tables, constraints, workflow functions and triggers.", 1)[1].split("-- V1 least-privilege application grants.", 1)[0]
        self.assertEqual(normalized(ddl), normalized(source))
        source = (ROOT / "database/schema/Database_Schema_V1_A02_A05_RBAC_REVIEW_TEMPLATE.sql").read_text(encoding="utf-8-sig")
        source = source[source.index("SELECT pg_catalog.set_config"):source.index("END $postflight$;")+len("END $postflight$;")]
        source = source.replace(":'v1_app_role'", "'project_app'").replace(":'v1_owner_role'", "'project_owner'")
        source = source.replace(':"v1_app_role"', "project_app").replace(':"v1_owner_role"', "project_owner")
        rbac = target[target.index("SELECT pg_catalog.set_config"):target.index("END $postflight$;")+len("END $postflight$;")]
        self.assertEqual(normalized(rbac), normalized(source))

    def test_v1_tables_and_all_52_functions_are_verbatim(self):
        source = (ROOT / "database/schema/Database_Schema_V1_A02_A05_REVIEW_DRAFT.sql").read_text(encoding="utf-8-sig")
        target = (ROOT / "database/supabase/001_bootstrap.sql").read_text(encoding="utf-8")
        for kind, count in (("FUNCTION", 52), ("TABLE", 14)):
            original, actual = definitions(source, kind), definitions(target, kind)
            self.assertEqual(len(original), count)
            for name, sql in original.items():
                self.assertEqual(actual.get(name), sql, name)

    def test_auth_functions_and_tables_only_change_schema_namespace(self):
        source = "\n".join((ROOT / f"database/auth/{name}").read_text(encoding="utf-8-sig")
                           for name in ("001_auth_storage_review.sql", "002_auth_rbac_review.sql"))
        target = (ROOT / "database/supabase/001_bootstrap.sql").read_text(encoding="utf-8")
        for kind in ("FUNCTION", "TABLE"):
            original, actual = definitions(source, kind), definitions(target, kind)
            self.assertEqual(len(original), 2)
            for name, sql in original.items():
                expected = sql.replace("auth.", "spms_auth.")
                self.assertEqual(actual.get(name.replace("auth.", "spms_auth.")), expected)

    def test_install_is_guarded_fresh_only_and_includes_api_boundary(self):
        text = (ROOT / "database/supabase/001_bootstrap.sql").read_text(encoding="utf-8")
        self.assertIn("refusing to overwrite", text)
        self.assertIn("current_database() <> 'postgres'", text)
        self.assertIn("current_user <> 'postgres'", text)
        self.assertIn("$api_boundary$", text)
        self.assertNotIn("rolpassword IS NOT NULL", text)
        self.assertEqual(len(re.findall(r"^BEGIN;", text, re.M)), 1)
        self.assertEqual(len(re.findall(r"^COMMIT;", text, re.M)), 1)
        self.assertNotRegex(text, r"(?im)^\s*(DROP|TRUNCATE)\s")

    def test_role_creation_is_atomic_and_app_does_not_inherit_owner(self):
        text = (ROOT / "database/supabase/000_roles.sql").read_text(encoding="utf-8")
        self.assertIn("BEGIN;", text)
        self.assertIn("COMMIT;", text)
        self.assertIn("GRANT project_owner TO postgres WITH INHERIT FALSE, SET TRUE", text)
        self.assertNotRegex(text, r"GRANT project_owner TO project_app")
        self.assertNotIn("PASSWORD '", text)


class SupabasePreflightTests(unittest.TestCase):
    def connection(self):
        conn = MagicMock()
        conn.execute.return_value.fetchone.return_value = ("on",)
        return conn

    def test_preflight_is_structural_readonly_and_explicit_about_limits(self):
        conn = self.connection()
        values = [(14,14), (86,), (28,), (52,), (24,), (2,),
                  (False,False,False,False,False,False,True,True,True), (False,), ("17.fixture",)]
        conn.cursor.return_value.__enter__.return_value.fetchone.side_effect = values
        with patch.object(tool, "assert_auth_connection"):
            result = tool.inspect(conn)
        self.assertEqual(result["status"], "PASS_PRELIMINARY_READONLY")
        self.assertFalse(result["writes_tested"])
        self.assertFalse(result["full_v1_parity_verified"])
        for call in conn.cursor.return_value.__enter__.return_value.execute.call_args_list:
            self.assertTrue(call.args[0].lstrip().startswith(("SELECT", "SHOW")))

    def test_readwrite_and_wrong_counts_fail_closed(self):
        conn = self.connection()
        conn.execute.return_value.fetchone.return_value = ("off",)
        with patch.object(tool, "assert_auth_connection") as guard:
            with self.assertRaises(StorageUnavailable):
                tool.inspect(conn)
            guard.assert_not_called()
        conn.execute.return_value.fetchone.return_value = ("on",)
        conn.cursor.return_value.__enter__.return_value.fetchone.return_value = (13,13)
        with patch.object(tool, "assert_auth_connection"):
            with self.assertRaises(StorageUnavailable):
                tool.inspect(conn)

    def test_local_mode_does_not_open_any_connection(self):
        with patch.object(tool, "runtime_target", return_value=MagicMock(mode="local_test")), patch.object(tool, "open_auth_connection") as connect, patch("sys.stdout", new_callable=io.StringIO):
            self.assertEqual(tool.main(), 1)
            connect.assert_not_called()

    def test_driver_errors_are_redacted_and_connection_rolled_back(self):
        conn = self.connection()
        with patch.object(tool, "runtime_target", return_value=MagicMock(mode="supabase_test")), patch.object(tool, "open_auth_connection", return_value=conn) as connect, patch.object(tool, "inspect", side_effect=RuntimeError("PrivateURLFixture")), patch("sys.stdout", new_callable=io.StringIO) as output:
            self.assertEqual(tool.main(), 1)
            connect.assert_called_once_with(readonly=True)
            conn.rollback.assert_called_once()
            conn.close.assert_called_once()
            self.assertNotIn("PrivateURLFixture", output.getvalue())


if __name__ == "__main__":
    unittest.main()
