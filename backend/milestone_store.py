"""Team-scoped Milestones through existing V1 controlled operations."""
from contextlib import closing, contextmanager
import psycopg
from backend.auth_store import AuthRepository, StorageUnavailable, assert_auth_connection, open_auth_connection


class MilestoneError(Exception):
    def __init__(self, code):
        self.code = code


@contextmanager
def milestone_transaction_on(conn):
    try:
        with conn.transaction():
            conn.execute("SET LOCAL statement_timeout = '15s'")
            conn.execute("SET LOCAL lock_timeout = '3s'")
            assert_auth_connection(conn)
            yield MilestoneRepository(conn)
    except psycopg.Error as exc:
        code = None
        if exc.sqlstate == "23505" and exc.diag.constraint_name == "uq_milestones_project_name_ci":
            code = "MILESTONE_NAME_CONFLICT"
        elif exc.sqlstate in ("23001", "23503") and exc.diag.constraint_name == "tasks_milestone_id_fkey":
            code = "MILESTONE_HAS_TASKS"
        elif exc.sqlstate == "P0001":
            code = {
                "Milestones locked after first committee evaluation": "MILESTONE_LOCKED",
                "Milestone due_date is before current Bangkok date": "MILESTONE_DUE_DATE_PAST",
                "D-01: adjust task due dates before shortening milestone due date": "TASK_DUE_DATE_CONFLICT",
            }.get(exc.diag.message_primary)
        if code:
            raise MilestoneError(code) from None
        raise StorageUnavailable() from None


@contextmanager
def milestone_transaction():
    with closing(open_auth_connection()) as conn:
        with milestone_transaction_on(conn) as store:
            yield store


class MilestoneRepository:
    COLUMNS = "m.id,m.project_id,m.name,m.description,m.due_date,m.status,m.created_at,m.updated_at,m.created_by,m.updated_by,m.completed_at"

    def __init__(self, conn):
        self.conn = conn
        self.auth = AuthRepository(conn)

    @staticmethod
    def dto(row):
        return dict(zip(("id", "project_id", "name", "description", "due_date", "status", "created_at", "updated_at", "created_by", "updated_by", "completed_at"),
                        (str(row[0]), str(row[1]), *row[2:8], str(row[8]), str(row[9]) if row[9] is not None else None, row[10])))

    def context(self, actor):
        row = self.conn.execute("""SELECT t.team_id,t.role,p.id FROM public.team_members t
            LEFT JOIN public.projects p ON p.team_id=t.team_id WHERE t.user_id=%s""", (actor,)).fetchone()
        if row is None:
            raise MilestoneError("TEAM_NOT_FOUND")
        if row[2] is None:
            raise MilestoneError("PROJECT_NOT_FOUND")
        return row

    def locked(self, project):
        return self.conn.execute("""SELECT EXISTS(SELECT 1 FROM public.committee_evaluations e
            JOIN public.committee_assignments a ON a.id=e.committee_assignment_id WHERE a.project_id=%s)""", (project,)).fetchone()[0]

    def detail(self, actor, identifier):
        row = self.conn.execute(f"""SELECT {self.COLUMNS} FROM public.milestones m
            JOIN public.projects p ON p.id=m.project_id JOIN public.team_members t ON t.team_id=p.team_id
            WHERE m.id=%s AND t.user_id=%s""", (identifier, actor)).fetchone()
        if row is None:
            raise MilestoneError("MILESTONE_NOT_FOUND")
        return self.dto(row)

    def listing(self, actor):
        team, role, project = self.context(actor)
        rows = self.conn.execute(f"""SELECT {self.COLUMNS} FROM public.milestones m
            JOIN public.projects p ON p.id=m.project_id JOIN public.team_members t ON t.team_id=p.team_id
            WHERE m.project_id=%s AND t.user_id=%s ORDER BY m.due_date,m.id""", (project, actor)).fetchall()
        return {"project_id": str(project), "can_manage": role == "leader" and not self.locked(project), "milestones": [self.dto(row) for row in rows]}

    def authorize_write(self, actor, identifier=None):
        if identifier is not None:
            self.detail(actor, identifier)  # Hide cross-project existence.
        context = self.context(actor)
        team, _, project = context
        self.conn.execute("SELECT set_config('app.actor_user_id',%s,true)", (actor,))
        self.conn.execute("SELECT public.v1_lock_team(%s)", (team,))
        self.conn.execute("SELECT public.v1_lock_project(%s)", (project,))
        current = self.context(actor)
        if current[0] != team or current[2] != project:
            raise MilestoneError("MILESTONE_NOT_FOUND" if identifier else "PROJECT_NOT_FOUND")
        if identifier is not None:
            self.detail(actor, identifier)
        if current[1] != "leader":
            raise MilestoneError("MILESTONE_ACTION_FORBIDDEN")
        if self.locked(project):
            raise MilestoneError("MILESTONE_LOCKED")
        return project

    def create(self, actor, name, description, due_date):
        project = self.authorize_write(actor)
        identifier = self.conn.execute("SELECT public.v1_create_milestone(%s,%s,%s,%s)", (project, name, description, due_date)).fetchone()[0]
        self.conn.execute("SET CONSTRAINTS ALL IMMEDIATE")
        return self.detail(actor, identifier)

    def update(self, actor, identifier, changes):
        self.authorize_write(actor, identifier)
        current = self.detail(actor, identifier)
        values = {**current, **changes}
        self.conn.execute("SELECT public.v1_update_milestone(%s,%s,%s,%s)", (identifier, values["name"], values["description"], values["due_date"]))
        self.conn.execute("SET CONSTRAINTS ALL IMMEDIATE")
        return self.detail(actor, identifier)

    def delete(self, actor, identifier):
        self.authorize_write(actor, identifier)
        self.conn.execute("SELECT public.v1_delete_milestone(%s)", (identifier,))
        self.conn.execute("SET CONSTRAINTS ALL IMMEDIATE")
