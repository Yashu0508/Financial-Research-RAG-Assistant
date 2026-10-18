"""Idempotent pgvector persistence for source-consistent narrative embeddings."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Protocol

from app.retrieval.semantic.config import SemanticEmbeddingConfiguration
from app.retrieval.semantic.embeddings import EmbeddingInputSegment, vector_literal


class SemanticStorageError(RuntimeError):
    """Raised when embedding persistence would weaken evidence integrity."""


class Cursor(Protocol):
    def execute(self, query: str, params: tuple[object, ...] | None = ...) -> object: ...
    def fetchall(self) -> list[tuple[Any, ...]]: ...
    def fetchone(self) -> tuple[Any, ...] | None: ...
    def close(self) -> None: ...


class Connection(Protocol):
    def cursor(self) -> Cursor: ...


@dataclass(frozen=True)
class NarrativeEmbeddingSource:
    chunk_id: str
    document_id: str
    source_sha256: str
    text: str


@dataclass(frozen=True)
class EmbeddingBackfillResult:
    eligible_chunks: int
    prepared_segments: int
    inserted_segments: int
    existing_segments: int


class PostgresSemanticEmbeddingRepository:
    """Persist model/version-specific segments without modifying source evidence."""

    def __init__(self, connection: Connection) -> None:
        self.connection = connection

    def eligible_narrative_sources(self) -> tuple[NarrativeEmbeddingSource, ...]:
        cursor = self.connection.cursor()
        try:
            cursor.execute(
                """
                SELECT n.chunk_id, n.document_id, n.source_sha256, n.text
                FROM narrative_chunks AS n
                JOIN registered_documents AS d
                  ON d.document_id = n.document_id
                 AND d.source_sha256 = n.source_sha256
                WHERE n.validation_status = 'ADMITTED'
                ORDER BY n.document_id, n.chunk_sequence
                """
            )
            return tuple(NarrativeEmbeddingSource(*row) for row in cursor.fetchall())
        finally:
            cursor.close()

    def assert_no_source_hash_mismatch(self) -> None:
        cursor = self.connection.cursor()
        try:
            cursor.execute(
                """
                SELECT COUNT(*)
                FROM narrative_chunks AS n
                LEFT JOIN registered_documents AS d ON d.document_id = n.document_id
                WHERE d.document_id IS NULL OR d.source_sha256 <> n.source_sha256
                """
            )
            row = cursor.fetchone()
        finally:
            cursor.close()
        if not row or int(row[0]) != 0:
            raise SemanticStorageError("Narrative source-hash mismatch prevents semantic backfill.")

    def register_configuration(self, configuration: SemanticEmbeddingConfiguration) -> None:
        cursor = self.connection.cursor()
        try:
            cursor.execute(
                """
                INSERT INTO semantic_embedding_configurations
                    (configuration_hash, configuration_json, model_id, model_revision,
                     embedding_dimension, normalized)
                VALUES (%s, %s::jsonb, %s, %s, %s, %s)
                ON CONFLICT (configuration_hash) DO NOTHING
                """,
                (
                    configuration.configuration_hash,
                    json.dumps(configuration.payload, sort_keys=True),
                    configuration.model_id,
                    configuration.model_revision,
                    configuration.embedding_dimension,
                    configuration.normalized,
                ),
            )
        finally:
            cursor.close()

    def insert_segments(
        self,
        configuration: SemanticEmbeddingConfiguration,
        source: NarrativeEmbeddingSource,
        segments: tuple[EmbeddingInputSegment, ...],
        vectors: list[list[float]],
    ) -> tuple[int, int]:
        if len(segments) != len(vectors):
            raise SemanticStorageError("Prepared embedding segments and vectors are not aligned.")
        inserted = 0
        existing = 0
        cursor = self.connection.cursor()
        try:
            for segment, vector in zip(segments, vectors, strict=True):
                cursor.execute(
                    """
                    INSERT INTO narrative_embedding_segments
                        (embedding_id, configuration_hash, chunk_id, document_id, source_sha256,
                         segment_index, character_start, character_end, input_text_sha256,
                         input_text, embedding)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s::public.vector)
                    ON CONFLICT (configuration_hash, chunk_id, segment_index) DO NOTHING
                    RETURNING embedding_id
                    """,
                    (
                        segment.embedding_id,
                        configuration.configuration_hash,
                        source.chunk_id,
                        source.document_id,
                        source.source_sha256,
                        segment.segment_index,
                        segment.character_start,
                        segment.character_end,
                        segment.input_text_sha256,
                        segment.text,
                        vector_literal(vector),
                    ),
                )
                if cursor.fetchone():
                    inserted += 1
                else:
                    existing += 1
        finally:
            cursor.close()
        return inserted, existing
