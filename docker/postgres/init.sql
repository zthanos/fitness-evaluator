-- Create databases and users
-- NOTE: schema-level grants are handled by init.sh (runs after this file)
CREATE DATABASE fitness;
CREATE DATABASE keycloak;
CREATE DATABASE fitness_telemetry;

CREATE USER fitness_user WITH PASSWORD 'fitness_password';
CREATE USER keycloak_user WITH PASSWORD 'keycloak_password';

GRANT ALL PRIVILEGES ON DATABASE fitness TO fitness_user;
GRANT ALL PRIVILEGES ON DATABASE keycloak TO keycloak_user;
GRANT ALL PRIVILEGES ON DATABASE fitness_telemetry TO fitness_user;
