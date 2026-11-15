"""Leave/removal + installed V1 Task cleanup. All fixtures share ROLLBACK."""

from contextlib import contextmanager
from datetime import timedelta
import unittest
from unittest.mock import patch
from uuid import uuid4

import psycopg

from backend.auth_api import CSRF_COOKIE, CSRF_HEADER, SESSION_COOKIE
from backend.auth_security import session_digest
from backend.auth_store import StorageUnavailable
from backend.team_api import get_team_uow
from backend.team_store import TeamRepository, team_transaction_on
from backend.tests import test_team_api as base, test_team_leader_transfer_api as transfer_base
from database.tests.Auth_Regression import switch

LEAVE = "/api/v1/teams/me/leave"


class MembershipExitAPIIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        base.TeamAPIIntegrationTests.setUpClass.__func__(cls)

    @classmethod
    def tearDownClass(cls):
        base.TeamAPIIntegrationTests.tearDownClass.__func__(cls)

    setUp = transfer_base.LeaderTransferAPIIntegrationTests.setUp
    tearDown = base.TeamAPIIntegrationTests.tearDown
    signed_in = base.TeamAPIIntegrationTests.signed_in
    create_team = base.TeamAPIIntegrationTests.create
    assert_error = base.TeamAPIIntegrationTests.assert_error
    team = transfer_base.LeaderTransferAPIIntegrationTests.team
    post = transfer_base.LeaderTransferAPIIntegrationTests.post
    member = transfer_base.LeaderTransferAPIIntegrationTests.member
    login_as = transfer_base.LeaderTransferAPIIntegrationTests.login_as
    fixture_actor = transfer_base.LeaderTransferAPIIntegrationTests.fixture_actor
    fixture_submission = transfer_base.LeaderTransferAPIIntegrationTests.fixture_submission
    headers = transfer_base.LeaderTransferAPIIntegrationTests.headers
    scenario = transfer_base.LeaderTransferAPIIntegrationTests.scenario

    def exit(self, mode, target, headers=None, payload=None):
        path=LEAVE if mode=="leave" else f"/api/v1/teams/me/members/{target}/remove"
        return self.client.post(path,headers={**self.headers(),**(headers or {})},json={} if payload is None else payload)

    def task_fixture(self, leader, member, target, project, status, other=False):
        self.fixture_actor(leader)
        today=self.conn.execute("SELECT (now() AT TIME ZONE 'Asia/Bangkok')::date").fetchone()[0]
        milestone=self.conn.execute("SELECT public.v1_create_milestone(%s,%s,NULL,%s)",
            (project["id"],"Exit milestone "+uuid4().hex,today+timedelta(days=14))).fetchone()[0]
        task=self.conn.execute("SELECT public.v1_create_task(%s,'Exit task',NULL,%s)",
            (milestone,today+timedelta(days=7))).fetchone()[0]
        self.conn.execute("SELECT public.v1_assign_task(%s,%s)",(task,target))
        if other:
            leader_member=self.conn.execute("SELECT id FROM public.team_members WHERE user_id=%s",(leader["id"],)).fetchone()[0]
            self.conn.execute("SELECT public.v1_assign_task(%s,%s)",(task,leader_member))
        if status!="not_started":
            self.fixture_actor(member)
            self.conn.execute("SELECT public.v1_set_task_status(%s,'in_progress')",(task,))
            if status=="completed": self.conn.execute("SELECT public.v1_set_task_status(%s,'completed')",(task,))
        self.conn.execute("SET CONSTRAINTS ALL IMMEDIATE")
        self.conn.execute("SET CONSTRAINTS ALL DEFERRED")
        return task

    def target_state(self, target):
        return (
            self.conn.execute("SELECT id,team_id,user_id,role FROM public.team_members WHERE id=%s",(target,)).fetchall(),
            self.conn.execute("SELECT task_id,assigned_at FROM public.task_assignees WHERE team_member_id=%s ORDER BY task_id",(target,)).fetchall(),
            self.conn.execute("SELECT id,task_id,user_id,assigned_at,unassigned_at FROM public.task_assignment_history ORDER BY id").fetchall(),
        )

    def assert_exited(self, response, member, target, team, project=None):
        self.assertEqual(response.status_code,204,response.text)
        self.assertEqual(response.content,b"")
        self.assertEqual(response.headers["cache-control"],"no-store")
        self.assertFalse(response.headers.get_list("set-cookie"))
        self.assertFalse(self.conn.execute("SELECT EXISTS(SELECT 1 FROM public.team_members WHERE id=%s)",(target,)).fetchone()[0])
        self.assertEqual(self.conn.execute("SELECT count(*) FROM public.teams WHERE id=%s",(team["id"],)).fetchone()[0],1)
        self.login_as(member)
        self.assertEqual(self.client.get("/api/v1/auth/me").status_code,200)
        for path in ("/api/v1/teams/me","/api/v1/teams/me/members","/api/v1/projects/me","/api/v1/projects/me/advisor-invitations"):
            self.assert_error(self.client.get(path),404,"TEAM_NOT_FOUND")
        if project:
            self.assertEqual(self.conn.execute("SELECT created_by FROM public.projects WHERE id=%s",(project["id"],)).fetchone()[0],int(project["created_by"]))

    def test_leave_and_removal_preserve_account_team_project_and_revoke_membership_access(self):
        for mode in ("leave","remove"):
            with self.subTest(mode=mode),self.conn.transaction(force_rollback=True):
                leader,team,member,target,project=self.scenario(with_project=True)
                self.login_as(member if mode=="leave" else leader)
                token=self.client.cookies.get(SESSION_COOKIE)
                response=self.exit(mode,target)
                self.assertEqual(self.client.get("/api/v1/auth/me").status_code,200)
                self.assertTrue(self.client.cookies.get(SESSION_COOKIE)==token)
                self.assert_exited(response,member,target,team,project)
                self.assert_error(self.exit("leave",target),404,"TEAM_NOT_FOUND")

    def test_exit_without_project_and_future_join_is_possible(self):
        leader,team,member,target,_=self.scenario()
        self.login_as(member)
        self.assert_exited(self.exit("leave",target),member,target,team)
        response=self.create_team()
        self.assertEqual(response.status_code,201,response.text)
        self.assertNotEqual(response.json()["data"]["id"],team["id"])

    def test_leader_must_transfer_before_leave_or_removal(self):
        leader,team,member,target,_=self.scenario()
        own=self.client.get("/api/v1/teams/me").json()["data"]["membership"]["id"]
        self.assert_error(self.exit("leave",target),409,"TEAM_LEADERSHIP_TRANSFER_REQUIRED")
        self.assert_error(self.exit("remove",own),409,"TEAM_LEADERSHIP_TRANSFER_REQUIRED")
        response=self.client.post("/api/v1/teams/me/leader",headers=self.headers(),json={"team_member_id":str(target)})
        self.assertEqual(response.status_code,200)
        self.assertEqual(self.exit("leave",target).status_code,204)
        self.login_as(member)
        self.assertEqual(self.client.get("/api/v1/teams/me").json()["data"]["membership"]["role"],"leader")

    def test_not_started_and_completed_cleanup_keep_status_and_record_history_once(self):
        for mode in ("leave","remove"):
            for status in ("not_started","completed"):
                with self.subTest(mode=mode,status=status),self.conn.transaction(force_rollback=True):
                    leader,team,member,target,project=self.scenario(with_project=True)
                    task=self.task_fixture(leader,member,target,project,status)
                    assigned=self.conn.execute("SELECT assigned_at FROM public.task_assignees WHERE task_id=%s",(task,)).fetchone()[0]
                    self.login_as(member if mode=="leave" else leader)
                    response=self.exit(mode,target)
                    self.assertEqual(response.status_code,204,response.text)
                    self.assertEqual(self.conn.execute("SELECT status FROM public.tasks WHERE id=%s",(task,)).fetchone()[0],status)
                    self.assertEqual(self.conn.execute("SELECT count(*) FROM public.task_assignees WHERE task_id=%s",(task,)).fetchone()[0],0)
                    self.assertEqual(self.conn.execute("SELECT user_id,assigned_at,unassigned_at>=assigned_at FROM public.task_assignment_history WHERE task_id=%s",(task,)).fetchall(),[(int(member["id"]),assigned,True)])
                    repeat=self.exit(mode,target)
                    self.assertEqual(repeat.status_code,404)
                    self.assertEqual(self.conn.execute("SELECT count(*) FROM public.task_assignment_history WHERE task_id=%s",(task,)).fetchone()[0],1)

    def test_in_progress_last_assignee_blocks_entire_exit_including_other_tasks(self):
        for mode in ("leave","remove"):
            with self.subTest(mode=mode),self.conn.transaction(force_rollback=True):
                leader,team,member,target,project=self.scenario(with_project=True)
                self.task_fixture(leader,member,target,project,"not_started")
                self.task_fixture(leader,member,target,project,"in_progress")
                before=self.target_state(target)
                self.login_as(member if mode=="leave" else leader)
                self.assert_error(self.exit(mode,target),409,"MEMBER_EXIT_BLOCKED_BY_TASK")
                self.assertEqual(self.target_state(target),before)

    def test_in_progress_multiple_assignees_allows_exit_and_keeps_other_assignee(self):
        for mode in ("leave","remove"):
            with self.subTest(mode=mode),self.conn.transaction(force_rollback=True):
                leader,team,member,target,project=self.scenario(with_project=True)
                task=self.task_fixture(leader,member,target,project,"in_progress",other=True)
                self.login_as(member if mode=="leave" else leader)
                self.assertEqual(self.exit(mode,target).status_code,204)
                remaining=self.conn.execute("SELECT m.user_id FROM public.task_assignees a JOIN public.team_members m ON m.id=a.team_member_id WHERE a.task_id=%s",(task,)).fetchall()
                self.assertEqual(remaining,[(int(leader["id"]),)])
                self.conn.execute("SET CONSTRAINTS ALL IMMEDIATE")

    def test_sql_guard_still_blocks_orphaned_task_if_precheck_is_bypassed(self):
        leader,team,member,target,project=self.scenario(with_project=True)
        self.task_fixture(leader,member,target,project,"in_progress")
        before=self.target_state(target)
        with patch.object(TeamRepository,"exit_blocked_by_task",return_value=False):
            self.assert_error(self.exit("remove",target),500,"INTERNAL_ERROR")
        self.assertEqual(self.target_state(target),before)

    def test_cleanup_after_first_evaluation_uses_only_exit_exception_and_keeps_c02(self):
        for blocked in (False,True):
            with self.subTest(blocked=blocked),self.conn.transaction(force_rollback=True):
                leader,team,member,target,project=self.scenario(with_project=True)
                submission=self.fixture_submission(leader,project,"approved")
                completed=self.task_fixture(leader,member,target,project,"completed")
                if blocked: self.task_fixture(leader,member,target,project,"in_progress")
                committee=[self.signed_in("advisor") for _ in range(3)]
                coordinator=self.signed_in("coordinator"); self.fixture_actor(coordinator)
                assignments=[self.conn.execute("SELECT public.v1_appoint_committee(%s,%s)",(project["id"],u["id"])).fetchone()[0] for u in committee]
                for user,assignment in zip(committee,assignments):
                    self.fixture_actor(user)
                    self.conn.execute("SELECT public.v1_cast_vote(%s,%s,'approved',NULL)",(submission,assignment))
                self.fixture_actor(committee[0])
                self.conn.execute("SELECT public.v1_record_evaluation(%s,50,'Exit exception test')",(assignments[0],))
                before=self.target_state(target)
                self.login_as(leader)
                response=self.exit("remove",target)
                if blocked:
                    self.assert_error(response,409,"MEMBER_EXIT_BLOCKED_BY_TASK")
                    self.assertEqual(self.target_state(target),before)
                else:
                    self.assertEqual(response.status_code,204,response.text)
                    self.assertEqual(self.conn.execute("SELECT count(*) FROM public.task_assignment_history WHERE task_id=%s",(completed,)).fetchone()[0],1)

    def test_exit_has_no_additional_metadata_phase_gate(self):
        for review in (None,"approved","revision_requested"):
            with self.subTest(review=review),self.conn.transaction(force_rollback=True):
                leader,team,member,target,project=self.scenario(with_project=True)
                submission=self.fixture_submission(leader,project,review)
                self.assertEqual(self.exit("remove",target).status_code,204)
                self.assertEqual(self.conn.execute("SELECT submitted_by FROM public.project_submissions WHERE id=%s",(submission,)).fetchone()[0],int(leader["id"]))

    def test_roles_foreign_targets_and_unknown_targets_are_private(self):
        self.assert_error(self.exit("leave","1"),401,"AUTHENTICATION_REQUIRED")
        for role in ("student","advisor","coordinator"):
            self.signed_in(role)
            status,code=(404,"TEAM_NOT_FOUND") if role=="student" else (403,"TEAM_ACCESS_FORBIDDEN")
            for mode in ("leave","remove"): self.assert_error(self.exit(mode,"1"),status,code)
        leader,team,member,target,_=self.scenario()
        self.login_as(member)
        self.assert_error(self.exit("remove",target,{"X-User-ID":leader["id"],"X-Role":"leader"}),403,"TEAM_MEMBER_REMOVAL_FORBIDDEN")
        other,other_team,outsider,foreign,_=self.scenario()
        self.login_as(leader)
        self.assert_error(self.exit("remove",foreign),404,"TEAM_MEMBER_NOT_FOUND")
        self.assert_error(self.exit("remove","9223372036854775807"),404,"TEAM_MEMBER_NOT_FOUND")

    def test_empty_body_and_strict_path_validation_do_not_echo_input(self):
        self.scenario()
        for payload in ({"team_member_id":"DoNotEchoExitFixture"},{"role":"DoNotEchoExitFixture"},[],False):
            self.assert_error(self.exit("leave","1",payload=payload),422,"VALIDATION_ERROR")
        for value in ("0","-1","bad","1.0","9223372036854775808"):
            response=self.exit("remove",value)
            self.assert_error(response,422,"VALIDATION_ERROR")
            self.assertEqual(response.json()["error"]["fields"][0]["field"],"team_member_id")

    def test_authority_and_target_rechecked_after_team_lock(self):
        self.scenario(); current=TeamRepository.current_team
        for mode in ("missing","member"):
            calls=0
            def changed(store,actor):
                nonlocal calls
                row=current(store,actor); calls+=1
                if calls==2: return None if mode=="missing" else (*row[:4],"member")
                return row
            with patch.object(TeamRepository,"current_team",changed):
                self.assert_error(self.exit("remove","1"),404 if mode=="missing" else 403,
                    "TEAM_NOT_FOUND" if mode=="missing" else "TEAM_MEMBER_REMOVAL_FORBIDDEN")
        with patch.object(TeamRepository,"target_member",return_value=None):
            self.assert_error(self.exit("remove","1"),404,"TEAM_MEMBER_NOT_FOUND")

    def test_origin_csrf_expiry_and_revocation(self):
        leader,team,member,target,_=self.scenario(); self.login_as(member)
        for origin in ("","null","http://untrusted.example.test"):
            self.assert_error(self.exit("leave",target,{"Origin":origin}),403,"ORIGIN_NOT_ALLOWED")
        self.assert_error(self.exit("leave",target,{CSRF_HEADER:"wrong"}),403,"CSRF_INVALID")
        token=self.client.cookies.get(SESSION_COOKIE)
        for mode in ("expired","revoked"):
            with self.conn.transaction(force_rollback=True):
                with self.conn.cursor() as cur:
                    switch(cur,"project_owner")
                    if mode=="expired": cur.execute("UPDATE auth.sessions SET created_at=clock_timestamp()-interval '2 hours',expires_at=clock_timestamp()-interval '1 hour' WHERE token_hash=%s",(session_digest(token),))
                    else: cur.execute("DELETE FROM auth.sessions WHERE token_hash=%s",(session_digest(token),))
                    switch(cur,"project_app")
                self.assert_error(self.exit("leave",target),401,"AUTHENTICATION_REQUIRED")

    def test_failures_after_cleanup_and_at_commit_restore_membership_assignments_history(self):
        leader,team,member,target,project=self.scenario(with_project=True)
        self.task_fixture(leader,member,target,project,"not_started")
        before=self.target_state(target); operation=TeamRepository.controlled_exit
        def fail_after_exit(store,*args):
            operation(store,*args)
            raise StorageUnavailable()
        with patch.object(TeamRepository,"controlled_exit",fail_after_exit):
            self.assert_error(self.exit("remove",target),500,"INTERNAL_ERROR")
        self.assertEqual(self.target_state(target),before)
        @contextmanager
        def fail_completion():
            with team_transaction_on(self.conn) as store:
                yield store
                raise StorageUnavailable()
        self.app.dependency_overrides[get_team_uow]=lambda:fail_completion
        self.assert_error(self.exit("remove",target),500,"INTERNAL_ERROR")
        self.app.dependency_overrides[get_team_uow]=lambda:lambda:team_transaction_on(self.conn)
        self.assertEqual(self.target_state(target),before)

    def test_unknown_privilege_trigger_errors_stay_sanitized_500(self):
        leader,team,member,target,_=self.scenario(); before=self.target_state(target)
        for error in (psycopg.errors.InsufficientPrivilege("DoNotEchoExitSQL"),psycopg.errors.RaiseException("DoNotEchoExitSQL")):
            with patch.object(TeamRepository,"controlled_exit",side_effect=error):
                response=self.exit("remove",target)
                self.assert_error(response,500,"INTERNAL_ERROR")
                self.assertNotIn("DoNotEchoExitSQL",response.text)
        self.assertEqual(self.target_state(target),before)


if __name__ == "__main__":
    unittest.main()
