#!/bin/bash
set -e

# Grant schema-level privileges and enable extensions.
# This runs after init.sql (Docker processes files in alphabetical order).
# We connect to each database explicitly rather than using \connect inside SQL,
# which doesn't work reliably in Docker's psql init context.

psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "fitness" <<-EOSQL
    CREATE EXTENSION IF NOT EXISTS vector;
    GRANT ALL ON SCHEMA public TO fitness_user;
EOSQL

psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "keycloak" <<-EOSQL
    GRANT ALL ON SCHEMA public TO keycloak_user;
EOSQL

psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "fitness_telemetry" <<-EOSQL
    GRANT ALL ON SCHEMA public TO fitness_user;
EOSQL
