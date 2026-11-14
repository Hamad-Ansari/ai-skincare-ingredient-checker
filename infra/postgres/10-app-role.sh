#!/bin/sh
# Create a dedicated non-superuser runtime/migration role on first DB initialization.
set -eu

: "${APP_DB_USER:?APP_DB_USER must be set}"
: "${APP_DB_PASSWORD:?APP_DB_PASSWORD must be set}"
: "${POSTGRES_DB:?POSTGRES_DB must be set}"

psql --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" --set=ON_ERROR_STOP=1 <<'SQL'
\getenv app_db_name POSTGRES_DB
\getenv app_db_user APP_DB_USER
\getenv app_db_password APP_DB_PASSWORD
CREATE ROLE :"app_db_user" LOGIN PASSWORD :'app_db_password';
ALTER DATABASE :"app_db_name" OWNER TO :"app_db_user";
REVOKE CONNECT ON DATABASE :"app_db_name" FROM PUBLIC;
GRANT CONNECT ON DATABASE :"app_db_name" TO :"app_db_user";
SQL
