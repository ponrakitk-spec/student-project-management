"""Real V1 Milestone HTTP tests, all fixtures under outer ROLLBACK."""
from datetime import timedelta
import unittest
from unittest.mock import patch
from backend.auth_api import CSRF_HEADER
from backend.auth_store import StorageUnavailable
from backend.milestone_api import get_milestone_uow
from backend.milestone_store import MilestoneRepository, milestone_transaction_on
from backend.committee_api import get_committee_uow
from backend.committee_store import committee_transaction_on
from backend.topic_vote_api import get_topic_vote_uow
from backend.topic_vote_store import topic_vote_transaction_on
from backend.evaluation_api import get_evaluation_uow
from backend.evaluation_store import evaluation_transaction_on
from backend.invitation_api import get_invitation_uow
from backend.invitation_store import invitation_transaction_on
from backend.tests import test_team_api as base, test_project_api as projects, test_evaluation_api as evaluations

ROOT = "/api/v1/projects/me/milestones"


class MilestoneAPIIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        base.TeamAPIIntegrationTests.setUpClass.__func__(cls)

    @classmethod
    def tearDownClass(cls):
        base.TeamAPIIntegrationTests.tearDownClass.__func__(cls)

    def setUp(self):
        projects.ProjectAPIIntegrationTests.setUp(self)
        for dependency, factory in ((get_milestone_uow, milestone_transaction_on), (get_invitation_uow, invitation_transaction_on),
                                    (get_committee_uow, committee_transaction_on), (get_topic_vote_uow, topic_vote_transaction_on),
                                    (get_evaluation_uow, evaluation_transaction_on)):
            self.app.dependency_overrides[dependency] = lambda factory=factory: lambda: factory(self.conn)
        for module in ("auth", "team", "project", "invitation", "committee", "topic_vote", "evaluation", "milestone", "submission"):
            guard = patch(f"backend.{module}_store.open_auth_connection", side_effect=AssertionError("Escaped rollback fixture"))
            guard.start()
            self.addCleanup(guard.stop)
        self.today = self.conn.execute("SELECT (NOW() AT TIME ZONE 'Asia/Bangkok')::date").fetchone()[0]

    tearDown = base.TeamAPIIntegrationTests.tearDown
    signed_in = base.TeamAPIIntegrationTests.signed_in
    create_team = base.TeamAPIIntegrationTests.create
    team = projects.ProjectAPIIntegrationTests.team
    post_project = projects.ProjectAPIIntegrationTests.post
    login_as = projects.ProjectAPIIntegrationTests.login_as
    assert_error = base.TeamAPIIntegrationTests.assert_error

    def setup_project(self):
        leader, team = self.team()
        project = self.post_project().json()["data"]
        return leader, team, project

    def write(self, method, path, body=None):
        return self.client.request(method, path, headers={**base.ORIGIN, CSRF_HEADER: self.client.cookies.get("spms_csrf") or ""}, json=body)

    def create(self, name="Milestone fixture", days=7, **extra):
        return self.write("POST", ROOT, {"name": name, "due_date": (self.today + timedelta(days=days)).isoformat(), **extra})

    def url(self, row):
        return "/api/v1/milestones/" + row["id"]

    def task(self, row, days=5):
        return self.conn.execute("SELECT public.v1_create_task(%s,'Task fixture',NULL,%s)",
                                 (row["id"], self.today + timedelta(days=days))).fetchone()[0]

    def test_create_normalize_read_order_patch_noop_and_delete_without_advisor_gate(self):
        leader, _, project = self.setup_project()
        response = self.create("  Milestone  ", description=" \t ")
        self.assertEqual(response.status_code, 201, response.text)
        row = response.json()["data"]
        self.assertEqual(row["name"], "Milestone")
        self.assertIsNone(row["description"])
        self.assertEqual(row["project_id"], project["id"])
        self.assertEqual(row["created_by"], leader["id"])
        self.assertIsNone(row["updated_by"])
        self.assertEqual(row["status"], "not_started")
        self.assertIsNone(row["completed_at"])
        self.assertEqual(self.client.get(self.url(row)).json()["data"], row)
        self.assertEqual(self.write("PATCH", self.url(row), {"name": "Milestone"}).json()["data"], row)
        earlier = self.create("Earlier", days=0).json()["data"]
        listing = self.client.get(ROOT).json()["data"]
        self.assertEqual(listing["project_id"], project["id"])
        self.assertTrue(listing["can_manage"])
        self.assertEqual([r["id"] for r in listing["milestones"]], [earlier["id"], row["id"]])
        updated = self.write("PATCH", self.url(row), {"description": " Changed "}).json()["data"]
        self.assertEqual(updated["description"], "Changed")
        self.assertEqual(updated["updated_by"], leader["id"])
        self.assertEqual(updated["created_at"], row["created_at"])
        response = self.write("DELETE", self.url(row))
        self.assertEqual(response.status_code, 204, response.text)
        self.assertEqual(response.content, b"")
        self.assert_error(self.client.get(self.url(row)), 404, "MILESTONE_NOT_FOUND")
        self.assertEqual(self.client.get("/api/v1/projects/me").json()["data"]["id"], project["id"])

    def test_validation_and_unique_constraint_do_not_write_partial_data(self):
        self.setup_project()
        for payload in ({"name": "  ", "due_date": self.today.isoformat()}, {"name": "x" * 256, "due_date": self.today.isoformat()},
                        {"name": "N", "due_date": "2026-02-30"}, {"name": "N", "due_date": self.today.isoformat(), "status": "completed"},
                        {"name": "N", "due_date": self.today.isoformat(), "created_by": "1"}):
            self.assert_error(self.write("POST", ROOT, payload), 422, "VALIDATION_ERROR")
        self.assert_error(self.create(days=-1), 422, "MILESTONE_DUE_DATE_PAST")
        row = self.create("แ" * 255).json()["data"]
        self.assertEqual(len(row["name"]), 255)
        self.assertEqual(self.create("Unique").status_code, 201)
        self.assert_error(self.create(" UNIQUE "), 409, "MILESTONE_NAME_CONFLICT")
        for payload in ({}, {"due_date": None}, {"name": None}, {"status": "completed"}):
            self.assert_error(self.write("PATCH", self.url(row), payload), 422, "VALIDATION_ERROR")

    def test_members_read_but_cannot_write_and_cross_team_ids_are_hidden(self):
        leader, team, _ = self.setup_project()
        row = self.create().json()["data"]
        member = projects.ProjectAPIIntegrationTests.member(self, leader, team)
        self.assertEqual(self.client.get(ROOT).json()["data"]["can_manage"], False)
        self.assertEqual(self.client.get(self.url(row)).status_code, 200)
        self.assert_error(self.create(), 403, "MILESTONE_ACTION_FORBIDDEN")
        self.assert_error(self.write("PATCH", self.url(row), {"description": "No"}), 403, "MILESTONE_ACTION_FORBIDDEN")
        self.assert_error(self.write("DELETE", self.url(row)), 403, "MILESTONE_ACTION_FORBIDDEN")
        self.signed_in()
        self.assert_error(self.client.get(self.url(row)), 404, "MILESTONE_NOT_FOUND")
        self.assert_error(self.write("DELETE", self.url(row)), 404, "MILESTONE_NOT_FOUND")
        self.login_as(leader)
        membership = self.conn.execute("SELECT id FROM public.team_members WHERE user_id=%s", (member["id"],)).fetchone()[0]
        self.assertEqual(self.write("POST", f"/api/v1/teams/me/members/{membership}/remove", {}).status_code, 204)
        self.login_as(member)
        self.assert_error(self.client.get(self.url(row)), 404, "MILESTONE_NOT_FOUND")

    def test_d01_and_task_fk_restrict_preserve_both_records(self):
        self.setup_project()
        row = self.create(days=10).json()["data"]
        task = self.task(row, days=8)
        self.assert_error(self.write("PATCH", self.url(row), {"due_date": (self.today + timedelta(days=5)).isoformat(), "name": "Must roll back"}), 409, "TASK_DUE_DATE_CONFLICT")
        self.assertEqual(self.client.get(self.url(row)).json()["data"], row)
        self.assertEqual(self.conn.execute("SELECT due_date FROM public.tasks WHERE id=%s", (task,)).fetchone()[0], self.today + timedelta(days=8))
        self.assert_error(self.write("DELETE", self.url(row)), 409, "MILESTONE_HAS_TASKS")
        self.assertEqual(self.client.get(self.url(row)).status_code, 200)

    def test_status_is_derived_from_real_tasks_and_completed_at_changes(self):
        leader, _, _ = self.setup_project()
        row = self.create().json()["data"]
        task = self.task(row)
        member = self.conn.execute("SELECT id FROM public.team_members WHERE user_id=%s", (leader["id"],)).fetchone()[0]
        self.conn.execute("SELECT public.v1_assign_task(%s,%s)", (task, member))
        self.conn.execute("SELECT public.v1_set_task_status(%s,'in_progress')", (task,))
        self.assertEqual(self.client.get(self.url(row)).json()["data"]["status"], "in_progress")
        self.conn.execute("SELECT public.v1_set_task_status(%s,'completed')", (task,))
        result = self.client.get(self.url(row)).json()["data"]
        self.assertEqual(result["status"], "completed")
        self.assertIsNotNone(result["completed_at"])

    def test_first_evaluation_locks_all_writes_but_keeps_reads(self):
        # Borrow the existing phase builder; it uses this same connection,
        # HTTP client and outer ROLLBACK, with all V1 prerequisites enforced.
        phase = evaluations.EvaluationAPIIntegrationTests()
        for key in ("conn", "app", "client", "before"):
            setattr(phase, key, getattr(self, key))
        data = phase.ready()
        self.assertEqual(phase.evaluate(data).status_code, 201)
        self.login_as(data["leader"])
        row = {"id": data["milestone"]}
        self.assertFalse(self.client.get(ROOT).json()["data"]["can_manage"])
        self.assert_error(self.create(), 409, "MILESTONE_LOCKED")
        self.assert_error(self.write("PATCH", self.url(row), {"description": "No"}), 409, "MILESTONE_LOCKED")
        self.assert_error(self.write("DELETE", self.url(row)), 409, "MILESTONE_LOCKED")
        self.assertEqual(self.client.get(self.url(row)).status_code, 200)

    def test_auth_csrf_origin_role_id_and_missing_context_errors_are_no_store(self):
        self.assert_error(self.client.get(ROOT), 401, "AUTHENTICATION_REQUIRED")
        self.signed_in()
        self.assert_error(self.client.get(ROOT), 404, "TEAM_NOT_FOUND")
        self.create_team()
        self.assert_error(self.client.get(ROOT), 404, "PROJECT_NOT_FOUND")
        self.post_project()
        self.assert_error(self.client.post(ROOT, headers=base.ORIGIN, json={"name": "No CSRF", "due_date": self.today.isoformat()}), 403, "CSRF_INVALID")
        row = self.create().json()["data"]
        self.assert_error(self.client.delete(self.url(row), headers={"Origin": "https://untrusted.example"}), 403, "ORIGIN_NOT_ALLOWED")
        self.assert_error(self.client.get("/api/v1/milestones/0"), 422, "VALIDATION_ERROR")
        for role in ("advisor", "coordinator"):
            self.signed_in(role)
            self.assert_error(self.client.get(ROOT), 403, "MILESTONE_ACCESS_FORBIDDEN")
        response = self.client.options(self.url(row), headers={**base.ORIGIN, "Access-Control-Request-Method": "DELETE", "Access-Control-Request-Headers": "X-CSRF-Token"})
        self.assertEqual(response.status_code, 200)
        self.assertIn("DELETE", response.headers["access-control-allow-methods"])

    def test_storage_failure_after_insert_rolls_back_without_false_201(self):
        self.setup_project()
        count = self.conn.execute("SELECT count(*) FROM public.milestones").fetchone()[0]
        with patch.object(MilestoneRepository, "detail", side_effect=StorageUnavailable()):
            self.assert_error(self.create(), 500, "INTERNAL_ERROR")
        self.assertEqual(self.conn.execute("SELECT count(*) FROM public.milestones").fetchone()[0], count)


if __name__ == "__main__":
    unittest.main()
