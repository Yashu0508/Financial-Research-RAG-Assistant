"""Persistence boundary for hash-validated, admitted Phase 3 evidence."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Any, Protocol

from app.ingestion.loaders.sec_manifest import RegistrationManifest
from app.storage.table_search_projection import (
    TABLE_SEARCH_PROJECTION_VERSION,
    build_table_search_text,
)


class StorageError(RuntimeError):
    pass


class StorageConflictError(StorageError):
    pass


class EvidenceAdmissionError(StorageError):
    pass


@dataclass(frozen=True)
class PersistenceResult:
    run_id: str
    inserted: bool
    narrative_count: int
    table_count: int
    quarantine_count: int


class EvidenceRepository(Protocol):
    def persist_run(
        self,
        manifest: RegistrationManifest,
        metadata: dict[str, Any],
        artifacts: list[dict[str, Any]],
    ) -> PersistenceResult: ...
    def get_narrative_chunk(self, chunk_id: str) -> dict[str, Any] | None: ...
    def get_table_evidence(self, table_evidence_id: str) -> dict[str, Any] | None: ...


def _canonical(value: object) -> str:
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":"))


def _validate(
    manifest: RegistrationManifest, metadata: dict[str, Any], artifacts: list[dict[str, Any]]
) -> tuple[str, str]:
    if (
        metadata.get("record_type") != "evidence_run_metadata"
        or metadata.get("manifest_id") != manifest.manifest_id
    ):
        raise EvidenceAdmissionError(
            "Evidence metadata is absent or conflicts with the registration manifest."
        )
    if not isinstance(metadata.get("artifact_sha256"), dict):
        raise EvidenceAdmissionError("Evidence metadata lacks artifact hashes.")
    documents = {item.document_id: item for item in manifest.documents}
    if len(artifacts) != len(documents):
        raise EvidenceAdmissionError("One artifact is required for every registered document.")
    seen: set[str] = set()
    for artifact in artifacts:
        document_id = artifact.get("document_id")
        document = documents.get(document_id)
        if (
            not document
            or document_id in seen
            or artifact.get("source_sha256") != document.source_sha256
        ):
            raise EvidenceAdmissionError("Evidence document identity conflicts with registration.")
        seen.add(document_id)
        if artifact.get("admission_status") not in {
            "ADMITTED",
            "ADMITTED_WITH_QUARANTINED_RECORDS",
        }:
            raise EvidenceAdmissionError(
                "Quarantined document cannot be persisted as approved evidence."
            )
        for key in ("narrative_chunks", "table_evidence"):
            for record in artifact.get(key, []):
                if (
                    record.get("validation_status") != "ADMITTED"
                    or record.get("document_id") != document_id
                ):
                    raise EvidenceAdmissionError(
                        "Only admitted, same-document evidence may be persisted."
                    )
    substantive = {k: v for k, v in metadata.items() if k != "operational_timestamp_utc"}
    digest = hashlib.sha256(_canonical(substantive).encode()).hexdigest()
    return f"evidence-{digest[:24]}", digest


class InMemoryEvidenceRepository:
    """Isolated behavioral test double; not evidence of PostgreSQL compatibility."""

    def __init__(self) -> None:
        self.documents: dict[str, str] = {}
        self.runs: dict[str, str] = {}
        self.narrative: dict[str, dict[str, Any]] = {}
        self.tables: dict[str, dict[str, Any]] = {}
        self.quarantine: dict[tuple[str, str], list[dict[str, Any]]] = {}

    def persist_run(
        self,
        manifest: RegistrationManifest,
        metadata: dict[str, Any],
        artifacts: list[dict[str, Any]],
    ) -> PersistenceResult:
        run_id, digest = _validate(manifest, metadata, artifacts)
        if run_id in self.runs:
            if self.runs[run_id] != digest:
                raise StorageConflictError("Processing-run identity collision.")
            return PersistenceResult(run_id, False, 0, 0, 0)
        saved = (
            self.documents.copy(),
            self.runs.copy(),
            self.narrative.copy(),
            self.tables.copy(),
            self.quarantine.copy(),
        )
        try:
            for doc in manifest.documents:
                if (
                    doc.document_id in self.documents
                    and self.documents[doc.document_id] != doc.source_sha256
                ):
                    raise StorageConflictError("Registered document source hash conflict.")
                self.documents[doc.document_id] = doc.source_sha256
            narratives = tables = quarantines = 0
            for artifact in artifacts:
                for chunk in artifact.get("narrative_chunks", []):
                    if chunk["chunk_id"] in self.narrative:
                        raise StorageConflictError("Duplicate narrative chunk ID.")
                    self.narrative[chunk["chunk_id"]] = dict(chunk)
                    narratives += 1
                for table in artifact.get("table_evidence", []):
                    if table["table_evidence_id"] in self.tables:
                        raise StorageConflictError("Duplicate table evidence ID.")
                    self.tables[table["table_evidence_id"]] = dict(table)
                    tables += 1
                records = list(artifact.get("quarantined_evidence", []))
                self.quarantine[(run_id, artifact["document_id"])] = records
                quarantines += len(records)
            self.runs[run_id] = digest
            return PersistenceResult(run_id, True, narratives, tables, quarantines)
        except Exception:
            self.documents, self.runs, self.narrative, self.tables, self.quarantine = saved
            raise

    def get_narrative_chunk(self, chunk_id: str) -> dict[str, Any] | None:
        return self.narrative.get(chunk_id)

    def get_table_evidence(self, table_evidence_id: str) -> dict[str, Any] | None:
        return self.tables.get(table_evidence_id)


class PostgresEvidenceRepository:
    """PostgreSQL DB-API repository. Apply numbered migrations before use."""

    def __init__(self, connection: Any) -> None:
        self.connection = connection

    def persist_run(
        self,
        manifest: RegistrationManifest,
        metadata: dict[str, Any],
        artifacts: list[dict[str, Any]],
    ) -> PersistenceResult:
        run_id, digest = _validate(manifest, metadata, artifacts)
        cur = self.connection.cursor()
        try:
            cur.execute("SELECT run_content_hash FROM processing_runs WHERE run_id = %s", (run_id,))
            existing = cur.fetchone()
            if existing:
                if existing[0] != digest:
                    raise StorageConflictError("Processing-run identity collision.")
                self.connection.rollback()
                return PersistenceResult(run_id, False, 0, 0, 0)
            for doc in manifest.documents:
                cur.execute(
                    "SELECT source_sha256 FROM registered_documents WHERE document_id = %s",
                    (doc.document_id,),
                )
                prior = cur.fetchone()
                if prior and prior[0] != doc.source_sha256:
                    raise StorageConflictError("Registered document source hash conflict.")
                cur.execute(
                    "INSERT INTO registered_documents (document_id,source_sha256,company,ticker,form_type,filing_date,reporting_period_end,fiscal_year,fiscal_quarter,official_sec_source_url,local_source_path,source_byte_size,manifest_id,manifest_schema_version,registration_metadata,validation_warnings) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s::jsonb,%s::jsonb) ON CONFLICT (document_id) DO NOTHING",  # noqa: E501
                    (
                        doc.document_id,
                        doc.source_sha256,
                        doc.company,
                        doc.ticker,
                        doc.form_type,
                        doc.filing_date,
                        doc.reporting_period_end,
                        doc.fiscal_year,
                        doc.fiscal_quarter,
                        doc.official_sec_source_url,
                        doc.local_source_path,
                        doc.source_byte_size,
                        manifest.manifest_id,
                        manifest.schema_version,
                        _canonical(doc.registration.__dict__),
                        _canonical(list(doc.validation_warnings)),
                    ),
                )
            cur.execute(
                "INSERT INTO processing_runs (run_id,run_content_hash,manifest_id,manifest_schema_version,parser_version,parser_configuration_hash,chunking_version,chunking_configuration_hash,artifact_hashes) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s::jsonb)",  # noqa: E501
                (
                    run_id,
                    digest,
                    manifest.manifest_id,
                    manifest.schema_version,
                    metadata["parser_version"],
                    metadata["parser_configuration_hash"],
                    metadata["chunking_version"],
                    metadata["configuration_hash"],
                    _canonical(metadata["artifact_sha256"]),
                ),
            )
            nc = tc = qc = 0
            for artifact in artifacts:
                doc_id = artifact["document_id"]
                cur.execute(
                    "INSERT INTO document_evidence_runs (run_id,document_id,source_sha256,artifact_sha256,admission_status) VALUES (%s,%s,%s,%s,%s)",  # noqa: E501
                    (
                        run_id,
                        doc_id,
                        artifact["source_sha256"],
                        metadata["artifact_sha256"][doc_id],
                        artifact["admission_status"],
                    ),
                )
                for chunk in artifact.get("narrative_chunks", []):
                    cur.execute(
                        "INSERT INTO narrative_chunks (chunk_id,run_id,document_id,source_sha256,chunk_sequence,text,section_heading,source_elements,inherited_source_warnings,parser_version,parser_configuration_hash,chunking_version,chunking_configuration_hash,validation_status) VALUES (%s,%s,%s,%s,%s,%s,%s::jsonb,%s::jsonb,%s::jsonb,%s,%s,%s,%s,%s)",  # noqa: E501
                        (
                            chunk["chunk_id"],
                            run_id,
                            doc_id,
                            chunk["source_sha256"],
                            chunk["chunk_sequence"],
                            chunk["text"],
                            _canonical(chunk["section_heading"]),
                            _canonical(chunk["source_elements"]),
                            _canonical(chunk["inherited_source_warnings"]),
                            chunk["parser_version"],
                            chunk["parser_configuration_hash"],
                            chunk["chunking_version"],
                            chunk["chunking_configuration_hash"],
                            "ADMITTED",
                        ),
                    )
                    nc += 1
                for table in artifact.get("table_evidence", []):
                    cur.execute(
                        "INSERT INTO financial_table_evidence (table_evidence_id,run_id,document_id,source_sha256,parser_table_id,original_html_table_index,source_locator,caption,preceding_heading,unit_hints,period_header_text,header_association_status,table_warnings,inherited_source_warnings,parser_version,parser_configuration_hash,chunking_version,chunking_configuration_hash,validation_status) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s::jsonb,%s::jsonb,%s::jsonb,%s,%s::jsonb,%s::jsonb,%s,%s,%s,%s,%s)",  # noqa: E501
                        (
                            table["table_evidence_id"],
                            run_id,
                            doc_id,
                            table["source_sha256"],
                            table["parser_table_id"],
                            table["original_html_table_index"],
                            table["source_locator"],
                            table.get("caption"),
                            _canonical(table.get("preceding_heading")),
                            _canonical(table["unit_hints"]),
                            _canonical(table["period_header_text"]),
                            table["header_association_status"],
                            _canonical(table["table_warnings"]),
                            _canonical(table["inherited_source_warnings"]),
                            table["parser_version"],
                            table["parser_configuration_hash"],
                            table["chunking_version"],
                            table["chunking_configuration_hash"],
                            "ADMITTED",
                        ),
                    )
                    for row in table["rows"]:
                        cur.execute(
                            "INSERT INTO financial_table_rows (table_evidence_id,row_index,source_locator) VALUES (%s,%s,%s)",  # noqa: E501
                            (table["table_evidence_id"], row["row_index"], row["source_locator"]),
                        )
                        for cell in row["cells"]:
                            cur.execute(
                                "INSERT INTO financial_table_cells (table_evidence_id,row_index,cell_index,cell_id,source_locator,cell_kind,text,rowspan,colspan) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)",  # noqa: E501
                                (
                                    table["table_evidence_id"],
                                    row["row_index"],
                                    cell["cell_index"],
                                    cell["cell_id"],
                                    cell["source_locator"],
                                    cell["cell_kind"],
                                    cell["text"],
                                    cell["rowspan"],
                                    cell["colspan"],
                                ),
                            )
                    cur.execute(
                        "INSERT INTO financial_table_search_documents (table_evidence_id,document_id,source_sha256,projection_version,search_text) VALUES (%s,%s,%s,%s,%s)",  # noqa: E501
                        (
                            table["table_evidence_id"],
                            doc_id,
                            table["source_sha256"],
                            TABLE_SEARCH_PROJECTION_VERSION,
                            build_table_search_text(table),
                        ),
                    )
                    tc += 1
                for number, record in enumerate(artifact.get("quarantined_evidence", []), 1):
                    cur.execute(
                        "INSERT INTO quarantine_records (run_id,document_id,record_sequence,reason_code,evidence_type,source_locator,diagnostic,payload,validation_status) VALUES (%s,%s,%s,%s,%s,%s,%s,%s::jsonb,'QUARANTINED')",  # noqa: E501
                        (
                            run_id,
                            doc_id,
                            number,
                            record.get("reason_code", "UNSPECIFIED"),
                            record.get("evidence_type", "quarantined_evidence"),
                            record.get("source_locator"),
                            record.get("diagnostic"),
                            _canonical(record),
                        ),
                    )
                    qc += 1
            self.connection.commit()
            return PersistenceResult(run_id, True, nc, tc, qc)
        except Exception:
            self.connection.rollback()
            raise
        finally:
            cur.close()

    def _get(self, table: str, key: str, value: str) -> dict[str, Any] | None:
        cur = self.connection.cursor()
        try:
            cur.execute(
                f"SELECT row_to_json(record) FROM (SELECT * FROM {table} WHERE {key} = %s) record",
                (value,),
            )
            row = cur.fetchone()
            return row[0] if row else None
        finally:
            cur.close()

    def get_narrative_chunk(self, chunk_id: str) -> dict[str, Any] | None:
        return self._get("narrative_chunks", "chunk_id", chunk_id)

    def get_table_evidence(self, table_evidence_id: str) -> dict[str, Any] | None:
        return self._get("financial_table_evidence", "table_evidence_id", table_evidence_id)
