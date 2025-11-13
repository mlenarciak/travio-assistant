# Product Requirements Document (PRD): Travio API Functional Analysis and Test Plan

## 1. Overview
- API: Travio API v2.7.0 (OpenAPI 3.1.0)
- Base URL: `https://api.travio.it`
- Security: JWT bearer (except `/auth`)
- Scope covered:
  - Authentication: `POST /auth`
  - Generic Repositories: `GET/POST /rest/{repository}`, `GET/PUT/DELETE /rest/{repository}/{id}`
  - Booking: `POST /booking/search` (multi-step availability and selection)

## 2. Objectives and Success Criteria
- Provide high-confidence functional coverage across primary surfaces (Auth, REST repositories, Booking flow).
- Validate positive, negative, boundary, and security behaviors.
- Verify conformance to schemas: required fields, types, enums, and links.
- Confirm pagination, sorting, filtering, unfolding links, and error surfaces.
- Acceptance criteria:
  - Auth returns token for valid id/key; rejects invalid.
  - Repositories list honor `filters`, `sort_by`, pagination, `unfold`.
  - Repository CRUD behaves as specified, including options and read-only semantics.
  - Booking search handles multiple service types, multi-room occupancy, segments, `expand_next_step`, and returns `groups`, `step`, `pick_type`, `warnings` consistently.

## 3. Non-Goals
- Full supplier/provider integration testing beyond API surface.
- Performance/latency SLAs (covered at high level in Modernization section).

## 4. Test Environments
- Staging environment with seeded data for each repository.
- Secrets management for `id` and `key` used by `/auth`.
- Dedicated accounts to run destructive CRUD tests without affecting production.

## 5. High-Level Test Matrix

### 5.1 Authentication `/auth`
- Positive: valid `id` + `key` -> token returned.
- Negative: missing field, wrong types, invalid creds -> 401.
- Error: malformed JSON -> 500 (or 4xx if validated earlier).

### 5.2 Repositories `/rest/{repository}` and `/rest/{repository}/{id}`
- List: baseline fetch, pagination (`page`, `per_page`), sorting (`sort_by`), filters (`filters` JSON), unfold link fields (`unfold` comma list).
- Create: basic create; `options.allow_id` true/false; per-entity rules (e.g., master-data VAT checks); read-only props ignored.
- Get: fetch item; `unfold` on link fields.
- Update: patch subset via `data` object; read-only props ignored.
- Delete: delete item; 404 on missing.
- Security: unauthorized (401), forbidden (403) for protected repos.

### 5.3 Booking `/booking/search`
- Single search type (e.g., hotels) with occupancy.
- Multi-search in one request (e.g., flights + hotels).
- Date-range vs segments (mutually exclusive constraints).
- `expand_next_step` true/false; verify `groups`, `pick_type`, `final`, and `allow_partial` behavior.
- Filters/sorting/per_page at search level.
- Tags & `client_country` usage.

## 6. Detailed Test Cases (Representative)

### 6.1 Auth
1. Valid credentials -> 200 { token }
2. Invalid credentials -> 401
3. Missing `id` or `key` -> 401
4. Wrong types (`id` as string) -> 401 or 4xx validation

Curl example:
```
curl -sS -X POST "$BASE/auth" \
  -H 'Content-Type: application/json' \
  -d '{"id": 1234, "key": "<redacted>"}'
```

### 6.2 Repositories: List
1. Baseline list airports
```
GET /rest/airports
```
2. Pagination and sorting
```
GET /rest/airports?page=2&per_page=20&sort_by={"code":"asc"}
```
3. Filters (JSON-encoded in query)
```
GET /rest/services?filters={"type":{"op":"eq","value":1}}
```
4. Unfold link fields
```
GET /rest/services?unfold=classification_id,category
```
5. Unauthorized (missing token) -> 401

### 6.3 Repositories: Create
1. Create `master-data` with VAT check true (default)
2. Create `master-data` with `options.check_vat=false`
3. `options.allow_id=true` to preserve a known id
4. Attempt to set read-only field (ignored)

Curl example:
```
curl -sS -X POST "$BASE/rest/master-data" \
  -H "Authorization: Bearer $TOKEN" \
  -H 'Content-Type: application/json' \
  -d '{"data": {"profiles": ["customer"], "name": "Mario", "surname": "Rossi"}, "options": {"check_vat": false}}'
```

### 6.4 Repositories: Get/Update/Delete
1. Get: `GET /rest/master-data/{id}` with/without `unfold`.
2. Update: `PUT /rest/master-data/{id}` with minimal `data` subset; ensure read-only ignored.
3. Delete: `DELETE /rest/master-data/{id}`; repeat delete -> 404.

### 6.5 Booking: Search and Steps
1. Hotels search with occupancy and dates.
2. Flights search with round-trip `segments`.
3. Mixed search (flights + hotels) with `expand_next_step=true`.
4. Validate `groups[idx].type` and `pick_type` contract; `final=true` gating for add-to-cart.
5. Partial exploration (`allow_partial=true`) returns `partial=true` and cannot be used for next step.

## 7. Data Validation Rules (Selected)
- Enums honored (e.g., `services.type`, `services.show_prices`, VAT type enums, etc.).
- Read-only properties must not be writable (`id`, `full_number`, computed amounts).
- Link fields (`format: link:...`) unfolded via `unfold`.
- Files use base64+mime when writing; strings (URLs) when reading.

## 8. Tooling and Artifacts
- Sample payloads in `api analysis/samples`.
- Workflow diagrams and ERD in `api analysis/diagrams.mmd`.
- In-depth LaTeX paper in `api analysis/travio_api_analysis.tex`.

## 9. Risks and Mitigations
- Ambiguity in filter grammar: define a minimal operator set and examples.
- Data dependencies: seed fixtures for each repository and isolate destructive tests.
- Booking provider variability: validate core contract properties and warn on provider-specific deviations.

## 10. Acceptance Checklist
- [ ] All endpoints tested for 200/401/403/404/500 where applicable.
- [ ] Pagination, sorting, filtering, unfolding validated.
- [ ] CRUD semantics verified; read-only enforcement observed.
- [ ] Booking multi-step flow verified (`groups`, `step`, `pick_type`, `final`).
- [ ] Artifacts generated and stored in repo.

## 11. Modernization Opportunities (Preview)
- See the LaTeX paper for the full modernization and scale blueprint; highlights include: typed clients and server, query DSL for filters, OpenAPI-first CI checks, telemetry and SLOs, idempotency, outbox, and CRM event streaming.

