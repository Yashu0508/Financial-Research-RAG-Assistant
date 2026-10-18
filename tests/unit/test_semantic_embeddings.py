"""Deterministic local-model input and vector validation contracts."""

from __future__ import annotations

import math

import pytest

from app.retrieval.semantic.config import SemanticEmbeddingConfiguration
from app.retrieval.semantic.embeddings import (
    SemanticEmbeddingError,
    encode_texts,
    prepare_embedding_segments,
)


def _configuration() -> SemanticEmbeddingConfiguration:
    return SemanticEmbeddingConfiguration(
        "model", "revision", 4, True, 4, "offset-windows", "st", "tf", "torch", "numpy"
    )


class Tokenizer:
    def __call__(self, text, **kwargs):
        offsets = []
        cursor = 0
        for word in text.split():
            start = text.index(word, cursor)
            offsets.append((start, start + len(word)))
            cursor = start + len(word)
        return {"input_ids": list(range(len(offsets))), "offset_mapping": offsets}

    def num_special_tokens_to_add(self, pair=False):
        return 2


class Model:
    def encode(self, texts, **kwargs):
        return [[0.5, 0.5, 0.5, 0.5] for _ in texts]


def test_overlength_text_is_windowed_with_stable_parent_provenance():
    config = _configuration()
    first = prepare_embedding_segments("chunk", "one two three four five", Tokenizer(), config)
    second = prepare_embedding_segments("chunk", "one two three four five", Tokenizer(), config)
    assert [
        (item.embedding_id, item.character_start, item.character_end, item.text) for item in first
    ] == [
        (item.embedding_id, item.character_start, item.character_end, item.text) for item in second
    ]
    assert [item.text for item in first] == ["one two", "three four", "five"]
    assert all(item.parent_chunk_id == "chunk" for item in first)


def test_empty_source_and_malformed_vectors_are_rejected():
    with pytest.raises(SemanticEmbeddingError, match="non-empty"):
        prepare_embedding_segments("chunk", " ", Tokenizer(), _configuration())
    with pytest.raises(SemanticEmbeddingError, match="malformed"):
        encode_texts(
            type("Bad", (), {"encode": lambda *_a, **_k: [[math.nan] * 4]})(),
            ["x"],
            _configuration(),
            1,
        )


def test_normalized_vectors_and_batch_bounds_are_checked():
    assert encode_texts(Model(), ["x"], _configuration(), 1) == [[0.5, 0.5, 0.5, 0.5]]
    with pytest.raises(SemanticEmbeddingError, match="batch size"):
        encode_texts(Model(), ["x"], _configuration(), 0)
