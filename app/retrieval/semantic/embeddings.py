"""Offline-only pinned-model loading and deterministic embedding preparation."""

from __future__ import annotations

import hashlib
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol

from .config import SemanticEmbeddingConfiguration


class SemanticEmbeddingError(RuntimeError):
    """Raised when the pinned local model or an embedding is not trustworthy."""


class Tokenizer(Protocol):
    def __call__(self, text: str, **kwargs: Any) -> dict[str, list[Any]]: ...
    def num_special_tokens_to_add(self, pair: bool = False) -> int: ...


@dataclass(frozen=True)
class EmbeddingInputSegment:
    """A measured text span linked to an immutable parent evidence chunk."""

    embedding_id: str
    parent_chunk_id: str
    segment_index: int
    character_start: int
    character_end: int
    text: str
    input_text_sha256: str


def pinned_model_snapshot(cache_dir: Path, configuration: SemanticEmbeddingConfiguration) -> Path:
    """Locate the exact cached Hugging Face snapshot without network resolution."""

    if not cache_dir.is_absolute():
        raise SemanticEmbeddingError("SEMANTIC_MODEL_CACHE_DIR must be an absolute path.")
    repository = "models--" + configuration.model_id.replace("/", "--")
    snapshot = cache_dir / "hub" / repository / "snapshots" / configuration.model_revision
    required = (snapshot / "config.json", snapshot / "model.safetensors", snapshot / "modules.json")
    if not snapshot.is_dir() or any(not item.is_file() for item in required):
        raise SemanticEmbeddingError(
            "Pinned model revision is unavailable in the configured local cache; "
            "download it explicitly before running this command."
        )
    return snapshot


def load_pinned_model(cache_dir: Path, configuration: SemanticEmbeddingConfiguration) -> Any:
    """Load an exact local snapshot; never ask Hugging Face to resolve/download it."""

    try:
        from sentence_transformers import SentenceTransformer
    except ImportError as exc:  # pragma: no cover - installation boundary
        raise SemanticEmbeddingError("Install the semantic optional dependency.") from exc
    snapshot = pinned_model_snapshot(cache_dir, configuration)
    try:
        model = SentenceTransformer(str(snapshot), local_files_only=True)
    except Exception as exc:  # model libraries expose several exception classes
        raise SemanticEmbeddingError("Pinned local model snapshot could not be loaded.") from exc
    dimension = model.get_embedding_dimension()
    if dimension != configuration.embedding_dimension:
        raise SemanticEmbeddingError(
            f"Pinned model dimension is {dimension}, not {configuration.embedding_dimension}."
        )
    if model.max_seq_length != configuration.max_sequence_length:
        raise SemanticEmbeddingError(
            f"Pinned model maximum sequence length is {model.max_seq_length}, not "
            f"{configuration.max_sequence_length}."
        )
    return model


def prepare_embedding_segments(
    parent_chunk_id: str,
    text: str,
    tokenizer: Tokenizer,
    configuration: SemanticEmbeddingConfiguration,
) -> tuple[EmbeddingInputSegment, ...]:
    """Window WordPiece offsets before encoding; never rely on model truncation."""

    if not isinstance(text, str) or not text.strip():
        raise SemanticEmbeddingError("Admitted narrative evidence must have non-empty text.")
    encoded = tokenizer(
        text, add_special_tokens=False, return_offsets_mapping=True, truncation=False
    )
    token_ids = encoded.get("input_ids")
    offsets = encoded.get("offset_mapping")
    if (
        not isinstance(token_ids, list)
        or not isinstance(offsets, list)
        or len(token_ids) != len(offsets)
    ):
        raise SemanticEmbeddingError("Tokenizer did not return aligned token offsets.")
    capacity = configuration.max_sequence_length - tokenizer.num_special_tokens_to_add(pair=False)
    if capacity <= 0:
        raise SemanticEmbeddingError("Tokenizer leaves no capacity for source tokens.")
    segments: list[EmbeddingInputSegment] = []
    for segment_index, start_index in enumerate(range(0, len(offsets), capacity)):
        window = offsets[start_index : start_index + capacity]
        valid = [(int(start), int(end)) for start, end in window if int(end) > int(start)]
        if not valid:
            continue
        character_start, character_end = valid[0][0], valid[-1][1]
        input_text = text[character_start:character_end]
        digest = hashlib.sha256(input_text.encode("utf-8")).hexdigest()
        identity = "\0".join(
            (
                configuration.configuration_hash,
                parent_chunk_id,
                str(segment_index),
                str(character_start),
                str(character_end),
                digest,
            )
        )
        segments.append(
            EmbeddingInputSegment(
                hashlib.sha256(identity.encode()).hexdigest()[:24],
                parent_chunk_id,
                segment_index,
                character_start,
                character_end,
                input_text,
                digest,
            )
        )
    if not segments:
        raise SemanticEmbeddingError("Tokenizer produced no usable source spans.")
    return tuple(segments)


def encode_texts(
    model: Any, texts: list[str], configuration: SemanticEmbeddingConfiguration, batch_size: int
) -> list[list[float]]:
    """Encode bounded batches and reject NaN, wrong dimension, or unnormalised vectors."""

    if not texts:
        return []
    if (
        isinstance(batch_size, bool)
        or not isinstance(batch_size, int)
        or not 1 <= batch_size <= 128
    ):
        raise SemanticEmbeddingError("Embedding batch size must be an integer from 1 through 128.")
    values = model.encode(
        texts, batch_size=batch_size, normalize_embeddings=True, show_progress_bar=False
    )
    vectors = [[float(value) for value in row] for row in values]
    for vector in vectors:
        if len(vector) != configuration.embedding_dimension or not all(
            math.isfinite(value) for value in vector
        ):
            raise SemanticEmbeddingError("Model returned a malformed embedding vector.")
        norm = math.sqrt(sum(value * value for value in vector))
        if not math.isclose(norm, 1.0, abs_tol=1e-4):
            raise SemanticEmbeddingError("Model returned a non-normalized embedding vector.")
    return vectors


def vector_literal(vector: list[float]) -> str:
    """Serialize a validated vector for the parameterized pgvector cast."""

    return "[" + ",".join(format(value, ".9g") for value in vector) + "]"
