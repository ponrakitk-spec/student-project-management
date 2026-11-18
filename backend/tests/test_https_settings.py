"""Offline HTTPS configuration and real HTTP cookie/CSRF boundary checks."""

from contextlib import contextmanager
import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

from backend.auth_api import AuthSettings, CSRF_COOKIE, get_auth_uow
from backend.auth_security import hash_password
from backend.main import create_app


ORIGIN = "https://spms-frontend.example.test"


class HTTPSSettingsTests(unittest.TestCase):
    def test_local_defaults_are_unchanged(self):
        self.assertEqual(AuthSettings.from_environment({}), AuthSettings())

    def test_canonical_origin_enforces_secure_and_preserves_eight_hours(self):
        settings = AuthSettings.from_environment({"AUTH_WEB_ORIGIN": ORIGIN+"/", "VERCEL": "1"})
        self.assertEqual(settings.allowed_origins, (ORIGIN,))
        self.assertTrue(settings.cookie_secure)
        self.assertEqual(settings.session_ttl_seconds, 28800)

    def test_vercel_without_explicit_web_origin_fails_closed(self):
        with self.assertRaises(ValueError):
            AuthSettings.from_environment({"VERCEL": "1"})

    def test_rejects_insecure_wildcard_paths_and_url_credentials(self):
        for origin in ("http://localhost:3000", "http://spms.example.test", "https://*.vercel.app", "https://localhost", "https://127.0.0.1", ORIGIN+"/login", ORIGIN+"?x=1", ORIGIN+"#x", "https://user:PrivateFixture@spms.example.test", ORIGIN+":8443", " "+ORIGIN, ORIGIN+",https://other.example.test", "https://spms.example.test\\evil"):
            with self.subTest(origin=origin), self.assertRaises(ValueError) as caught:
                AuthSettings.from_environment({"AUTH_WEB_ORIGIN": origin})
            self.assertNotIn("PrivateFixture", str(caught.exception))

    def test_explicit_settings_for_tests_do_not_read_hosting_environment(self):
        with patch.dict("os.environ", {"VERCEL": "1"}, clear=True):
            app = create_app(AuthSettings())
            self.assertEqual(app.state.auth_settings, AuthSettings())

    def test_app_loads_environment_without_opening_database(self):
        with patch.dict("os.environ", {"AUTH_WEB_ORIGIN": ORIGIN}, clear=True), patch("psycopg.connect", side_effect=AssertionError("Unexpected connection")):
            app = create_app()
            self.assertEqual(app.state.auth_settings.allowed_origins, (ORIGIN,))
            self.assertTrue(app.state.auth_settings.cookie_secure)
            self.assertEqual(len(app.openapi()["paths"]), 47)


class HTTPSCookieTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.encoded = hash_password("ReviewPassA1")

    def setUp(self):
        self.user = {"id": "1", "full_name": "HTTPS Fixture", "email": "student@example.test", "role": "student"}
        self.deleted = []
        testcase = self
        class Repository:
            def credentials(self, email): return (1, testcase.encoded)
            def user(self, user_id): return testcase.user
            def create_session(self, *args): pass
            def delete_session(self, digest): testcase.deleted.append(digest)
            def active_user(self, digest): return testcase.user
        @contextmanager
        def uow():
            yield Repository()
        self.app = create_app(AuthSettings.from_environment({"AUTH_WEB_ORIGIN": ORIGIN}))
        self.app.dependency_overrides[get_auth_uow] = lambda: uow
        # Same-origin HTTPS from the browser's perspective (a deployment proxy
        # is still a separate integration check, not claimed by these tests).
        self.client = TestClient(self.app, base_url=ORIGIN)

    def tearDown(self):
        self.client.close()

    def login(self, origin=ORIGIN):
        return self.client.post("/api/v1/auth/login", headers={"Origin": origin}, json={"email": self.user["email"], "password": "ReviewPassA1"})

    def test_https_login_sets_host_only_secure_cookies_and_me_works(self):
        response = self.login()
        self.assertEqual(response.status_code, 200)
        cookies = response.headers.get_list("set-cookie")
        self.assertEqual(len(cookies), 2)
        self.assertTrue(all("Secure" in c and "SameSite=lax" in c and "Max-Age=28800" in c and "Domain=" not in c for c in cookies))
        self.assertIn("HttpOnly", cookies[0])
        self.assertNotIn("HttpOnly", cookies[1])
        self.assertEqual(self.client.get("/api/v1/auth/me").json()["data"], self.user)

    def test_wrong_origin_is_rejected_even_when_forwarded_headers_claim_allowed_origin(self):
        response = self.client.post("/api/v1/auth/login", headers={"Origin": "https://other.example.test", "X-Forwarded-Host": "spms-frontend.example.test"}, json={"email": self.user["email"], "password": "ReviewPassA1"})
        self.assertEqual(response.status_code, 403)
        self.assertFalse(response.headers.get_list("set-cookie"))
        self.assertEqual(self.login("http://localhost:3000").status_code, 403)

    def test_https_logout_still_requires_csrf_and_deletes_secure_cookies(self):
        self.assertEqual(self.login().status_code, 200)
        self.assertEqual(self.client.post("/api/v1/auth/logout", headers={"Origin": ORIGIN}).status_code, 403)
        token = self.client.cookies.get(CSRF_COOKIE)
        response = self.client.post("/api/v1/auth/logout", headers={"Origin": ORIGIN, "X-CSRF-Token": token})
        self.assertEqual(response.status_code, 204)
        self.assertTrue(self.deleted)
        self.assertTrue(all("Secure" in c and "Max-Age=0" in c and "SameSite=lax" in c for c in response.headers.get_list("set-cookie")))

    def test_cors_grants_only_explicit_frontend(self):
        for origin, expected in ((ORIGIN, 200), ("https://other.example.test", 400)):
            response = self.client.options("/api/v1/auth/login", headers={"Origin": origin, "Access-Control-Request-Method": "POST"})
            self.assertEqual(response.status_code, expected)
            self.assertEqual(response.headers.get("access-control-allow-origin"), ORIGIN if expected==200 else None)


if __name__ == "__main__":
    unittest.main()
