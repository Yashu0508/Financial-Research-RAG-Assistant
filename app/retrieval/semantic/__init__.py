"""Locally reproducible semantic retrieval over admitted narrative evidence."""

from .config import SemanticEmbeddingConfiguration, current_embedding_configuration
from .embeddings import (
    EmbeddingInputSegment,
    SemanticEmbeddingError,
    encode_texts,
    load_pinned_model,
    prepare_embedding_segments,
)
from .postgres_semantic_retriever import (
    PostgresSemanticRetriever,
    SemanticRetrievalError,
    SemanticSearchFilters,
    SemanticSearchResult,
)

__all__ = [
    "EmbeddingInputSegment",
    "SemanticEmbeddingConfiguration",
    "SemanticEmbeddingError",
    "current_embedding_configuration",
    "encode_texts",
    "load_pinned_model",
    "prepare_embedding_segments",
    "PostgresSemanticRetriever",
    "SemanticRetrievalError",
    "SemanticSearchFilters",
    "SemanticSearchResult",
]
