"""Offline safety tests. Mocked servers/workers do not prove TCP/PG locking."""

from contextlib import contextmanager
import io
import json
from queue import Queue
import unittest
from unittest.mock import MagicMock, patch

from fastapi import Depends
import psycopg

from backend.auth_store import StorageUnavailable
from backend.tests import http_concurrency as runner
from backend.tests.test_team_project_concurrency_harness import manifest as team_manifest
from backend.tests.test_topic_vote_concurrency import manifest as vote_manifest


class HttpConcurrencySafetyTests(unittest.TestCase):
    def setUp(self):
        for target in ("backend.auth_store.psycopg.connect", "backend.auth_store.dotenv_values",
                       "database.tools.Test_Database.dotenv_values", "backend.tests.http_concurrency.socket.socket"):
            blocker = patch(target, side_effect=AssertionError("REAL_NETWORK_OR_CONFIG_FORBIDDEN"))
            blocker.start()
            self.addCleanup(blocker.stop)
        self.team = runner.team_cases.Fixture.parse(team_manifest())
        self.vote = runner.vote_cases.VoteFixture.parse(vote_manifest())

    def test_default_and_manifest_arguments_alone_remain_offline(self):
        for args in ([], ["--team-fixture", "missing.json", "--vote-fixture", "missing2.json"]):
            with patch("sys.stdout", new_callable=io.StringIO) as output:
                self.assertEqual(runner.main(args), 0)
            result = json.loads(output.getvalue())
            self.assertFalse(result["database_connected"])
            self.assertEqual(len(result["cases"]), 14)
            self.assertFalse(result["new_persistent_fixture_required"])
            self.assertNotIn('"PASS"', output.getvalue())

    def test_both_manifests_are_required_before_loading_or_connecting(self):
        for args in (["--run-rollback"], ["--run-rollback", "--team-fixture", "missing.json"]):
            with patch.object(runner.team_cases.Fixture, "load") as load, patch("sys.stdout", new_callable=io.StringIO) as output:
                self.assertEqual(runner.main(args), 1)
            load.assert_not_called()
            self.assertEqual(json.loads(output.getvalue())["reason"], "BOTH_MANIFESTS_REQUIRED")

    def test_bad_manifest_stops_before_connections(self):
        with patch.object(runner.team_cases.Fixture, "load", side_effect=runner.CheckFailed("MANIFEST_DATABASE")), \
                patch.object(runner, "rollback_connection") as connect, patch("sys.stdout", new_callable=io.StringIO):
            self.assertEqual(runner.main(["--run-rollback", "--team-fixture", "bad.json", "--vote-fixture", "bad2.json"]), 1)
        connect.assert_not_called()

    def test_request_plans_use_approved_actors_methods_and_statuses(self):
        for case in runner.CASES:
            fixture = self.team if case.startswith("HRC") else self.vote
            plan = runner.request_plan(fixture, case)
            self.assertIn(plan.actor, fixture.users.values())
            self.assertTrue(plan.path.startswith("/api/v1/"))
            self.assertNotIn("actor_user_id", plan.body or {})
        self.assertEqual(runner.request_plan(self.team, "HRC02").actor, self.team.users["member_b"])
        self.assertEqual(runner.request_plan(self.team, "HRC06").status, 500)
        self.assertEqual(runner.request_plan(self.vote, "HVC06").actor, self.vote.users["c"])
        self.assertEqual(runner.request_plan(self.vote, "HVC07").method, "GET")
        with self.assertRaises(runner.CheckFailed):
            runner.request_plan(self.team, "UNKNOWN")

    def test_all_six_uows_borrow_only_the_intended_connection(self):
        conn = MagicMock()
        @contextmanager
        def manager(actual):
            self.assertIs(actual, conn)
            yield "fixture repository"
        with patch.dict(runner.MANAGERS, {key: manager for key in runner.MANAGERS}):
            app = runner.request_app(conn, [])
            self.assertEqual(set(app.dependency_overrides), set(runner.MANAGERS))
            for override in app.dependency_overrides.values():
                with override()() as value:
                    self.assertEqual(value, "fixture repository")
        conn.commit.assert_not_called()

    def test_new_unhandled_uow_prevents_server_creation(self):
        app = runner.create_app()
        def get_unhandled_uow():
            raise AssertionError("Must not execute")
        @app.get("/test-only", dependencies=[Depends(get_unhandled_uow)])
        def test_only():
            return {}
        with patch.object(runner, "create_app", return_value=app), self.assertRaisesRegex(runner.CheckFailed, "HTTP_UOW_OVERRIDE_SET_CHANGED"):
            runner.request_app(MagicMock(), [])

    def test_uow_observes_sqlstate_without_replacing_production_error(self):
        @contextmanager
        def manager(conn):
            try:
                raise psycopg.errors.LockNotAvailable("SyntheticPrivateSQL")
            except psycopg.Error:
                raise StorageUnavailable() from None
            yield  # pragma: no cover
        states = []
        with patch.dict(runner.MANAGERS, {runner.get_team_uow: manager}):
            app = runner.request_app(MagicMock(), states)
            with self.assertRaises(StorageUnavailable):
                with app.dependency_overrides[runner.get_team_uow]()():
                    pass
        self.assertEqual(states, ["55P03"])

    def credential_connection(self, *, existing=False, superuser=False):
        conn = MagicMock()
        cur = conn.cursor.return_value.__enter__.return_value
        cur.fetchone.side_effect = [("project_owner", superuser), (existing,)]
        conn.execute.return_value.fetchone.return_value = (runner.TEST_DB, "project_app", "read committed")
        return conn, cur

    def test_credential_fixture_uses_owner_only_before_serving_and_forces_rollback(self):
        conn, cur = self.credential_connection()
        with patch.object(runner, "switch") as switch, patch.object(runner, "assert_auth_connection"), \
                patch.object(runner, "validate"), patch.object(runner, "encoded_password", return_value="encoded"):
            with runner.http_connection(self.team, "HRC01", connector=lambda: conn):
                pass
        self.assertEqual([call.args[1] for call in switch.call_args_list], ["project_app", "project_owner", "project_app"])
        inserts = [call for call in cur.execute.call_args_list if call.args[0].startswith("INSERT")]
        self.assertEqual(len(inserts), 1)
        self.assertIn("auth.credentials", inserts[0].args[0])
        self.assertEqual(inserts[0].args[1][0], self.team.users["leader_a"])
        conn.transaction.assert_called_once_with(force_rollback=True)
        conn.commit.assert_not_called()
        conn.rollback.assert_called()
        conn.close.assert_called_once()

    def test_existing_credential_or_superuser_owner_never_overwrites_or_serves(self):
        for options in ({"existing": True}, {"superuser": True}):
            conn, cur = self.credential_connection(**options)
            with patch.object(runner, "switch"), patch.object(runner, "assert_auth_connection"), \
                    patch.object(runner, "validate"), self.assertRaises(runner.CheckFailed):
                with runner.http_connection(self.team, "HRC01", connector=lambda: conn):
                    self.fail("Fixture must stop before serving")
            self.assertFalse(any(call.args[0].startswith("INSERT") for call in cur.execute.call_args_list))
            conn.rollback.assert_called()
            conn.close.assert_called_once()

    def test_http_identity_mismatch_still_rolls_back_and_closes(self):
        conn, _ = self.credential_connection()
        conn.execute.return_value.fetchone.return_value = (runner.TEST_DB, "project_owner", "read committed")
        with patch.object(runner, "switch"), patch.object(runner, "assert_auth_connection"), \
                patch.object(runner, "validate"), patch.object(runner, "encoded_password", return_value="encoded"), \
                self.assertRaisesRegex(runner.CheckFailed, "HTTP_CONNECTION_IDENTITY"):
            with runner.http_connection(self.team, "HRC01", connector=lambda: conn):
                pass
        conn.rollback.assert_called()
        conn.close.assert_called_once()

    def test_live_server_binds_only_owned_ephemeral_loopback_and_disables_proxy(self):
        listener, server, thread = MagicMock(), MagicMock(), MagicMock()
        listener.getsockname.return_value = ("127.0.0.1", 51234)
        server.started, thread.is_alive.return_value = True, False
        with patch.object(runner.socket, "socket", return_value=listener), \
                patch.object(runner.uvicorn, "Config"), patch.object(runner.uvicorn, "Server", return_value=server), \
                patch.object(runner, "Thread", return_value=thread), patch.object(runner.httpx, "Client") as client:
            with runner.live_client(object()):
                pass
        listener.bind.assert_called_once_with(("127.0.0.1", 0))
        client.assert_called_once_with(base_url="http://127.0.0.1:51234", timeout=12, trust_env=False, follow_redirects=False)
        self.assertTrue(server.should_exit)
        thread.join.assert_called()
        listener.close.assert_called_once()

    def test_failed_server_start_stops_and_closes_owned_socket(self):
        listener, server, thread = MagicMock(), MagicMock(), MagicMock()
        listener.getsockname.return_value = ("127.0.0.1", 51234)
        server.started, thread.is_alive.return_value = False, False
        with patch.object(runner.socket, "socket", return_value=listener), patch.object(runner.uvicorn, "Config"), \
                patch.object(runner.uvicorn, "Server", return_value=server), patch.object(runner, "Thread", return_value=thread), \
                self.assertRaisesRegex(runner.CheckFailed, "HTTP_SERVER_NOT_READY"):
            with runner.live_client(object()):
                pass
        self.assertTrue(server.should_exit)
        listener.close.assert_called_once()

    def test_http_response_requires_exact_status_cache_and_empty_204(self):
        client = MagicMock()
        response = client.request.return_value
        response.status_code, response.content, response.headers = 204, b"", {"cache-control": "no-store"}
        runner.http_call(client, "POST", "/api/v1/teams/me/leave", body={}, status=204)
        self.assertEqual(client.request.call_args.kwargs["headers"]["Origin"], "http://localhost:3000")
        response.content = b"Unexpected body"
        with self.assertRaisesRegex(runner.CheckFailed, "HTTP_BODY_SHAPE"):
            runner.http_call(client, "POST", "/api/v1/teams/me/leave", body={}, status=204)
        response.status_code = 200
        with self.assertRaisesRegex(runner.CheckFailed, "HTTP_STATUS_MISMATCH"):
            runner.http_call(client, "POST", "/api/v1/teams/me/leave", body={}, status=204)

    def test_login_identity_and_csrf_are_checked_before_business_request(self):
        conn, client = MagicMock(), MagicMock()
        conn.execute.return_value.fetchone.return_value = ("fixture@example.test", "student")
        response = MagicMock()
        response.json.return_value = {"data": {"id": "wrong", "role": "student"}}
        with patch.object(runner, "http_call", return_value=response), self.assertRaisesRegex(runner.CheckFailed, "HTTP_SESSION_IDENTITY"):
            runner.authenticate(client, conn, "1")

    def test_timeout_requires_real_observed_sqlstate_and_no_leaked_sql_fields(self):
        response = MagicMock()
        response.json.return_value = {"error": {"code": "INTERNAL_ERROR", "message": "fixed"}}
        runner.verify_response(None, None, self.team, "HRC06", {}, response, ["55P03"])
        with self.assertRaisesRegex(runner.CheckFailed, "HTTP_TIMEOUT_TRANSLATION"):
            runner.verify_response(None, None, self.team, "HRC06", {}, response, [])
        response.json.return_value["error"]["sql"] = "SyntheticPrivateSQL"
        with self.assertRaisesRegex(runner.CheckFailed, "HTTP_TIMEOUT_LEAK"):
            runner.verify_response(None, None, self.team, "HRC06", {}, response, ["55P03"])

    def test_worker_reports_only_after_server_and_outer_transaction_close(self):
        ready, done, events, conn = Queue(), Queue(), [], MagicMock()
        @contextmanager
        def connection(*args):
            try:
                yield conn
            finally:
                self.assertTrue(done.empty())
                events.append("rollback")
        @contextmanager
        def client(*args):
            try:
                yield MagicMock()
            finally:
                events.append("server_closed")
        with patch.object(runner, "http_connection", connection), patch.object(runner, "live_client", client), \
                patch.object(runner, "request_app"), patch.object(runner, "authenticate"), patch.object(runner, "http_call"), \
                patch.object(runner, "verify_response"):
            runner.worker(self.team, "HRC01", {}, ready, done)
        self.assertEqual(events, ["server_closed", "rollback"])
        self.assertTrue(done.get_nowait()["ok"])

    def test_worker_failure_has_no_secret_error_text(self):
        done = Queue()
        with patch.object(runner, "http_connection", side_effect=psycopg.OperationalError("SyntheticPrivatePassword")):
            runner.worker(self.team, "HRC01", {}, Queue(), done)
        result = done.get_nowait()
        self.assertFalse(result["ok"])
        self.assertNotIn("SyntheticPrivatePassword", json.dumps(result))

    def orchestration(self, *, case="HRC01", wait=True, public_drift=False, auth_drift=False, worker_ok=True):
        observer, first, second = MagicMock(), MagicMock(), MagicMock()
        observer.execute.return_value.fetchone.return_value = (10,)
        first.execute.return_value.fetchone.return_value = (20,)
        first_closed = False
        @contextmanager
        def connection(**kwargs):
            nonlocal first_closed
            if kwargs.get("readonly"):
                yield observer
            else:
                try:
                    yield first
                finally:
                    first_closed = True
        def start_thread(*, target, args, daemon):
            self.assertIs(target, runner.worker)
            self.assertTrue(daemon)
            ready, done = args[-2:]
            thread = MagicMock()
            def start():
                ready.put((second, 30))
                done.put({"ok": True, "http_status": 500 if case == "HRC06" else 200, "sqlstate": "55P03" if case == "HRC06" else None}
                         if worker_ok else {"ok": False, "sqlstate": "42501", "reason": "WORKER_FAILED"})
            thread.start.side_effect = start
            return thread
        def finish(*args):
            self.assertTrue(first_closed)
        with patch.object(runner, "rollback_connection", connection), patch.object(runner, "validate", return_value={}), \
                patch.object(runner.team_cases, "action"), patch.object(runner, "Thread", side_effect=start_thread), \
                patch.object(runner, "fingerprint", side_effect=["before", "changed" if public_drift else "before"]), \
                patch.object(runner, "baseline", side_effect=["before", "changed" if auth_drift else "before"]), \
                patch.object(runner, "wait_for_block", side_effect=None if wait else runner.CheckFailed("NO_DATABASE_BLOCK")) as observed, \
                patch.object(runner, "finish_worker", side_effect=finish) as cleanup:
            try:
                return runner.run_case(self.team, case)
            finally:
                observed.assert_called_once_with(observer, 20, 30)
                cleanup.assert_called_once_with(unittest.mock.ANY, second)

    def test_orchestrator_requires_real_wait_evidence_and_releases_a_before_join(self):
        result = self.orchestration()
        self.assertTrue(result["wait_observed"])
        self.assertEqual(result["transport"], "LOOPBACK_TCP")

    def test_timeout_expects_http_500_and_sqlstate_55p03(self):
        result = self.orchestration(case="HRC06")
        self.assertEqual((result["http_status"], result["sqlstate"]), (500, "55P03"))

    def test_missing_wait_never_reports_pass(self):
        with self.assertRaisesRegex(runner.CheckFailed, "NO_DATABASE_BLOCK"):
            self.orchestration(wait=False)

    def test_public_or_auth_drift_never_reports_pass(self):
        for options in ({"public_drift": True}, {"auth_drift": True}):
            with self.assertRaises(runner.CheckFailed):
                self.orchestration(**options)

    def test_worker_error_propagates_fixed_reason_and_sqlstate(self):
        with self.assertRaises(runner.CheckFailed) as error:
            self.orchestration(worker_ok=False)
        self.assertEqual(error.exception.sqlstate, "42501")
        self.assertEqual(str(error.exception), "HTTP_UNEXPECTED_WORKER_RESULT")

    def test_unknown_case_stops_before_snapshot_or_connection(self):
        with patch.object(runner, "baseline") as before, self.assertRaises(runner.CheckFailed):
            runner.run_case(self.team, "UNKNOWN")
        before.assert_not_called()


if __name__ == "__main__":
    unittest.main()
