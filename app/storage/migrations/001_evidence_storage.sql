-- PostgreSQL schema for immutable, admitted Phase 3 evidence.  No search or vector indexes.
CREATE TABLE registered_documents (
    document_id TEXT PRIMARY KEY,
    source_sha256 CHAR(64) NOT NULL CHECK (source_sha256 ~ '^[0-9a-f]{64}$'),
    company TEXT NOT NULL, ticker TEXT NOT NULL, form_type TEXT NOT NULL,
    filing_date DATE NULL, reporting_period_end DATE NOT NULL,
    fiscal_year INTEGER NULL, fiscal_quarter SMALLINT NULL CHECK (fiscal_quarter BETWEEN 1 AND 4),
    official_sec_source_url TEXT NULL, local_source_path TEXT NOT NULL UNIQUE,
    source_byte_size BIGINT NOT NULL CHECK (source_byte_size > 0), manifest_id TEXT NOT NULL,
    manifest_schema_version TEXT NOT NULL, registration_metadata JSONB NOT NULL,
    validation_warnings JSONB NOT NULL
);
CREATE TABLE processing_runs (
    run_id TEXT PRIMARY KEY, run_content_hash CHAR(64) NOT NULL UNIQUE,
    manifest_id TEXT NOT NULL, manifest_schema_version TEXT NOT NULL,
    parser_version TEXT NOT NULL, parser_configuration_hash CHAR(64) NOT NULL,
    chunking_version TEXT NOT NULL, chunking_configuration_hash CHAR(64) NOT NULL,
    artifact_hashes JSONB NOT NULL, created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE document_evidence_runs (
    run_id TEXT NOT NULL REFERENCES processing_runs(run_id), document_id TEXT NOT NULL REFERENCES registered_documents(document_id),
    source_sha256 CHAR(64) NOT NULL, artifact_sha256 CHAR(64) NOT NULL,
    admission_status TEXT NOT NULL CHECK (admission_status IN ('ADMITTED','ADMITTED_WITH_QUARANTINED_RECORDS')),
    PRIMARY KEY (run_id, document_id)
);
CREATE TABLE narrative_chunks (
    chunk_id TEXT PRIMARY KEY, run_id TEXT NOT NULL REFERENCES processing_runs(run_id), document_id TEXT NOT NULL REFERENCES registered_documents(document_id),
    source_sha256 CHAR(64) NOT NULL, chunk_sequence INTEGER NOT NULL CHECK (chunk_sequence >= 0), text TEXT NOT NULL,
    section_heading JSONB NOT NULL, source_elements JSONB NOT NULL, inherited_source_warnings JSONB NOT NULL,
    parser_version TEXT NOT NULL, parser_configuration_hash CHAR(64) NOT NULL, chunking_version TEXT NOT NULL,
    chunking_configuration_hash CHAR(64) NOT NULL, validation_status TEXT NOT NULL CHECK (validation_status = 'ADMITTED'),
    UNIQUE (run_id, document_id, chunk_sequence)
);
CREATE TABLE financial_table_evidence (
    table_evidence_id TEXT PRIMARY KEY, run_id TEXT NOT NULL REFERENCES processing_runs(run_id), document_id TEXT NOT NULL REFERENCES registered_documents(document_id),
    source_sha256 CHAR(64) NOT NULL, parser_table_id TEXT NOT NULL, original_html_table_index INTEGER NOT NULL,
    source_locator TEXT NOT NULL, caption TEXT NULL, preceding_heading JSONB NULL, unit_hints JSONB NOT NULL,
    period_header_text JSONB NOT NULL, header_association_status TEXT NOT NULL CHECK (header_association_status = 'NOT_ESTABLISHED'),
    table_warnings JSONB NOT NULL, inherited_source_warnings JSONB NOT NULL, parser_version TEXT NOT NULL,
    parser_configuration_hash CHAR(64) NOT NULL, chunking_version TEXT NOT NULL, chunking_configuration_hash CHAR(64) NOT NULL,
    validation_status TEXT NOT NULL CHECK (validation_status = 'ADMITTED'), UNIQUE (run_id, document_id, parser_table_id)
);
CREATE TABLE financial_table_rows (
    table_evidence_id TEXT NOT NULL REFERENCES financial_table_evidence(table_evidence_id) ON DELETE CASCADE,
    row_index INTEGER NOT NULL CHECK (row_index > 0), source_locator TEXT NOT NULL, PRIMARY KEY (table_evidence_id, row_index)
);
CREATE TABLE financial_table_cells (
    table_evidence_id TEXT NOT NULL, row_index INTEGER NOT NULL, cell_index INTEGER NOT NULL CHECK (cell_index > 0),
    cell_id TEXT NOT NULL UNIQUE, source_locator TEXT NOT NULL, cell_kind TEXT NOT NULL CHECK (cell_kind IN ('header','data')),
    text TEXT NOT NULL, rowspan INTEGER NOT NULL CHECK (rowspan >= 1), colspan INTEGER NOT NULL CHECK (colspan >= 1),
    PRIMARY KEY (table_evidence_id, row_index, cell_index),
    FOREIGN KEY (table_evidence_id, row_index) REFERENCES financial_table_rows(table_evidence_id, row_index) ON DELETE CASCADE
);
CREATE TABLE quarantine_records (
    run_id TEXT NOT NULL REFERENCES processing_runs(run_id), document_id TEXT NOT NULL REFERENCES registered_documents(document_id),
    record_sequence INTEGER NOT NULL CHECK (record_sequence > 0), reason_code TEXT NOT NULL, evidence_type TEXT NOT NULL,
    source_locator TEXT NULL, diagnostic TEXT NULL, payload JSONB NOT NULL,
    validation_status TEXT NOT NULL CHECK (validation_status = 'QUARANTINED'), PRIMARY KEY (run_id, document_id, record_sequence)
);
CREATE INDEX narrative_chunks_document_sequence_idx ON narrative_chunks (document_id, chunk_sequence);
CREATE INDEX financial_table_evidence_document_index_idx ON financial_table_evidence (document_id, original_html_table_index);
CREATE INDEX quarantine_records_document_idx ON quarantine_records (document_id);
