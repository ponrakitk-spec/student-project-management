"""Coordinator roster HTTP + PostgreSQL tests; one outer ROLLBACK per case."""

from contextlib import contextmanager
import unittest
from unittest.mock import patch
from uuid import uuid4

import psycopg

from backend.auth_api import CSRF_COOKIE, CSRF_HEADER, SESSION_COOKIE
from backend.auth_security import session_digest
from backend.auth_store import StorageUnavailable
from backend.committee_api import get_committee_uow
from backend.committee_store import CommitteeError, CommitteeRepository, committee_transaction_on
from backend.tests import test_project_api as project_base, test_team_api as base
from backend.invitation_api import get_invitation_uow
from backend.invitation_store import invitation_transaction_on
from database.tests.Auth_Regression import switch

ROOT = "/api/v1/coordinator/projects"


class CommitteeAPIIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        base.TeamAPIIntegrationTests.setUpClass.__func__(cls)

    @classmethod
    def tearDownClass(cls):
        base.TeamAPIIntegrationTests.tearDownClass.__func__(cls)

    def setUp(self):
        project_base.ProjectAPIIntegrationTests.setUp(self)
        self.app.dependency_overrides[get_invitation_uow] = lambda: lambda: invitation_transaction_on(self.conn)
        self.app.dependency_overrides[get_committee_uow] = lambda: lambda: committee_transaction_on(self.conn)

    tearDown = base.TeamAPIIntegrationTests.tearDown
    signed_in = base.TeamAPIIntegrationTests.signed_in
    create_team = base.TeamAPIIntegrationTests.create
    assert_error = base.TeamAPIIntegrationTests.assert_error
    team = project_base.ProjectAPIIntegrationTests.team
    post_project = project_base.ProjectAPIIntegrationTests.post
    login_as = project_base.ProjectAPIIntegrationTests.login_as
    fixture_actor = project_base.ProjectAPIIntegrationTests.fixture_actor
    fixture_submission = project_base.ProjectAPIIntegrationTests.fixture_submission

    def advisor(self, name="Committee fixture"):
        with self.conn.cursor() as cur:
            switch(cur, "project_owner")
            cur.execute("INSERT INTO public.users(full_name,email,role) VALUES (%s,%s,'advisor') RETURNING id",
                        (name, "committee-" + uuid4().hex + "@example.test"))
            identifier = str(cur.fetchone()[0])
            switch(cur, "project_app")
        return identifier

    def scenario(self, review="approved"):
        leader, team = self.team()
        project = self.post_project().json()["data"]
        submission = self.fixture_submission(leader, project, review)
        accepted = str(self.conn.execute("SELECT public.v1_advisor_for_project(%s)", (project["id"],)).fetchone()[0])
        coordinator = self.signed_in("coordinator")
        return leader, project, submission, accepted, coordinator

    def url(self, project, assignment=None):
        return f"{ROOT}/{project['id']}/committee" + (f"/{assignment}" if assignment else "")

    def write(self, method, path, body, headers=None):
        return self.client.request(method, path, headers={**base.ORIGIN,
            CSRF_HEADER: self.client.cookies.get(CSRF_COOKIE) or "", **(headers or {})}, json=body)

    def add(self, project, advisor):
        return self.write("POST", self.url(project), {"advisor_id": advisor})

    def detail(self, project):
        response = self.client.get(self.url(project))
        self.assertEqual(response.status_code, 200, response.text)
        return response.json()["data"]

    def roster(self, project, count=3):
        result = []
        for _ in range(count):
            advisor = self.advisor()
            response = self.add(project, advisor)
            self.assertEqual(response.status_code, 201, response.text)
            result.append(response.json()["data"])
        return result

    def vote(self, submission, assignment, decision="approved"):
        self.conn.execute("SELECT set_config('app.actor_user_id',%s,true)", (assignment["advisor"]["id"],))
        self.conn.execute("SELECT public.v1_cast_vote(%s,%s,%s,%s)",
                          (submission, assignment["id"], decision, "Please revise" if decision == "revision_requested" else None))
        self.conn.execute("SET CONSTRAINTS ALL IMMEDIATE")

    def test_project_list_is_scoped_to_approved_and_dto_has_no_submission_or_private_metadata(self):
        _, project, _, _, coordinator = self.scenario()
        self.team()
        hidden = self.post_project().json()["data"]
        self.login_as(coordinator)
        response = self.client.get(ROOT)
        self.assertEqual(response.status_code, 200)
        data = response.json()["data"]
        ids = [row["id"] for row in data]
        self.assertIn(project["id"], ids)
        self.assertNotIn(hidden["id"], ids)
        self.assertEqual(ids, sorted(ids, key=int, reverse=True))
        for row in data:
            self.assertEqual(set(row), {"id", "name", "description", "team"})
            self.assertEqual(set(row["team"]), {"id", "name"})
        self.assertEqual(response.headers["cache-control"], "no-store")
        self.assertFalse(response.headers.get_list("set-cookie"))

    def test_pending_and_advisor_revision_are_not_visible_and_do_not_allow_roster_writes(self):
        for review in (None, "revision_requested"):
            with self.subTest(review=review), self.conn.transaction(force_rollback=True):
                _, project, _, _, _ = self.scenario(review)
                advisor = self.advisor()
                for response in (self.client.get(self.url(project)),
                                 self.client.get(f"{ROOT}/{project['id']}/committee-candidates"),
                                 self.add(project, advisor)):
                    self.assert_error(response, 404, "PROJECT_NOT_FOUND")

    def test_candidates_only_advisors_exclude_own_advisor_and_existing_roster(self):
        _, project, _, accepted, coordinator = self.scenario()
        first = self.advisor("Committee identical")
        second = self.advisor("Committee identical")
        self.assertEqual(self.add(project, first).status_code, 201)
        response = self.client.get(f"{ROOT}/{project['id']}/committee-candidates")
        data = response.json()["data"]
        ids = [row["id"] for row in data]
        self.assertNotIn(first, ids)
        self.assertNotIn(accepted, ids)
        self.assertNotIn(coordinator["id"], ids)
        self.assertIn(second, ids)
        self.assertTrue(all(set(row) == {"id", "full_name"} for row in data))

    def test_add_one_two_and_more_than_three_then_replace_remove_preserve_identity(self):
        _, project, _, _, _ = self.scenario()
        self.assertEqual(self.detail(project)["assignments"], [])
        rows = self.roster(project, 4)
        self.assertFalse(self.detail(project)["roster_locked"])
        self.assertEqual([r["id"] for r in self.detail(project)["assignments"]], [r["id"] for r in rows])
        replacement = self.advisor()
        response = self.write("PATCH", self.url(project, rows[0]["id"]), {"advisor_id": replacement})
        self.assertEqual(response.status_code, 200, response.text)
        changed = response.json()["data"]
        self.assertEqual(changed["id"], rows[0]["id"])
        self.assertEqual(changed["assigned_at"], rows[0]["assigned_at"])
        self.assertEqual(changed["advisor"]["id"], replacement)
        self.assertEqual(set(changed), {"id", "advisor", "assigned_at"})
        response = self.write("POST", self.url(project, rows[0]["id"]) + "/remove", {})
        self.assertEqual((response.status_code, response.content), (204, b""))
        self.assertFalse(response.headers.get_list("set-cookie"))
        self.assertIsNotNone(self.conn.execute("SELECT id FROM public.users WHERE id=%s", (replacement,)).fetchone())
        self.assertIsNotNone(self.conn.execute("SELECT id FROM public.projects WHERE id=%s", (project["id"],)).fetchone())

    def test_wrong_advisor_own_advisor_duplicate_and_noop_are_distinct(self):
        leader, project, _, accepted, coordinator = self.scenario()
        self.assert_error(self.add(project, accepted), 409, "PROJECT_ADVISOR_INELIGIBLE")
        for target in (leader["id"], coordinator["id"], "9223372036854775807"):
            self.assert_error(self.add(project, target), 404, "COMMITTEE_ADVISOR_NOT_FOUND")
        rows = self.roster(project, 2)
        self.assert_error(self.add(project, rows[0]["advisor"]["id"]), 409, "COMMITTEE_ADVISOR_ALREADY_ASSIGNED")
        self.assert_error(self.write("PATCH", self.url(project, rows[0]["id"]),
                                    {"advisor_id": rows[1]["advisor"]["id"]}), 409, "COMMITTEE_ADVISOR_ALREADY_ASSIGNED")
        self.assertEqual(self.write("PATCH", self.url(project, rows[0]["id"]),
                                    {"advisor_id": rows[0]["advisor"]["id"]}).json()["data"], rows[0])

    def test_first_vote_locks_all_writes_including_noop(self):
        _, project, submission, _, _ = self.scenario()
        rows = self.roster(project)
        self.vote(submission, rows[0])
        before = self.detail(project)
        self.assertTrue(before["roster_locked"])
        for response in (self.add(project, self.advisor()),
                         self.write("PATCH", self.url(project, rows[0]["id"]), {"advisor_id": rows[0]["advisor"]["id"]}),
                         self.write("POST", self.url(project, rows[0]["id"]) + "/remove", {})):
            self.assert_error(response, 409, "COMMITTEE_ROSTER_LOCKED")
        self.assertEqual(self.detail(project), before)

    def test_roster_lock_and_visibility_persist_into_new_submission_round(self):
        leader, project, submission, accepted, _ = self.scenario()
        rows = self.roster(project)
        for row in rows:
            self.vote(submission, row, "revision_requested")
        self.fixture_actor(leader)
        self.conn.execute("SET CONSTRAINTS public.c_submission_requires_file DEFERRED")
        latest = self.conn.execute("INSERT INTO public.project_submissions(project_id,submitted_by) VALUES (%s,%s) RETURNING id",
                                   (project["id"], leader["id"])).fetchone()[0]
        self.conn.execute("INSERT INTO public.project_submission_files(submission_id,file_data,original_filename,mime_type) VALUES (%s,%s,'phase.pdf','application/pdf')",
                          (latest, b"DB-only phase fixture"))
        self.conn.execute("SET CONSTRAINTS ALL IMMEDIATE")
        self.assertTrue(self.detail(project)["roster_locked"])
        self.assert_error(self.add(project, self.advisor()), 409, "COMMITTEE_ROSTER_LOCKED")
        self.assertIn(project["id"], [r["id"] for r in self.client.get(ROOT).json()["data"]])

    def test_foreign_assignment_and_missing_resources_are_opaque_404(self):
        _, first, _, _, coordinator = self.scenario()
        assignment = self.roster(first, 1)[0]
        _, second, _, _, _ = self.scenario()
        self.login_as(coordinator)
        for response in (self.write("PATCH", self.url(second, assignment["id"]), {"advisor_id": self.advisor()}),
                         self.write("POST", self.url(second, assignment["id"]) + "/remove", {}),
                         self.write("POST", self.url(second, "9223372036854775807") + "/remove", {})):
            self.assert_error(response, 404, "COMMITTEE_ASSIGNMENT_NOT_FOUND")
        self.assert_error(self.client.get(f"{ROOT}/9223372036854775807/committee"), 404, "PROJECT_NOT_FOUND")

    def test_student_and_advisor_cannot_read_or_mutate_coordinator_area(self):
        leader, project, _, _, _ = self.scenario()
        advisor = self.advisor()
        for role in ("student", "advisor"):
            self.signed_in(role)
            for response in (self.client.get(ROOT), self.client.get(self.url(project)),
                             self.client.get(f"{ROOT}/{project['id']}/committee-candidates"), self.add(project, advisor)):
                self.assert_error(response, 403, "COMMITTEE_ACCESS_FORBIDDEN")

    def test_auth_csrf_origin_revocation_and_expiry(self):
        _, project, _, _, coordinator = self.scenario()
        advisor = self.advisor()
        csrf = self.client.cookies.get(CSRF_COOKIE)
        self.assert_error(self.write("POST", self.url(project), {"advisor_id": advisor}, {CSRF_HEADER: "wrong"}), 403, "CSRF_INVALID")
        self.assert_error(self.write("POST", self.url(project), {"advisor_id": advisor}, {"Origin": "https://invalid.example"}), 403, "ORIGIN_NOT_ALLOWED")
        self.client.cookies.clear()
        self.assert_error(self.client.get(ROOT), 401, "AUTHENTICATION_REQUIRED")
        self.login_as(coordinator)
        digest = session_digest(self.client.cookies.get(SESSION_COOKIE))
        self.conn.execute("DELETE FROM auth.sessions WHERE token_hash=%s", (digest,))
        self.assert_error(self.client.get(ROOT), 401, "AUTHENTICATION_REQUIRED")
        self.login_as(coordinator)
        digest = session_digest(self.client.cookies.get(SESSION_COOKIE))
        with self.conn.cursor() as cur:
            switch(cur, "project_owner")
            cur.execute("UPDATE auth.sessions SET created_at=clock_timestamp()-interval '2 hours', expires_at=clock_timestamp()-interval '1 hour' WHERE token_hash=%s", (digest,))
            switch(cur, "project_app")
        self.assert_error(self.client.get(ROOT), 401, "AUTHENTICATION_REQUIRED")

    def test_invalid_ids_payload_and_spoofing_never_echo_inputs(self):
        _, project, _, _, _ = self.scenario()
        for value in ("0", "01", "-1", "1.0", "9223372036854775808", "DoNotEchoCommittee"):
            self.assert_error(self.client.get(f"{ROOT}/{value}/committee"), 422, "VALIDATION_ERROR")
        for body in ({}, {"advisor_id": 1}, {"advisor_id": None}, {"advisor_id": "0"},
                     {"advisor_id": "1", "actor_user_id": "DoNotEchoCommittee"},
                     {"advisor_id": "1", "role": "coordinator"}):
            response = self.write("POST", self.url(project), body)
            self.assert_error(response, 422, "VALIDATION_ERROR")
            self.assertNotIn("DoNotEchoCommittee", response.text)
        self.assert_error(self.write("POST", self.url(project, "1") + "/remove", {"actor": "1"}), 422, "VALIDATION_ERROR")

    def test_visibility_is_checked_again_after_lock(self):
        _, project, _, _, _ = self.scenario()
        original = CommitteeRepository.project
        calls = []
        def recheck(store, actor, identifier):
            calls.append(identifier)
            if len(calls) == 2:
                raise CommitteeError("PROJECT_NOT_FOUND")
            return original(store, actor, identifier)
        with patch.object(CommitteeRepository, "project", recheck), patch.object(CommitteeRepository, "controlled_write") as write:
            self.assert_error(self.add(project, self.advisor()), 404, "PROJECT_NOT_FOUND")
        self.assertEqual(len(calls), 2)
        write.assert_not_called()

    def test_database_unique_violation_maps_only_known_constraint(self):
        _, project, _, _, _ = self.scenario()
        row = self.roster(project, 1)[0]
        with patch.object(CommitteeRepository, "validate_advisor"):
            self.assert_error(self.add(project, row["advisor"]["id"]), 409, "COMMITTEE_ADVISOR_ALREADY_ASSIGNED")
        with patch.object(CommitteeRepository, "controlled_write", side_effect=psycopg.errors.UniqueViolation("PrivateUnknownConstraint")):
            response = self.add(project, self.advisor())
        self.assert_error(response, 500, "INTERNAL_ERROR")
        self.assertNotIn("PrivateUnknownConstraint", response.text)

    def test_failure_after_sql_rolls_back_add_replace_and_remove(self):
        _, project, _, _, _ = self.scenario()
        row = self.roster(project, 1)[0]
        advisor = self.advisor()
        before = self.detail(project)
        original = CommitteeRepository.controlled_write
        def fail(store, *args):
            original(store, *args)
            raise StorageUnavailable()
        for method, path, body in (("POST", self.url(project), {"advisor_id": advisor}),
                                   ("PATCH", self.url(project, row["id"]), {"advisor_id": advisor}),
                                   ("POST", self.url(project, row["id"]) + "/remove", {})):
            with patch.object(CommitteeRepository, "controlled_write", fail):
                self.assert_error(self.write(method, path, body), 500, "INTERNAL_ERROR")
            self.assertEqual(self.detail(project), before)

    def test_transaction_completion_failure_prevents_success_response(self):
        _, project, _, _, _ = self.scenario()
        advisor = self.advisor()
        @contextmanager
        def failing():
            with committee_transaction_on(self.conn) as store:
                yield store
                raise StorageUnavailable()
        self.app.dependency_overrides[get_committee_uow] = lambda: failing
        self.assert_error(self.add(project, advisor), 500, "INTERNAL_ERROR")
        self.app.dependency_overrides[get_committee_uow] = lambda: lambda: committee_transaction_on(self.conn)
        self.assertEqual(self.detail(project)["assignments"], [])


if __name__ == "__main__":
    unittest.main()
