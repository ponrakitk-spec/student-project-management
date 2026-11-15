"""Topic vote HTTP/PostgreSQL/privacy tests. All fixtures share outer ROLLBACK."""

from contextlib import contextmanager
import json
import unittest
from unittest.mock import patch
from uuid import uuid4

import psycopg

from backend.auth_api import CSRF_COOKIE, CSRF_HEADER, SESSION_COOKIE
from backend.auth_security import hash_password, session_digest
from backend.auth_store import StorageUnavailable
from backend.committee_api import get_committee_uow
from backend.committee_store import committee_transaction_on
from backend.invitation_api import get_invitation_uow
from backend.invitation_store import invitation_transaction_on
from backend.tests import test_committee_api as committee_base, test_project_api as project_base, test_team_api as base
from backend.topic_vote_api import get_topic_vote_uow
from backend.topic_vote_store import TopicVoteError, TopicVoteRepository, topic_vote_transaction_on
from database.tests.Auth_Regression import switch

ROOT = "/api/v1/committee/projects"
TEAM = "/api/v1/projects/me/committee"


class TopicVoteAPIIntegrationTests(unittest.TestCase):
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
        self.app.dependency_overrides[get_topic_vote_uow] = lambda: lambda: topic_vote_transaction_on(self.conn)

    tearDown = base.TeamAPIIntegrationTests.tearDown
    signed_in = base.TeamAPIIntegrationTests.signed_in
    create_team = base.TeamAPIIntegrationTests.create
    assert_error = base.TeamAPIIntegrationTests.assert_error
    team = project_base.ProjectAPIIntegrationTests.team
    post_project = project_base.ProjectAPIIntegrationTests.post
    login_as = project_base.ProjectAPIIntegrationTests.login_as
    fixture_actor = project_base.ProjectAPIIntegrationTests.fixture_actor
    fixture_submission = project_base.ProjectAPIIntegrationTests.fixture_submission
    write = committee_base.CommitteeAPIIntegrationTests.write
    add = committee_base.CommitteeAPIIntegrationTests.add
    url = committee_base.CommitteeAPIIntegrationTests.url
    roster = committee_base.CommitteeAPIIntegrationTests.roster

    def advisor(self, name="Vote committee fixture"):
        with self.conn.cursor() as cur:
            switch(cur, "project_owner")
            cur.execute("INSERT INTO public.users(full_name,email,role) VALUES (%s,%s,'advisor') RETURNING id",
                        (name, "topic-vote-" + uuid4().hex + "@example.test"))
            identifier = str(cur.fetchone()[0])
            cur.execute("INSERT INTO auth.credentials(user_id,password_hash) VALUES (%s,%s)",
                        (identifier, hash_password(base.PASSWORD)))
            switch(cur, "project_app")
        return identifier

    def login_id(self, identifier):
        email = self.conn.execute("SELECT email FROM public.users WHERE id=%s", (identifier,)).fetchone()[0]
        self.login_as({"email": email})

    def scenario(self, count=3, *, review="approved", member=False):
        leader, team = self.team()
        extra = project_base.ProjectAPIIntegrationTests.member(self, leader, team) if member else None
        self.login_as(leader)
        project = self.post_project({"name": "Live project", "description": "Original topic"}).json()["data"]
        submission = self.fixture_submission(leader, project, review)
        accepted = str(self.conn.execute("SELECT public.v1_advisor_for_project(%s)", (project["id"],)).fetchone()[0])
        coordinator = self.signed_in("coordinator")
        # Committee appointment requires approved; pending scenarios begin with
        # an approved round then create a later round, never bypass the guard.
        rows = self.roster(project, count) if review == "approved" else []
        return {"leader": leader, "project": project, "submission": str(submission), "advisor": accepted,
                "coordinator": coordinator, "assignments": rows, "member": extra}

    def vote_url(self, data):
        return f"{ROOT}/{data['project']['id']}/topic-votes"

    def vote(self, data, member=0, vote="approved", comment=None, submission=None):
        self.login_id(data["assignments"][member]["advisor"]["id"])
        return self.write("POST", self.vote_url(data), {"submission_id": submission or data["submission"], "vote": vote, "comment": comment})

    def reader(self, data, mode="team"):
        if mode == "team":
            self.login_as(data["leader"])
            response = self.client.get(TEAM)
        elif mode == "advisor":
            self.login_id(data["advisor"])
            response = self.client.get(f"/api/v1/advisor/projects/{data['project']['id']}/committee")
        else:
            self.login_as(data["coordinator"])
            response = self.client.get(f"/api/v1/coordinator/projects/{data['project']['id']}/topic-votes")
        self.assertEqual(response.status_code, 200, response.text)
        return response.json()["data"]

    def resubmit(self, data, review=None):
        self.fixture_actor(data["leader"])
        self.conn.execute("SET CONSTRAINTS public.c_submission_requires_file DEFERRED")
        identifier = self.conn.execute("INSERT INTO public.project_submissions(project_id,submitted_by) VALUES (%s,%s) RETURNING id",
                                       (data["project"]["id"], data["leader"]["id"])).fetchone()[0]
        self.conn.execute("INSERT INTO public.project_submission_files(submission_id,file_data,original_filename,mime_type) VALUES (%s,%s,'phase.pdf','application/pdf')",
                          (identifier, b"DB-only vote phase fixture"))
        self.conn.execute("SET CONSTRAINTS ALL IMMEDIATE")
        if review is not None:
            self.conn.execute("SELECT set_config('app.actor_user_id',%s,true)", (data["advisor"],))
            self.conn.execute("SELECT public.v1_review_submission(%s,%s,%s)",
                              (identifier, review, "Please revise" if review == "revision_requested" else None))
        return str(identifier)

    def test_assignment_scoped_worklist_and_accepted_advisor_list_are_separate(self):
        data = self.scenario()
        self.login_id(data["assignments"][0]["advisor"]["id"])
        response = self.client.get(ROOT)
        self.assertIn(data["project"]["id"], [row["id"] for row in response.json()["data"]])
        self.assertEqual(self.client.get("/api/v1/advisor/projects").json()["data"], [])
        self.login_id(data["advisor"])
        self.assertNotIn(data["project"]["id"], [row["id"] for row in self.client.get(ROOT).json()["data"]])
        accepted = self.client.get("/api/v1/advisor/projects").json()["data"]
        self.assertIn(data["project"]["id"], [row["id"] for row in accepted])
        self.assertTrue(all(set(row) == {"id", "name", "description", "team"} for row in accepted))

    def test_before_completion_every_role_gets_only_its_allowed_projection(self):
        data = self.scenario()
        first = self.vote(data, 0, comment="Zulu secret comment").json()["data"]
        self.assertEqual(self.vote(data, 1, "revision_requested", "Alpha secret comment").status_code, 201)
        self.login_id(data["assignments"][2]["advisor"]["id"])
        context = self.client.get(self.vote_url(data)).json()["data"]
        self.assertTrue(context["can_vote"])
        self.assertIsNone(context["rounds"][0]["own_vote"])
        self.assertIsNone(context["rounds"][0]["decision"])
        self.assertNotIn("secret comment", json.dumps(context))
        for mode in ("team", "advisor"):
            result = self.reader(data, mode)
            self.assertEqual(set(result), {"project", "committee", "rounds"})
            self.assertEqual(len(result["committee"]), 3)
            self.assertTrue(all(set(row) == {"full_name"} for row in result["committee"]))
            self.assertIsNone(result["rounds"][0]["decision"])
            self.assertEqual(result["rounds"][0]["comments"], [])
            self.assertNotIn("secret comment", json.dumps(result))
        coordinator = self.reader(data, "coordinator")
        votes = coordinator["rounds"][0]["votes"]
        self.assertEqual(len(votes), 2)
        self.assertEqual(votes[0]["id"], first["id"])
        self.assertEqual(set(votes[0]), {"id", "advisor", "vote", "comment", "voted_at"})
        self.assertEqual(votes[0]["advisor"]["id"], data["assignments"][0]["advisor"]["id"])

    def test_completion_releases_only_decision_and_content_sorted_real_comments(self):
        data = self.scenario()
        self.assertEqual(self.vote(data, 0, comment="Zulu comment").status_code, 201)
        self.assertEqual(self.vote(data, 1, "revision_requested", "Alpha comment").status_code, 201)
        response = self.vote(data, 2, comment=" \t\n")
        self.assertEqual(response.status_code, 201)
        self.assertIsNone(response.json()["data"]["comment"])
        self.assertEqual(set(response.json()["data"]), {"id", "submission_id", "vote", "comment", "voted_at"})
        self.assertEqual(response.headers["cache-control"], "no-store")
        self.assertFalse(response.headers.get_list("set-cookie"))
        context = self.client.get(self.vote_url(data)).json()["data"]
        self.assertEqual(context["rounds"][0]["decision"], "approved")
        self.assertEqual(context["blocking_reason"], "ALREADY_VOTED")
        self.assertNotIn("Alpha comment", json.dumps(context))
        for mode in ("team", "advisor"):
            result = self.reader(data, mode)
            round = result["rounds"][0]
            self.assertEqual(set(round), {"submission", "decision", "comments"})
            self.assertEqual(round["decision"], "approved")
            self.assertEqual(round["comments"], ["Alpha comment", "Zulu comment"])
            self.assertTrue(all(isinstance(row, str) for row in round["comments"]))

    def test_half_is_revision_and_duplicate_comments_are_preserved_without_author_order(self):
        data = self.scenario(4)
        for index in range(4):
            response = self.vote(data, index, "approved" if index < 2 else "revision_requested", "Same comment")
            self.assertEqual(response.status_code, 201)
            if index < 3:
                self.assertIsNone(self.client.get(self.vote_url(data)).json()["data"]["rounds"][0]["decision"])
        result = self.reader(data)
        self.assertEqual(result["rounds"][0]["decision"], "revision_requested")
        self.assertEqual(result["rounds"][0]["comments"], ["Same comment"] * 4)

    def test_less_than_three_members_and_pending_submission_do_not_allow_votes(self):
        data = self.scenario(2)
        self.login_id(data["assignments"][0]["advisor"]["id"])
        self.assertEqual(self.client.get(self.vote_url(data)).json()["data"]["blocking_reason"], "COMMITTEE_INCOMPLETE")
        self.assert_error(self.vote(data), 409, "COMMITTEE_INCOMPLETE")
        # A later pending round is prepared after a completed revision decision.
        other = self.scenario()
        for index in range(3):
            self.vote(other, index, "revision_requested", "Please revise")
        latest = self.resubmit(other)
        self.assert_error(self.vote(other, submission=latest), 409, "SUBMISSION_NOT_APPROVED")

    def test_duplicate_vote_is_conflict_and_http_has_no_edit_or_delete_methods(self):
        data = self.scenario()
        first = self.vote(data).json()["data"]
        self.assert_error(self.vote(data, vote="revision_requested", comment="Different"), 409, "VOTE_ALREADY_CAST")
        self.assertEqual(self.client.get(self.vote_url(data)).json()["data"]["rounds"][0]["own_vote"], first)
        for method in ("PATCH", "PUT", "DELETE"):
            self.assertEqual(self.write(method, self.vote_url(data), {}).status_code, 405)

    def test_new_round_requires_current_snapshot_token_and_keeps_own_history(self):
        data = self.scenario()
        for index in range(3):
            self.vote(data, index, "revision_requested", "Please revise")
        latest = self.resubmit(data)
        self.assert_error(self.vote(data), 409, "SUBMISSION_CHANGED")
        context = self.client.get(self.vote_url(data)).json()["data"]
        self.assertEqual(context["latest_submission_id"], latest)
        self.assertEqual(context["blocking_reason"], "SUBMISSION_NOT_APPROVED")
        self.assertEqual(len(context["rounds"]), 2)
        self.assertIsNone(context["rounds"][0]["own_vote"])
        self.assertIsNotNone(context["rounds"][1]["own_vote"])
        self.conn.execute("SELECT set_config('app.actor_user_id',%s,true)", (data["advisor"],))
        self.conn.execute("SELECT public.v1_review_submission(%s,'approved',NULL)", (latest,))
        self.assertEqual(self.vote(data, submission=latest).status_code, 201)
        reader = self.reader(data)
        self.assertIsNone(reader["rounds"][0]["decision"])
        self.assertEqual(reader["rounds"][0]["comments"], [])
        self.assertEqual(reader["rounds"][1]["decision"], "revision_requested")

    def test_vote_locks_coordinator_roster_and_snapshot_is_not_live_project_name(self):
        data = self.scenario()
        self.assertEqual(self.vote(data).status_code, 201)
        context = self.client.get(self.vote_url(data)).json()["data"]
        self.assertEqual(context["rounds"][0]["submission"]["snapshot_name"], "Live project")
        self.login_as(data["coordinator"])
        response = self.add(data["project"], self.advisor())
        self.assert_error(response, 409, "COMMITTEE_ROSTER_LOCKED")

    def test_unassigned_advisor_and_foreign_project_cannot_read_or_cast(self):
        data = self.scenario()
        stranger = self.advisor()
        self.login_id(stranger)
        self.assert_error(self.client.get(self.vote_url(data)), 404, "COMMITTEE_PROJECT_NOT_FOUND")
        self.assert_error(self.write("POST", self.vote_url(data), {"submission_id": data["submission"], "vote": "approved"}), 404, "COMMITTEE_PROJECT_NOT_FOUND")
        self.assert_error(self.client.get(f"/api/v1/advisor/projects/{data['project']['id']}/committee"), 404, "PROJECT_NOT_FOUND")
        self.login_id(data["assignments"][0]["advisor"]["id"])
        self.assert_error(self.client.get(f"{ROOT}/9223372036854775807/topic-votes"), 404, "COMMITTEE_PROJECT_NOT_FOUND")

    def test_reader_membership_and_accepted_advisor_are_rechecked_without_exposing_individuals(self):
        data = self.scenario(member=True)
        self.login_as(data["member"])
        self.assertEqual(self.client.get(TEAM).status_code, 200)
        self.assertEqual(self.write("POST", "/api/v1/teams/me/leave", {}).status_code, 204)
        self.assert_error(self.client.get(TEAM), 404, "TEAM_NOT_FOUND")
        self.login_id(data["assignments"][0]["advisor"]["id"])
        self.assert_error(self.client.get(f"/api/v1/advisor/projects/{data['project']['id']}/committee"), 404, "PROJECT_NOT_FOUND")

    def test_role_auth_csrf_origin_expiry_and_revocation(self):
        data = self.scenario()
        payload = {"submission_id": data["submission"], "vote": "approved"}
        self.assert_error(self.write("POST", self.vote_url(data), payload), 403, "VOTE_ACCESS_FORBIDDEN")
        self.login_as(data["leader"])
        self.assert_error(self.client.get(ROOT), 403, "VOTE_ACCESS_FORBIDDEN")
        self.login_id(data["assignments"][0]["advisor"]["id"])
        self.assert_error(self.write("POST", self.vote_url(data), payload, {CSRF_HEADER: "bad"}), 403, "CSRF_INVALID")
        self.assert_error(self.write("POST", self.vote_url(data), payload, {"Origin": "https://invalid.example"}), 403, "ORIGIN_NOT_ALLOWED")
        digest = session_digest(self.client.cookies.get(SESSION_COOKIE))
        with self.conn.cursor() as cur:
            switch(cur, "project_owner")
            cur.execute("UPDATE auth.sessions SET created_at=clock_timestamp()-interval '2 hours',expires_at=clock_timestamp()-interval '1 hour' WHERE token_hash=%s", (digest,))
            switch(cur, "project_app")
        self.assert_error(self.client.get(ROOT), 401, "AUTHENTICATION_REQUIRED")
        self.login_id(data["assignments"][0]["advisor"]["id"])
        digest = session_digest(self.client.cookies.get(SESSION_COOKIE))
        self.conn.execute("DELETE FROM auth.sessions WHERE token_hash=%s", (digest,))
        self.assert_error(self.client.get(ROOT), 401, "AUTHENTICATION_REQUIRED")
        self.client.cookies.clear()
        self.assert_error(self.write("POST", self.vote_url(data), payload), 401, "AUTHENTICATION_REQUIRED")

    def test_invalid_payload_comment_ids_and_actor_spoof_are_rejected_without_echo(self):
        data = self.scenario()
        self.login_id(data["assignments"][0]["advisor"]["id"])
        for body in ({}, {"submission_id": 1, "vote": "approved"}, {"submission_id": "0", "vote": "approved"},
                     {"submission_id": data["submission"], "vote": "unknown"},
                     {"submission_id": data["submission"], "vote": "revision_requested", "comment": " \t\n"},
                     {"submission_id": data["submission"], "vote": "approved", "comment": "bad\x00text"},
                     {"submission_id": data["submission"], "vote": "approved", "assignment_id": "DoNotEchoTopicVote"}):
            response = self.write("POST", self.vote_url(data), body)
            self.assert_error(response, 422, "VALIDATION_ERROR")
            self.assertNotIn("DoNotEchoTopicVote", response.text)
        response = self.write("POST", self.vote_url(data), {"submission_id": data["submission"], "vote": "approved", "comment": "x" * 4096},
                              {"X-Actor-User-Id": data["coordinator"]["id"], "X-Role": "coordinator"})
        self.assertEqual(response.status_code, 201)
        self.assertEqual(len(response.json()["data"]["comment"]), 4096)

    def test_project_authorization_is_checked_again_after_lock(self):
        data = self.scenario()
        self.login_id(data["assignments"][0]["advisor"]["id"])
        original, calls = TopicVoteRepository.project, []
        def recheck(store, actor, project, scope):
            calls.append(project)
            if len(calls) == 2:
                raise TopicVoteError("COMMITTEE_PROJECT_NOT_FOUND")
            return original(store, actor, project, scope)
        with patch.object(TopicVoteRepository, "project", recheck), patch.object(TopicVoteRepository, "controlled_vote") as cast:
            self.assert_error(self.write("POST", self.vote_url(data), {"submission_id": data["submission"], "vote": "approved"}), 404, "COMMITTEE_PROJECT_NOT_FOUND")
        cast.assert_not_called()

    def test_sql_and_transaction_completion_failures_never_return_fake_success(self):
        data = self.scenario()
        self.login_id(data["assignments"][0]["advisor"]["id"])
        original = TopicVoteRepository.controlled_vote
        def fail(store, *args):
            original(store, *args)
            raise StorageUnavailable()
        with patch.object(TopicVoteRepository, "controlled_vote", fail):
            self.assert_error(self.write("POST", self.vote_url(data), {"submission_id": data["submission"], "vote": "approved"}), 500, "INTERNAL_ERROR")
        self.assertIsNone(self.client.get(self.vote_url(data)).json()["data"]["rounds"][0]["own_vote"])
        @contextmanager
        def failing():
            with topic_vote_transaction_on(self.conn) as store:
                yield store
                raise StorageUnavailable()
        self.app.dependency_overrides[get_topic_vote_uow] = lambda: failing
        self.assert_error(self.write("POST", self.vote_url(data), {"submission_id": data["submission"], "vote": "approved"}), 500, "INTERNAL_ERROR")
        self.app.dependency_overrides[get_topic_vote_uow] = lambda: lambda: topic_vote_transaction_on(self.conn)
        self.assertIsNone(self.client.get(self.vote_url(data)).json()["data"]["rounds"][0]["own_vote"])

    def test_unknown_sql_permission_failures_are_sanitized_without_owner_fallback(self):
        data = self.scenario()
        self.login_id(data["assignments"][0]["advisor"]["id"])
        for error in (psycopg.errors.InsufficientPrivilege("DoNotEchoSQL"), psycopg.errors.RaiseException("DoNotEchoSQL")):
            with patch.object(TopicVoteRepository, "controlled_vote", side_effect=error):
                response = self.write("POST", self.vote_url(data), {"submission_id": data["submission"], "vote": "approved"})
            self.assert_error(response, 500, "INTERNAL_ERROR")
            self.assertNotIn("DoNotEchoSQL", response.text)

    def test_database_unique_defense_maps_only_the_vote_constraint(self):
        data = self.scenario()
        self.assertEqual(self.vote(data).status_code, 201)
        with patch.object(TopicVoteRepository, "own_vote", return_value=None):
            response = self.write("POST", self.vote_url(data), {"submission_id": data["submission"], "vote": "approved"})
        self.assert_error(response, 409, "VOTE_ALREADY_CAST")
        self.assertIsNotNone(self.client.get(self.vote_url(data)).json()["data"]["rounds"][0]["own_vote"])

    def test_reader_distinguishes_no_team_and_no_project(self):
        self.signed_in()
        self.assert_error(self.client.get(TEAM), 404, "TEAM_NOT_FOUND")
        self.create_team()
        self.assert_error(self.client.get(TEAM), 404, "PROJECT_NOT_FOUND")


if __name__ == "__main__":
    unittest.main()
