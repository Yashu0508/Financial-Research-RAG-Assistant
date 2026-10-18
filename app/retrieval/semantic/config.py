"""Pinned, inspectable configuration for local narrative embeddings."""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from importlib.metadata import version

MODEL_ID = "sentence-transformers/all-MiniLM-L6-v2"
MODEL_REVISION = "1110a243fdf4706b3f48f1d95db1a4f5529b4d41"
EMBEDDING_DIMENSION = 384
MODEL_MAX_SEQUENCE_LENGTH = 256
INPUT_POLICY = "wordpiece_offset_windows_254_content_tokens_v1"


@dataclass(frozen=True)
class SemanticEmbeddingConfiguration:
    """All identity-bearing values needed to reproduce one embedding set."""

    model_id: str
    model_revision: str
    embedding_dimension: int
    normalized: bool
    max_sequence_length: int
    input_policy: str
    sentence_transformers_version: str
    transformers_version: str
    torch_version: str
    numpy_version: str

    @property
    def payload(self) -> dict[str, object]:
        return asdict(self)

    @property
    def configuration_hash(self) -> str:
        encoded = json.dumps(self.payload, sort_keys=True, separators=(",", ":")).encode()
        return hashlib.sha256(encoded).hexdigest()


def current_embedding_configuration() -> SemanticEmbeddingConfiguration:
    """Read installed library versions rather than treating them as implicit state."""

    return SemanticEmbeddingConfiguration(
        MODEL_ID,
        MODEL_REVISION,
        EMBEDDING_DIMENSION,
        True,
        MODEL_MAX_SEQUENCE_LENGTH,
        INPUT_POLICY,
        version("sentence-transformers"),
        version("transformers"),
        version("torch"),
        version("numpy"),
    )
