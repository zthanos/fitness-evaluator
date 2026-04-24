-- Create the fitness application database
CREATE DATABASE fitness;

-- Create the keycloak database
CREATE DATABASE keycloak;

-- Create dedicated users
CREATE USER fitness_user WITH PASSWORD 'fitness_password';
CREATE USER keycloak_user WITH PASSWORD 'keycloak_password';

-- Grant privileges
GRANT ALL PRIVILEGES ON DATABASE fitness TO fitness_user;
GRANT ALL PRIVILEGES ON DATABASE keycloak TO keycloak_user;

-- Enable pgvector extension in the fitness database
\connect fitness
CREATE EXTENSION IF NOT EXISTS vector;
GRANT ALL ON SCHEMA public TO fitness_user;

\connect keycloak
GRANT ALL ON SCHEMA public TO keycloak_user;
