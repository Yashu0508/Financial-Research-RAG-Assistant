-- Local semantic retrieval storage for admitted narrative evidence only.
-- ``public`` is deliberately qualified: pgvector is installed there while
-- application connections use a non-public schema plus pg_catalog.
CREATE TABLE semantic_embedding_configurations (
    configuration_hash CHAR(64) PRIMARY KEY,
    configuration_json JSONB NOT NULL,
    model_id TEXT NOT NULL,
    model_revision TEXT NOT NULL,
    embedding_dimension INTEGER NOT NULL CHECK (embedding_dimension = 384),
    normalized BOOLEAN NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE narrative_embedding_segments (
    embedding_id TEXT PRIMARY KEY,
    configuration_hash CHAR(64) NOT NULL
        REFERENCES semantic_embedding_configurations(configuration_hash),
    chunk_id TEXT NOT NULL REFERENCES narrative_chunks(chunk_id) ON DELETE CASCADE,
    document_id TEXT NOT NULL REFERENCES registered_documents(document_id),
    source_sha256 CHAR(64) NOT NULL CHECK (source_sha256 ~ '^[0-9a-f]{64}$'),
    segment_index INTEGER NOT NULL CHECK (segment_index >= 0),
    character_start INTEGER NOT NULL CHECK (character_start >= 0),
    character_end INTEGER NOT NULL CHECK (character_end > character_start),
    input_text_sha256 CHAR(64) NOT NULL CHECK (input_text_sha256 ~ '^[0-9a-f]{64}$'),
    input_text TEXT NOT NULL,
    embedding public.vector(384) NOT NULL,
    UNIQUE (configuration_hash, chunk_id, segment_index)
);

CREATE INDEX narrative_embedding_segments_cosine_hnsw_idx
    ON narrative_embedding_segments USING hnsw (embedding public.vector_cosine_ops);
CREATE INDEX narrative_embedding_segments_lookup_idx
    ON narrative_embedding_segments (configuration_hash, document_id, chunk_id, segment_index);
