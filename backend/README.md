# EKT Bridge — Phase 1

A small, read-only FastAPI backend owned by **Dauren**. It serves process health and
normalized EKT product details. It does not implement the rest of the specification.

**Two application endpoints, one source of product evidence, no write operations.**

## What is included

| Endpoint | Purpose |
|---|---|
| `GET /health` | Process liveness, source mode, and the product-detail capability. Does not contact EKT. |
| `GET /api/products/{product_id}` | Fetch one detail record and return a documented Pydantic response. |

Interactive API documentation is at `/docs`; the schema is at `/openapi.json`.

**Not included:** sessions, carts, confirmation tokens, product listing/search,
analog candidates, warehouse reconciliation, purchase validation, stock reservation,
checkout, frontend, or LLM integration. There are no placeholder endpoints for them.

## Start locally

Use Python **3.11 or later**. From this archive's `backend/` directory:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
cp .env.example .env

python -m pytest -q
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --workers 1 --no-access-log
```

Keep the server running and use another terminal for the examples below.
Run commands from `backend/`, because that is where `.env` and `app/` are located.
The optional shortcuts `make test` and `make run` execute the same test/server commands
using the active Python environment.

### Try the offline example first

`.env.example` defaults to `EKT_MODE=mock`. No EKT access is required.
Only the supplied example product **515291** is available in this mode.
These are fixture values, not current supplier prices or inventory.

```bash
curl -sS http://127.0.0.1:8000/health | python -m json.tool
curl -sS http://127.0.0.1:8000/api/products/515291 | python -m json.tool

# Product not present in the mock fixture: HTTP 404.
curl -i http://127.0.0.1:8000/api/products/999

# Invalid identifier: HTTP 422, not an upstream request.
curl -i http://127.0.0.1:8000/api/products/0
```

Expected mock health body:

```json
{
  "status": "ok",
  "phase": 1,
  "source_mode": "mock",
  "upstream_status": "not_checked",
  "capabilities": {"product_detail": true}
}
```

Every application response has `X-EKT-Source: mock` or `X-EKT-Source: live`, a generated
`X-Request-ID`, and `Cache-Control: no-store`. Read the source header before presenting
product evidence. Neither health nor a configured path proves upstream availability.
CORS is disabled; cross-origin frontend integration is not configured in this phase.

## Live detail configuration

The specification supplies this integration information, **not a verified live result**:

```text
GET https://ekt.kz/api/products/detail?id={product_id}
```

Set `EKT_MODE=live` in `.env` and restart to enable the HTTP implementation. The client
uses only `EKT_BASE_URL`, `EKT_PRODUCT_DETAIL_PATH`, and the supplied `id` parameter.
It expects a top-level detail object with a positive integer `id` equal to the requested
ID. An unrecognized envelope, including an undocumented `data` wrapper, is rejected
rather than guessed. Nullable optional fields may be absent.

No live EKT call was made during this delivery. Authentication requirements and the
actual live detail envelope still need verification against the supplier contract.
No credentials, endpoints, or integration success are fabricated. List/search paths
and parameter mappings remain unknown and are deliberately absent from Phase 1.

The live client never falls back to the fixture. Operator-configured paths must stay
on the configured origin; redirects are disabled. Catalog `url_api_detail`, image URLs,
and product URLs are never followed. A single shared `httpx.AsyncClient` is created in
application lifespan and closed on shutdown. Requests have bounded time and response
size. There are no retries, caches, or hidden follow-up requests per product.

### Settings

| Variable | Default | Meaning |
|---|---|---|
| `EKT_MODE` | `mock` | Explicit fixture or live-HTTP source. |
| `EKT_BASE_URL` | `https://ekt.kz` | HTTP(S) origin only; non-local origins require HTTPS. |
| `EKT_PRODUCT_DETAIL_PATH` | `/api/products/detail` | Same-origin absolute path, without query or URL escapes. |
| `EKT_TIMEOUT_SECONDS` | `10` | Positive request timeout, at most 60 seconds. |
| `MAX_UPSTREAM_RESPONSE_BYTES` | `2097152` | Response limit; configurable from 1 KiB to 10 MiB. |

These are prototype defaults, not EKT operational limits. Settings are validated when
the application is created and are immutable afterward. Environment variables override
`.env`. Unrelated environment settings are ignored.

## Product normalization

The route never returns the raw supplier object. It returns `NormalizedProduct`,
containing identity/text fields, price, reported quantity, availability, warehouse
records, specifications, display URLs, issues, and derived readable warnings.

| Supplied property | Normalized field |
|---|---|
| `TORGOVAYA_MARKA` | `specifications.brand` |
| `OBYEM` | `specifications.product_type` |
| `KOLICHESTVO_POLYUSOV` | `specifications.poles` |
| `NOMINALNYY_TOK` | `specifications.rated_current` |
| `NOMINALNOE_NAPRYAZHENIE` | `specifications.rated_voltage` |
| `NOMINALNAYA_OTKLYUCHAYUSHCHAYA_SPOSOBNOST` | `specifications.breaking_capacity` |
| `TIP_USTANOVKI` | `specifications.installation_type` |
| `ARTIKULPOSTAVSHCHIKA` | `supplier_article` |

**Unknown is not zero.** Missing or unusable price, quantity, names, and specification
values remain `null`. Genuine reported zero remains zero. A missing quantity gives
`available: null`; a usable quantity gives `available: quantity > 0`. This is simple
field normalization, not a purchase validation service.

`total_quantity` comes exclusively from top-level `quantity`. Warehouse records are
mapped as received, without totals, duplicate reconciliation, positive-only filtering,
or claims that every warehouse is represented. Invalid warehouse identities are
skipped with an issue; unusable quantities remain null. Missing lists have an explicit
issue, rather than implying zero inventory. Advanced stock logic is deferred.

**Money is exact decimal text.** JSON numeric fractions are parsed directly as `Decimal`.
Responses serialize money as strings, for example `"64920"` or `"0.10"`, without assumed
currency or currency rounding. Boolean, negative, nonfinite, and malformed prices are
unusable. Whole-unit quantities cannot be fractional. Prototype bounds are 64-bit
positive product/warehouse IDs, quantities at most 1,000,000,000, and decimal scalars
with at most 100 digits and exponent magnitude at most 100.

Article strings preserve leading zeros and trailing underscores. A missing top-level
article is not replaced with `CML2_ARTICLE`. Brand and technical values are never guessed
from the title. Text must be rendered as untrusted data, not executable instructions or HTML.

The supplied product keeps structured rated current **`250 А`** and emits
`RATED_CURRENT_CONFLICT` with the title's **160A** and the property's **250A**. A small
current-token detector distinguishes explicit A/А tokens from `DRX250` and `18kA`/`18кА`;
multiple distinct tokens produce ambiguity instead of choosing a value. This is a
normalization warning, not electrical selection or analog logic.

`warnings` is computed from `issues`, so the two cannot contradict each other. An issue
contains `code`, `field`, `message`, and optional `observed_values`. Invalid scalar values
are preserved where safe; non-JSON numbers are represented as text, nested values by
type, and observed strings are capped at 1,024 characters. Nonempty or malformed
`offers` produces a variant-contract limitation; no variant selection is attempted.

## Error contract

```json
{
  "error": {
    "code": "EKT_API_UNAVAILABLE",
    "message": "The upstream catalog is unavailable.",
    "details": {"upstream_status": 503}
  },
  "request_id": "server-generated-id"
}
```

| HTTP | Code | Meaning |
|---|---|---|
| 404 | `PRODUCT_NOT_FOUND` | Upstream detail 404, or absent mock product. |
| 422 | `INVALID_PRODUCT_ID` | ID is not a positive integer within the prototype bound. |
| 503 | `EKT_API_UNAVAILABLE` | Timeout, connection/protocol error, upstream authentication failure, throttling, or server error. |
| 502 | `INVALID_EKT_RESPONSE` | Invalid JSON, wrong identity/envelope, oversized response, redirect, or other unexpected status. |
| 500 | `INTERNAL_ERROR` | Unexpected internal failure; public message is generic. |

Invalid JSON intentionally uses `INVALID_EKT_RESPONSE`, consistent with the supplied
specification, rather than adding a competing error code. Other transport validation
uses `VALIDATION_ERROR`; nonexistent routes use `NOT_FOUND`. Upstream bodies, request
headers, validation input values, and exception messages are not copied into public errors.
The bridge's routine logs contain operation/status metadata, not complete payloads.

## Read the code in this order

```text
app/config.py                      Validated settings
app/main.py                        Lifespan, wiring, error responses
app/api/health.py                  Liveness route
app/api/products.py                Detail route and input validation
app/clients/ekt_client.py           Async HTTP client and explicit mock source
app/services/product_service.py    Fetch → normalize
app/services/normalization.py      Pure field mapping and data-quality issues
app/schemas/product.py             Documented response models
```

`dependencies.py` supplies the small per-application service bundle. `exceptions.py`
defines the shared error type and envelope. There are no empty future-phase layers.

## Tests and delivery boundaries

```bash
python -m pytest -q
```

Tests cover only this phase: configuration, detail requests and errors, normalization,
health, response models, source separation, lifespan cleanup, application isolation,
and the absence of later-phase routes. Tests use `httpx.MockTransport` or injected
clients, enter application lifespan explicitly, and block real HTTP transport calls.
No external service or `respx` dependency is required.

See `VERIFICATION.md` for the actual run results and verification gaps. The pinned
requirements were retained from the inspected project and checked against the installed
environment; a clean package-index installation is a separate verification concern.

This is a **standalone Phase 1 extraction**, not a claim that the full project was never
implemented. The earlier `ekt-bridge-backend.zip` and mounted documentation were left
unchanged. The shared dependency pins, fixture, module naming, error envelope, and
relevant client/normalization conventions were reused. Later-phase code and its tests
were not included in this deliverable.

Framework reference material used during implementation:
[FastAPI lifespan](https://fastapi.tiangolo.com/advanced/events/),
[HTTPX transports](https://www.python-httpx.org/advanced/transports/), and
[Pydantic standard-library types](https://docs.pydantic.dev/latest/api/standard_library_types/).
These references are not verification of the EKT contract.
