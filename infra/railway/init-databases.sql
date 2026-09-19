-- One-time setup of the two application databases on Railway PostgreSQL.
-- Owner: M3 (C-06). Mirrors infra/postgres/init-databases.sh.
--
-- Run it yourself with the Railway superuser URL (Postgres service > Connect):
--   psql "<superuser DATABASE_PUBLIC_URL>" -f infra/railway/init-databases.sql
-- psql asks for both passwords, so they never appear in shell history or Git.
-- Then build APP_DATABASE_URL / JOB_DATABASE_URL from these roles, not the
-- superuser.

\set ON_ERROR_STOP on
\prompt 'Password for career_app_user: ' app_password
\prompt 'Password for career_jobs_user: ' job_password

CREATE ROLE career_app_user LOGIN PASSWORD :'app_password';
CREATE ROLE career_jobs_user LOGIN PASSWORD :'job_password';
CREATE DATABASE career_app OWNER career_app_user;
CREATE DATABASE career_jobs OWNER career_jobs_user;
REVOKE CONNECT, TEMPORARY ON DATABASE career_app FROM PUBLIC;
REVOKE CONNECT, TEMPORARY ON DATABASE career_jobs FROM PUBLIC;
GRANT CONNECT ON DATABASE career_app TO career_app_user;
GRANT CONNECT ON DATABASE career_jobs TO career_jobs_user;
