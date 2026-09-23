# Phase 1 verification

Verification performed on 2026-09-23 in the provided Linux environment with
Python **3.13.5**. This report applies only to the standalone
Phase 1 project, not to the earlier full-backend archive.

## Executed checks

| Check | Actual result |
|---|---|
| First `python -m pytest -q` run | **154 passed in 1.34s** |
| Final working-tree `python -m pytest -q` run | **154 passed in 1.14s** |
| `python -m compileall -q app tests` | Exit status 0 |
| `python -m pip install --no-index -r requirements.txt` | Exit status 0; all requirements already installed |
| Uvicorn localhost smoke check in explicit mock mode | **6 checks passed**; application shutdown completed |

The exact final working-tree pytest output is in `test-results.txt`.
The server check results are in `smoke-results.json`.
The extracted-package test run is recorded in `package-test-results.txt`.

No Phase 1 pytest failures were observed. The first server-check helper incorrectly
required exit code 0 after sending SIGTERM. All endpoint assertions had passed and
Uvicorn logged application shutdown completion, but the process returned -15.
The helper was corrected to require shutdown completion and accept either 0 or the
SIGTERM return code; the entire server check was rerun successfully. No application
code change was needed for that helper error.

## What the tests exercise

The suite contains parameterized cases for configuration, HTTP detail success and
failures, invalid JSON, invalid envelopes and identities, redirects, arbitrary catalog
URLs, bounded bodies, exact Decimal parsing/serialization, nullable fields, all eight
property mappings, the supplied current conflict, malformed optional values, basic
warehouse field mapping, source separation, per-application lifespan and client
shutdown, error envelopes, and safe diagnostics.

An OpenAPI assertion requires exactly `/health` and `/api/products/{product_id}`.
Another check confirms there are no cart, sessions, stock, or analog routes.
The network transport is blocked by an autouse fixture: tests require no external
service and cannot silently make live EKT requests.

The localhost smoke check exercised health, known product detail, missing mock product,
invalid ID, the exact OpenAPI endpoint surface, and the API documentation route.
It used a real single-worker Uvicorn process and a local TCP connection, not ASGITransport.

## Installed direct dependencies used

- `fastapi==0.128.2`
- `uvicorn==0.48.0`
- `httpx==0.28.1`
- `pydantic==2.13.4`
- `pydantic-settings==2.14.1`
- `pytest==9.0.2`
- `pytest-asyncio==1.3.0`

The requirement pins were copied from the inspected earlier project. `respx` is not
required; the tests use HTTPX MockTransport and injected clients.

## Verification limits

No live request to EKT was made. The supplied detail path is implemented but not
independently validated against production. The live detail envelope and any required
authentication still need supplier confirmation. There is no mock fallback in live mode.

The dependency command above checked the already-installed environment without a package
index. It is **not** evidence of a clean virtual-environment install, package-index
availability, or tests on Python 3.11/3.12/macOS. Only Python 3.13.5
on this Linux environment was exercised.

No tests or implementation for carts, confirmations, analog search, or advanced stock
were added to this Phase 1 project. No production-readiness claim is made.

## Source preservation

Inspected archive: `ekt-bridge-backend.zip`, SHA-256
`335c3e23b312a729ee068c1e05386de35ad426582a03b876fe48205dd9670ad1`.
The source archive and mounted earlier documents remain unchanged. The Phase 1 fixture
was copied byte-for-byte from its supplied-conflict fixture. No unrelated repository
files were deleted or overwritten.
