
# ContextQuery AI

**Live API:** [https://contextquery-api.onrender.com/docs](https://contextquery-api.onrender.com/docs)  
**Web Console:** [https://context-query-ai-frontend.vercel.app/](https://context-query-ai-frontend.vercel.app/)  
**Repository:** [https://github.com/Ramsha-Anwar/context-query-ai](https://github.com/Ramsha-Anwar/context-query-ai)

## What it does

ContextQuery AI is a zero-cost, multi-tenant B2B SaaS backend. Users create isolated **Knowledge Hubs**, add knowledge by pasting text or uploading PDFs, and ask natural-language questions. Answers are generated using **Groq** and retrieved via **pgvector** similarity search over chunked, embedded documents.

Every write path is idempotent, every query is strictly tenant-isolated, and the RAG pipeline is gated by a custom LLM-as-a-Judge evaluation suite.

## Tech Stack

- **Backend:** Python 3.11, FastAPI, SQLAlchemy 2.0, Alembic
- **Database:** PostgreSQL with `pgvector` (Neon)
- **AI Generation:** Groq (`openai/gpt-oss-120b`)
- **AI Embeddings:** FastEmbed (`BAAI/bge-small-en-v1.5`) running locally via ONNX
- **Evaluation:** Custom LLM-as-a-Judge suite (Faithfulness, Relevancy, Recall@5, MRR)
- **Deployment:** Docker, Render (API), Vercel (Frontend), Neon (DB)

## Authentication and Isolation

- Every protected route requires a valid JWT (`Authorization: Bearer <token>`).
- Tenant isolation is enforced at the repository layer. Cross-tenant reads, lists, and deletes return a cloaked `404 HUB_NOT_FOUND` (never a 403, which would leak existence).
- Vector search filters by `owner_id` and `hub_id` *before* calculating cosine distance.
- Proven by tests: `test_user_b_cannot_read_user_a_hub`, `test_vector_search_is_scoped_to_owner`.

## Retry Safety

If a network drops during a write, retrying is safe. For `POST /hubs` and `POST /hubs/{id}/documents`, provide an `X-Idempotency-Key` header (UUIDv4).

The server hashes the request body and stores it with your key. If you retry with the same key and same body, the server returns the original cached response with `Idempotent-Replayed: true`, without creating duplicate rows or burning AI quota.

## Errors

Every error uses a standard JSON envelope.

**Field-level error (422):**

```json
{
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "Request validation failed.",
    "status": 422,
    "request_id": "7c9e6679-7425-40de-944b-e07fc1f90ae7",
    "details": [
      {
        "field": "body.name",
        "reason": "string_too_short",
        "message": "String should have at least 1 character"
      }
    ]
  }
}
````

Non-field error (404):

```
{
  "error": {
    "code": "HUB_NOT_FOUND",
    "message": "Hub not found.",
    "status": 404,
    "request_id": "7c9e6679-7425-40de-944b-e07fc1f90ae7",
    "details": []
  }
}
```

## Measured RAG Quality

Evaluated on a 50-question golden dataset (run on 2026-10-25).

- Faithfulness: 0.92 (Gate ≥ 0.70)
- Answer Relevancy: 0.98 (Gate ≥ 0.70)
- Recall\@5: 0.98 (Gate ≥ 0.85)
- MRR: 0.98 (Gate ≥ 0.65)

## Cost and Latency

- Cost: $0.00/month (Render free tier, Neon free tier, Groq free tier, Vercel free tier).
- Latency: Avg query response \~2.5s (dominated by Groq generation).
- Cold Starts: Render free tier sleeps after 15 mins. A cron-job pings `/healthz` every 10 minutes to keep it warm. This is a workaround, not a guarantee.

## Run Locally

### Using Docker (Recommended)

```
git clone https://github.com/Ramsha-Anwar/context-query-ai.git
cd context-query-ai
cp .env.example .env
# Add your GROQ_API_KEY and DATABASE_URL to .env
docker compose up -d
alembic upgrade head
```

The API is now running at `http://localhost:8000`.

### Bare Metal

```
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt -r requirements-dev.txt
alembic upgrade head
uvicorn app.main:app --reload
```

## Tests

```
# Fast tests (mocks the AI layer)
pytest -q -m "not eval"

# Full 50-question evaluation gate (requires real GROQ_API_KEY)
pytest -q -m eval -s
```

## Try it (cURL)

```
# Create a hub with inline text
curl -X POST https://<YOUR_RENDER_URL>/api/v1/hubs \
  -H "Authorization: Bearer YOUR_JWT_TOKEN" \
  -H "X-Idempotency-Key: $(uuidgen)" \
  -H "Content-Type: application/json" \
  -d '{"name": "HR Policies", "content": "Employees get 20 days of annual leave."}'
```

## Environment Variables

| Variable              | Description                                       |
| --------------------- | ------------------------------------------------- |
| `DATABASE_URL`        | Postgres connection string (pooled).              |
| `DIRECT_DATABASE_URL` | Postgres connection string (direct, for Alembic). |
| `JWT_SECRET_KEY`      | 32+ byte random string for HS256.                 |
| `GROQ_API_KEY`        | API key for Groq generation.                      |
| `GROQ_MODEL`          | `openai/gpt-oss-120b`                             |
| `EMBEDDING_DIM`       | `384`                                             |
| `RAG_MIN_SIMILARITY`  | `0.25` (threshold to prevent hallucinations)      |
| `CORS_ORIGINS`        | Comma-separated allowed origins (Vercel URL).     |

## What we fixed vs. what we documented

| Fixed                                              | Documented as trade-off                        |
| -------------------------------------------------- | ---------------------------------------------- |
| Cross-chunk retrieval via multi-query expansion    | Fixed-size chunking (no semantic boundaries)   |
| Refusal path when retrieval similarity is too low  | In-memory rate limiter (single instance)       |
| Retrieval evaluation (Recall\@5 + MRR) in the gate | Client-driven ingestion (no background worker) |
| Idempotent document `process` state machine        | PDF text extraction (not layout-aware)         |

### Architectural Deviations from PRD

- Generation: The PRD specified Gemini. We use Groq (`openai/gpt-oss-120b`) because the Gemini free tier capped at 20 requests/day, making CI evaluation impossible.
- Embeddings: The PRD specified Gemini Embeddings. We use FastEmbed (`bge-small-en-v1.5`) running locally to save memory on Render's 512MB free tier.
- Evaluation: The PRD specified RAGAS. We built a custom LLM-as-a-Judge suite because RAGAS had unresolvable C++/LangChain dependency conflicts.

## Known Limitations

- Fixed-size chunking with overlap; no semantic chunking.
- Single-instance rate limiter (will break if scaled to multiple servers).
- No update endpoints for hubs or documents.
- The database schema and query plans are detailed in `DATA_MODEL.md`.

