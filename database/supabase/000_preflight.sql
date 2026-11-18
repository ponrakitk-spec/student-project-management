-- READ ONLY: run in the SQL Editor of the approved Supabase test project
-- czylcqdmtzztabkcqewn. This file creates/changes nothing and reads no passwords.
-- Confirm the Dashboard project URL before running; current_database() alone
-- cannot distinguish two Supabase projects whose databases are both postgres.
SELECT
  current_database() AS database_name,
  current_user AS database_role,
  current_setting('server_version') AS postgres_version,
  (
    SELECT count(*)
    FROM pg_catalog.pg_class c
    JOIN pg_catalog.pg_namespace n ON n.oid = c.relnamespace
    WHERE n.nspname = 'public'
      AND c.relkind = 'r'
      AND c.relname IN (
        'users', 'teams', 'team_members', 'projects',
        'advisor_invitations', 'project_submissions',
        'project_submission_files', 'committee_assignments',
        'committee_topic_votes', 'committee_evaluations',
        'milestones', 'tasks', 'task_assignees',
        'task_assignment_history'
      )
  ) AS existing_v1_tables,
  (
    SELECT count(*)
    FROM pg_catalog.pg_proc p
    JOIN pg_catalog.pg_namespace n ON n.oid = p.pronamespace
    WHERE n.nspname = 'public'
      AND left(p.proname, 3) = 'v1_'
  ) AS existing_v1_functions,
  (
    SELECT count(*)
    FROM pg_catalog.pg_roles
    WHERE rolname IN ('project_owner', 'project_app')
  ) AS existing_app_roles,
  EXISTS (
    SELECT 1 FROM pg_catalog.pg_namespace WHERE nspname = 'spms_auth'
  ) AS spms_auth_exists;
