# Grounded Product Copy Service

AI-generated product copy (headline + subline) that's verified against real product data before it ships — every factual claim is checked against a product's attributes or reviews, not just generated and trusted.

## Live Demo

- **App**: `https://grounded-copy-service.vercel.app/`
- **API docs**: `https://grounded-copy-service.onrender.com/docs`
- **Repo**: `https://github.com/dhra28/grounded-copy-service.git`
- **Demo API key** (use in `/docs` → Authorize, or as the `X-API-Key` header): `test-key-123`

## Tech Stack

- **Backend**: FastAPI, Python
- **Database**: PostgreSQL (hosted on Neon)
- **LLM**: Google Gemini (`gemini-3.5-flash-lite`)
- **Frontend**: React + Vite
- **Deployment**: Render (backend), Vercel (frontend)

## Architecture

```
React (Vercel) → FastAPI (Render) → PostgreSQL (Neon)
                        │
                        └──→ Gemini API
```

Two tables: `generated_copy` (cached results per product) and `eval_runs` (aggregate evaluation summaries).

## Setup

```bash
# Backend
cd backend
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # add DATABASE_URL, GEMINI_API_KEY, SERVICE_API_KEY
uvicorn app.main:app --reload

# Frontend
cd frontend
npm install
cp .env.example .env   # add VITE_API_BASE_URL, VITE_API_KEY
npm run dev
```

## API Endpoints

| Method | Endpoint | Description |
|---|---|---|
| `POST` | `/generate/{product_id}` | Generate (or return cached) copy for a product |
| `GET` | `/copy/{product_id}` | Fetch previously generated copy with citations |
| `POST` | `/eval/run` | Run the full evaluation across all products |
| `GET` | `/eval/results` | View the latest evaluation results |
| `GET` | `/products` | List all products with generation status |

All endpoints (except `/health`) require an `X-API-Key` header.

## Grounding & Citation Design

Every claim in generated copy is tagged with its source (a product attribute or a review ID) and passes through three verification layers before being accepted:

1. **Evidence pre-filtering** — reviews containing unusable claims (e.g. health/medical statements) are filtered out before the prompt is built, rather than relying on the model to recognize them.
2. **Structural and compliance checks** — length limits, banned words, and health/medical language.
3. **Groundedness verification** — attribute and review citations are checked for existence, and an LLM judge verifies that review-backed claims aren't exaggerated beyond what the source actually says.

If a generation fails verification, the system retries once with the specific failure reason, then falls back to a deterministic, attribute-only template if needed — ensuring the service never ships an unverified claim.

## Evidence Handling

The system is designed to handle imperfect data explicitly:
- **Conflicting reviews** → the model is instructed not to assert either side; verified copy relies on attributes instead.
- **Reviews contradicting specs** → verified attribute values take priority.
- **Missing reviews or attributes** → the system produces honest, generic copy rather than inventing detail.
- **Banned words in source data** (e.g. a product name) → excluded from the rule, since it applies only to generated copy.

## Evaluation

`POST /eval/run` generates and verifies copy across all products, reporting a programmatic pass rate, a groundedness pass rate (claim-level, LLM-judged), and repair/fallback counts. Results are viewable via `GET /eval/results` and in the dashboard.

## Engineering Notes

**Parameters**: `temperature=0.4` for generation (allows natural phrasing variation while staying controlled), `temperature=0.0` for the groundedness judge (consistency matters more than creativity when fact-checking). `max_tokens=3000` — sized for the model's internal reasoning overhead as well as the JSON output itself.

**Caching**: generated copy is stored keyed on `product_id`, so repeat requests return instantly without a new LLM call unless `force=true` is passed.

**Failure handling**: LLM timeouts and rate limits are retried once with a delay before falling back to a deterministic, attribute-only template — the service never returns an unverified claim, and a global exception handler prevents any unhandled error (e.g. a database hiccup) from crashing the API or leaking internal details in the response.

## Cost & Latency

Based on 18 real logged generations using `gemini-3.5-flash-lite`:

| Metric | Value |
|---|---|
| Avg latency (first-attempt pass) | 1.29s |
| Avg latency (with a repair) | 2.46s |
| Avg cost per generation | $0.000174 |
| Total cost, 18 products | $0.0031 |

At 100,000 products, sequential generation projects to roughly **$17 and 41 hours**. Cost is trivial at that scale, but time requires concurrency (batched parallel requests) rather than one-at-a-time processing — bounded in practice by the LLM provider's rate limits.

## Limitations & Future Work

- Health-claim filtering is currently English-only; multilingual review content would need a translation or classification step.
- Attribute verification confirms a cited field exists, but not that the claim text fully matches its value.
- Evaluation runs synchronously; at larger scale this would move to an async job with status polling.
- Would upgrade from `google-generativeai` (deprecated) to `google-genai` with more time.