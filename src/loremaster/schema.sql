-- Loremaster episodic memory schema.
-- Idempotent; safe to re-run.

CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE IF NOT EXISTS events (
    id           BIGSERIAL PRIMARY KEY,
    session_id   TEXT        NOT NULL,
    content      TEXT        NOT NULL,
    embedding    vector(1024) NOT NULL,
    importance   SMALLINT    NOT NULL CHECK (importance BETWEEN 1 AND 10),
    created_at   TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS events_session_created_idx
    ON events (session_id, created_at DESC);

-- HNSW gives correct nearest-neighbour results from the first row, unlike
-- ivfflat (which needs to be built after bulk-loading representative data).
CREATE INDEX IF NOT EXISTS events_embedding_cosine_idx
    ON events USING hnsw (embedding vector_cosine_ops);

CREATE TABLE IF NOT EXISTS semantic_facts (
    id                BIGSERIAL PRIMARY KEY,
    session_id        TEXT        NOT NULL,
    content           TEXT        NOT NULL,
    embedding         vector(1024) NOT NULL,
    source_event_ids  BIGINT[]    NOT NULL DEFAULT '{}',
    created_at        TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS semantic_facts_session_created_idx
    ON semantic_facts (session_id, created_at DESC);

CREATE INDEX IF NOT EXISTS semantic_facts_embedding_cosine_idx
    ON semantic_facts USING hnsw (embedding vector_cosine_ops);
