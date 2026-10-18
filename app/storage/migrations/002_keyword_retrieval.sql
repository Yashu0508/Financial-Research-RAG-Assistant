-- PostgreSQL-native keyword baseline over admitted narrative evidence only.
-- Financial tables remain structured evidence and are intentionally not flattened into this index.
CREATE INDEX narrative_chunks_english_fts_idx
    ON narrative_chunks USING GIN (to_tsvector('english', text));

CREATE INDEX registered_documents_keyword_filter_idx
    ON registered_documents (ticker, form_type, reporting_period_end);
