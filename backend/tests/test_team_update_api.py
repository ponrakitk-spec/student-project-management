"""Team metadata HTTP + PostgreSQL tests; every fixture shares outer ROLLBACK."""

from contextlib import contextmanager
import unittest
from unittest.mock import patch

import psycopg
from pydantic import ValidationError

from backend.auth_api import CSRF_COOKIE, CSRF_HEADER, SESSION_COOKIE
from backend.auth_security import session_digest
from backend.auth_store import StorageUnavailable
from backend.team_api import TeamUpdateInput, get_team_uow
from backend.team_store import TeamRepository, team_transaction_on
from backend.tests import test_project_api as project_base, test_team_api as base
from database.tests.Auth_Regression import switch

URL = "/api/v1/teams/me"


class TeamUpdateAPIIntegrationTests(unittest.TestCase):
    # Reuse the reviewed app/outer transaction and Project phase fixtures;
    # do not inherit its test methods or add a second connection/UOW fallback.
    @classmethod
    def setUpClass(cls):
        base.TeamAPIIntegrationTests.setUpClass.__func__(cls)

    @classmethod
    def tearDownClass(cls):
        base.TeamAPIIntegrationTests.tearDownClass.__func__(cls)

    setUp = project_base.ProjectAPIIntegrationTests.setUp
    tearDown = base.TeamAPIIntegrationTests.tearDown
    signed_in = base.TeamAPIIntegrationTests.signed_in
    create_team = base.TeamAPIIntegrationTests.create
    assert_error = base.TeamAPIIntegrationTests.assert_error
    team = project_base.ProjectAPIIntegrationTests.team
    post = project_base.ProjectAPIIntegrationTests.post
    member = project_base.ProjectAPIIntegrationTests.member
    login_as = project_base.ProjectAPIIntegrationTests.login_as
    fixture_actor = project_base.ProjectAPIIntegrationTests.fixture_actor
    fixture_submission = project_base.ProjectAPIIntegrationTests.fixture_submission

    def patch_team(self, payload, headers=None):
        return self.client.patch(URL, json=payload,
            headers={**base.ORIGIN,CSRF_HEADER:self.client.cookies.get(CSRF_COOKIE) or "",**(headers or {})})

    def current(self):
        response=self.client.get(URL)
        self.assertEqual(response.status_code,200,response.text)
        return response.json()["data"]

    def test_partial_update_without_project_normalizes_and_preserves_membership(self):
        self.team(); original=self.current()
        for payload,expected in (({"description":" Keep this "},(original["name"],"Keep this")),
                                 ({"name":" \tEdited team\n"},("Edited team","Keep this")),
                                 ({"description":None},("Edited team",None)),
                                 ({"description":" \t"},("Edited team",None)),
                                 ({"name":"Edited team"},("Edited team",None))):
            response=self.patch_team(payload)
            self.assertEqual(response.status_code,200,response.text)
            data=response.json()["data"]
            self.assertEqual((data["name"],data["description"]),expected)
            self.assertEqual(data["id"],original["id"])
            self.assertEqual(data["membership"],original["membership"])
            self.assertEqual(set(data),{"id","name","description","membership"})
            self.assertEqual(response.headers["cache-control"],"no-store")
            self.assertFalse(response.headers.get_list("set-cookie"))
            self.assertEqual(self.current(),data)

    def test_invalid_payloads_are_sanitized_and_unicode_boundaries_match_v1(self):
        self.team(); original=self.current()
        for payload in ({},{"name":None},{"name":True},{"name":42},{"name":" "},{"name":"x"*256},
                        {"name":"bad\x00name"},{"description":False},{"description":"bad\x00text"},
                        *({field:"DoNotEchoTeamFixture"} for field in ("id","team_id","membership","user_id","actor_user_id","role","status","password"))):
            response=self.patch_team(payload)
            self.assert_error(response,422,"VALIDATION_ERROR")
            self.assertNotIn("DoNotEchoTeamFixture",response.text)
            self.assertEqual(self.current(),original)
        for field in ("name","description"):
            with self.assertRaises(ValidationError): TeamUpdateInput(**{field:"bad\ud800text"})
        response=self.patch_team({"name":"📚"*255,"description":"x"*4096})
        self.assertEqual(response.status_code,200,response.text)
        self.assertEqual(response.json()["data"]["name"],"📚"*255)
        self.assertEqual(response.json()["data"]["description"],"x"*4096)
        response=self.patch_team({"name":"\u00a0Team\u00a0","description":"\u00a0"})
        self.assertEqual(response.status_code,200)
        self.assertEqual(response.json()["data"]["description"],"\u00a0")

    def test_no_team_staff_and_missing_sessions(self):
        self.assert_error(self.patch_team({"name":"Edit"}),401,"AUTHENTICATION_REQUIRED")
        for role in ("student","advisor","coordinator"):
            self.signed_in(role)
            status,code=(404,"TEAM_NOT_FOUND") if role=="student" else (403,"TEAM_ACCESS_FORBIDDEN")
            self.assert_error(self.patch_team({"name":"Edit"}),status,code)

    def test_member_and_identity_spoof_cannot_modify_or_select_another_team(self):
        leader,team=self.team(); private=self.current()
        self.member(leader,team)
        self.assert_error(self.patch_team({"name":"Denied"}),403,"TEAM_UPDATE_FORBIDDEN")
        self.assert_error(self.patch_team({"name":private["name"]}),403,"TEAM_UPDATE_FORBIDDEN")
        self.team(); own=self.current()
        response=self.client.patch(URL+"?team_id="+team["id"]+"&user_id="+leader["id"],
            headers={**base.ORIGIN,CSRF_HEADER:self.client.cookies.get(CSRF_COOKIE),"X-User-ID":leader["id"],"X-Role":"leader"},
            json={"name":"Own updated"})
        self.assertEqual(response.status_code,200)
        self.assertEqual(response.json()["data"]["id"],own["id"])
        self.login_as(leader)
        self.assertEqual(self.current(),private)

    def test_authority_rechecked_after_lock_and_partial_fields_use_locked_row(self):
        self.team(); original=self.current(); current=TeamRepository.current_team
        for mode in ("missing","member"):
            calls=0
            def changed(store,actor):
                nonlocal calls
                row=current(store,actor); calls+=1
                if calls==2: return None if mode=="missing" else (*row[:4],"member")
                return row
            with patch.object(TeamRepository,"current_team",changed):
                self.assert_error(self.patch_team({"name":"Edit"}),404 if mode=="missing" else 403,
                    "TEAM_NOT_FOUND" if mode=="missing" else "TEAM_UPDATE_FORBIDDEN")
        self.assertEqual(self.current(),original)
        calls=0
        def stale_before_lock(store,actor):
            nonlocal calls
            row=current(store,actor); calls+=1
            return (row[0],row[1],"stale pre-lock value",row[3],row[4]) if calls==1 else row
        with patch.object(TeamRepository,"current_team",stale_before_lock):
            response=self.patch_team({"name":"Locked row"})
        self.assertEqual(response.status_code,200)
        self.assertEqual(response.json()["data"]["description"],original["description"])

    def test_transferred_leadership_changes_update_authority_without_membership_spoof(self):
        leader,team=self.team(); member=self.member(leader,team)
        self.fixture_actor(leader)
        self.conn.execute("SET CONSTRAINTS public.c_team_member_cardinality DEFERRED")
        self.conn.execute("SELECT public.v1_transfer_team_leader(%s,%s)",(team["id"],member["id"]))
        self.conn.execute("SET CONSTRAINTS public.c_team_member_cardinality IMMEDIATE")
        self.login_as(leader)
        self.assert_error(self.patch_team({"name":"Old leader"}),403,"TEAM_UPDATE_FORBIDDEN")
        self.login_as(member); before=self.current()
        response=self.patch_team({"name":"New leader edit"})
        self.assertEqual(response.status_code,200,response.text)
        self.assertEqual(response.json()["data"]["membership"],before["membership"])

    def test_project_phase_and_noop_lock_rules_preserve_project_and_submission_snapshot(self):
        for review in (None,"approved","revision_requested"):
            with self.subTest(review=review),self.conn.transaction(force_rollback=True):
                leader,_=self.team(); project=self.post().json()["data"]
                # A Project without a Submission does not lock Team metadata.
                self.assertEqual(self.patch_team({"description":"Before submission"}).status_code,200)
                submission=self.fixture_submission(leader,project,review)
                original=self.current()
                for payload in ({"name":"Updated after revision"},{"name":original["name"]}):
                    response=self.patch_team(payload)
                    if review=="revision_requested": self.assertEqual(response.status_code,200,response.text)
                    else: self.assert_error(response,409,"TEAM_METADATA_LOCKED")
                self.assertEqual(self.client.get("/api/v1/projects/me").json()["data"],project)
                self.assertEqual(self.conn.execute("SELECT snapshot_name,snapshot_description FROM public.project_submissions WHERE id=%s",(submission,)).fetchone(),
                                 (project["name"],project["description"]))

    def test_committee_partial_final_revision_and_approval_follow_existing_predicate(self):
        for votes in (("approved","approved","approved"),("revision_requested","revision_requested","approved")):
            with self.subTest(votes=votes),self.conn.transaction(force_rollback=True):
                leader,_=self.team(); project=self.post().json()["data"]
                submission=self.fixture_submission(leader,project,"approved")
                committee=[self.signed_in("advisor") for _ in range(3)]
                coordinator=self.signed_in("coordinator"); self.fixture_actor(coordinator)
                assignments=[self.conn.execute("SELECT public.v1_appoint_committee(%s,%s)",(project["id"],u["id"])).fetchone()[0] for u in committee]
                for index,(user,assignment,vote) in enumerate(zip(committee,assignments,votes)):
                    self.fixture_actor(user)
                    self.conn.execute("SELECT public.v1_cast_vote(%s,%s,%s,%s)",
                        (submission,assignment,vote,"Please revise" if vote=="revision_requested" else None))
                    self.login_as(leader)
                    response=self.patch_team({"description":"Committee complete"})
                    if index==2 and votes[0]=="revision_requested": self.assertEqual(response.status_code,200,response.text)
                    else: self.assert_error(response,409,"TEAM_METADATA_LOCKED")

    def test_origin_session_bound_csrf_expiry_and_revocation(self):
        self.team(); original=self.current()
        for origin in ("","null","http://untrusted.example.test"):
            self.assert_error(self.patch_team({"name":"Edit"},{"Origin":origin}),403,"ORIGIN_NOT_ALLOWED")
        self.assert_error(self.patch_team({"name":"Edit"},{CSRF_HEADER:"wrong"}),403,"CSRF_INVALID")
        token=self.client.cookies.get(SESSION_COOKIE)
        for mode in ("expired","revoked"):
            with self.conn.transaction(force_rollback=True):
                with self.conn.cursor() as cur:
                    switch(cur,"project_owner")
                    if mode=="expired": cur.execute("UPDATE auth.sessions SET created_at=clock_timestamp()-interval '2 hours',expires_at=clock_timestamp()-interval '1 hour' WHERE token_hash=%s",(session_digest(token),))
                    else: cur.execute("DELETE FROM auth.sessions WHERE token_hash=%s",(session_digest(token),))
                    switch(cur,"project_app")
                self.assert_error(self.patch_team({"name":"Edit"}),401,"AUTHENTICATION_REQUIRED")
        self.assertEqual(self.current(),original)

    def test_failure_after_update_and_at_transaction_completion_rolls_back(self):
        self.team(); original=self.current(); update=TeamRepository.update_metadata
        def fail_after_update(store,*args):
            update(store,*args)
            raise StorageUnavailable()
        with patch.object(TeamRepository,"update_metadata",fail_after_update):
            self.assert_error(self.patch_team({"name":"Must rollback"}),500,"INTERNAL_ERROR")
        self.assertEqual(self.current(),original)
        @contextmanager
        def fail_completion():
            with team_transaction_on(self.conn) as store:
                yield store
                raise StorageUnavailable()
        self.app.dependency_overrides[get_team_uow]=lambda:fail_completion
        self.assert_error(self.patch_team({"description":"Must rollback"}),500,"INTERNAL_ERROR")
        self.app.dependency_overrides[get_team_uow]=lambda:lambda:team_transaction_on(self.conn)
        self.assertEqual(self.current(),original)

    def test_unknown_privilege_and_trigger_errors_remain_sanitized_500(self):
        self.team(); original=self.current()
        for error in (psycopg.errors.InsufficientPrivilege("DoNotEchoSQLFixture"),psycopg.errors.RaiseException("DoNotEchoSQLFixture")):
            with patch.object(TeamRepository,"update_metadata",side_effect=error):
                response=self.patch_team({"name":"Edit"})
                self.assert_error(response,500,"INTERNAL_ERROR")
                self.assertNotIn("DoNotEchoSQLFixture",response.text)
        self.assertEqual(self.current(),original)

    def test_cors_patch_and_no_put_delete_or_new_member_operations(self):
        response=self.client.options(URL,headers={**base.ORIGIN,"Access-Control-Request-Method":"PATCH","Access-Control-Request-Headers":"content-type,x-csrf-token"})
        self.assertEqual(response.status_code,200)
        self.assertEqual(response.headers["access-control-allow-origin"],base.ORIGIN["Origin"])
        self.assertEqual(set(self.app.openapi()["paths"][URL]),{"get","patch"})
        for method in ("put","delete"):
            self.assertEqual(getattr(self.client,method)(URL,headers=base.ORIGIN).status_code,405)


if __name__ == "__main__":
    unittest.main()
