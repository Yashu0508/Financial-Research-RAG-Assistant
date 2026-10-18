"""Shared verification for the persistent local development evidence corpus."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol


class Cursor(Protocol):
    def execute(self, query: str, params: tuple[object, ...] | None = ...) -> object: ...
    def fetchone(self) -> Any: ...
    def close(self) -> None: ...


class Connection(Protocol):
    def cursor(self) -> Cursor: ...


class CorpusVerificationError(RuntimeError):
    """Raised when admitted evidence is absent or does not match expected counts."""


@dataclass(frozen=True)
class CorpusCounts:
    documents: int
    narrative_chunks: int
    tables: int
    quarantines: int


def expected_counts(artifacts: list[dict[str, object]]) -> CorpusCounts:
    """Derive expected counts from already hash-verified evidence artifacts."""

    return CorpusCounts(
        documents=len(artifacts),
        narrative_chunks=sum(len(item.get("narrative_chunks", [])) for item in artifacts),
        tables=sum(len(item.get("table_evidence", [])) for item in artifacts),
        quarantines=sum(len(item.get("quarantined_evidence", [])) for item in artifacts),
    )


def verify_corpus_counts(connection: Connection, expected: CorpusCounts) -> CorpusCounts:
    """Read back counts without altering the selected schema."""

    cursor = connection.cursor()
    try:
        cursor.execute(
            "SELECT (SELECT COUNT(*) FROM registered_documents), "
            "(SELECT COUNT(*) FROM narrative_chunks), "
            "(SELECT COUNT(*) FROM financial_table_evidence), "
            "(SELECT COUNT(*) FROM quarantine_records)"
        )
        row = cursor.fetchone()
    finally:
        cursor.close()
    if not row:
        raise CorpusVerificationError("Corpus count query returned no row.")
    actual = CorpusCounts(*(int(value) for value in row))
    if actual != expected:
        raise CorpusVerificationError(f"Corpus counts do not match approved artifacts: {actual!r}.")
    return actual
