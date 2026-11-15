"""Role-scoped topic voting and result projections using existing V1 SQL."""

from contextlib import closing, contextmanager

import psycopg

from backend.auth_store import AuthRepository, StorageUnavailable, assert_auth_connection, open_auth_connection
from backend.committee_store import CommitteeRepository


class TopicVoteError(Exception):
    def __init__(self, code):
        self.code = code


@contextmanager
def topic_vote_transaction_on(conn):
    try:
        with conn.transaction():
            assert_auth_connection(conn)
            yield TopicVoteRepository(conn)
    except psycopg.Error as exc:
        if (exc.sqlstate == "23505" and exc.diag.schema_name == "public" and
                exc.diag.table_name == "committee_topic_votes" and
                exc.diag.constraint_name == "uq_committee_vote_submission_member"):
            raise TopicVoteError("VOTE_ALREADY_CAST") from None
        raise StorageUnavailable() from None


@contextmanager
def topic_vote_transaction():
    with closing(open_auth_connection()) as conn:
        with topic_vote_transaction_on(conn) as repository:
            yield repository


PROJECT_SELECT = """SELECT p.id,p.name,p.description,t.id,t.name
    FROM public.projects p JOIN public.teams t ON t.id=p.team_id"""
SCOPES = {
    "committee": """EXISTS(SELECT 1 FROM public.committee_assignments a JOIN public.users u ON u.id=a.advisor_id
        WHERE a.project_id=p.id AND u.id=%s AND u.role='advisor')""",
    "advisor": """EXISTS(SELECT 1 FROM public.advisor_invitations i JOIN public.users u ON u.id=i.advisor_id
        WHERE i.project_id=p.id AND i.status='accepted' AND u.id=%s AND u.role='advisor')""",
    "coordinator": """EXISTS(SELECT 1 FROM public.users u WHERE u.id=%s AND u.role='coordinator')
        AND EXISTS(SELECT 1 FROM public.project_submissions s WHERE s.project_id=p.id AND s.status='approved')""",
}


class TopicVoteRepository:
    def __init__(self, conn):
        self.conn = conn
        self.auth = AuthRepository(conn)

    def projects(self, actor, scope):
        rows = self.conn.execute(PROJECT_SELECT + " WHERE " + SCOPES[scope] + " ORDER BY p.id DESC", (actor,)).fetchall()
        return [CommitteeRepository.project_dto(row) for row in rows]

    def project(self, actor, project, scope):
        row = self.conn.execute(PROJECT_SELECT + " WHERE p.id=%s AND " + SCOPES[scope], (project, actor)).fetchone()
        if row is None:
            raise TopicVoteError("COMMITTEE_PROJECT_NOT_FOUND" if scope == "committee" else "PROJECT_NOT_FOUND")
        return CommitteeRepository.project_dto(row)

    def set_actor(self, actor):
        self.conn.execute("SELECT set_config('app.actor_user_id',%s,true)", (actor,))

    def lock_project(self, project):
        self.conn.execute("SELECT public.v1_lock_project(%s)", (project,))

    def locked_context(self, actor, project, scope):
        self.project(actor, project, scope)
        self.set_actor(actor)
        self.lock_project(project)
        return self.project(actor, project, scope)

    @staticmethod
    def submission_dto(row):
        return {"id": str(row[0]), "snapshot_name": row[1], "snapshot_description": row[2],
                "status": row[3], "submitted_at": row[4].isoformat()}

    def submissions(self, project, *, approved_only=False):
        rows = self.conn.execute("""SELECT id,snapshot_name,snapshot_description,status,submitted_at
            FROM public.project_submissions WHERE project_id=%s""" +
            (" AND status='approved'" if approved_only else "") + " ORDER BY id DESC", (project,)).fetchall()
        return [self.submission_dto(row) for row in rows]

    def decision(self, submission):
        return self.conn.execute("SELECT public.v1_topic_decision(%s)", (submission,)).fetchone()[0]

    @staticmethod
    def own_vote_dto(row):
        return {"id": str(row[0]), "submission_id": str(row[1]), "vote": row[2],
                "comment": row[3], "voted_at": row[4].isoformat()}

    def own_vote(self, assignment, submission):
        row = self.conn.execute("""SELECT id,submission_id,vote,comment,voted_at FROM public.committee_topic_votes
            WHERE committee_assignment_id=%s AND submission_id=%s""", (assignment, submission)).fetchone()
        return self.own_vote_dto(row) if row is not None else None

    def assignment(self, actor, project):
        row = self.conn.execute("SELECT id FROM public.committee_assignments WHERE project_id=%s AND advisor_id=%s",
                                (project, actor)).fetchone()
        if row is None:
            raise TopicVoteError("COMMITTEE_PROJECT_NOT_FOUND")
        return row[0]

    def committee_count(self, project):
        return self.conn.execute("SELECT count(*) FROM public.committee_assignments WHERE project_id=%s", (project,)).fetchone()[0]

    def committee_context(self, actor, project):
        context = self.locked_context(actor, project, "committee")
        assignment = self.assignment(actor, project)
        submissions = self.submissions(project)
        rounds = [{"submission": row, "own_vote": self.own_vote(assignment, row["id"]),
                   "decision": self.decision(row["id"])} for row in submissions]
        latest = rounds[0] if rounds else None
        reason = ("NO_SUBMISSION" if latest is None else
                  "SUBMISSION_NOT_APPROVED" if latest["submission"]["status"] != "approved" else
                  "COMMITTEE_INCOMPLETE" if self.committee_count(project) < 3 else
                  "ALREADY_VOTED" if latest["own_vote"] is not None else None)
        return {"project": context, "latest_submission_id": latest["submission"]["id"] if latest else None,
                "can_vote": reason is None, "blocking_reason": reason, "rounds": rounds}

    def controlled_vote(self, submission, assignment, vote, comment):
        self.conn.execute("SELECT public.v1_cast_vote(%s,%s,%s,%s)", (submission, assignment, vote, comment))

    def cast(self, actor, project, submission, vote, comment):
        self.locked_context(actor, project, "committee")
        assignment = self.assignment(actor, project)
        rounds = self.submissions(project)
        if not rounds:
            raise TopicVoteError("SUBMISSION_NOT_APPROVED")
        latest = rounds[0]
        if latest["id"] != submission:
            raise TopicVoteError("SUBMISSION_CHANGED")
        if latest["status"] != "approved":
            raise TopicVoteError("SUBMISSION_NOT_APPROVED")
        if self.committee_count(project) < 3:
            raise TopicVoteError("COMMITTEE_INCOMPLETE")
        if self.own_vote(assignment, submission) is not None:
            raise TopicVoteError("VOTE_ALREADY_CAST")
        self.controlled_vote(submission, assignment, vote, comment)
        self.conn.execute("SET CONSTRAINTS ALL IMMEDIATE")
        return self.own_vote(assignment, submission)

    def reader_context(self, context):
        project = context["id"]
        roster = self.conn.execute("""SELECT u.full_name FROM public.committee_assignments a
            JOIN public.users u ON u.id=a.advisor_id WHERE a.project_id=%s ORDER BY a.assigned_at ASC,a.id ASC""",
            (project,)).fetchall()
        rounds = []
        for submission in self.submissions(project):
            decision = self.decision(submission["id"])
            comments = []
            if decision is not None:
                # No vote/author/timestamp selected or serialized for readers.
                comments = [row[0] for row in self.conn.execute("""SELECT v.comment FROM public.committee_topic_votes v
                    JOIN public.committee_assignments a ON a.id=v.committee_assignment_id
                    WHERE a.project_id=%s AND v.submission_id=%s AND v.comment IS NOT NULL
                    ORDER BY v.comment COLLATE "C" ASC""", (project, submission["id"])).fetchall()]
            rounds.append({"submission": submission, "decision": decision, "comments": comments})
        return {"project": context, "committee": [{"full_name": row[0]} for row in roster], "rounds": rounds}

    def team_context(self, actor):
        def own():
            return self.conn.execute("""SELECT m.team_id,p.id FROM public.team_members m
                LEFT JOIN public.projects p ON p.team_id=m.team_id
                WHERE m.user_id=%s""", (actor,)).fetchone()
        row = own()
        if row is None:
            raise TopicVoteError("TEAM_NOT_FOUND")
        team = row[0]
        self.set_actor(actor)
        self.conn.execute("SELECT public.v1_lock_team(%s)", (team,))
        row = own()
        if row is None or row[0] != team:
            raise TopicVoteError("TEAM_NOT_FOUND")
        if row[1] is None:
            raise TopicVoteError("PROJECT_NOT_FOUND")
        self.lock_project(row[1])
        context = self.conn.execute(PROJECT_SELECT + " WHERE p.id=%s AND t.id=%s", (row[1], team)).fetchone()
        return self.reader_context(CommitteeRepository.project_dto(context))

    def advisor_context(self, actor, project):
        return self.reader_context(self.locked_context(actor, project, "advisor"))

    def coordinator_context(self, actor, project):
        context = self.locked_context(actor, project, "coordinator")
        rounds = []
        for submission in self.submissions(project, approved_only=True):
            rows = self.conn.execute("""SELECT v.id,a.advisor_id,u.full_name,v.vote,v.comment,v.voted_at
                FROM public.committee_topic_votes v JOIN public.committee_assignments a ON a.id=v.committee_assignment_id
                JOIN public.users u ON u.id=a.advisor_id WHERE a.project_id=%s AND v.submission_id=%s
                ORDER BY v.voted_at ASC,v.id ASC""", (project, submission["id"])).fetchall()
            votes = [{"id": str(row[0]), "advisor": {"id": str(row[1]), "full_name": row[2]},
                      "vote": row[3], "comment": row[4], "voted_at": row[5].isoformat()} for row in rows]
            rounds.append({"submission": submission, "decision": self.decision(submission["id"]), "votes": votes})
        return {"project": context, "rounds": rounds}
