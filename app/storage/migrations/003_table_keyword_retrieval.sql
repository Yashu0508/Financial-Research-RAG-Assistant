-- Versioned, derived search projection for admitted structured table evidence.
-- It never replaces financial_table_evidence, rows, or cells.
CREATE TABLE financial_table_search_documents (
    table_evidence_id TEXT PRIMARY KEY
        REFERENCES financial_table_evidence(table_evidence_id) ON DELETE CASCADE,
    document_id TEXT NOT NULL REFERENCES registered_documents(document_id),
    source_sha256 CHAR(64) NOT NULL CHECK (source_sha256 ~ '^[0-9a-f]{64}$'),
    projection_version TEXT NOT NULL,
    search_text TEXT NOT NULL
);

CREATE INDEX financial_table_search_documents_english_fts_idx
    ON financial_table_search_documents USING GIN (to_tsvector('english', search_text));

CREATE INDEX financial_table_search_documents_document_idx
    ON financial_table_search_documents (document_id, projection_version);

-- Backfill only already-admitted records.  The projection consists solely of
-- contract-approved display/context fields and ordered raw cell text.
INSERT INTO financial_table_search_documents (
    table_evidence_id, document_id, source_sha256, projection_version, search_text
)
SELECT
    table_record.table_evidence_id,
    table_record.document_id,
    table_record.source_sha256,
    '1.0',
    concat_ws(
        ' ',
        table_record.caption,
        table_record.preceding_heading ->> 'text',
        COALESCE(periods.text, ''),
        COALESCE(units.text, ''),
        COALESCE(cells.text, '')
    )
FROM financial_table_evidence AS table_record
JOIN registered_documents AS document_record
    ON document_record.document_id = table_record.document_id
   AND document_record.source_sha256 = table_record.source_sha256
LEFT JOIN LATERAL (
    SELECT string_agg(value, ' ' ORDER BY ordinality) AS text
    FROM jsonb_array_elements_text(table_record.period_header_text)
        WITH ORDINALITY AS period(value, ordinality)
) AS periods ON TRUE
LEFT JOIN LATERAL (
    SELECT string_agg(value, ' ' ORDER BY ordinality) AS text
    FROM jsonb_array_elements_text(table_record.unit_hints)
        WITH ORDINALITY AS unit(value, ordinality)
) AS units ON TRUE
LEFT JOIN LATERAL (
    SELECT string_agg(cell.text, ' ' ORDER BY cell.row_index, cell.cell_index) AS text
    FROM financial_table_cells AS cell
    WHERE cell.table_evidence_id = table_record.table_evidence_id
) AS cells ON TRUE
WHERE table_record.validation_status = 'ADMITTED'
ON CONFLICT (table_evidence_id) DO NOTHING;
