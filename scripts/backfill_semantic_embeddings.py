"""Guardedly backfill pinned local embeddings for admitted narrative evidence."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def main(argv: list[str] | None = None) -> int:
    from app.core.config import get_settings
    from app.ingestion.loaders.sec_manifest import (
        check_registered_sources,
        load_registration_manifest,
    )
    from app.retrieval.semantic import (
        current_embedding_configuration,
        encode_texts,
        load_pinned_model,
        prepare_embedding_segments,
    )
    from app.storage.development import (
        DevelopmentDatabaseError,
        development_target_from_settings,
        prepare_development_connection,
    )
    from app.storage.migrations.runner import apply_migrations
    from app.storage.repositories.semantic_embedding_repository import (
        PostgresSemanticEmbeddingRepository,
        SemanticStorageError,
    )

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--batch-size", type=int, default=None)
    args = parser.parse_args(argv)
    settings = get_settings()
    try:
        target = development_target_from_settings(settings)
        if not settings.semantic_model_cache_dir:
            raise ValueError("SEMANTIC_MODEL_CACHE_DIR must be configured.")
        manifest = load_registration_manifest(ROOT / "data/manifests/sec_documents.v1.json")
        checks = check_registered_sources(ROOT, manifest)
        if not all(check.is_valid for check in checks):
            raise ValueError("Registered SEC source validation failed; refusing semantic backfill.")
        configuration = current_embedding_configuration()
        model = load_pinned_model(Path(settings.semantic_model_cache_dir), configuration)
        batch_size = (
            args.batch_size
            if args.batch_size is not None
            else settings.semantic_embedding_batch_size
        )
    except (DevelopmentDatabaseError, OSError, ValueError, RuntimeError) as exc:
        print(f"Semantic embedding preflight failed: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 2
    try:
        import psycopg
    except ImportError:
        print(
            "PostgreSQL driver is not installed; install the storage optional dependency.",
            file=sys.stderr,
        )
        return 2
    try:
        with psycopg.connect(settings.database_url) as connection:
            prepare_development_connection(connection, target, create_schema=False)
            migrations = apply_migrations(connection, ROOT / "app/storage/migrations")
            repository = PostgresSemanticEmbeddingRepository(connection)
            repository.assert_no_source_hash_mismatch()
            sources = repository.eligible_narrative_sources()
            repository.register_configuration(configuration)
            inserted = existing = prepared = 0
            for source in sources:
                segments = prepare_embedding_segments(
                    source.chunk_id, source.text, model.tokenizer, configuration
                )
                vectors = encode_texts(
                    model, [segment.text for segment in segments], configuration, batch_size
                )
                added, reused = repository.insert_segments(configuration, source, segments, vectors)
                inserted += added
                existing += reused
                prepared += len(segments)
            connection.commit()
    except (
        DevelopmentDatabaseError,
        OSError,
        ValueError,
        RuntimeError,
        SemanticStorageError,
    ) as exc:
        print(f"Semantic embedding backfill failed: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1
    print(
        "Target: "
        f"database={target.database_name} role={target.role_name} schema={target.schema_name}"
    )
    print("Migrated: " + (", ".join(migrations) if migrations else "none (already current)"))
    print(f"Configuration hash: {configuration.configuration_hash}")
    print(
        "Embedded: "
        f"chunks={len(sources)} segments={prepared} inserted={inserted} existing={existing}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
