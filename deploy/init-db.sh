#!/usr/bin/env bash
set -euo pipefail
psql -v ON_ERROR_STOP=1 --username postgres --dbname agenteval --set=app_password="$APP_DB_PASSWORD" <<'SQL'
CREATE ROLE agenteval_runtime LOGIN PASSWORD :'app_password' NOSUPERUSER NOCREATEDB NOCREATEROLE;
CREATE DATABASE agenteval_test;
CREATE DATABASE agenteval_benchmark;
SQL
