# SEC registration manifest

`data/manifests/sec_documents.v1.json` is the tracked, versioned registration contract for immutable local SEC sources. It is distinct from the generated verification CSV under `data/processed/document_verification/`: the CSV records a verification run, while this manifest states the source bytes approved for later ingestion.

## Contract

The root contains `schema_version`, `manifest_id`, and a non-empty `documents` list. Schema version `1.0` requires every entry to include:

- Stable lowercase-kebab-case `document_id`; canonical issuer, ticker, and SEC form type.
- Nullable `filing_date`, `fiscal_year`, `fiscal_quarter`, and `official_sec_source_url`. `null` means unavailable or not yet confirmed; the system must not infer or invent it.
- Required `reporting_period_end`, safe project-relative `local_source_path` beneath `data/raw/sec_filings/`, immutable `source_sha256`, and immutable `source_byte_size`.
- `registration` metadata with a registration timestamp or explicit acquisition note, a `registered` processing status, and a list of validation warnings.

The current corpus preserves the ten prior document IDs, verified company/form/period values, source hashes, and byte sizes. Filing dates and official SEC URLs are `null` because they were not independently confirmed for this registration task. Microsoft/Apple ticker identifiers are curated corpus metadata. Fiscal year/quarter remains `null` when it was not registered from an authoritative source.

## Invariant and lifecycle

`registered` is the only manifest processing lifecycle status in Phase 1. A local check returns a separate runtime source status:

- `VALID`: file exists and both byte size and SHA-256 match the registration.
- `MISSING`: approved path has no file.
- `CHANGED`: bytes or SHA-256 differ; the manifest is not repaired automatically.
- `UNREADABLE` or `INVALID_PATH`: the file cannot safely be checked.

The loader reads only an approved manifest path. It uses no network APIs and writes neither the raw source nor the manifest. A changed file must be manually investigated and explicitly re-registered in a future controlled manifest change.

## Validation command

From the repository root:

```powershell
python scripts\validate_sec_registration_manifest.py
```

Exit codes are `0` for a fully valid manifest/source set, `1` for a missing, changed, unreadable, or unsafe registered source, and `2` for an invalid manifest. The command never downloads content and never overwrites a registered hash.
