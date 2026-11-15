"""Evaluation operations and approved role-specific projections on V1 SQL."""

from contextlib import closing, contextmanager

import psycopg

from backend.auth_store import StorageUnavailable, assert_auth_connection, open_auth_connection
from backend.committee_store import CommitteeRepository
from backend.topic_vote_store import PROJECT_SELECT, TopicVoteRepository


class EvaluationError(Exception):
    def __init__(self, code):
        self.code = code


@contextmanager
def evaluation_transaction_on(conn):
    try:
        with conn.transaction():
            assert_auth_connection(conn)
            yield EvaluationRepository(conn)
    except psycopg.Error as exc:
        if (exc.sqlstate == "23505" and exc.diag.schema_name == "public" and
                exc.diag.table_name == "committee_evaluations" and
                exc.diag.constraint_name == "committee_evaluations_committee_assignment_id_key"):
            raise EvaluationError("EVALUATION_ALREADY_RECORDED") from None
        raise StorageUnavailable() from None


@contextmanager
def evaluation_transaction():
    with closing(open_auth_connection()) as conn:
        with evaluation_transaction_on(conn) as repository:
            yield repository


class EvaluationRepository:
    def __init__(self, conn):
        self.conn = conn
        self.scope = TopicVoteRepository(conn)
        self.auth = self.scope.auth

    @staticmethod
    def own_dto(row):
        return {"id": str(row[0]), "score": row[1], "comment": row[2], "created_at": row[3].isoformat()}

    def own(self, assignment):
        row = self.conn.execute("SELECT id,score,comment,created_at FROM public.committee_evaluations "
                                "WHERE committee_assignment_id=%s", (assignment,)).fetchone()
        return self.own_dto(row) if row is not None else None

    def summary(self, project):
        # HAVING prevents any partial scores/counts from becoming a DTO.
        row = self.conn.execute("""SELECT sum(e.score)::text,round(avg(e.score))::integer
            FROM public.committee_assignments a LEFT JOIN public.committee_evaluations e
            ON e.committee_assignment_id=a.id WHERE a.project_id=%s
            HAVING count(*)>0 AND count(e.id)=count(*)""", (project,)).fetchone()
        return {"total_score": row[0], "average_score": row[1]} if row is not None else None

    def reason(self, project, own):
        if own is not None:
            return "ALREADY_EVALUATED"
        latest = self.conn.execute("SELECT id FROM public.project_submissions WHERE project_id=%s ORDER BY id DESC LIMIT 1",
                                   (project,)).fetchone()
        if latest is None:
            return "NO_SUBMISSION"
        if self.scope.decision(latest[0]) != "approved":
            return "TOPIC_NOT_APPROVED"
        if not self.conn.execute("SELECT EXISTS(SELECT 1 FROM public.milestones WHERE project_id=%s AND status='completed')",
                                 (project,)).fetchone()[0]:
            return "COMPLETED_MILESTONE_REQUIRED"
        return None

    def committee_context(self, actor, project):
        context = self.scope.locked_context(actor, project, "committee")
        own = self.own(self.scope.assignment(actor, project))
        reason = self.reason(project, own)
        return {"project": context, "can_evaluate": reason is None, "blocking_reason": reason,
                "own_evaluation": own, "summary": self.summary(project)}

    def controlled_record(self, assignment, score, comment):
        self.conn.execute("SELECT public.v1_record_evaluation(%s,%s,%s)", (assignment, score, comment))

    def record(self, actor, project, score, comment):
        self.scope.locked_context(actor, project, "committee")
        assignment = self.scope.assignment(actor, project)
        reason = self.reason(project, self.own(assignment))
        if reason is not None:
            raise EvaluationError({"ALREADY_EVALUATED": "EVALUATION_ALREADY_RECORDED",
                                   "NO_SUBMISSION": "TOPIC_NOT_APPROVED"}.get(reason, reason))
        self.controlled_record(assignment, score, comment)
        self.conn.execute("SET CONSTRAINTS ALL IMMEDIATE")
        return self.own(assignment)

    def team_context(self, actor):
        def own_team():
            return self.conn.execute("SELECT m.team_id,p.id FROM public.team_members m LEFT JOIN public.projects p "
                                     "ON p.team_id=m.team_id WHERE m.user_id=%s", (actor,)).fetchone()
        row = own_team()
        if row is None:
            raise EvaluationError("TEAM_NOT_FOUND")
        team = row[0]
        self.scope.set_actor(actor)
        self.conn.execute("SELECT public.v1_lock_team(%s)", (team,))
        row = own_team()
        if row is None or row[0] != team:
            raise EvaluationError("TEAM_NOT_FOUND")
        if row[1] is None:
            raise EvaluationError("PROJECT_NOT_FOUND")
        self.scope.lock_project(row[1])
        context = self.conn.execute(PROJECT_SELECT + " WHERE p.id=%s AND t.id=%s", (row[1], team)).fetchone()
        return {"project": CommitteeRepository.project_dto(context), "summary": self.summary(row[1])}

    def advisor_context(self, actor, project):
        context = self.scope.locked_context(actor, project, "advisor")
        return {"project": context, "summary": self.summary(project)}

    def coordinator_context(self, actor, project):
        context = self.scope.locked_context(actor, project, "coordinator")
        summary = self.summary(project)
        evaluations = []
        if summary is not None:
            rows = self.conn.execute("""SELECT e.id,a.advisor_id,u.full_name,e.score,e.comment,e.created_at
                FROM public.committee_evaluations e JOIN public.committee_assignments a ON a.id=e.committee_assignment_id
                JOIN public.users u ON u.id=a.advisor_id WHERE a.project_id=%s ORDER BY e.created_at ASC,e.id ASC""", (project,)).fetchall()
            evaluations = [{"id": str(row[0]), "advisor": {"id": str(row[1]), "full_name": row[2]},
                            "score": row[3], "comment": row[4], "created_at": row[5].isoformat()} for row in rows]
        return {"project": context, "summary": summary, "evaluations": evaluations}
