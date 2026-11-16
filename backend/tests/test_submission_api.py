"""Submission API and PostgreSQL V1 workflow tests; all fixture writes roll back."""

from io import BytesIO
import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient
from pptx import Presentation
from pypdf import PdfWriter

from backend.auth_api import CSRF_COOKIE, CSRF_HEADER
from backend.submission_api import get_submission_uow
from backend.auth_store import StorageUnavailable
from backend.submission_store import SubmissionRepository, submission_transaction_on
from backend.committee_api import get_committee_uow
from backend.committee_store import committee_transaction_on
from backend.topic_vote_api import get_topic_vote_uow
from backend.topic_vote_store import topic_vote_transaction_on
from backend.evaluation_api import get_evaluation_uow
from backend.evaluation_store import evaluation_transaction_on
from backend.project_api import get_project_uow
from backend.project_store import project_transaction_on
from backend.invitation_api import get_invitation_uow
from backend.invitation_store import invitation_transaction_on
from backend.tests import test_project_api as project_base, test_team_api as base

URL = "/api/v1/projects/me/submissions"
PDF_MIME = "application/pdf"


def valid_pdf():
    output = BytesIO()
    writer = PdfWriter()
    writer.add_blank_page(width=612, height=792)
    writer.write(output)
    return output.getvalue()


def valid_pptx():
    output = BytesIO()
    presentation = Presentation()
    presentation.slides.add_slide(presentation.slide_layouts[6])
    presentation.save(output)
    return output.getvalue()


class SubmissionAPIIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        base.TeamAPIIntegrationTests.setUpClass.__func__(cls)

    @classmethod
    def tearDownClass(cls):
        base.TeamAPIIntegrationTests.tearDownClass.__func__(cls)

    def setUp(self):
        base.TeamAPIIntegrationTests.setUp(self)
        self.app.dependency_overrides[get_project_uow] = lambda: lambda: project_transaction_on(self.conn)
        self.app.dependency_overrides[get_invitation_uow] = lambda: lambda: invitation_transaction_on(self.conn)
        self.app.dependency_overrides[get_submission_uow] = lambda: lambda: submission_transaction_on(self.conn)
        self.app.dependency_overrides[get_committee_uow] = lambda: lambda: committee_transaction_on(self.conn)
        self.app.dependency_overrides[get_topic_vote_uow] = lambda: lambda: topic_vote_transaction_on(self.conn)
        self.app.dependency_overrides[get_evaluation_uow] = lambda: lambda: evaluation_transaction_on(self.conn)
        # Fail before any accidental production UOW can open a separate connection.
        for module in ("auth", "team", "project", "invitation", "submission", "committee", "topic_vote", "evaluation"):
            guard = patch(f"backend.{module}_store.open_auth_connection",
                          side_effect=AssertionError("Request escaped the rollback fixture"))
            guard.start()
            self.addCleanup(guard.stop)

    def assert_no_submissions_written(self):
        self.assertEqual(self.conn.execute("SELECT count(*) FROM public.project_submissions").fetchone()[0],
                         self.before[1]["public.project_submissions"])
        self.assertEqual(self.conn.execute("SELECT count(*) FROM public.project_submission_files").fetchone()[0],
                         self.before[1]["public.project_submission_files"])

    tearDown = base.TeamAPIIntegrationTests.tearDown
    signed_in = base.TeamAPIIntegrationTests.signed_in
    create_team = base.TeamAPIIntegrationTests.create
    assert_error = base.TeamAPIIntegrationTests.assert_error
    login_as = project_base.ProjectAPIIntegrationTests.login_as

    def headers(self):
        return {**base.ORIGIN, CSRF_HEADER: self.client.cookies.get(CSRF_COOKIE) or ""}

    def project_with_advisor(self):
        leader = self.signed_in()
        team = self.create_team().json()["data"]
        response = self.client.post("/api/v1/projects", headers=self.headers(),
                                    json={"name": "Submission topic", "description": "Snapshot description"})
        self.assertEqual(response.status_code, 201)
        project = response.json()["data"]
        advisor = self.signed_in("advisor")
        self.login_as(leader)
        invitation = self.client.post("/api/v1/projects/me/advisor-invitations",
            headers=self.headers(), json={"advisor_id": advisor["id"]})
        self.assertEqual(invitation.status_code, 201)
        self.login_as(advisor)
        response = self.client.post(f"/api/v1/advisor-invitations/{invitation.json()['data']['id']}/respond",
            headers=self.headers(), json={"decision": "accepted"})
        self.assertEqual(response.status_code, 200)
        self.login_as(leader)
        return leader, team, project, advisor

    def upload(self, filename="topic.pdf", data=None, mime=PDF_MIME, extra=None):
        parts = {"file": (filename, valid_pdf() if data is None else data, mime)}
        if extra:
            return self.client.post(URL, headers=self.headers(), data=extra, files=parts)
        return self.client.post(URL, headers=self.headers(), files=parts)

    def post_json(self, path, payload):
        return self.client.post(path, headers=self.headers(), json=payload)

    def approve_and_assign(self, advisor, project, submission):
        self.login_as(advisor)
        reviewed = self.post_json(f"/api/v1/project-submissions/{submission['id']}/review", {"decision": "approved"})
        self.assertEqual(reviewed.status_code, 200, reviewed.text)
        coordinator = self.signed_in("coordinator")
        listing = self.client.get("/api/v1/coordinator/projects")
        self.assertIn(project["id"], [p["id"] for p in listing.json()["data"]])
        committee = [self.signed_in("advisor") for _ in range(3)]
        self.login_as(coordinator)
        for teacher in committee:
            response = self.post_json(f"/api/v1/coordinator/projects/{project['id']}/committee",
                                      {"advisor_id": teacher["id"]})
            self.assertEqual(response.status_code, 201, response.text)
        return coordinator, committee

    def cast_votes(self, committee, project, submission, decision="approved"):
        for teacher in committee:
            self.login_as(teacher)
            self.assertEqual(self.client.get(f"/api/v1/project-submissions/{submission['id']}/file").status_code, 200)
            response = self.post_json(f"/api/v1/committee/projects/{project['id']}/topic-votes", {
                "submission_id": submission["id"], "vote": decision,
                "comment": "Revise the topic" if decision == "revision_requested" else None,
            })
            self.assertEqual(response.status_code, 201, response.text)

    def test_uploaded_submission_connects_to_committee_votes_and_evaluation(self):
        leader, _, project, advisor = self.project_with_advisor()
        submission = self.upload().json()["data"]
        coordinator, committee = self.approve_and_assign(advisor, project, submission)
        self.cast_votes(committee, project, submission)
        self.login_as(leader)
        result = self.client.get("/api/v1/projects/me/committee").json()["data"]
        self.assertEqual(result["rounds"][0]["decision"], "approved")
        self.assert_error(self.upload(), 409, "SUBMISSION_PHASE_CLOSED")

        # Milestone/Task HTTP APIs are not in the peer snapshot. Prepare only
        # this phase through existing V1 functions, under the same ROLLBACK.
        self.conn.execute("SELECT set_config('app.actor_user_id',%s,true)", (leader["id"],))
        due = self.conn.execute("SELECT (NOW() AT TIME ZONE 'Asia/Bangkok')::date+7").fetchone()[0]
        milestone = self.conn.execute("SELECT public.v1_create_milestone(%s,'Integration phase',NULL,%s)",
                                      (project["id"], due)).fetchone()[0]
        task = self.conn.execute("SELECT public.v1_create_task(%s,'Integration task',NULL,%s)",
                                 (milestone, due)).fetchone()[0]
        member = self.conn.execute("SELECT id FROM public.team_members WHERE user_id=%s", (leader["id"],)).fetchone()[0]
        self.conn.execute("SELECT public.v1_assign_task(%s,%s)", (task, member))
        self.conn.execute("SELECT public.v1_set_task_status(%s,'completed')", (task,))
        self.conn.execute("SET CONSTRAINTS ALL IMMEDIATE")
        self.assertEqual(self.conn.execute("SELECT status FROM public.milestones WHERE id=%s", (milestone,)).fetchone()[0], "completed")
        for teacher, score in zip(committee, (80, 70, 60)):
            self.login_as(teacher)
            response = self.post_json(f"/api/v1/committee/projects/{project['id']}/evaluations",
                                      {"score": score, "comment": "Integration feedback"})
            self.assertEqual(response.status_code, 201, response.text)
        self.login_as(leader)
        result = self.client.get("/api/v1/projects/me/evaluations").json()["data"]
        self.assertEqual(result["summary"], {"total_score": "210", "average_score": 70})
        self.login_as(coordinator)
        result = self.client.get(f"/api/v1/coordinator/projects/{project['id']}/evaluations").json()["data"]
        self.assertEqual(len(result["evaluations"]), 3)

    def test_committee_revision_opens_new_round_and_coordinator_file_access_stays_per_round(self):
        leader, _, project, advisor = self.project_with_advisor()
        first = self.upload().json()["data"]
        coordinator, committee = self.approve_and_assign(advisor, project, first)
        self.cast_votes(committee, project, first, "revision_requested")
        self.login_as(leader)
        self.assertTrue(self.client.get(URL + "/eligibility").json()["data"]["can_submit"])
        second = self.upload("revised.pdf").json()["data"]
        self.assertNotEqual(first["id"], second["id"])
        self.assertEqual(second["status"], "pending_review")
        self.login_as(coordinator)
        self.assertEqual(self.client.get(f"/api/v1/project-submissions/{first['id']}/file").status_code, 200)
        self.assert_error(self.client.get(f"/api/v1/project-submissions/{second['id']}/file"), 404, "SUBMISSION_NOT_FOUND")
        self.assert_error(self.client.get(f"/api/v1/project-submissions/{second['id']}"), 404, "SUBMISSION_NOT_FOUND")
        self.login_as(committee[0])
        self.assertEqual(self.client.get(f"/api/v1/project-submissions/{second['id']}/file").status_code, 200)
        self.login_as(leader)
        self.assertEqual([s["id"] for s in self.client.get(URL).json()["data"]], [second["id"], first["id"]])

    def test_member_loses_submission_and_file_access_after_leaving_team(self):
        leader, team, _, _ = self.project_with_advisor()
        member = self.signed_in()
        self.login_as(leader)
        response = self.post_json("/api/v1/teams/me/members", {"email": member["email"]})
        self.assertEqual(response.status_code, 201, response.text)
        submission = self.upload().json()["data"]
        self.login_as(member)
        self.assert_error(self.upload(), 403, "SUBMISSION_ACTION_FORBIDDEN")
        path = f"/api/v1/project-submissions/{submission['id']}"
        self.assertEqual(self.client.get(path + "/file").status_code, 200)
        response = self.post_json("/api/v1/teams/me/leave", {})
        self.assertEqual(response.status_code, 204, response.text)
        self.assert_error(self.client.get(path), 404, "SUBMISSION_NOT_FOUND")
        self.assert_error(self.client.get(path + "/file"), 404, "SUBMISSION_NOT_FOUND")
        self.assert_error(self.client.get(URL), 404, "TEAM_NOT_FOUND")
        self.assertEqual(self.conn.execute("SELECT count(*) FROM public.team_members WHERE team_id=%s AND user_id=%s",
                                          (team["id"], member["id"])).fetchone()[0], 0)

    def test_failure_after_inserts_rolls_back_both_submission_and_file_without_false_success(self):
        self.project_with_advisor()
        with patch.object(SubmissionRepository, "dto", side_effect=StorageUnavailable()):
            response = self.upload()
        self.assert_error(response, 500, "INTERNAL_ERROR")
        self.assert_no_submissions_written()

    def test_submission_round_trip_snapshot_history_download_and_advisor_approval(self):
        leader, team, project, advisor = self.project_with_advisor()
        # Membership additions must happen before the first pending submission.
        member = self.signed_in()
        self.conn.execute("SELECT set_config('app.actor_user_id',%s,true)", (leader["id"],))
        self.conn.execute("INSERT INTO public.team_members(team_id,user_id,role) VALUES (%s,%s,'member')",
                          (team["id"], member["id"]))
        self.conn.execute("SET CONSTRAINTS ALL IMMEDIATE")
        self.login_as(leader)
        original_pdf = valid_pdf()
        response = self.upload(data=original_pdf)
        self.assertEqual(response.status_code, 201, response.text)
        data = response.json()["data"]
        self.assertEqual(data["project_id"], project["id"])
        self.assertEqual(data["submitted_by"], leader["id"])
        self.assertEqual(data["snapshot_name"], "Submission topic")
        self.assertEqual(data["snapshot_description"], "Snapshot description")
        self.assertEqual(data["status"], "pending_review")
        self.assertEqual(data["original_filename"], "topic.pdf")
        self.assertIsNone(data["reviewed_by"])
        self.assertEqual(response.headers["cache-control"], "no-store")
        self.assertEqual(self.client.get(URL).json(), {"data": [data]})
        self.assertEqual(self.client.get(f"/api/v1/project-submissions/{data['id']}").json(), {"data": data})
        downloaded = self.client.get(f"/api/v1/project-submissions/{data['id']}/file")
        self.assertEqual(downloaded.status_code, 200)
        self.assertEqual(downloaded.content, original_pdf)
        self.assertEqual(downloaded.headers["content-type"], PDF_MIME)
        self.assertIn("attachment", downloaded.headers["content-disposition"])
        self.assertEqual(downloaded.headers["x-content-type-options"], "nosniff")

        self.login_as(member)
        self.assertEqual(self.client.get(f"/api/v1/project-submissions/{data['id']}").status_code, 200)
        self.login_as(advisor)
        inbox = self.client.get("/api/v1/advisor/submissions")
        self.assertEqual(inbox.status_code, 200)
        self.assertEqual(inbox.json()["data"], [data])
        reviewed = self.client.post(f"/api/v1/project-submissions/{data['id']}/review",
            headers=self.headers(), json={"decision": "approved"})
        self.assertEqual(reviewed.status_code, 200, reviewed.text)
        self.assertEqual(reviewed.json()["data"]["status"], "approved")
        self.assertEqual(reviewed.json()["data"]["reviewed_by"], advisor["id"])
        self.assert_error(self.client.post(f"/api/v1/project-submissions/{data['id']}/review",
            headers=self.headers(), json={"decision": "approved"}), 409, "SUBMISSION_ALREADY_REVIEWED")

    def test_revision_requires_comment_and_allows_immutable_new_round(self):
        leader, _, _, advisor = self.project_with_advisor()
        first = self.upload().json()["data"]
        self.assert_error(self.client.post(f"/api/v1/project-submissions/{first['id']}/review",
            headers=self.headers(), json={"decision": "revision_requested"}), 422, "VALIDATION_ERROR")
        self.login_as(advisor)
        response = self.client.post(f"/api/v1/project-submissions/{first['id']}/review",
            headers=self.headers(), json={"decision": "revision_requested", "comment": "ปรับขอบเขตงาน"})
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json()["data"]["review_comment"], "ปรับขอบเขตงาน")
        self.login_as(leader)
        second = self.upload("round-2.pdf", valid_pdf()).json()["data"]
        self.assertGreater(int(second["id"]), int(first["id"]))
        self.assertEqual(second["status"], "pending_review")
        self.assertEqual(self.client.get(URL).json()["data"], [second, response.json()["data"]])

    def test_pending_duplicate_requires_accepted_advisor_and_invalid_files_do_not_write(self):
        leader = self.signed_in()
        self.create_team()
        self.client.post("/api/v1/projects", headers=self.headers(), json={"name": "No advisor"})
        self.assert_error(self.upload(), 409, "ACCEPTED_ADVISOR_REQUIRED")
        self.assert_no_submissions_written()

        self.login_as(leader)
        self.project_with_advisor()
        invalid = self.upload("topic.pdf", b"%PDF-1.7\nnot a document")
        self.assert_error(invalid, 422, "FILE_CONTENT_INVALID")
        self.assert_no_submissions_written()
        accepted = self.upload()
        self.assertEqual(accepted.status_code, 201, accepted.text)
        self.assert_error(self.upload(), 409, "SUBMISSION_PENDING")

    def test_upload_enforces_actual_size_type_and_multipart_field_limits(self):
        self.project_with_advisor()
        too_large = self.upload("topic.pdf", b"x" * 4_000_001)
        self.assert_error(too_large, 413, "FILE_TOO_LARGE")
        self.assert_error(self.upload("topic.pdf", valid_pptx()), 422, "FILE_CONTENT_INVALID")
        self.assert_error(self.upload(extra={"extra": "not allowed"}), 422, "VALIDATION_ERROR")
        self.assert_no_submissions_written()
        accepted = self.upload("topic.pptx", valid_pptx(),
            "application/vnd.openxmlformats-officedocument.presentationml.presentation")
        self.assertEqual(accepted.status_code, 201, accepted.text)

    def test_access_is_scoped_to_current_team_and_accepted_or_assigned_advisor(self):
        _, _, _, advisor = self.project_with_advisor()
        submission = self.upload().json()["data"]
        outsider = self.signed_in("advisor")
        self.login_as(outsider)
        self.assert_error(self.client.get(f"/api/v1/project-submissions/{submission['id']}"),
                          404, "SUBMISSION_NOT_FOUND")
        self.assert_error(self.client.get(f"/api/v1/project-submissions/{submission['id']}/file"),
                          404, "SUBMISSION_NOT_FOUND")
        self.assertEqual(self.client.get("/api/v1/advisor/submissions").json(), {"data": []})
        self.assert_error(self.client.post(f"/api/v1/project-submissions/{submission['id']}/review",
            headers=self.headers(), json={"decision": "approved"}), 404, "SUBMISSION_NOT_FOUND")

        student = self.signed_in()
        self.login_as(student)
        self.assert_error(self.client.get(f"/api/v1/project-submissions/{submission['id']}"),
                          404, "SUBMISSION_NOT_FOUND")
        self.assert_error(self.upload(), 404, "TEAM_NOT_FOUND")

        self.login_as(advisor)
        self.assertEqual(self.client.get(f"/api/v1/project-submissions/{submission['id']}/file").status_code, 200)

    def test_auth_csrf_and_validation_errors_are_no_store(self):
        self.project_with_advisor()
        self.client.cookies.clear()
        self.assert_error(self.client.get(URL), 401, "AUTHENTICATION_REQUIRED")
        student = self.signed_in()
        self.create_team()
        self.client.post("/api/v1/projects", headers=self.headers(), json={"name": "Wrong file"})
        self.client.cookies.set(CSRF_COOKIE, "invalid", domain="localhost.local", path="/")
        response = self.upload()
        self.assert_error(response, 403, "CSRF_INVALID")
        self.assert_no_submissions_written()


if __name__ == "__main__":
    unittest.main()
