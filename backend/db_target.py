"""Explicit database destinations. No network access or config read at import."""

from dataclasses import dataclass, field
import re

from psycopg.conninfo import conninfo_to_dict


LOCAL_DATABASE = "student_project_management_v1_test"
APP_ROLE = "project_app"


class InvalidDatabaseTarget(ValueError):
    """Deliberately contains no connection string or driver error."""


@dataclass(frozen=True)
class DatabaseTarget:
    mode: str
    database: str
    auth_schema: str
    connect_kwargs: dict = field(repr=False)


def database_target(values):
    """Accept only the local test DB or an explicitly pinned Supabase test project.

    This is runtime configuration only. Local installers and test fixtures keep
    their independent local-only connection guards.
    """
    def reject():
        raise InvalidDatabaseTarget("Invalid database target configuration") from None

    mode = values.get("AUTH_DB_TARGET") or "local_test"
    if mode == "local_test":
        # Never silently ignore a cloud URL and use a different database.
        if values.get("AUTH_DATABASE_URL") or not values.get("AUTH_DB_PASSWORD"):
            reject()
        try:
            port = int(values.get("AUTH_DB_PORT") or "5432")
            if not 1 <= port <= 65535:
                reject()
        except (TypeError, ValueError):
            reject()
        return DatabaseTarget(mode, LOCAL_DATABASE, "auth", {
            "host": values.get("AUTH_DB_HOST") or "localhost", "port": port,
            "dbname": LOCAL_DATABASE, "user": APP_ROLE,
            "password": values["AUTH_DB_PASSWORD"],
        })
    if mode != "supabase_test":
        reject()
    ref = values.get("SUPABASE_PROJECT_REF") or ""
    url = values.get("AUTH_DATABASE_URL") or ""
    if not re.fullmatch(r"[a-z0-9]{20}", ref) or not url.startswith(("postgresql://", "postgres://")):
        reject()
    try:
        settings = conninfo_to_dict(url)
    except Exception:
        reject()
    # Reject query overrides, alternate databases, service keys, options, local
    # hosts, transaction poolers and admin logins. Passwords belong only here.
    allowed = {"host", "port", "dbname", "user", "password", "sslmode", "sslrootcert"}
    if set(settings) - allowed or settings.get("dbname") != "postgres" or not settings.get("password"):
        reject()
    if settings.get("sslmode") not in ("require", "verify-full"):
        reject()
    host = settings.get("host", "")
    direct = host == f"db.{ref}.supabase.co" and settings.get("user") == APP_ROLE
    session = bool(re.fullmatch(r"aws-[0-9]+-[a-z0-9-]+\.pooler\.supabase\.com", host))
    session = session and settings.get("user") == f"{APP_ROLE}.{ref}"
    if not (direct or session) or settings.get("port", "5432") != "5432":
        reject()
    settings["port"] = 5432
    return DatabaseTarget(mode, "postgres", "spms_auth", settings)
