# MongoDB and Qdrant Production Data Pipeline

## Current data responsibilities

- MongoDB is the source of truth for scheme records. Qdrant is a derived retrieval index.
- The Qdrant indexing script reads `schemes_enriched` by default.
- The current application also has paths that read `schemes`, including candidate intake and hydration fallback. Keep both collections available for the full application unless those paths are deliberately removed or redirected.
- Each Qdrant point includes a `mongo_ref` with its MongoDB database, collection, document ID, and scheme URL. The application uses that reference to hydrate retrieved schemes.

## Integrity requirement

The MongoDB reference stored with a Qdrant point must resolve to the corresponding scheme document. Preserve MongoDB `_id` values when copying collections. Build the production Qdrant index from the production or staging MongoDB data, using the matching database and collection names, so the payload references point to the documents the deployed application can read.

Before promoting a collection, verify that sampled (and, where practical, all) Qdrant `mongo_ref` values resolve to MongoDB documents and that the resolved document has the expected scheme URL. A vector count alone does not establish that retrieval results can be hydrated.

## Recommended promotion workflow

1. Copy `schemes` and `schemes_enriched` to an isolated MongoDB Atlas staging database, preserving document IDs and required indexes.
2. Validate the staged documents and their relationships. Keep the database name and collection names consistent with the values used by the indexer and application.
3. Build a versioned Qdrant staging collection from the staged `schemes_enriched` data. Keep the indexing manifest and visible batch logs for that run.
4. Check collection schema, point counts, embedding model/profile configuration, and MongoDB reference integrity. Run a small retrieval smoke check against the staging collection.
5. Promote by changing the deployed environment configuration to the validated MongoDB and Qdrant targets. Retain the previous collection/configuration until the new target has been confirmed, so rollback is a configuration change.

Do not update MongoDB and Qdrant independently in place as the normal release process. Treat a MongoDB data revision and its derived Qdrant collection as one promotion unit.

## Incremental synchronization

Local-to-production sync tooling is not implemented yet. When added, it should support dry-run output, explicit source/target selection, resumable and visible progress, an auditable change summary, and a validation step before promotion. It must define how updates and deletions are reconciled in both MongoDB and Qdrant; do not assume that upserting changed records also removes stale vectors.

Prefer a separate staging environment (staging MongoDB database and Qdrant collection) over relying on a long-lived Git `staging` branch for data safety. A Git branch controls code; it does not isolate databases. Deploying a reviewed candidate to staging and promoting its validated data/configuration keeps those responsibilities explicit.

Keep database URIs, API keys, and other credentials in environment secrets; never commit them in configuration files or manifests.
