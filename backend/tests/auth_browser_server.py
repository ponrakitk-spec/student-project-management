"""Browser fixture: effective app requests, every fixture write rolled back.

Port 8001 is isolated from the normal Backend on 8000. Never use this fixture
as the normal application server: successful responses do not persist records.
Default mode connects directly as app. Explicit invitation-fixture mode seeds
staff as non-superuser owner before switching to app for all HTTP requests.
The runner verifies metadata/row counts and that this connection has closed.
"""

import argparse
from contextlib import contextmanager
import json
import os
import re
from threading import RLock

from dotenv import dotenv_values
import psycopg
from psycopg.pq import TransactionStatus
import uvicorn

from backend.auth_api import get_auth_uow
from backend.auth_store import StorageUnavailable, assert_auth_connection, open_auth_connection, transaction_on, runtime_target
from backend.auth_security import hash_password
from backend.main import create_app
from backend.team_api import get_team_uow
from backend.team_store import team_transaction_on
from backend.project_api import get_project_uow
from backend.project_store import project_transaction_on
from backend.invitation_api import get_invitation_uow
from backend.invitation_store import invitation_transaction_on
from backend.committee_api import get_committee_uow
from backend.committee_store import committee_transaction_on
from backend.topic_vote_api import get_topic_vote_uow
from backend.topic_vote_store import topic_vote_transaction_on
from backend.evaluation_api import get_evaluation_uow
from backend.evaluation_store import evaluation_transaction_on
from backend.submission_api import get_submission_uow
from backend.submission_store import submission_transaction_on
from backend.milestone_api import get_milestone_uow
from backend.milestone_store import milestone_transaction_on
from backend.task_api import get_task_uow
from backend.task_store import task_transaction_on
from database.tests.Auth_Regression import BASE, OWNER, TEST_DB, snapshot, switch
from database.tools.Test_Database import connect_test_database

APPLICATION_NAME = "spms_auth_browser_rollback"


def seed_invitation_accounts(conn, tag):
    # Explicit browser-fixture mode only, never the normal API. The connection
    # remains in one outer rollback transaction; role changes happen BEFORE
    # serving requests. No test-only HTTP provisioning endpoint is exposed.
    if not re.fullmatch(r"[a-f0-9]{32}", tag or ""):
        raise RuntimeError("A unique browser fixture tag is required")
    with conn.cursor() as cur:
        switch(cur, OWNER)
        cur.execute("SELECT current_user,r.rolsuper FROM pg_roles r WHERE r.rolname=current_user")
        if cur.fetchone() != (OWNER, False):
            raise RuntimeError("Non-superuser fixture owner required")
        encoded = hash_password("AdvisorBrowserFixtureA1")
        accounts = {}
        for label,role in (("a","advisor"),("b","advisor"),("c","advisor"),("d","advisor"),("e","advisor"),("coordinator","coordinator")):
            cur.execute("INSERT INTO public.users(full_name,email,role) VALUES (%s,%s,%s) RETURNING id",
                ("อาจารย์ทดสอบ "+label.upper()+" "+tag[:6] if role=='advisor' else 'ผู้ประสานงานทดสอบ',
                 f"advisor-browser-{tag}-{label}@example.test",role))
            user = cur.fetchone()[0]
            accounts[label] = str(user)
            cur.execute("INSERT INTO auth.credentials(user_id,password_hash) VALUES (%s,%s)", (user,encoded))
        switch(cur,"project_app")
    return accounts


def seed_committee_projects(conn, tag, accounts):
    # DB-only phase graph in the explicit outer rollback fixture. No upload,
    # review or seed HTTP endpoint is added to the normal app or peer code.
    leaders = {}
    with conn.cursor() as cur:
        switch(cur, OWNER)
        for label in ("eligible", "hidden", "locked"):
            cur.execute("INSERT INTO public.users(full_name,email,role) VALUES (%s,%s,'student') RETURNING id",
                        ("Committee browser leader", f"committee-browser-{tag}-{label}@example.test"))
            leaders[label] = str(cur.fetchone()[0])
        switch(cur, "project_app")
    for label, leader in leaders.items():
        with team_transaction_on(conn) as store:
            store.create(f"ทีมกรรมการ {tag[:6]} {label}", None, leader)
        with project_transaction_on(conn) as store:
            project = store.create(f"โครงงานกรรมการ {tag[:6]} {label}", None, leader)
        if label == "hidden":
            continue
        invitation = conn.execute("INSERT INTO public.advisor_invitations(project_id,advisor_id,sent_by) VALUES (%s,%s,%s) RETURNING id",
                                  (project["id"], accounts["a"], leader)).fetchone()[0]
        conn.execute("SELECT set_config('app.actor_user_id',%s,true)", (accounts["a"],))
        conn.execute("SELECT public.v1_resolve_invitation(%s,'accepted')", (invitation,))
        conn.execute("SELECT set_config('app.actor_user_id',%s,true)", (leader,))
        conn.execute("SET CONSTRAINTS public.c_submission_requires_file DEFERRED")
        submission = conn.execute("INSERT INTO public.project_submissions(project_id,submitted_by) VALUES (%s,%s) RETURNING id",
                                  (project["id"], leader)).fetchone()[0]
        conn.execute("INSERT INTO public.project_submission_files(submission_id,file_data,original_filename,mime_type) VALUES (%s,%s,'phase.pdf','application/pdf')",
                     (submission, b"DB-only committee browser phase fixture"))
        conn.execute("SET CONSTRAINTS ALL IMMEDIATE")
        conn.execute("SELECT set_config('app.actor_user_id',%s,true)", (accounts["a"],))
        conn.execute("SELECT public.v1_review_submission(%s,'approved',NULL)", (submission,))
        if label == "locked":
            assignments = []
            for candidate in ("b", "c", "d"):
                with committee_transaction_on(conn) as store:
                    assignments.append(store.mutate(accounts["coordinator"], project["id"],
                                                    operation="add", advisor=accounts[candidate]))
            conn.execute("SELECT set_config('app.actor_user_id',%s,true)", (accounts["b"],))
            conn.execute("SELECT public.v1_cast_vote(%s,%s,'approved',NULL)", (submission, assignments[0]["id"]))
        conn.execute("SET CONSTRAINTS ALL IMMEDIATE")


def seed_topic_projects(conn, tag, accounts):
    labels = ("flow", "lost", "mobile", "incomplete", "stale", "private", "error", "revision", "tie")
    leaders = {}
    with conn.cursor() as cur:
        switch(cur, OWNER)
        encoded = hash_password("TopicBrowserFixtureA1")
        for label in labels:
            cur.execute("INSERT INTO public.users(full_name,email,role) VALUES (%s,%s,'student') RETURNING id",
                        ("นักศึกษาทดสอบผลหัวข้อ", f"topic-browser-{tag}-{label}@example.test"))
            leaders[label] = str(cur.fetchone()[0])
            cur.execute("INSERT INTO auth.credentials(user_id,password_hash) VALUES (%s,%s)", (leaders[label], encoded))
        switch(cur, "project_app")
    for label, leader in leaders.items():
        with team_transaction_on(conn) as store:
            store.create(f"ทีมลงมติ {tag[:6]} {label}", None, leader)
        with project_transaction_on(conn) as store:
            project = store.create(f"โครงงานลงมติ {tag[:6]} {label}", "หัวข้อ snapshot สำหรับทดสอบ", leader)
        invitation = conn.execute("INSERT INTO public.advisor_invitations(project_id,advisor_id,sent_by) VALUES (%s,%s,%s) RETURNING id",
                                  (project["id"], accounts["a"], leader)).fetchone()[0]
        conn.execute("SELECT set_config('app.actor_user_id',%s,true)", (accounts["a"],))
        conn.execute("SELECT public.v1_resolve_invitation(%s,'accepted')", (invitation,))

        def submission(approved=True):
            conn.execute("SELECT set_config('app.actor_user_id',%s,true)", (leader,))
            conn.execute("SET CONSTRAINTS public.c_submission_requires_file DEFERRED")
            identifier = conn.execute("INSERT INTO public.project_submissions(project_id,submitted_by) VALUES (%s,%s) RETURNING id",
                                       (project["id"], leader)).fetchone()[0]
            conn.execute("INSERT INTO public.project_submission_files(submission_id,file_data,original_filename,mime_type) VALUES (%s,%s,'phase.pdf','application/pdf')",
                         (identifier, b"DB-only topic browser phase fixture"))
            conn.execute("SET CONSTRAINTS ALL IMMEDIATE")
            if approved:
                conn.execute("SELECT set_config('app.actor_user_id',%s,true)", (accounts["a"],))
                conn.execute("SELECT public.v1_review_submission(%s,'approved',NULL)", (identifier,))
            return str(identifier)

        current = submission()
        members = ("b", "c") if label == "incomplete" else ("b", "c", "d", "e") if label == "tie" else ("b", "c", "d")
        for member in members:
            with committee_transaction_on(conn) as store:
                store.mutate(accounts["coordinator"], project["id"], operation="add", advisor=accounts[member])
        if label in ("stale", "revision", "private", "tie"):
            votes = 2 if label == "private" else len(members)
            for index, member in enumerate(members[:votes]):
                choice = ("revision_requested" if label in ("stale", "revision") else
                          "approved" if (label == "private" and index == 0) or (label == "tie" and index < 2) else "revision_requested")
                comment = "Private topic comment " + member if label == "private" else "Same revision advice"
                with topic_vote_transaction_on(conn) as store:
                    store.cast(accounts[member], project["id"], current, choice, comment)
            if label in ("stale", "revision"):
                submission(approved=label == "stale")
        conn.execute("SET CONSTRAINTS ALL IMMEDIATE")


def seed_evaluation_projects(conn, tag, accounts):
    # Only this explicit rollback fixture prepares completed work. It does not
    # call peer APIs or bypass derived status / first-evaluation locks.
    labels = ("flow", "lost", "mobile", "phase", "topic", "privacy", "error", "half")
    leaders = {}
    with conn.cursor() as cur:
        switch(cur, OWNER)
        encoded = hash_password("EvaluationBrowserFixtureA1")
        for label in labels:
            cur.execute("INSERT INTO public.users(full_name,email,role) VALUES (%s,%s,'student') RETURNING id",
                        ("นักศึกษาทดสอบผลประเมิน", f"evaluation-browser-{tag}-{label}@example.test"))
            leaders[label] = str(cur.fetchone()[0])
            cur.execute("INSERT INTO auth.credentials(user_id,password_hash) VALUES (%s,%s)", (leaders[label], encoded))
        switch(cur, "project_app")
    for label, leader in leaders.items():
        with team_transaction_on(conn) as store:
            team = store.create(f"ทีมประเมิน {tag[:6]} {label}", None, leader)
        with project_transaction_on(conn) as store:
            project = store.create(f"โครงงานประเมิน {tag[:6]} {label}", None, leader)
        invitation = conn.execute("INSERT INTO public.advisor_invitations(project_id,advisor_id,sent_by) VALUES (%s,%s,%s) RETURNING id",
                                  (project["id"], accounts["a"], leader)).fetchone()[0]
        conn.execute("SELECT set_config('app.actor_user_id',%s,true)", (accounts["a"],))
        conn.execute("SELECT public.v1_resolve_invitation(%s,'accepted')", (invitation,))
        conn.execute("SELECT set_config('app.actor_user_id',%s,true)", (leader,))
        conn.execute("SET CONSTRAINTS public.c_submission_requires_file DEFERRED")
        submission = conn.execute("INSERT INTO public.project_submissions(project_id,submitted_by) VALUES (%s,%s) RETURNING id",
                                  (project["id"], leader)).fetchone()[0]
        conn.execute("INSERT INTO public.project_submission_files(submission_id,file_data,original_filename,mime_type) VALUES (%s,%s,'phase.pdf','application/pdf')",
                     (submission, b"DB-only evaluation browser phase fixture"))
        conn.execute("SET CONSTRAINTS ALL IMMEDIATE")
        conn.execute("SELECT set_config('app.actor_user_id',%s,true)", (accounts["a"],))
        conn.execute("SELECT public.v1_review_submission(%s,'approved',NULL)", (submission,))
        members = ("b", "c", "d", "e") if label == "half" else ("b", "c", "d")
        for member in members:
            with committee_transaction_on(conn) as store:
                store.mutate(accounts["coordinator"], project["id"], operation="add", advisor=accounts[member])
        if label != "topic":
            for member in members:
                with topic_vote_transaction_on(conn) as store:
                    store.cast(accounts[member], project["id"], str(submission), "approved", None)
        if label != "phase":
            conn.execute("SELECT set_config('app.actor_user_id',%s,true)", (leader,))
            due = conn.execute("SELECT (NOW() AT TIME ZONE 'Asia/Bangkok')::date+7").fetchone()[0]
            milestone = conn.execute("SELECT public.v1_create_milestone(%s,'Evaluation milestone',NULL,%s)", (project["id"], due)).fetchone()[0]
            task = conn.execute("SELECT public.v1_create_task(%s,'Evaluation task',NULL,%s)", (milestone, due)).fetchone()[0]
            membership = conn.execute("SELECT id FROM public.team_members WHERE team_id=%s AND user_id=%s", (team["id"], leader)).fetchone()[0]
            conn.execute("SELECT public.v1_assign_task(%s,%s)", (task, membership))
            conn.execute("SELECT public.v1_set_task_status(%s,'completed')", (task,))
        if label == "privacy":
            with evaluation_transaction_on(conn) as store:
                store.record(accounts["b"], project["id"], 10, "Private evaluation browser feedback")
        elif label == "half":
            for member, score in zip(members, (0, 0, 1, 1)):
                with evaluation_transaction_on(conn) as store:
                    store.record(accounts[member], project["id"], score, "Completed evaluation advice " + member)
        conn.execute("SET CONSTRAINTS ALL IMMEDIATE")


def baseline_snapshot():
    cfg = dotenv_values(BASE / "backend/.env")
    conn = None
    try:
        conn = psycopg.connect(
            host=cfg.get("DB_HOST"), port=int(cfg.get("DB_PORT") or 5432),
            dbname=TEST_DB, user=cfg.get("DB_USER"), password=cfg.get("DB_PASSWORD"),
            connect_timeout=8, autocommit=False,
            options="-c statement_timeout=15000 -c lock_timeout=3000",
        )
        with conn.cursor() as cur:
            cur.execute("SET TRANSACTION READ ONLY")
            cur.execute("SELECT current_database()")
            if cur.fetchone()[0] != TEST_DB:
                raise RuntimeError("Database guard failed")
            switch(cur, OWNER)
            digest, counts = snapshot(cur)
            cur.execute("""SELECT count(*) FROM pg_catalog.pg_stat_activity
                WHERE datname=current_database() AND application_name=%s""", (APPLICATION_NAME,))
            connections = cur.fetchone()[0]
            return {"metadata_sha256": digest, "row_counts": counts, "fixture_connections": connections}
    finally:
        if conn is not None:
            conn.rollback()
            conn.close()


def run_fixture():
    if os.environ.get("SPMS_AUTH_BROWSER_ROLLBACK") != "1":
        raise RuntimeError("Explicit browser rollback-test mode is required")
    if runtime_target().mode != "local_test":
        raise StorageUnavailable()
    owner_fixtures = os.environ.get("SPMS_INVITATION_BROWSER_FIXTURES") == "1"
    conn = connect_test_database() if owner_fixtures else open_auth_connection()
    lock = RLock()
    try:
        with conn.transaction(force_rollback=True):
            if owner_fixtures:
                tag = os.environ.get("SPMS_ADVISOR_FIXTURE_TAG")
                accounts = seed_invitation_accounts(conn, tag)
                seed_committee_projects(conn, tag, accounts)
                seed_topic_projects(conn, tag, accounts)
                seed_evaluation_projects(conn, tag, accounts)
            assert_auth_connection(conn)
            conn.execute("SELECT set_config('application_name',%s,true)", (APPLICATION_NAME,))

            @contextmanager
            def borrowed_uow(factory):
                with lock:
                    # If the outer transaction ever disappears, fail closed
                    # rather than allowing a request to commit a top-level tx.
                    if conn.info.transaction_status != TransactionStatus.INTRANS:
                        raise StorageUnavailable()
                    with factory(conn) as repository:
                        yield repository

            app = create_app()
            app.dependency_overrides[get_auth_uow] = lambda: lambda: borrowed_uow(transaction_on)
            app.dependency_overrides[get_team_uow] = lambda: lambda: borrowed_uow(team_transaction_on)
            app.dependency_overrides[get_project_uow] = lambda: lambda: borrowed_uow(project_transaction_on)
            app.dependency_overrides[get_invitation_uow] = lambda: lambda: borrowed_uow(invitation_transaction_on)
            app.dependency_overrides[get_committee_uow] = lambda: lambda: borrowed_uow(committee_transaction_on)
            app.dependency_overrides[get_topic_vote_uow] = lambda: lambda: borrowed_uow(topic_vote_transaction_on)
            app.dependency_overrides[get_evaluation_uow] = lambda: lambda: borrowed_uow(evaluation_transaction_on)
            app.dependency_overrides[get_submission_uow] = lambda: lambda: borrowed_uow(submission_transaction_on)
            app.dependency_overrides[get_milestone_uow] = lambda: lambda: borrowed_uow(milestone_transaction_on)
            app.dependency_overrides[get_task_uow] = lambda: lambda: borrowed_uow(task_transaction_on)
            uvicorn.run(app, host="127.0.0.1", port=8001, log_level="warning")
    finally:
        conn.rollback()
        conn.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--snapshot", action="store_true")
    args = parser.parse_args()
    try:
        if args.snapshot:
            print(json.dumps(baseline_snapshot()))
        else:
            run_fixture()
        return 0
    except Exception as exc:
        print(json.dumps({"result": "FAIL", "error_type": type(exc).__name__, "sqlstate": getattr(exc, "sqlstate", None)}))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
