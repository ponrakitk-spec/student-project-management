"""Team-scoped V1 Tasks and assignments; controlled functions own all writes."""
from contextlib import closing, contextmanager
import re
import psycopg
from backend.auth_store import AuthRepository, StorageUnavailable, assert_auth_connection, open_auth_connection
from backend.milestone_store import MilestoneRepository


class TaskError(Exception):
    def __init__(self, code):
        self.code = code


@contextmanager
def task_transaction_on(conn):
    try:
        with conn.transaction():
            conn.execute("SET LOCAL statement_timeout = '15s'")
            conn.execute("SET LOCAL lock_timeout = '3s'")
            assert_auth_connection(conn)
            yield TaskRepository(conn)
    except psycopg.Error as exc:
        code = None
        if exc.sqlstate == "23505":
            code = {"uq_tasks_milestone_name_ci": "TASK_NAME_CONFLICT", "uq_task_assignees_task_member": "ASSIGNEE_ALREADY_ASSIGNED"}.get(exc.diag.constraint_name)
        elif exc.sqlstate == "P0001":
            message = exc.diag.message_primary or ""
            code = {
                "Tasks locked after first committee evaluation": "TASK_LOCKED",
                "Reopen completed Task before deleting": "TASK_COMPLETED",
                "Reopen completed Task before editing metadata": "TASK_COMPLETED",
                "Invalid Task due_date": "TASK_DUE_DATE_INVALID",
                "Task completion requires >=1 assignee": "TASK_ASSIGNEE_REQUIRED",
                "In-progress Task requires >=1 assignee": "TASK_ASSIGNEE_REQUIRED",
                "Only leader may reopen completed Task to in_progress": "TASK_STATUS_CONFLICT",
                "Task assignments locked": "TASK_LOCKED", "Unassignment locked": "TASK_LOCKED",
                "Assignee must be current member of same team": "ASSIGNEE_NOT_CURRENT_MEMBER",
            }.get(message)
            if re.fullmatch(r"In-progress Task [0-9]+ must have an assignee at COMMIT", message):
                code = "TASK_ASSIGNEE_REQUIRED"
        if code:
            raise TaskError(code) from None
        raise StorageUnavailable() from None


@contextmanager
def task_transaction():
    with closing(open_auth_connection()) as conn:
        with task_transaction_on(conn) as store:
            yield store


class TaskRepository:
    COLUMNS = "t.id,t.milestone_id,t.name,t.description,t.due_date,t.status,t.created_at,t.updated_at,t.created_by,t.updated_by,t.completed_at"
    SCOPE = """ FROM public.tasks t JOIN public.milestones m ON m.id=t.milestone_id
        JOIN public.projects p ON p.id=m.project_id JOIN public.team_members own ON own.team_id=p.team_id
        WHERE t.id=%s AND own.user_id=%s"""

    def __init__(self, conn):
        self.conn = conn
        self.auth = AuthRepository(conn)
        self.parents = MilestoneRepository(conn)

    @staticmethod
    def dto(row):
        return dict(zip(("id", "milestone_id", "name", "description", "due_date", "status", "created_at", "updated_at", "created_by", "updated_by", "completed_at"),
                        (str(row[0]), str(row[1]), *row[2:8], str(row[8]), str(row[9]) if row[9] is not None else None, row[10])))

    def context(self, actor, task):
        row = self.conn.execute("SELECT own.team_id,own.role,p.id,m.id,t.status" + self.SCOPE, (task, actor)).fetchone()
        if row is None:
            raise TaskError("TASK_NOT_FOUND")
        return row

    def detail(self, actor, task):
        row = self.conn.execute("SELECT " + self.COLUMNS + self.SCOPE, (task, actor)).fetchone()
        if row is None:
            raise TaskError("TASK_NOT_FOUND")
        return self.dto(row)

    def listing(self, actor, milestone):
        parent = self.parents.detail(actor, milestone)
        _, role, project = self.parents.context(actor)
        rows = self.conn.execute(f"""SELECT {self.COLUMNS} FROM public.tasks t
            JOIN public.milestones m ON m.id=t.milestone_id JOIN public.projects p ON p.id=m.project_id
            JOIN public.team_members own ON own.team_id=p.team_id
            WHERE m.id=%s AND own.user_id=%s ORDER BY t.due_date ASC NULLS LAST,t.id""", (milestone, actor)).fetchall()
        return {"milestone": parent, "can_manage": role == "leader" and not self.parents.locked(project), "tasks": [self.dto(r) for r in rows]}

    def write_context(self, actor, task, leader=True):
        old = self.context(actor, task)
        team, _, project, milestone, _ = old
        self.conn.execute("SELECT set_config('app.actor_user_id',%s,true)", (actor,))
        self.conn.execute("SELECT public.v1_lock_team(%s)", (team,))
        self.conn.execute("SELECT public.v1_lock_project(%s)", (project,))
        current = self.context(actor, task)
        if (current[0], current[2], current[3]) != (team, project, milestone):
            raise TaskError("TASK_NOT_FOUND")
        if leader and current[1] != "leader":
            raise TaskError("TASK_ACTION_FORBIDDEN")
        if self.parents.locked(project):
            raise TaskError("TASK_LOCKED")
        return current

    def create(self, actor, milestone, name, description, due_date):
        self.parents.detail(actor, milestone)
        self.parents.authorize_write(actor, milestone)
        identifier = self.conn.execute("SELECT public.v1_create_task(%s,%s,%s,%s)", (milestone, name, description, due_date)).fetchone()[0]
        self.conn.execute("SET CONSTRAINTS ALL IMMEDIATE")
        return self.detail(actor, identifier)

    def update(self, actor, task, changes):
        self.write_context(actor, task)
        row = {**self.detail(actor, task), **changes}
        self.conn.execute("SELECT public.v1_update_task_metadata(%s,%s,%s,%s)", (task, row["name"], row["description"], row["due_date"]))
        self.conn.execute("SET CONSTRAINTS ALL IMMEDIATE")
        return self.detail(actor, task)

    def status(self, actor, task, status):
        context = self.write_context(actor, task, leader=False)
        if context[4] == "completed" and status != "completed":
            if status != "in_progress":
                raise TaskError("TASK_STATUS_CONFLICT")
            if context[1] != "leader":
                raise TaskError("TASK_ACTION_FORBIDDEN")
        self.conn.execute("SELECT public.v1_set_task_status(%s,%s)", (task, status))
        self.conn.execute("SET CONSTRAINTS ALL IMMEDIATE")
        return self.detail(actor, task)

    def delete(self, actor, task):
        self.write_context(actor, task)
        self.conn.execute("SELECT public.v1_delete_task(%s)", (task,))
        self.conn.execute("SET CONSTRAINTS ALL IMMEDIATE")

    def assignees(self, actor, task):
        self.context(actor, task)
        rows = self.conn.execute("""SELECT a.id,a.team_member_id,u.id,u.full_name,a.assigned_at
            FROM public.task_assignees a JOIN public.team_members tm ON tm.id=a.team_member_id
            JOIN public.users u ON u.id=tm.user_id JOIN public.tasks t ON t.id=a.task_id
            JOIN public.milestones m ON m.id=t.milestone_id JOIN public.projects p ON p.id=m.project_id
            JOIN public.team_members own ON own.team_id=p.team_id
            WHERE a.task_id=%s AND own.user_id=%s ORDER BY a.assigned_at,a.id""", (task, actor)).fetchall()
        return [{"id": str(r[0]), "team_member_id": str(r[1]), "user": {"id": str(r[2]), "full_name": r[3]}, "assigned_at": r[4]} for r in rows]

    def assign(self, actor, task, member):
        team, _, _, _, status = self.write_context(actor, task)
        if status == "completed":
            raise TaskError("TASK_LOCKED")
        if not self.conn.execute("SELECT EXISTS(SELECT 1 FROM public.team_members WHERE id=%s AND team_id=%s)", (member, team)).fetchone()[0]:
            raise TaskError("ASSIGNEE_NOT_CURRENT_MEMBER")
        identifier = self.conn.execute("SELECT public.v1_assign_task(%s,%s)", (task, member)).fetchone()[0]
        self.conn.execute("SET CONSTRAINTS ALL IMMEDIATE")
        return next(r for r in self.assignees(actor, task) if r["id"] == str(identifier))

    def unassign(self, actor, task, member):
        context = self.write_context(actor, task)
        if context[4] == "completed":
            raise TaskError("TASK_LOCKED")
        if not self.conn.execute("SELECT EXISTS(SELECT 1 FROM public.task_assignees WHERE task_id=%s AND team_member_id=%s)", (task, member)).fetchone()[0]:
            raise TaskError("ASSIGNEE_NOT_FOUND")
        self.conn.execute("SELECT public.v1_unassign_task(%s,%s)", (task, member))
        self.conn.execute("SET CONSTRAINTS ALL IMMEDIATE")

    def history(self, actor, task):
        self.context(actor, task)
        rows = self.conn.execute("""SELECT h.id,u.id,u.full_name,h.assigned_at,h.unassigned_at
            FROM public.task_assignment_history h JOIN public.users u ON u.id=h.user_id
            JOIN public.tasks t ON t.id=h.task_id JOIN public.milestones m ON m.id=t.milestone_id
            JOIN public.projects p ON p.id=m.project_id JOIN public.team_members own ON own.team_id=p.team_id
            WHERE h.task_id=%s AND own.user_id=%s ORDER BY h.unassigned_at DESC,h.id DESC""", (task, actor)).fetchall()
        return [{"id": str(r[0]), "user": {"id": str(r[1]), "full_name": r[2]}, "assigned_at": r[3], "unassigned_at": r[4]} for r in rows]
