# Data dictionary

The Phase 1 registration manifest is now implemented at
`data/manifests/sec_documents.v1.json`; its detailed contract is in
`docs/SEC_REGISTRATION_MANIFEST.md`. The database schema and passage records below remain intended
contracts, not implemented storage.

## Document metadata

| Field | Type (intended) | Required | Meaning |
| --- | --- | --- | --- |
| `document_id` | string/UUID | Yes | Stable internal identifier; never derived from a mutable file path alone. |
| `company` | string | Yes | Canonical issuer name, such as `Microsoft`. |
| `ticker` | string | Yes | Issuer ticker at corpus curation time, normalized uppercase. |
| `form_type` | string | Yes | SEC form type, initially `10-K` or `10-Q`. |
| `filing_date` | date | No | Official filing date; null until confirmed. |
| `reporting_period` | date or period string | Yes | Period end represented by the filing. |
| `fiscal_year` | integer | No | Issuer fiscal year represented by the filing; null until registered from authoritative metadata. |
| `fiscal_quarter` | integer | No | Issuer fiscal quarter; null for annual reports or when not applicable. |
| `title` | string | Yes | Human-readable filing title. |
| `source_url` | URL/string | No | Official source URL used to acquire or verify the document; null until confirmed. |
| `local_path` | path/string | Yes for local ingestion | Repository-relative location of the immutable local source; may be null in a remote-only catalog. |
| `downloaded_at` | timezone-aware datetime | No | Acquisition timestamp; null when legacy local acquisition data was not recorded. |
| `parser_version` | string | No | Parser/configuration version used for the latest successful processing; null before parsing. |
| `processing_status` | enum/string | Yes | Phase 1 registrations use `registered`; later states remain deferred. |
| `content_hash` | string | Yes for acquired files | Cryptographic hash of source bytes for integrity/idempotency; null before acquisition. |

Dates must not be inferred from filenames when authoritative filing metadata is available. A controlled status vocabulary and transition rules will be established with the manifest/schema.

## Passage/chunk metadata

| Field | Type (intended) | Required | Meaning |
| --- | --- | --- | --- |
| `chunk_id` | string/UUID | Yes | Stable passage identifier scoped to content and chunking version. |
| `document_id` | string/UUID | Yes | Foreign key to document provenance. |
| `section` | string | Yes | Best available normalized filing section; use an explicit unknown value rather than silently guessing. |
| `page_number` | integer | No | One-based PDF page when reliably available; null for formats without dependable pagination. |
| `source_location` | structured value/string | No | HTML anchor, character span, page label, or other format-appropriate locator. |
| `chunk_index` | integer | Yes | Deterministic zero-based ordinal within the processed document/version. |
| `text` | text | Yes | Validated passage content used for retrieval. |
| `token_count` | integer | No | Count under a named tokenizer; null if not calculated. |
| `embedding_model` | string | No | Embedding model identifier; null until embedded. |
| `embedding_version` | string | No | Model/revision/configuration identity needed to reproduce vectors; null until embedded. |

The storage schema will also need processing/chunking version and timestamps so derived passages can be regenerated safely; exact fields are deferred to the database-design phase.

## Implemented evidence storage contract

Phase 4A stores registered document metadata, deterministic processing runs, admitted narrative chunks, financial-table evidence, table rows/cells, and quarantine records in separate PostgreSQL tables. `narrative_chunks` and `financial_table_evidence` each retain document/source hashes, parser/chunker versions and configuration hashes. Table rows and cells retain order, locator, kind, displayed text, and spans. `header_association_status` is constrained to `NOT_ESTABLISHED`; storage does not invent table semantics. Quarantine records are structurally separate and cannot be persisted through the approved-evidence admission path. See `app/storage/migrations/001_evidence_storage.sql`.

The keyword baseline adds an English `to_tsvector` GIN expression index on `narrative_chunks.text` and filters through registered-document ticker, form type, and reporting-period end. Its candidate contract returns `chunk_id`, `document_id`, source hash, exact stored narrative text, heading/source-element provenance, deterministic sequence, document metadata, and a PostgreSQL rank. Financial tables and quarantines are excluded; table search requires a future table-aware retrieval design.

## Implemented parsed-artifact contract

Phase 1 parser artifacts are deterministic JSON files under `data/processed/sec_parsed/v1/`, one per registered document. `parsed_document` artifacts contain separate `narrative_blocks`, `tables`, and `quarantined_tables` arrays. Each retained record includes `document_id`, `source_sha256`, parser/configuration version data, a deterministic identifier, and a structural locator.

- Narrative locator: `element:<visible narrative ordinal>:<DOM tag>`. It identifies parser source order after demonstrably hidden HTML is removed; it is not a raw-file byte offset.
- Table locator: `table:<one-based DOM table order>/row:<one-based row>/cell:<one-based direct cell>`. It is a structural pointer into the parsed HTML tree, not a fabricated page number or source anchor.
- Table cells retain their extracted displayed `text`, `cell_kind`, `rowspan`, `colspan`, and structural positions. Unit and period hints are observed text only, never inferred accounting semantics.
- `quarantined_tables` use a distinct `QUARANTINED` status and diagnostic fields. They are not trusted parsed-table output.

Run metadata contains parser/configuration identity and SHA-256 values of deterministic document artifacts. Its operational timestamp is explicitly excluded from those artifact hashes.

## Implemented evidence-chunk contract

`data/processed/sec_evidence/v1/` contains one deterministic evidence JSON document per admitted parser artifact plus run metadata. Narrative chunks and table evidence are deliberately separate arrays.

- `narrative_chunk` has an ordered `chunk_sequence`, exact parser-derived text, character count, heading context, ordered source-element references, inherited parser warnings, and manifest/parser/chunking provenance. Character counts use Unicode Python-string characters. Chunks never cross a heading boundary and use no overlap in configuration `1.0`.
- `financial_table` retains parser table rows/cells without prose flattening. It carries a table-evidence ID, original table index/locator, caption/heading, units, period-header text, raw cell display strings, spans, and `header_association_status: NOT_ESTABLISHED` unless a future explicit semantic layer proves a relationship.
- `quarantined_evidence` records excluded low-information narrative blocks or structurally invalid tables. A document with no admitted evidence is itself `QUARANTINED`; quarantined records are never placed in trusted narrative/table arrays.

Chunk IDs include document/source identity, parser identity, chunking configuration hash, sequence, and content. Table evidence IDs include equivalent source/configuration identity plus the parser table identity/index. Operational timestamps remain separate from substantive evidence hashes.

## Traceability rules

1. A manifest entry connects the official source URL, immutable local file, and source content hash to one stable `document_id`.
2. Parsing and chunking may create new versions but must never discard `document_id` or the original source locator.
3. Every retrieval result carries `chunk_id`, `document_id`, and its ranking signals.
4. Answer citations resolve through `chunk_id` to passage text and through `document_id` to filing metadata and source URL.
5. A page number is included only when the source format and parser provide a reliable mapping. HTML anchors or other locators are valid alternatives; missing pagination must remain null rather than fabricated.
