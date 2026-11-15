"""Coordinator-scoped roster management through existing V1 SQL functions."""

from contextlib import closing, contextmanager

import psycopg

from backend.auth_store import AuthRepository, StorageUnavailable, assert_auth_connection, open_auth_connection


class CommitteeError(Exception):
    def __init__(self, code):
        self.code = code


@contextmanager
def committee_transaction_on(conn):
    try:
        with conn.transaction():
            assert_auth_connection(conn)
            yield CommitteeRepository(conn)
    except psycopg.Error as exc:
        if (exc.sqlstate == "23505" and exc.diag.schema_name == "public" and
                exc.diag.table_name == "committee_assignments" and
                exc.diag.constraint_name == "uq_committee_project_advisor"):
            raise CommitteeError("COMMITTEE_ADVISOR_ALREADY_ASSIGNED") from None
        raise StorageUnavailable() from None


@contextmanager
def committee_transaction():
    with closing(open_auth_connection()) as conn:
        with committee_transaction_on(conn) as repository:
            yield repository


class CommitteeRepository:
    def __init__(self, conn):
        self.conn = conn
        self.auth = AuthRepository(conn)

    @staticmethod
    def project_dto(row):
        return {"id": str(row[0]), "name": row[1], "description": row[2],
                "team": {"id": str(row[3]), "name": row[4]}}

    def projects(self, actor):
        rows = self.conn.execute("""SELECT p.id,p.name,p.description,t.id,t.name
            FROM public.projects p JOIN public.teams t ON t.id=p.team_id
            WHERE EXISTS(SELECT 1 FROM public.users WHERE id=%s AND role='coordinator')
              AND EXISTS(SELECT 1 FROM public.project_submissions s WHERE s.project_id=p.id AND s.status='approved')
            ORDER BY p.id DESC""", (actor,)).fetchall()
        return [self.project_dto(row) for row in rows]

    def project(self, actor, project):
        row = self.conn.execute("""SELECT p.id,p.name,p.description,t.id,t.name
            FROM public.projects p JOIN public.teams t ON t.id=p.team_id
            WHERE p.id=%s AND EXISTS(SELECT 1 FROM public.users WHERE id=%s AND role='coordinator')
              AND EXISTS(SELECT 1 FROM public.project_submissions s WHERE s.project_id=p.id AND s.status='approved')""",
            (project, actor)).fetchone()
        if row is None:
            raise CommitteeError("PROJECT_NOT_FOUND")
        return self.project_dto(row)

    def locked(self, project):
        return self.conn.execute("""SELECT EXISTS(SELECT 1 FROM public.committee_topic_votes v
            JOIN public.committee_assignments a ON a.id=v.committee_assignment_id
            WHERE a.project_id=%s)""", (project,)).fetchone()[0]

    @staticmethod
    def assignment_dto(row):
        return {"id": str(row[0]), "advisor": {"id": str(row[1]), "full_name": row[2]},
                "assigned_at": row[3].isoformat()}

    def assignments(self, project):
        rows = self.conn.execute("""SELECT a.id,a.advisor_id,u.full_name,a.assigned_at
            FROM public.committee_assignments a JOIN public.users u ON u.id=a.advisor_id
            WHERE a.project_id=%s ORDER BY a.assigned_at ASC,a.id ASC""", (project,)).fetchall()
        return [self.assignment_dto(row) for row in rows]

    def detail(self, actor, project):
        context = self.project(actor, project)
        return {"project": context, "roster_locked": self.locked(project),
                "assignments": self.assignments(project)}

    def candidates(self, actor, project):
        self.project(actor, project)
        rows = self.conn.execute("""SELECT u.id,u.full_name FROM public.users u WHERE u.role='advisor'
            AND u.id IS DISTINCT FROM public.v1_advisor_for_project(%s)
            AND NOT EXISTS(SELECT 1 FROM public.committee_assignments a WHERE a.project_id=%s AND a.advisor_id=u.id)
            ORDER BY u.full_name ASC,u.id ASC""", (project, project)).fetchall()
        return [{"id": str(row[0]), "full_name": row[1]} for row in rows]

    def target(self, project, assignment):
        row = self.conn.execute("SELECT id FROM public.committee_assignments WHERE project_id=%s AND id=%s",
                                (project, assignment)).fetchone()
        if row is None:
            raise CommitteeError("COMMITTEE_ASSIGNMENT_NOT_FOUND")

    def validate_advisor(self, project, advisor, assignment):
        if self.conn.execute("SELECT id FROM public.users WHERE id=%s AND role='advisor'", (advisor,)).fetchone() is None:
            raise CommitteeError("COMMITTEE_ADVISOR_NOT_FOUND")
        if self.conn.execute("SELECT public.v1_advisor_for_project(%s)", (project,)).fetchone()[0] == int(advisor):
            raise CommitteeError("PROJECT_ADVISOR_INELIGIBLE")
        if self.conn.execute("""SELECT id FROM public.committee_assignments
            WHERE project_id=%s AND advisor_id=%s AND id IS DISTINCT FROM %s::bigint""",
            (project, advisor, assignment)).fetchone() is not None:
            raise CommitteeError("COMMITTEE_ADVISOR_ALREADY_ASSIGNED")

    def controlled_write(self, project, advisor, assignment, operation):
        if operation == "add":
            return self.conn.execute("SELECT public.v1_appoint_committee(%s,%s)", (project, advisor)).fetchone()[0]
        if operation == "replace":
            self.conn.execute("SELECT public.v1_replace_committee(%s,%s)", (assignment, advisor))
            return int(assignment)
        if operation == "remove":
            self.conn.execute("SELECT public.v1_remove_committee(%s)", (assignment,))
            return None
        raise ValueError("Unknown committee operation")

    def mutate(self, actor, project, *, advisor=None, assignment=None, operation):
        self.project(actor, project)
        self.conn.execute("SELECT set_config('app.actor_user_id',%s,true)", (actor,))
        self.conn.execute("SELECT public.v1_lock_project(%s)", (project,))
        self.project(actor, project)  # Fresh authorization/phase after lock wait.
        if assignment is not None:
            self.target(project, assignment)
        if self.locked(project):
            raise CommitteeError("COMMITTEE_ROSTER_LOCKED")
        if operation != "remove":
            self.validate_advisor(project, advisor, assignment)
        identifier = self.controlled_write(project, advisor, assignment, operation)
        self.conn.execute("SET CONSTRAINTS ALL IMMEDIATE")
        if operation == "remove":
            return None
        return next(row for row in self.assignments(project) if row["id"] == str(identifier))
