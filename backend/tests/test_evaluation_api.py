"""Evaluation HTTP/PG tests; all Auth/business fixtures share outer ROLLBACK."""

from contextlib import contextmanager
import json
import unittest
from unittest.mock import patch

import psycopg

from backend.auth_api import CSRF_HEADER, SESSION_COOKIE
from backend.auth_security import session_digest
from backend.auth_store import StorageUnavailable
from backend.evaluation_api import get_evaluation_uow
from backend.evaluation_store import EvaluationRepository, evaluation_transaction_on
from backend.tests import test_topic_vote_api as topic_base

ROOT = "/api/v1/committee/projects"
TEAM = "/api/v1/projects/me/evaluations"
def fixture_base():
    return topic_base.TopicVoteAPIIntegrationTests


class EvaluationAPIIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        fixture_base().setUpClass.__func__(cls)

    @classmethod
    def tearDownClass(cls):
        fixture_base().tearDownClass.__func__(cls)

    def setUp(self):
        fixture_base().setUp(self)
        self.app.dependency_overrides[get_evaluation_uow] = lambda: lambda: evaluation_transaction_on(self.conn)

    tearDown = fixture_base().tearDown
    signed_in = fixture_base().signed_in
    create_team = fixture_base().create_team
    assert_error = fixture_base().assert_error
    team = fixture_base().team
    post_project = fixture_base().post_project
    login_as = fixture_base().login_as
    fixture_actor = fixture_base().fixture_actor
    fixture_submission = fixture_base().fixture_submission
    write = fixture_base().write
    add = fixture_base().add
    url = fixture_base().url
    roster = fixture_base().roster
    advisor = fixture_base().advisor
    login_id = fixture_base().login_id
    scenario = fixture_base().scenario
    vote_url = fixture_base().vote_url
    vote = fixture_base().vote

    def eval_url(self, data):
        return f"{ROOT}/{data['project']['id']}/evaluations"

    def ready(self, count=3, *, work=True, member=False):
        data = self.scenario(count, member=member)
        for index in range(count):
            self.assertEqual(self.vote(data, index).status_code, 201)
        if work:
            self.complete_work(data)
        return data

    def complete_work(self, data):
        self.fixture_actor(data["leader"])
        due = self.conn.execute("SELECT (NOW() AT TIME ZONE 'Asia/Bangkok')::date+7").fetchone()[0]
        milestone = self.conn.execute("SELECT public.v1_create_milestone(%s,'Evaluation phase',NULL,%s)",
                                      (data["project"]["id"], due)).fetchone()[0]
        task = self.conn.execute("SELECT public.v1_create_task(%s,'Evaluation task',NULL,%s)", (milestone, due)).fetchone()[0]
        actor = data["member"]["id"] if data["member"] is not None else data["leader"]["id"]
        member = self.conn.execute("SELECT id FROM public.team_members WHERE user_id=%s", (actor,)).fetchone()[0]
        self.conn.execute("SELECT public.v1_assign_task(%s,%s)", (task, member))
        self.conn.execute("SELECT public.v1_set_task_status(%s,'completed')", (task,))
        self.conn.execute("SET CONSTRAINTS ALL IMMEDIATE")
        self.assertEqual(self.conn.execute("SELECT status FROM public.milestones WHERE id=%s", (milestone,)).fetchone()[0], "completed")
        data.update(milestone=str(milestone), task=str(task))

    def evaluate(self, data, index=0, score=80, comment="Evaluation feedback"):
        self.login_id(data["assignments"][index]["advisor"]["id"])
        return self.write("POST", self.eval_url(data), {"score": score, "comment": comment})

    def result(self, data, role="team"):
        if role == "team":
            self.login_as(data["leader"])
            path = TEAM
        elif role == "advisor":
            self.login_id(data["advisor"])
            path = f"/api/v1/advisor/projects/{data['project']['id']}/evaluations"
        else:
            self.login_as(data["coordinator"])
            path = f"/api/v1/coordinator/projects/{data['project']['id']}/evaluations"
        response = self.client.get(path)
        self.assertEqual(response.status_code, 200)
        return response.json()["data"]

    def test_before_complete_only_own_evaluation_is_visible_including_score_zero(self):
        data = self.ready()
        own = self.evaluate(data, score=0, comment="Private zero feedback").json()["data"]
        self.assertEqual(own["score"], 0)
        context = self.client.get(self.eval_url(data)).json()["data"]
        self.assertEqual(context["own_evaluation"], own)
        self.assertFalse(context["can_evaluate"])
        self.assertEqual(context["blocking_reason"], "ALREADY_EVALUATED")
        self.assertIsNone(context["summary"])
        self.login_id(data["assignments"][1]["advisor"]["id"])
        other = self.client.get(self.eval_url(data)).json()["data"]
        self.assertIsNone(other["own_evaluation"])
        self.assertNotIn("Private zero feedback", json.dumps(other))
        for role in ("team", "advisor", "coordinator"):
            result = self.result(data, role)
            self.assertIsNone(result["summary"])
            self.assertEqual(set(result), {"project", "summary", "evaluations"} if role == "coordinator" else {"project", "summary"})
            self.assertNotIn("Private zero feedback", json.dumps(result))
            if role == "coordinator":
                self.assertEqual(result["evaluations"], [])

    def test_complete_summary_and_individuals_are_released_only_to_approved_roles(self):
        data, own = self.ready(), []
        for index, score in enumerate((0, 100, 100)):
            response = self.evaluate(data, index, score, f"Private feedback {index}")
            self.assertEqual(response.status_code, 201)
            self.assertEqual(response.headers["cache-control"], "no-store")
            own.append(response.json()["data"])
        expected = {"total_score": "200", "average_score": 67}
        for role in ("team", "advisor"):
            result = self.result(data, role)
            self.assertEqual(set(result), {"project", "summary"})
            self.assertEqual(result["summary"], expected)
            self.assertNotIn("Private feedback", json.dumps(result))
        self.login_id(data["assignments"][0]["advisor"]["id"])
        committee = self.client.get(self.eval_url(data)).json()["data"]
        self.assertEqual(committee["own_evaluation"], own[0])
        self.assertEqual(committee["summary"], expected)
        self.assertNotIn("Private feedback 1", json.dumps(committee))
        coordinator = self.result(data, "coordinator")
        self.assertEqual(coordinator["summary"], expected)
        self.assertEqual([row["id"] for row in coordinator["evaluations"]], [row["id"] for row in own])
        self.assertTrue(all(set(row) == {"id", "advisor", "score", "comment", "created_at"} for row in coordinator["evaluations"]))

    def test_sql_average_rounds_half_up_and_zero_total_is_not_hidden(self):
        for scores, expected in (((0, 0, 1, 1), {"total_score": "2", "average_score": 1}),
                                 ((0, 0, 0), {"total_score": "0", "average_score": 0})):
            data = self.ready(len(scores))
            for index, score in enumerate(scores):
                self.assertEqual(self.evaluate(data, index, score).status_code, 201)
            self.assertEqual(self.result(data)["summary"], expected)

    def test_topic_and_completed_milestone_are_real_prerequisites(self):
        data = self.scenario()
        self.assert_error(self.evaluate(data), 409, "TOPIC_NOT_APPROVED")
        for index in range(3):
            self.assertEqual(self.vote(data, index).status_code, 201)
        self.assert_error(self.evaluate(data), 409, "COMPLETED_MILESTONE_REQUIRED")
        context = self.client.get(self.eval_url(data)).json()["data"]
        self.assertEqual(context["blocking_reason"], "COMPLETED_MILESTONE_REQUIRED")
        self.complete_work(data)
        self.assertEqual(self.evaluate(data).status_code, 201)

    def test_changed_milestone_state_is_rechecked_after_reading_eligible_form(self):
        data = self.ready()
        self.login_id(data["assignments"][0]["advisor"]["id"])
        self.assertTrue(self.client.get(self.eval_url(data)).json()["data"]["can_evaluate"])
        self.fixture_actor(data["leader"])
        self.conn.execute("SELECT public.v1_set_task_status(%s,'in_progress')", (data["task"],))
        self.assert_error(self.evaluate(data), 409, "COMPLETED_MILESTONE_REQUIRED")

    def test_duplicate_and_sql_unique_defense_keep_first_score_immutable(self):
        data = self.ready()
        first = self.evaluate(data, score=100).json()["data"]
        self.assert_error(self.evaluate(data, score=0), 409, "EVALUATION_ALREADY_RECORDED")
        with patch.object(EvaluationRepository, "own", return_value=None):
            self.assert_error(self.evaluate(data), 409, "EVALUATION_ALREADY_RECORDED")
        self.assertEqual(self.client.get(self.eval_url(data)).json()["data"]["own_evaluation"], first)
        for method in ("PATCH", "PUT", "DELETE"):
            self.assertEqual(self.write(method, self.eval_url(data), {"score": 20, "comment": "change"}).status_code, 405)

    def test_score_types_comment_and_extra_fields_are_validated_without_echo(self):
        data = self.ready()
        self.login_id(data["assignments"][0]["advisor"]["id"])
        for score in (-1, 101, True, False, 1.5, 80.0, "80", None):
            response = self.write("POST", self.eval_url(data), {"score": score, "comment": "DoNotEchoEvaluation"})
            self.assert_error(response, 422, "VALIDATION_ERROR")
            self.assertNotIn("DoNotEchoEvaluation", response.text)
            self.assertIn("คะแนน", response.json()["error"]["message"])
        for payload in ({}, {"score": 80}, {"score": 80, "comment": None}, {"score": 80, "comment": " \t\n"},
                        {"score": 80, "comment": "invalid\x00"}, {"score": 80, "comment": "valid", "assignment_id": "1"}):
            self.assert_error(self.write("POST", self.eval_url(data), payload), 422, "VALIDATION_ERROR")
        response = self.write("POST", self.eval_url(data), {"score": 80, "comment": "  " + "ก" * 4096 + "  "})
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json()["data"]["comment"], "ก" * 4096)

    def test_first_evaluation_locks_tasks_and_milestones_with_sql_guards(self):
        data = self.ready()
        self.assertEqual(self.evaluate(data).status_code, 201)
        self.fixture_actor(data["leader"])
        operations = (("SELECT public.v1_set_task_status(%s,'in_progress')", (data["task"],)),
                      ("SELECT public.v1_update_milestone(%s,'Changed',NULL,NULL)", (data["milestone"],)))
        for query, parameters in operations:
            with self.assertRaises(psycopg.errors.RaiseException):
                with self.conn.transaction():
                    self.conn.execute(query, parameters)
        self.assertEqual(self.conn.execute("SELECT status FROM public.tasks WHERE id=%s", (data["task"],)).fetchone()[0], "completed")

    def test_member_exit_after_first_score_preserves_exception_and_revokes_reader(self):
        data = self.ready(member=True)
        self.assertEqual(self.evaluate(data).status_code, 201)
        self.login_as(data["member"])
        self.assertEqual(self.client.get(TEAM).status_code, 200)
        self.assertEqual(self.write("POST", "/api/v1/teams/me/leave", {}).status_code, 204)
        self.assert_error(self.client.get(TEAM), 404, "TEAM_NOT_FOUND")
        self.assertEqual(self.conn.execute("SELECT count(*) FROM public.task_assignees WHERE task_id=%s", (data["task"],)).fetchone()[0], 0)
        self.assertEqual(self.conn.execute("SELECT count(*) FROM public.task_assignment_history WHERE task_id=%s", (data["task"],)).fetchone()[0], 1)

    def test_roles_sessions_csrf_and_origin_are_enforced(self):
        data = self.ready()
        self.login_as(data["leader"])
        self.assert_error(self.client.get(self.eval_url(data)), 403, "EVALUATION_ACCESS_FORBIDDEN")
        self.assert_error(self.client.get(f"/api/v1/coordinator/projects/{data['project']['id']}/evaluations"), 403, "EVALUATION_READER_ACCESS_FORBIDDEN")
        self.login_id(data["assignments"][0]["advisor"]["id"])
        payload = {"score": 80, "comment": "valid"}
        self.assert_error(self.client.post(self.eval_url(data), headers={"Origin": "http://localhost:3000"}, json=payload), 403, "CSRF_INVALID")
        self.assert_error(self.write("POST", self.eval_url(data), payload, {"Origin": "https://invalid.example"}), 403, "ORIGIN_NOT_ALLOWED")
        digest = session_digest(self.client.cookies.get(SESSION_COOKIE))
        self.conn.execute("DELETE FROM auth.sessions WHERE token_hash=%s", (digest,))
        self.assert_error(self.client.get(self.eval_url(data)), 401, "AUTHENTICATION_REQUIRED")
        self.client.cookies.clear()
        self.assert_error(self.write("POST", self.eval_url(data), payload), 401, "AUTHENTICATION_REQUIRED")

    def test_scoped_project_reads_and_no_team_no_project_are_distinct(self):
        data = self.ready()
        self.login_id(data["advisor"])
        self.assert_error(self.client.get(self.eval_url(data)), 404, "COMMITTEE_PROJECT_NOT_FOUND")
        stranger = self.advisor()
        self.login_id(stranger)
        self.assert_error(self.client.get(f"/api/v1/advisor/projects/{data['project']['id']}/evaluations"), 404, "PROJECT_NOT_FOUND")
        self.signed_in()
        self.assert_error(self.client.get(TEAM), 404, "TEAM_NOT_FOUND")
        self.create_team()
        self.assert_error(self.client.get(TEAM), 404, "PROJECT_NOT_FOUND")

    def test_coordinator_without_assignments_gets_null_not_zero_summary(self):
        data = self.scenario(count=0)
        result = self.result(data, "coordinator")
        self.assertIsNone(result["summary"])
        self.assertEqual(result["evaluations"], [])

    def test_sql_and_uow_completion_failures_rollback_before_response(self):
        data = self.ready()
        self.login_id(data["assignments"][0]["advisor"]["id"])
        original = EvaluationRepository.controlled_record
        def fail(store, *args):
            original(store, *args)
            raise StorageUnavailable()
        payload = {"score": 80, "comment": "valid"}
        with patch.object(EvaluationRepository, "controlled_record", fail):
            self.assert_error(self.write("POST", self.eval_url(data), payload), 500, "INTERNAL_ERROR")
        self.assertIsNone(self.client.get(self.eval_url(data)).json()["data"]["own_evaluation"])
        @contextmanager
        def failing():
            with evaluation_transaction_on(self.conn) as store:
                yield store
                raise StorageUnavailable()
        self.app.dependency_overrides[get_evaluation_uow] = lambda: failing
        self.assert_error(self.write("POST", self.eval_url(data), payload), 500, "INTERNAL_ERROR")
        self.app.dependency_overrides[get_evaluation_uow] = lambda: lambda: evaluation_transaction_on(self.conn)
        self.assertIsNone(self.client.get(self.eval_url(data)).json()["data"]["own_evaluation"])

    def test_unknown_permission_sql_errors_are_sanitized_without_fallback(self):
        data = self.ready()
        self.login_id(data["assignments"][0]["advisor"]["id"])
        for error in (psycopg.errors.InsufficientPrivilege("PrivateSQL"), psycopg.errors.RaiseException("PrivateSQL")):
            with patch.object(EvaluationRepository, "controlled_record", side_effect=error):
                response = self.write("POST", self.eval_url(data), {"score": 80, "comment": "valid"})
            self.assert_error(response, 500, "INTERNAL_ERROR")
            self.assertNotIn("PrivateSQL", response.text)


if __name__ == "__main__":
    unittest.main()
