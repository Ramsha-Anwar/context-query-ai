````
# ContextQuery AI: Data Model & Architecture

This document describes the database schema, relationships, and architectural decisions for ContextQuery AI. It is written for the next maintainer to understand not just *what* the tables are, but *why* they are designed this way.

## Entity-Relationship Diagram

```mermaid
erDiagram
    users ||--o{ hubs : "owns"
    users ||--o{ idempotency_keys : "scopes"
    hubs ||--o{ documents : "contains"
    hubs ||--o{ chunks : "contains"
    documents ||--o{ chunks : "contains"

    users {
        uuid id PK
        varchar email
        varchar password_hash
        user_role role
        boolean is_active
        timestamptz created_at
    }

    hubs {
        uuid id PK
        uuid owner_id FK
        varchar name
        varchar description
        text ai_summary
        jsonb suggested_questions
        timestamptz created_at
    }

    documents {
        uuid id PK
        uuid hub_id FK
        uuid owner_id FK
        doc_origin origin
        varchar filename
        doc_status status
        bytea file_bytes "Temporary storage"
    }

    chunks {
        uuid id PK
        uuid document_id FK
        uuid hub_id FK
        uuid owner_id FK
        integer chunk_index
        text text
        vector embedding "384 dimensions"
    }

    idempotency_keys {
        uuid user_id PK, FK
        uuid key PK
        varchar request_hash
        idem_status status
        jsonb response_body
    }
````

## Table-by-Table Breakdown

### 1. `users`

Purpose: The tenant root. Every row represents an isolated business account.

Relationships: One-to-many with `hubs`, `documents`, `chunks`, and `idempotency_keys`.

Non-obvious design decision: We use a unique index on `lower(email)` rather than a standard `UNIQUE(email)` constraint. This prevents users from creating multiple accounts by simply changing the casing of their email (e.g., `Alice@x.com` vs `alice@x.com`).

### 2. `hubs`

Purpose: Represents a logical grouping of knowledge (e.g., "HR Policies" or "Project Phoenix").

Relationships: Belongs to a `user`. Contains many `documents` and `chunks`.

Non-obvious design decision: There is no `content` column on this table. All knowledge is stored in the `documents` table, even if it was submitted as inline text. This enforces a unified content model, meaning the RAG query path and evidence verifier only ever have to look in one place.

### 3. `documents`

Purpose: Represents a single uploaded file (PDF, TXT) or inline text block.

Relationships: Belongs to a `hub` and a `user`. Contains many `chunks`.

Non-obvious design decision: The `file_bytes` column holds the raw binary data temporarily. Once the state machine reaches the `chunking` phase, this column is set to `NULL` to save storage space. If a document is `ready`, the bytes are gone, and only the text `chunks` remain.

### 4. `chunks`

Purpose: The core of the RAG system. Holds the text fragments and their 384-dimensional embeddings.

Relationships: Belongs to a `document`, `hub`, and `user`.

Non-obvious design decision: We denormalize `owner_id` and `hub_id` onto this table, even though they can be derived via `document → hub → user`. We do this because vector search is the most expensive query in the system. By duplicating these IDs, we can filter by tenant before doing the cosine distance calculation, without needing a triple-table `JOIN`.

### 5. `idempotency_keys`

Purpose: Ensures that network retries don't duplicate data or burn AI quota.

Relationships: Belongs to a `user`.

Non-obvious design decision: The primary key is a composite of `(user_id, key)`. This ensures that two different users can use the exact same UUID for their idempotency key without colliding.

## Constraint Rationale

Application code is fallible and subject to race conditions. These constraints enforce data integrity at the database level.

| Constraint                                         | What it prevents                                                 | Why it is in the schema, not application code                                                                                                                                 |
| -------------------------------------------------- | ---------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `UNIQUE (owner_id, name)` on `hubs`                | Two hubs with the exact same name for one user.                  | A Python check has a race condition. Two concurrent requests could both pass the check and insert duplicates. The database enforces this atomically.                          |
| `PRIMARY KEY (user_id, key)` on `idempotency_keys` | Replay attacks or accidental duplicate processing.               | Guarantees that a single user can only claim an idempotency key once. The `ON CONFLICT DO NOTHING` insert relies on this index to resolve races.                              |
| `UNIQUE (hub_id, checksum_sha256)` on `documents`  | Uploading the exact same file twice to the same hub.             | Saves storage space, prevents duplicate embeddings, and prevents wasted AI processing time.                                                                                   |
| `vector(384)` on `chunks`                          | Dimension mismatch between the database and the embedding model. | FastEmbed's `bge-small-en-v1.5` outputs exactly 384 floats. If we swapped models and the dimensions changed, the insert would fail immediately, preventing a corrupted index. |

## Query Plans (EXPLAIN ANALYZE)

To verify our indexes are working, we seeded the database with 100,000 chunks across 50 documents and ran `EXPLAIN ANALYZE` on the two most critical queries.

### 1. Hub List (B-Tree Index)

Query: Fetching a user's hubs sorted by creation date.

```
EXPLAIN ANALYZE SELECT * FROM hubs WHERE owner_id = '...' ORDER BY created_at DESC LIMIT 20;
```

Output:

```
Limit  (cost=8.17..8.18 rows=1 width=886) (actual time=0.026..0.028 rows=10.00 loops=1)
  Buffers: shared hit=2
  ->  Sort  (cost=8.17..8.18 rows=1 width=886) (actual time=0.026..0.027 rows=10.00 loops=1)
        Sort Key: created_at DESC
        Sort Method: quicksort  Memory: 26kB
        Buffers: shared hit=2
        ->  Index Scan using uq_hub_name_per_owner on hubs  (cost=0.14..8.16 rows=1 width=886) (actual time=0.017..0.021 rows=10.00 loops=1)
              Index Cond: (owner_id = '7eabfcfc-1fc8-4128-94c8-85d51cf197cf'::uuid)
              Index Searches: 1
              Buffers: shared hit=2
Planning Time: 0.073 ms
Execution Time: 0.050 ms
```

Reasoning: Postgres uses an `Index Scan` using `uq_hub_name_per_owner` instead of a `Seq Scan`. This is because the composite index perfectly matches the `WHERE` clause (`owner_id`). The database can jump straight to the user's hubs in the correct order, avoiding a memory sort. Because the user only has 10 hubs, Postgres opted for a `quicksort` in memory rather than a full index scan for the date sort.

### 2. Vector Search (HNSW Index)

Query: Finding the top 5 most similar chunks for a user.

```
EXPLAIN ANALYZE SELECT id, text FROM chunks WHERE owner_id = '...' AND hub_id = '...' ORDER BY embedding <=> '[...]' LIMIT 5;
```

Output:

```
Limit  (cost=26689.89..26689.90 rows=5 width=89) (actual time=26.378..26.381 rows=5.00 loops=1)
  Buffers: shared hit=25003
  ->  Sort  (cost=26689.89..26714.73 rows=9937 width=89) (actual time=26.377..26.378 rows=5.00 loops=1)
        Sort Key: ((embedding <=> '[0.1,0.1,...]'::vector))
        Sort Method: top-N heapsort  Memory: 26kB
        Buffers: shared hit=25003
        ->  Seq Scan on chunks  (cost=0.00..26524.84 rows=9937 width=89) (actual time=0.014..25.341 rows=10000.00 loops=1)
              Filter: ((owner_id = '7eabfcfc-1fc8-4128-94c8-85d51cf197cf'::uuid) AND (hub_id = 'c5abe460-cf72-4a4b-ae77-8a193eebc712'::uuid))
              Rows Removed by Filter: 90000
              Buffers: shared hit=25000
Planning Time: 0.763 ms
Execution Time: 26.466 ms
```

Reasoning: For 10,000 chunks, Postgres's query planner intelligently chose a `Seq Scan` combined with a top-N heapsort. Because the `owner_id` and `hub_id` filters reduce the dataset to 10,000 rows, it is faster to scan those rows and sort them in memory than to traverse the HNSW index. As documented below, this exact query will be the first to break when the table grows, at which point Postgres will automatically switch to the `ix_chunks_embedding` HNSW index.

## Similarity Threshold Decision

During the RAG query, we filter out chunks that do not meet the `RAG_MIN_SIMILARITY` threshold (default `0.25`).

Why a static threshold?

Without a threshold, the vector search will always return the "closest" 5 chunks, even if the user asks a question completely unrelated to the document (e.g., asking "What is the capital of France?" to an HR policy hub). A static threshold of `0.25` using FastEmbed's cosine distance acts as a safety net. If the highest similarity score is below this, the system returns `grounded: false` without calling the LLM, saving tokens and preventing hallucinations.

Tuning: The threshold was tuned using a custom evaluation script that sweeps values against the golden dataset to find the optimal balance between recall and precision.

## First-to-Break at 10× Scale

The Query: The vector similarity search (`ORDER BY embedding <=> ...`).

Why it breaks: As the database grows to 1 million+ chunks, the `Seq Scan` seen in the query plan above will take over 260ms per query. If Postgres switches to the HNSW index to compensate, the index itself will grow to roughly 1.5GB in memory. Neon's free tier has limited RAM, and when the index exceeds available memory, Postgres will be forced to read from disk, causing massive latency spikes. Furthermore, inserting new documents will become extremely slow because HNSW indexes are expensive to update.

Mitigation considered and rejected:

We considered partitioning the `chunks` table by `owner_id`. However, we rejected this for v2.0 because Postgres does not natively support partition pruning inside an HNSW index lookup. If we reach 10× scale, the correct mitigation is to migrate the vector search to a dedicated vector database (like Pinecone, Qdrant, or Weaviate) that supports disk-based indexes (like IVF-PQ) and horizontal sharding.

