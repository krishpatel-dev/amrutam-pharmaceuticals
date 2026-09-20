-- PostgreSQL initialisation script
-- Runs once on first container start via docker-entrypoint-initdb.d

-- Enable UUID extension
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Enable pg_trgm for fuzzy text search on doctor names / specialties
CREATE EXTENSION IF NOT EXISTS "pg_trgm";

-- Enable btree_gin for composite GIN indexes
CREATE EXTENSION IF NOT EXISTS "btree_gin";
