#!/usr/bin/env bash
# Sourced by the official PostgreSQL entrypoint on an empty volume.
set -euo pipefail
psql --username "$POSTGRES_USER" --dbname postgres --set ON_ERROR_STOP=1 \
  --set app_password="$APP_DB_PASSWORD" --set job_password="$JOB_DB_PASSWORD" <<'SQL'
CREATE ROLE career_app_user LOGIN PASSWORD :'app_password';
CREATE ROLE career_jobs_user LOGIN PASSWORD :'job_password';
CREATE DATABASE career_app OWNER career_app_user;
CREATE DATABASE career_jobs OWNER career_jobs_user;
REVOKE CONNECT, TEMPORARY ON DATABASE career_app FROM PUBLIC;
REVOKE CONNECT, TEMPORARY ON DATABASE career_jobs FROM PUBLIC;
GRANT CONNECT ON DATABASE career_app TO career_app_user;
GRANT CONNECT ON DATABASE career_jobs TO career_jobs_user;
SQL
