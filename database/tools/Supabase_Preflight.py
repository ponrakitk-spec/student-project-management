"""Preliminary READ ONLY checks; never install, seed or switch roles.

Run only after selecting an approved disposable project. PASS establishes
identity, structural counts and selected ACL boundaries, not full V1 parity
or successful application writes on Supabase.
"""

from contextlib import closing
import json

from backend.auth_store import StorageUnavailable, assert_auth_connection, open_auth_connection, runtime_target


TABLES = (
    "users", "teams", "team_members", "projects", "advisor_invitations",
    "project_submissions", "project_submission_files", "committee_assignments",
    "committee_topic_votes", "committee_evaluations", "milestones", "tasks",
    "task_assignees", "task_assignment_history",
)


def inspect(conn):
    if conn.execute("SHOW transaction_read_only").fetchone() != ("on",):
        raise StorageUnavailable()
    assert_auth_connection(conn)
    with conn.cursor() as cur:
        cur.execute("""SELECT count(*), sum((pg_get_userbyid(c.relowner) = 'project_owner')::int)
            FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace
            WHERE n.nspname='public' AND c.relkind='r' AND c.relname=ANY(%s)""", (list(TABLES),))
        if cur.fetchone() != (14, 14):
            raise StorageUnavailable()
        cur.execute("""SELECT count(*) FROM pg_attribute a JOIN pg_class c ON c.oid=a.attrelid
            JOIN pg_namespace n ON n.oid=c.relnamespace WHERE n.nspname='public'
            AND c.relname=ANY(%s) AND a.attnum>0 AND NOT a.attisdropped""", (list(TABLES),))
        if cur.fetchone() != (86,):
            raise StorageUnavailable()
        cur.execute("""SELECT count(*) FROM pg_constraint x JOIN pg_class c ON c.oid=x.conrelid
            JOIN pg_namespace n ON n.oid=c.relnamespace WHERE n.nspname='public'
            AND c.relname=ANY(%s) AND x.contype='f'""", (list(TABLES),))
        if cur.fetchone() != (28,):
            raise StorageUnavailable()
        cur.execute("""SELECT count(*) FROM pg_proc p JOIN pg_namespace n ON n.oid=p.pronamespace
            WHERE n.nspname='public' AND left(p.proname,3)='v1_'
            AND pg_get_userbyid(p.proowner)='project_owner'""")
        if cur.fetchone() != (52,):
            raise StorageUnavailable()
        cur.execute("""SELECT count(*) FROM pg_trigger t JOIN pg_class c ON c.oid=t.tgrelid
            JOIN pg_namespace n ON n.oid=c.relnamespace WHERE n.nspname='public'
            AND c.relname=ANY(%s) AND NOT t.tgisinternal AND t.tgenabled='O'""", (list(TABLES),))
        if cur.fetchone() != (24,):
            raise StorageUnavailable()
        cur.execute("""SELECT count(*) FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace
            WHERE n.nspname='spms_auth' AND c.relkind='r'
            AND c.relname IN ('credentials','sessions') AND pg_get_userbyid(c.relowner)='project_owner'""")
        if cur.fetchone() != (2,):
            raise StorageUnavailable()
        cur.execute("""SELECT has_table_privilege(current_user,'public.projects','DELETE'),
            has_any_column_privilege(current_user,'spms_auth.credentials','SELECT'),
            has_any_column_privilege(current_user,'spms_auth.credentials','INSERT'),
            has_any_column_privilege(current_user,'spms_auth.credentials','UPDATE'),
            has_table_privilege(current_user,'spms_auth.credentials','DELETE'),
            has_function_privilege(current_user,'public.v1_refresh_milestone(bigint)','EXECUTE'),
            has_function_privilege(current_user,'public.v1_lock_team(bigint)','EXECUTE'),
            has_function_privilege(current_user,'spms_auth.register_student(text,text,text)','EXECUTE'),
            has_function_privilege(current_user,'spms_auth.lookup_credentials(text)','EXECUTE')""")
        if cur.fetchone() != (False, False, False, False, False, False, True, True, True):
            raise StorageUnavailable()
        # FastAPI is the read-authorization boundary. No Supabase API role may
        # reach the application tables/functions by a separate API path.
        cur.execute("""SELECT EXISTS (
            SELECT 1 FROM pg_roles r CROSS JOIN pg_class c
            JOIN pg_namespace n ON n.oid=c.relnamespace
            WHERE r.rolname IN ('anon','authenticated','service_role')
            AND ((n.nspname='public' AND c.relname=ANY(%s)) OR n.nspname='spms_auth')
            AND c.relkind='r' AND (
                has_any_column_privilege(r.oid,c.oid,'SELECT') OR
                has_any_column_privilege(r.oid,c.oid,'INSERT') OR
                has_any_column_privilege(r.oid,c.oid,'UPDATE') OR
                has_table_privilege(r.oid,c.oid,'DELETE,TRUNCATE,REFERENCES,TRIGGER'))
            ) OR EXISTS (
            SELECT 1 FROM pg_roles r CROSS JOIN pg_proc p JOIN pg_namespace n ON n.oid=p.pronamespace
            WHERE r.rolname IN ('anon','authenticated','service_role')
            AND ((n.nspname='public' AND left(p.proname,3)='v1_') OR n.nspname='spms_auth')
            AND has_function_privilege(r.oid,p.oid,'EXECUTE'))""", (list(TABLES),))
        if cur.fetchone() != (False,):
            raise StorageUnavailable()
        cur.execute("SHOW server_version")
        version = cur.fetchone()[0]
    return {"status": "PASS_PRELIMINARY_READONLY", "database": "postgres", "role": "project_app",
            "server_version": version, "v1_tables": 14, "auth_schema": "spms_auth",
            "writes_tested": False, "full_v1_parity_verified": False}


def main():
    try:
        if runtime_target().mode != "supabase_test":
            raise StorageUnavailable()
        with closing(open_auth_connection(readonly=True)) as conn:
            try:
                result = inspect(conn)
            finally:
                conn.rollback()
        print(json.dumps(result))
        return 0
    except Exception:
        # Driver errors may contain connection URLs or authentication details.
        print(json.dumps({"status": "FAIL", "reason": "Supabase configuration, connection or preliminary checks failed; no changes applied"}))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
