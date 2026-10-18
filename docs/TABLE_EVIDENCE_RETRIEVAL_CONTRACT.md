# Table-evidence retrieval contract

## Status and scope

This contract was defined in Task 10 and implemented as a narrow PostgreSQL
keyword baseline in Task 11. It does not include embeddings, hybrid retrieval,
reranking, answer generation, or a UI. The narrative and table retrievers use
separate result types and separate evaluation datasets.

The contract is grounded in the admitted Phase 3 artifacts under
`data/processed/sec_evidence/v1/` and the persisted Phase 4A schema.  It
preserves tables as structured evidence rather than flattening them into
narrative text.

## Existing retrievable source record

A future table retriever may consider a record only when all of the following
already-existing conditions are true:

1. It is an artifact `table_evidence` record with
   `evidence_type: financial_table` and `validation_status: ADMITTED`.
2. Its persisted counterpart is an `financial_table_evidence` row with
   `validation_status = 'ADMITTED'`, joined to its registered document and
   retained rows/cells.
3. Its `document_id` is registered, and its `source_sha256` equals the
   registered source hash for that document.
4. It is not a `quarantine_records` row and is not a parser/chunker quarantine
   record.  Quarantined records are diagnostics, never trusted evidence.

The stable table-result identity is `table_evidence_id`.  A citation/result
must also retain `document_id`, `source_sha256`, `parser_table_id`,
`original_html_table_index`, and `source_locator`.  `parser_table_id` is stable
for a particular registered source and parser configuration; the source hash
prevents it from being confused with a table from changed source bytes.

`source_locator` is a structural HTML locator, not a page number or a source
URL anchor.  A table locator is `table:<one-based DOM table index>`, and row
and cell locators extend it with `/row:<one-based row>/cell:<one-based direct
cell>`.  It does not claim byte offsets, PDF pages, or an absent HTML anchor.

## Available fields and their meaning

| Need | Existing field(s) | Contract rule |
| --- | --- | --- |
| Document provenance | `document_id`, `source_sha256`, registered document metadata | Always return them. |
| Filing filters | registered `ticker`, `company`, `form_type`, `reporting_period_end`, plus nullable filing/fiscal metadata | Apply only values stored in `registered_documents`; never infer them from a filename. |
| Table identity/location | `table_evidence_id`, `parser_table_id`, `original_html_table_index`, `source_locator` | Return every field unchanged. |
| Title/context | nullable `caption`; nullable `preceding_heading.text` | Return both separately.  Do not claim a canonical title where both are absent. |
| Periods | `period_header_text` | Return observed header strings unchanged; do not manufacture dates. |
| Units | table `unit_hints` and cell `unit_hints` | Return observed hints at their original scope; absence means unknown, not unitless. |
| Structure | ordered rows and ordered cells, `row_index`, `cell_index`, `cell_kind`, `text`, `rowspan`, `colspan`, locators | Preserve raw cell text and structural order.  Parentheses, commas, signs, and empty cells remain display facts. |
| Quality/versioning | parser/chunker versions and configuration hashes; warnings; `header_association_status` | Return them or make them available in detailed results.  `NOT_ESTABLISHED` means headers have not been semantically associated with data cells. |

The current artifacts do not contain a canonical semantic row-label field,
normalized numeric value, canonical currency, canonical table title, or a
resolved cell-to-column-header mapping.  A future retriever must not pretend
these fields exist.  In particular, a table cell's raw `text` is evidence, not
a safely interpreted amount absent an explicit, versioned interpretation step.

## Result contract for a future retriever

A candidate result should include a compact retrieval projection and a
verbatim structural payload or a stable way to fetch it:

- `evidence_type: "financial_table"`, stable table/document/source identity,
  and registered filing metadata;
- caption and preceding heading separately; observed periods and units;
- ranked-match explanation that identifies matched table/row/cell locators,
  without fabricating header associations or numeric semantics;
- ordered rows/cells with their original text, cell kind, spans, and locators;
- validation status, warnings, parser/chunker versions and configuration
  hashes; and
- a retrieval score and retrieval-mode/configuration identity kept separate
  from source evidence.

For numerical questions, a caller must have enough context to show the raw
row label, period header strings, units (if present), and exact value cell
text.  If any required association is missing or ambiguous, return the table
with the ambiguity/warning or abstain from extracting a numeric claim; do not
silently select a value.

## Filters, admission, and ambiguity

The safely supported future filters are registered-document fields already in
the schema: ticker, form type, and reporting-period end.  A table ID and
document ID may be used for exact lookup.  Filters for fiscal year/quarter or
filing date are possible only where their registered nullable values are
present; they must not be inferred.  Caption, heading, period, units, row
labels, and cell text are evidence fields, not yet indexed search fields.

Conflicting tables, repeated values, missing captions, absent units, unknown
header associations, malformed spans, and quarantine diagnostics must remain
visible to the caller.  The future retrieval implementation needs a documented
policy for returning multiple candidates and must never collapse a conflict
into a single asserted fact.

## Implemented persistence/search projection

Migration `003_table_keyword_retrieval.sql` creates the versioned `1.0`
`financial_table_search_documents` projection and its English GIN expression
index. It contains only caption/preceding-heading text, observed period and
table-level unit hints, and ordered raw cell text. It maps directly to
`table_evidence_id` and never replaces raw structured storage. The retriever
returns a result type distinct from `KeywordSearchResult` and explicitly
retains `header_association_status = 'NOT_ESTABLISHED'` rather than inferring a
cell/header semantic relationship.

## Evaluation separation

`data/evaluation/table_retrieval_judgments.v1.json` is validation-only and is
checked by `app.evaluation.retrieval.table_judgments`.  It contains 8
answerable and 2 unanswerable table cases, including one multi-relevant case.
It is deliberately not accepted by the narrative evaluator and has no retrieval
metrics until a table retriever exists.  Narrative and table labels must remain
separate even if a future API returns both evidence types in one response;
their Recall, Precision, and MRR reports must retain their own denominators and
dataset identities.
