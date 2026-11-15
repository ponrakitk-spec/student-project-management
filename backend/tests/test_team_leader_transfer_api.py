"""Leader-transfer HTTP/PostgreSQL tests. Fixtures always use outer ROLLBACK."""

from contextlib import contextmanager
import unittest
from unittest.mock import patch

import psycopg

from backend.auth_api import CSRF_COOKIE, CSRF_HEADER, SESSION_COOKIE
from backend.auth_security import session_digest
from backend.auth_store import StorageUnavailable
from backend.team_api import LeaderTransferInput, get_team_uow
from backend.team_store import TeamRepository, team_transaction_on
from backend.invitation_api import get_invitation_uow
from backend.invitation_store import invitation_transaction_on
from backend.tests import test_project_api as project_base, test_team_api as base
from database.tests.Auth_Regression import switch

URL = "/api/v1/teams/me/leader"


class LeaderTransferAPIIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        base.TeamAPIIntegrationTests.setUpClass.__func__(cls)

    @classmethod
    def tearDownClass(cls):
        base.TeamAPIIntegrationTests.tearDownClass.__func__(cls)

    def setUp(self):
        project_base.ProjectAPIIntegrationTests.setUp(self)
        self.app.dependency_overrides[get_invitation_uow]=lambda:lambda:invitation_transaction_on(self.conn)

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

    def headers(self):
        return {**base.ORIGIN,CSRF_HEADER:self.client.cookies.get(CSRF_COOKIE) or ""}

    def transfer(self, membership_id, headers=None):
        return self.client.post(URL,headers={**self.headers(),**(headers or {})},json={"team_member_id":str(membership_id)})

    def roster(self):
        return self.client.get("/api/v1/teams/me/members").json()["data"]

    def scenario(self, with_project=False):
        leader,team=self.team()
        project=self.post().json()["data"] if with_project else None
        member=self.member(leader,team)
        target=self.conn.execute("SELECT id FROM public.team_members WHERE user_id=%s",(member["id"],)).fetchone()[0]
        self.login_as(leader)
        return leader,team,member,target,project

    def test_atomic_transfer_uses_membership_lookup_and_returns_callers_new_role(self):
        leader,team,member,target,_=self.scenario()
        before=self.roster(); own=self.client.get("/api/v1/teams/me").json()["data"]
        response=self.transfer(target)
        self.assertEqual(response.status_code,200,response.text)
        self.assertEqual(response.json()["data"],{**own,"membership":{**own["membership"],"role":"member"}})
        self.assertEqual(response.headers["cache-control"],"no-store")
        self.assertFalse(response.headers.get_list("set-cookie"))
        after=self.roster()
        self.assertEqual({r["id"] for r in before},{r["id"] for r in after})
        self.assertEqual({r["user_id"]:r["role"] for r in after},{leader["id"]:"member",member["id"]:"leader"})
        self.assertEqual(sum(r["role"]=="leader" for r in after),1)
        self.conn.execute("SET CONSTRAINTS ALL IMMEDIATE")
        self.assertEqual(self.conn.execute("SELECT count(*) FROM public.team_members WHERE team_id=%s",(team["id"],)).fetchone()[0],2)
        self.assertEqual(self.conn.execute("SELECT DISTINCT role FROM public.users WHERE id=ANY(%s)",([int(leader["id"]),int(member["id"])],)).fetchall(),[("student",)])

    def test_current_authority_changes_team_project_and_member_writes(self):
        leader,_,member,target,project=self.scenario(with_project=True)
        self.assertEqual(self.transfer(target).status_code,200)
        self.assert_error(self.client.patch("/api/v1/teams/me",headers=self.headers(),json={"name":"Denied"}),403,"TEAM_UPDATE_FORBIDDEN")
        self.assert_error(self.client.patch("/api/v1/projects/me",headers=self.headers(),json={"name":"Denied"}),403,"PROJECT_UPDATE_FORBIDDEN")
        self.assert_error(self.client.post("/api/v1/teams/me/members",headers=self.headers(),json={"email":"unused@example.test"}),403,"TEAM_MEMBER_ADDITION_FORBIDDEN")
        self.assert_error(self.transfer(target),403,"TEAM_LEADER_TRANSFER_FORBIDDEN")
        self.login_as(member)
        updated=self.client.patch("/api/v1/projects/me",headers=self.headers(),json={"name":"New leader edit"})
        self.assertEqual(updated.status_code,200,updated.text)
        self.assertEqual(updated.json()["data"]["created_by"],leader["id"])
        self.assertEqual(updated.json()["data"]["id"],project["id"])
        self.assertEqual(self.client.patch("/api/v1/teams/me",headers=self.headers(),json={"description":"New leader"}).status_code,200)
        extra=self.signed_in(); self.login_as(member)
        self.assertEqual(self.client.post("/api/v1/teams/me/members",headers=self.headers(),json={"email":extra["email"]}).status_code,201)

    def test_new_leader_can_create_project_without_rewriting_old_memberships(self):
        leader,team,member,target,_=self.scenario()
        self.assertEqual(self.transfer(target).status_code,200)
        self.assert_error(self.post(),403,"PROJECT_CREATION_FORBIDDEN")
        self.login_as(member)
        response=self.post()
        self.assertEqual(response.status_code,201)
        self.assertEqual(response.json()["data"]["created_by"],member["id"])
        self.assertEqual(response.json()["data"]["team_id"],team["id"])

    def test_invitation_authority_switches_but_original_sent_by_is_preserved(self):
        leader,_,member,target,project=self.scenario(with_project=True)
        advisor=self.signed_in("advisor"); self.login_as(leader)
        path="/api/v1/projects/me/advisor-invitations"
        sent=self.client.post(path,headers=self.headers(),json={"advisor_id":advisor["id"]})
        self.assertEqual(sent.status_code,201,sent.text)
        invitation=sent.json()["data"]["id"]
        self.assertEqual(self.transfer(target).status_code,200)
        self.assert_error(self.client.post(path,headers=self.headers(),json={"advisor_id":advisor["id"]}),403,"INVITATION_ACTION_FORBIDDEN")
        cancel=f"/api/v1/advisor-invitations/{invitation}/cancel"
        self.assert_error(self.client.post(cancel,headers=self.headers(),json={}),403,"INVITATION_ACTION_FORBIDDEN")
        self.login_as(member)
        response=self.client.post(cancel,headers=self.headers(),json={})
        self.assertEqual(response.status_code,200,response.text)
        row=self.conn.execute("SELECT sent_by,resolved_by FROM public.advisor_invitations WHERE id=%s",(invitation,)).fetchone()
        self.assertEqual(row,(int(leader["id"]),int(member["id"])))
        self.assertEqual(self.client.post(path,headers=self.headers(),json={"advisor_id":advisor["id"]}).status_code,201)

    def test_invalid_missing_self_foreign_or_unknown_targets_are_private(self):
        leader,team,member,target,_=self.scenario()
        original=self.roster()
        own_id=next(r["id"] for r in original if r["user_id"]==leader["id"])
        self.assert_error(self.transfer(own_id),409,"LEADER_TARGET_INVALID")
        self.assert_error(self.transfer(9223372036854775807),404,"TEAM_MEMBER_NOT_FOUND")
        other,other_team=self.team(); outsider=self.member(other,other_team)
        foreign=self.conn.execute("SELECT id FROM public.team_members WHERE user_id=%s",(outsider["id"],)).fetchone()[0]
        self.login_as(leader)
        response=self.transfer(foreign)
        self.assert_error(response,404,"TEAM_MEMBER_NOT_FOUND")
        self.assertNotIn(other_team["id"],response.text)
        self.assertEqual(self.roster(),original)

    def test_strict_ids_unknown_fields_and_invalid_json_are_sanitized(self):
        self.scenario(); before=self.roster()
        for value in (None,0,1,True,"","0","-1","1.0","1e2"," 1 ","x","๑","9223372036854775808"):
            response=self.client.post(URL,headers=self.headers(),json={"team_member_id":value})
            self.assert_error(response,422,"VALIDATION_ERROR")
            self.assertEqual(response.json()["error"]["fields"][0]["field"],"team_member_id")
        for field in ("actor_user_id","user_id","team_id","role","members","password"):
            response=self.client.post(URL,headers=self.headers(),json={"team_member_id":"1",field:"DoNotEchoTransferFixture"})
            self.assert_error(response,422,"VALIDATION_ERROR")
            self.assertNotIn("DoNotEchoTransferFixture",response.text)
        self.assert_error(self.client.post(URL,headers=self.headers(),json={}),422,"VALIDATION_ERROR")
        self.assert_error(self.client.post(URL,headers={**self.headers(),"Content-Type":"application/json"},content="{bad"),422,"VALIDATION_ERROR")
        self.assertEqual(LeaderTransferInput(team_member_id="0001").team_member_id,"1")
        self.assertEqual(LeaderTransferInput(team_member_id="9223372036854775807").team_member_id,"9223372036854775807")
        self.assertEqual(self.roster(),before)

    def test_no_team_staff_missing_member_and_forged_actor_are_rejected(self):
        self.assert_error(self.transfer("1"),401,"AUTHENTICATION_REQUIRED")
        for role in ("student","advisor","coordinator"):
            self.signed_in(role)
            status,code=(404,"TEAM_NOT_FOUND") if role=="student" else (403,"TEAM_ACCESS_FORBIDDEN")
            self.assert_error(self.transfer("1"),status,code)
        leader,_,member,target,_=self.scenario()
        self.login_as(member)
        self.assert_error(self.transfer(target,{"X-User-ID":leader["id"],"X-Role":"leader"}),403,"TEAM_LEADER_TRANSFER_FORBIDDEN")

    def test_authority_and_target_are_rechecked_under_team_lock(self):
        self.scenario(); original=TeamRepository.current_team
        for mode in ("missing","member"):
            calls=0
            def changed(store,actor):
                nonlocal calls
                row=original(store,actor); calls+=1
                if calls==2: return None if mode=="missing" else (*row[:4],"member")
                return row
            with patch.object(TeamRepository,"current_team",changed):
                self.assert_error(self.transfer("1"),404 if mode=="missing" else 403,
                    "TEAM_NOT_FOUND" if mode=="missing" else "TEAM_LEADER_TRANSFER_FORBIDDEN")
        with patch.object(TeamRepository,"target_member",return_value=None):
            self.assert_error(self.transfer("1"),404,"TEAM_MEMBER_NOT_FOUND")

    def test_successful_transfer_with_large_membership_id_and_duplicate_names(self):
        leader,team=self.team()
        member=self.signed_in(); self.login_as(leader); self.fixture_actor(leader)
        membership=9223372036854775803
        self.conn.execute("""INSERT INTO public.team_members(id,team_id,user_id,role) OVERRIDING SYSTEM VALUE
            VALUES (%s,%s,%s,'member')""",(membership,team["id"],member["id"]))
        self.conn.execute("SET CONSTRAINTS ALL IMMEDIATE")
        self.assertEqual(self.transfer(membership).status_code,200)
        self.login_as(member)
        self.assertEqual(self.client.get("/api/v1/teams/me").json()["data"]["membership"],{"id":str(membership),"role":"leader"})

    def test_transfer_does_not_add_metadata_phase_gate_or_change_snapshots(self):
        for review in (None,"approved","revision_requested"):
            with self.subTest(review=review),self.conn.transaction(force_rollback=True):
                leader,team,member,target,project=self.scenario(with_project=True)
                submission=self.fixture_submission(leader,project,review)
                response=self.transfer(target)
                self.assertEqual(response.status_code,200,response.text)
                self.assertEqual(self.conn.execute("SELECT snapshot_name,snapshot_description FROM public.project_submissions WHERE id=%s",(submission,)).fetchone(),(project["name"],project["description"]))
                self.login_as(member)
                edit=self.client.patch("/api/v1/projects/me",headers=self.headers(),json={"description":"New leader"})
                self.assertEqual(edit.status_code,200 if review=="revision_requested" else 409)

    def test_origin_csrf_expired_revoked_and_malformed_sessions(self):
        _,_,_,target,_=self.scenario()
        for origin in ("","null","http://untrusted.example.test"):
            self.assert_error(self.transfer(target,{"Origin":origin}),403,"ORIGIN_NOT_ALLOWED")
        self.assert_error(self.transfer(target,{CSRF_HEADER:"wrong"}),403,"CSRF_INVALID")
        token=self.client.cookies.get(SESSION_COOKIE)
        for mode in ("expired","revoked"):
            with self.conn.transaction(force_rollback=True):
                with self.conn.cursor() as cur:
                    switch(cur,"project_owner")
                    if mode=="expired": cur.execute("UPDATE auth.sessions SET created_at=clock_timestamp()-interval '2 hours',expires_at=clock_timestamp()-interval '1 hour' WHERE token_hash=%s",(session_digest(token),))
                    else: cur.execute("DELETE FROM auth.sessions WHERE token_hash=%s",(session_digest(token),))
                    switch(cur,"project_app")
                self.assert_error(self.transfer(target),401,"AUTHENTICATION_REQUIRED")
        self.client.cookies.clear(); self.client.cookies.set(SESSION_COOKIE,"bad")
        self.assert_error(self.transfer(target),401,"AUTHENTICATION_REQUIRED")

    def test_write_and_transaction_completion_failures_restore_both_roles(self):
        _,_,_,target,_=self.scenario(); before=self.roster(); transfer=TeamRepository.transfer_roles
        def fail_after_transfer(store,*args):
            transfer(store,*args)
            raise StorageUnavailable()
        with patch.object(TeamRepository,"transfer_roles",fail_after_transfer):
            self.assert_error(self.transfer(target),500,"INTERNAL_ERROR")
        self.assertEqual(self.roster(),before)
        @contextmanager
        def fail_completion():
            with team_transaction_on(self.conn) as store:
                yield store
                raise StorageUnavailable()
        self.app.dependency_overrides[get_team_uow]=lambda:fail_completion
        self.assert_error(self.transfer(target),500,"INTERNAL_ERROR")
        self.app.dependency_overrides[get_team_uow]=lambda:lambda:team_transaction_on(self.conn)
        self.assertEqual(self.roster(),before)

    def test_unknown_pg_errors_never_become_business_errors(self):
        _,_,_,target,_=self.scenario(); before=self.roster()
        for error in (psycopg.errors.InsufficientPrivilege("DoNotEchoSQLFixture"),psycopg.errors.RaiseException("DoNotEchoSQLFixture")):
            with patch.object(TeamRepository,"transfer_roles",side_effect=error):
                response=self.transfer(target)
                self.assert_error(response,500,"INTERNAL_ERROR")
                self.assertNotIn("DoNotEchoSQLFixture",response.text)
        self.assertEqual(self.roster(),before)


if __name__ == "__main__":
    unittest.main()
