"""Task API/V1 guards and complete workflow; every fixture uses ROLLBACK."""
from contextlib import contextmanager
from datetime import timedelta
import unittest
from unittest.mock import patch
from backend.auth_store import StorageUnavailable
from backend.task_api import get_task_uow
from backend.task_store import TaskRepository, task_transaction_on
from backend.submission_api import get_submission_uow
from backend.submission_store import submission_transaction_on
from backend.tests import test_milestone_api as milestones, test_evaluation_api as evaluations, test_submission_api as submissions


class TaskAPIIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        milestones.MilestoneAPIIntegrationTests.setUpClass.__func__(cls)

    @classmethod
    def tearDownClass(cls):
        milestones.MilestoneAPIIntegrationTests.tearDownClass.__func__(cls)

    def setUp(self):
        milestones.MilestoneAPIIntegrationTests.setUp(self)
        self.app.dependency_overrides[get_task_uow] = lambda: lambda: task_transaction_on(self.conn)
        self.app.dependency_overrides[get_submission_uow] = lambda: lambda: submission_transaction_on(self.conn)
        guard = patch("backend.task_store.open_auth_connection", side_effect=AssertionError("Escaped rollback fixture"))
        guard.start()
        self.addCleanup(guard.stop)

    tearDown = milestones.MilestoneAPIIntegrationTests.tearDown
    signed_in = milestones.MilestoneAPIIntegrationTests.signed_in
    create_team = milestones.MilestoneAPIIntegrationTests.create_team
    team = milestones.MilestoneAPIIntegrationTests.team
    post_project = milestones.MilestoneAPIIntegrationTests.post_project
    login_as = milestones.MilestoneAPIIntegrationTests.login_as
    assert_error = milestones.MilestoneAPIIntegrationTests.assert_error
    setup_project = milestones.MilestoneAPIIntegrationTests.setup_project
    create_milestone = milestones.MilestoneAPIIntegrationTests.create
    write = milestones.MilestoneAPIIntegrationTests.write

    def scenario(self, with_member=False):
        leader, team, project = self.setup_project()
        member = self.signed_in() if with_member else None
        if member:
            self.login_as(leader)
            self.assertEqual(self.write("POST", "/api/v1/teams/me/members", {"email": member["email"]}).status_code, 201)
        milestone = self.create_milestone().json()["data"]
        return leader, team, project, milestone, member

    def collection(self, milestone):
        return f"/api/v1/milestones/{milestone['id']}/tasks"

    def url(self, task):
        return f"/api/v1/tasks/{task['id']}"

    def create(self, milestone, **fields):
        return self.write("POST", self.collection(milestone), {"name": "Task fixture", **fields})

    def member_id(self, user):
        return str(self.conn.execute("SELECT id FROM public.team_members WHERE user_id=%s", (user["id"],)).fetchone()[0])

    def assign(self, task, user):
        return self.write("POST", self.url(task) + "/assignees", {"team_member_id": self.member_id(user)})

    def status(self, task, status):
        return self.write("POST", self.url(task) + "/status", {"status": status})

    def ready_phase(self):
        phase = evaluations.EvaluationAPIIntegrationTests()
        for key in ("conn", "app", "client", "before"):
            setattr(phase, key, getattr(self, key))
        data = phase.ready()
        return phase, data

    def test_leader_crud_strings_metadata_and_null_due_without_topic_gate(self):
        leader, _, _, milestone, _ = self.scenario()
        response = self.create(milestone, name="  Plan task  ", description=" \t ")
        self.assertEqual(response.status_code, 201, response.text)
        task = response.json()["data"]
        self.assertEqual(task["name"], "Plan task")
        self.assertEqual(task["created_by"], leader["id"])
        self.assertIsNone(task["updated_by"])
        self.assertIsNone(task["due_date"])
        self.assertIsNone(task["description"])
        self.assertEqual(self.client.get(self.url(task)).json()["data"], task)
        self.assertEqual(self.write("PATCH", self.url(task), {"name": "Plan task"}).json()["data"], task)
        response = self.write("PATCH", self.url(task), {"description": " Changed "})
        self.assertEqual(response.status_code, 200, response.text)
        updated = response.json()["data"]
        self.assertEqual(updated["description"], "Changed")
        self.assertEqual(updated["updated_by"], leader["id"])
        self.assertEqual(updated["created_at"], task["created_at"])
        response = self.write("DELETE", self.url(task))
        self.assertEqual(response.status_code, 204, response.text)
        self.assertEqual(response.content, b"")
        self.assert_error(self.client.get(self.url(task)), 404, "TASK_NOT_FOUND")
        self.assertEqual(self.client.get(self.collection(milestone)).json()["data"]["milestone"]["status"], "not_started")

    def test_validation_duplicates_nullable_dates_and_order(self):
        _, _, _, milestone, _ = self.scenario()
        for extra in ({"status": "completed"}, {"created_by": "1"}, {"milestone_id": "1"}, {"due_date": "2026-02-30"}, {"name": " "}):
            self.assert_error(self.create(milestone, **extra), 422, "VALIDATION_ERROR")
        self.assert_error(self.create(milestone, due_date=(self.today - timedelta(days=1)).isoformat()), 422, "TASK_DUE_DATE_INVALID")
        self.assert_error(self.create(milestone, due_date=(self.today + timedelta(days=8)).isoformat()), 422, "TASK_DUE_DATE_INVALID")
        task = self.create(milestone, name="Unique").json()["data"]
        self.assert_error(self.create(milestone, name=" UNIQUE "), 409, "TASK_NAME_CONFLICT")
        earlier = self.create(milestone, name="Earlier", due_date=self.today.isoformat()).json()["data"]
        listing = self.client.get(self.collection(milestone)).json()["data"]
        self.assertEqual([r["id"] for r in listing["tasks"]], [earlier["id"], task["id"]])
        self.assertEqual(self.create(milestone, name="🌳" * 255).status_code, 201)
        self.assert_error(self.create(milestone, name="🌳" * 256), 422, "VALIDATION_ERROR")
        other = self.create_milestone(name="Other").json()["data"]
        self.assertEqual(self.create(other, name="Unique").status_code, 201)
        for body in ({}, {"name": None}, {"status": "completed"}, {"created_at": "2026-01-01"}):
            self.assert_error(self.write("PATCH", self.url(task), body), 422, "VALIDATION_ERROR")
        self.assertEqual(self.write("PATCH", self.url(earlier), {"due_date": None}).json()["data"]["due_date"], None)

    def test_assignment_and_unassignment_history_with_cascade(self):
        leader, _, _, milestone, _ = self.scenario()
        task = self.create(milestone).json()["data"]
        assigned = self.assign(task, leader)
        self.assertEqual(assigned.status_code, 201, assigned.text)
        assignment = assigned.json()["data"]
        self.assertEqual(set(assignment), {"id", "team_member_id", "user", "assigned_at"})
        self.assertEqual(self.client.get(self.url(task)).json()["data"], task)
        self.assert_error(self.assign(task, leader), 409, "ASSIGNEE_ALREADY_ASSIGNED")
        removed = self.write("DELETE", self.url(task) + "/assignees/" + self.member_id(leader))
        self.assertEqual(removed.status_code, 204, removed.text)
        history = self.client.get(self.url(task) + "/assignment-history").json()["data"]
        self.assertEqual(len(history), 1)
        self.assertEqual(history[0]["user"]["id"], leader["id"])
        self.assertEqual(history[0]["assigned_at"], assignment["assigned_at"])
        self.assertEqual(self.client.get(self.url(task) + "/assignees").json()["data"], [])
        self.assertEqual(self.write("DELETE", self.url(task)).status_code, 204)
        self.assertEqual(self.conn.execute("SELECT count(*) FROM public.task_assignment_history WHERE task_id=%s", (task["id"],)).fetchone()[0], 0)

    def test_status_requires_assignee_and_derives_milestone_completion(self):
        leader, _, _, milestone, _ = self.scenario()
        task = self.create(milestone).json()["data"]
        for status in ("in_progress", "completed"):
            self.assert_error(self.status(task, status), 409, "TASK_ASSIGNEE_REQUIRED")
        self.assertEqual(self.assign(task, leader).status_code, 201)
        self.assertEqual(self.status(task, "completed").status_code, 200)
        data = self.client.get(self.collection(milestone)).json()["data"]
        self.assertEqual(data["milestone"]["status"], "completed")
        self.assertIsNotNone(data["tasks"][0]["completed_at"])
        self.assertEqual(self.status(task, "in_progress").status_code, 200)
        self.assertEqual(self.client.get(self.collection(milestone)).json()["data"]["milestone"]["status"], "in_progress")

    def test_member_status_without_assignee_authority_and_leader_only_operations(self):
        leader, _, _, milestone, member = self.scenario(True)
        task = self.create(milestone).json()["data"]
        self.assertEqual(self.assign(task, leader).status_code, 201)
        self.login_as(member)
        self.assertEqual(self.client.get(self.url(task)).status_code, 200)
        self.assertFalse(self.client.get(self.collection(milestone)).json()["data"]["can_manage"])
        self.assert_error(self.create(milestone), 403, "TASK_ACTION_FORBIDDEN")
        self.assert_error(self.write("PATCH", self.url(task), {"description": "No"}), 403, "TASK_ACTION_FORBIDDEN")
        self.assert_error(self.write("DELETE", self.url(task)), 403, "TASK_ACTION_FORBIDDEN")
        self.assert_error(self.assign(task, member), 403, "TASK_ACTION_FORBIDDEN")
        self.assertEqual(self.status(task, "completed").status_code, 200)
        self.assert_error(self.status(task, "in_progress"), 403, "TASK_ACTION_FORBIDDEN")
        self.login_as(leader)
        self.assert_error(self.write("PATCH", self.url(task), {"description": "No"}), 409, "TASK_COMPLETED")
        self.assert_error(self.write("DELETE", self.url(task)), 409, "TASK_COMPLETED")
        self.assert_error(self.assign(task, member), 409, "TASK_LOCKED")
        self.assert_error(self.status(task, "not_started"), 409, "TASK_STATUS_CONFLICT")
        self.assertEqual(self.status(task, "in_progress").status_code, 200)
        self.assertEqual(self.write("PATCH", self.url(task), {"description": "Reopened"}).status_code, 200)

    def test_last_in_progress_assignee_cannot_be_removed_and_exit_preserves_history(self):
        leader, _, _, milestone, member = self.scenario(True)
        task = self.create(milestone).json()["data"]
        self.assertEqual(self.assign(task, member).status_code, 201)
        self.assertEqual(self.status(task, "in_progress").status_code, 200)
        self.assert_error(self.write("DELETE", self.url(task) + "/assignees/" + self.member_id(member)), 409, "TASK_ASSIGNEE_REQUIRED")
        self.assertEqual(self.client.get(self.url(task) + "/assignment-history").json()["data"], [])
        self.login_as(member)
        self.assert_error(self.write("POST", "/api/v1/teams/me/leave", {}), 409, "MEMBER_EXIT_BLOCKED_BY_TASK")
        self.login_as(leader)
        self.assertEqual(self.status(task, "not_started").status_code, 200)
        self.login_as(member)
        self.assertEqual(self.write("POST", "/api/v1/teams/me/leave", {}).status_code, 204)
        self.assert_error(self.client.get(self.url(task)), 404, "TASK_NOT_FOUND")
        self.assert_error(self.client.get(self.url(task) + "/assignment-history"), 404, "TASK_NOT_FOUND")
        self.login_as(leader)
        self.assertEqual(self.client.get(self.url(task) + "/assignment-history").json()["data"][0]["user"]["id"], member["id"])

    def test_cross_team_targets_and_resource_ids_are_hidden(self):
        _, _, _, milestone, _ = self.scenario()
        task = self.create(milestone).json()["data"]
        self.assert_error(self.write("POST", self.url(task) + "/assignees", {"team_member_id": "9223372036854775807"}), 409, "ASSIGNEE_NOT_CURRENT_MEMBER")
        self.signed_in()
        for suffix in ("", "/assignees", "/assignment-history"):
            self.assert_error(self.client.get(self.url(task) + suffix), 404, "TASK_NOT_FOUND")
        self.assert_error(self.client.get(self.collection(milestone)), 404, "MILESTONE_NOT_FOUND")

    def test_completed_zero_assignees_after_exit_preserves_v1_reopen_restriction(self):
        leader, _, _, milestone, member = self.scenario(True)
        task = self.create(milestone).json()["data"]
        self.assertEqual(self.assign(task, member).status_code, 201)
        self.assertEqual(self.status(task, "completed").status_code, 200)
        self.login_as(member)
        self.assertEqual(self.write("POST", "/api/v1/teams/me/leave", {}).status_code, 204)
        self.login_as(leader)
        self.assertEqual(self.client.get(self.url(task) + "/assignees").json()["data"], [])
        self.assert_error(self.status(task, "in_progress"), 409, "TASK_ASSIGNEE_REQUIRED")
        self.assert_error(self.assign(task, leader), 409, "TASK_LOCKED")
        self.assertEqual(self.client.get(self.url(task)).json()["data"]["status"], "completed")

    def test_first_evaluation_locks_all_task_and_assignment_writes(self):
        phase, data = self.ready_phase()
        self.assertEqual(phase.evaluate(data).status_code, 201)
        self.login_as(data["leader"])
        task = {"id": data["task"]}; milestone = {"id": data["milestone"]}
        self.assertFalse(self.client.get(self.collection(milestone)).json()["data"]["can_manage"])
        self.assert_error(self.create(milestone), 409, "TASK_LOCKED")
        self.assert_error(self.write("PATCH", self.url(task), {"description": "No"}), 409, "TASK_LOCKED")
        self.assert_error(self.write("DELETE", self.url(task)), 409, "TASK_LOCKED")
        self.assert_error(self.status(task, "completed"), 409, "TASK_LOCKED")
        self.assert_error(self.assign(task, data["leader"]), 409, "TASK_LOCKED")
        self.assert_error(self.write("DELETE", self.url(task) + "/assignees/" + self.member_id(data["leader"])), 409, "TASK_LOCKED")
        self.assertEqual(self.client.get(self.url(task)).status_code, 200)

    def test_http_submission_vote_task_completion_unlocks_real_evaluation(self):
        phase = submissions.SubmissionAPIIntegrationTests()
        for key in ("conn", "app", "client", "before"):
            setattr(phase, key, getattr(self, key))
        leader, _, project, advisor = phase.project_with_advisor()
        submission = phase.upload().json()["data"]
        _, committee = phase.approve_and_assign(advisor, project, submission)
        phase.cast_votes(committee, project, submission)
        self.login_as(leader)
        milestone = self.create_milestone().json()["data"]
        task = self.create(milestone).json()["data"]
        self.assertEqual(self.assign(task, leader).status_code, 201)
        self.assertEqual(self.status(task, "completed").status_code, 200)
        self.login_as(committee[0])
        url = f"/api/v1/committee/projects/{project['id']}/evaluations"
        self.assertTrue(self.client.get(url).json()["data"]["can_evaluate"])
        self.assertEqual(self.write("POST", url, {"score": 80, "comment": "Complete API workflow"}).status_code, 201)
        self.login_as(leader)
        self.assert_error(self.status(task, "in_progress"), 409, "TASK_LOCKED")

    def test_atomic_failure_and_transaction_completion_do_not_return_success(self):
        _, _, _, milestone, _ = self.scenario()
        count = self.conn.execute("SELECT count(*) FROM public.tasks").fetchone()[0]
        with patch.object(TaskRepository, "detail", side_effect=StorageUnavailable()):
            self.assert_error(self.create(milestone), 500, "INTERNAL_ERROR")
        @contextmanager
        def fail_completion():
            with self.conn.transaction():
                with task_transaction_on(self.conn) as store:
                    yield store
                    raise StorageUnavailable()
        self.app.dependency_overrides[get_task_uow] = lambda: fail_completion
        self.assert_error(self.create(milestone), 500, "INTERNAL_ERROR")
        self.assertEqual(self.conn.execute("SELECT count(*) FROM public.tasks").fetchone()[0], count)

    def test_auth_role_csrf_and_strict_ids(self):
        _, _, _, milestone, _ = self.scenario()
        task = self.create(milestone).json()["data"]
        self.assert_error(self.client.post(self.url(task) + "/status", headers={"Origin": "http://localhost:3000"}, json={"status": "completed"}), 403, "CSRF_INVALID")
        self.assert_error(self.client.get("/api/v1/tasks/9223372036854775808"), 422, "VALIDATION_ERROR")
        for body in ({"status": True}, {"status": "done"}, {"status": "completed", "actor": "1"}):
            self.assert_error(self.write("POST", self.url(task) + "/status", body), 422, "VALIDATION_ERROR")
        for role in ("advisor", "coordinator"):
            self.signed_in(role)
            self.assert_error(self.client.get(self.url(task)), 403, "TASK_ACCESS_FORBIDDEN")
        self.client.cookies.clear()
        self.assert_error(self.client.get(self.collection(milestone)), 401, "AUTHENTICATION_REQUIRED")


if __name__ == "__main__":
    unittest.main()
