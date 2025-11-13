# Travio API Assistant – Product Requirements Document

## 1. Background & Problem Statement
- Travio partners need a lightweight tool to interact with core CRM and booking features without building a custom UI for each workflow.
- Customer‐facing teams currently rely on manual API calls or the full Travio back office to perform quick checks (customer lookup, property availability, quote issuance).
- Goal: ship a locally runnable web application (FastAPI backend + Streamlit UI) that accelerates routine operations while showcasing Travio API capabilities outlined in *Travio API Docs – Revision 2.6.0*.

## 2. Product Goals
- Enable authenticated, credentialed users to execute common Travio API workflows from a friendly UI.
- Reduce time to validate customer records, add new CRM entries, search inventory, and dispatch quotes.
- Provide an extendable foundation for future feature demos or partner onboarding.

### Non-Goals
- Replace Travio back office or handle full reservation lifecycle beyond quote placement.
- Provide anonymous access; all interactions require valid Travio API credentials.
- Support mobile form factor or an automated deployment pipeline (local run only).

## 3. Personas & Use Cases
- **Sales Agent / Customer Support** – needs to confirm if a traveler is already in CRM, add missing details, and issue quick quotes.
- **Implementation Consultant** – demonstrates Travio API workflows to new partners, expects readable request/response payloads.
- **Developer Evaluator** – validates API behavior before integrating Travio into production systems.

## 4. Assumptions & Dependencies
- Travio API credentials (id/key for `POST /auth`) are provided via environment variables or `.env.local` file.
- Network access to `https://api.travio.it/` is available from the user’s machine.
- The app will run entirely on localhost; no hosting requirements.
- PDF documentation references the canonical Swagger spec (`https://swagger.travio.it/`) for field definitions. Any gaps in the PDF must be reconciled against Swagger during implementation.
- User will run the app inside a Python virtual environment (Python ≥ 3.10).

## 5. Functional Requirements

### 5.1 Authentication & Session Management
- Prompt user for Travio `id` and `key` or load from local config.
- Call `POST /auth` to retrieve bearer token; cache in backend session until expiry.
- Show token status (valid/expired) in UI; allow manual refresh.
- Optional: support `POST /login` (username/password) to emulate staff login and display retrieved profile (`GET /profile`).

### 5.2 CRM – Customer Lookup
- Allow search by email, phone, surname, or Travio client code.
- Display table of matching clients with key fields (name, contact info, country, tags, notes).
- Surface raw JSON response in an expandable panel for debugging.
- If PDF/Swagger confirms filtering schema, use list endpoint (e.g., `GET /master-data/clients` with query parameters such as `filter[...]` or pagination as defined). Otherwise, document assumptions and provide graceful error if unsupported.

### 5.3 CRM – Add / Update Client
- Provide form matching required CRM fields (name, category, contact details, marketing consent).
- Validate inputs client-side (mandatory fields, country ISO code, date formats).
- Submit via `POST /master-data/clients` (create) and `PUT /master-data/clients/{id}` (update). Capture returned IDs.
- Show success toast + response payload; handle and display API validation errors.

### 5.4 Property Search & Availability
- Support hotel/property searches via booking flow:
  - Step 1: configure search criteria (`type`, `from`, `to`, `geo`/`ids`/`codes`, occupancy list) and execute `POST /booking/search`.
  - Step 2: paginate through results using `POST /booking/results` if necessary (per API doc).
  - Display summary cards with price, board basis, supplier, cancellation notes, and other metadata from response groups.
  - Maintain the returned `search_id` and expose progressed steps (groups, pick types).
- Provide filtering options (price, board, supplier) leveraging `return_filters`.

### 5.5 Quote Composition & Delivery
- Allow users to “pick” a room/package (`POST /booking/picks`) based on group requirements until `final = true`.
- Support adding selection to cart (`PUT /booking/cart`) and retrieving cart data (`GET /booking/cart/{cart_id}`).
- Permit marking reservation as quote by calling `POST /booking/place/{cart_id}` with `status = 0`, optional `due` date, passenger details (pax list from cart).
- Provide quick action to send quote email/PDF via `POST /tools/print/reservation/{reservation_id}` with `template` and `send = true`.
- Display confirmation with reservation ID, payment link (if requested), and status.

### 5.6 Audit & History
- Log all performed API calls (timestamp, endpoint, payload, status code) in backend and display in Streamlit “Activity” tab for troubleshooting.
- Allow export of session log to JSON.

### 5.7 Mock / Demo Mode
- If live API credentials are unavailable, allow switching to a mock backend that returns canned responses for core flows. Provide toggle and label UI clearly as “Demo data”.

## 6. API Integration Details

| Workflow | Endpoint | Method | Key Inputs | Key Outputs |
| --- | --- | --- | --- | --- |
| Authenticate | `/auth` | POST | `{"id": <int>, "key": "<string>"}` | `token`, expiry |
| Validate token | `/profile` | GET | Bearer token | User profile or `null` |
| CRM search* | `/master-data/clients` (assumed list endpoint) | GET | Query/filter params per Swagger (e.g., `page`, `per_page`, filters) | Paginated client records |
| CRM detail* | `/master-data/clients/{id}` | GET | `id` | Client object |
| CRM create* | `/master-data/clients` | POST | Client payload | Created client with `id` |
| CRM update* | `/master-data/clients/{id}` | PUT | Partial/complete payload | Updated client |
| Property search | `/booking/search` | POST | `type`, `from`, `to`, `geo/ids`, `occupancy`, optional filters | `search_id`, groups |
| Fetch more results | `/booking/results` | POST | `search_id`, `page`, `per_page`, filters | Paginated groups/items |
| Make selections | `/booking/picks` | POST | `search_id`, `step`, selections array | Next step groups or `final = true` |
| Cart add | `/booking/cart` | PUT | `search_id` | Cart object w/ items |
| Cart get | `/booking/cart/{cart_id}` | GET | `cart_id` | Cart object |
| Cart remove | `/booking/cart` | DELETE | `search_id` | Cart object |
| Place reservation (quote) | `/booking/place/{cart_id}` | POST | `pax`, `status`, `due`, `notes`, `payment_link` | Reservation payload |
| Send quote email | `/tools/print/reservation/{reservation_id}` | POST | `template`, `archive?`, `send?` | PDF metadata / status |

\* Exact client endpoints/parameters must be validated against Swagger; flag as dependency.

**Headers & Formats**
- `Authorization: Bearer <token>` for all requests after auth.
- `Content-Type: application/json`.
- Optional `X-Lang` header to request localized responses (supported values: it, en, de, ru, es, fr).
- Date format `yyyy-mm-dd`; datetime `yyyy-mm-dd hh:mm:ss`.

## 7. UX & Interaction Design
- Streamlit multi-tab layout:
  1. **Dashboard** – credential status, quick stats, activity log.
  2. **CRM Search** – input form, results table, detail drawer, add/update modal.
  3. **Property Search** – search form, results grid with filters, selection wizard.
  4. **Quote Builder** – review selected items, enter pax details, set quote metadata, trigger place/send actions.
  5. **Settings** – credential management, environment toggle (live/mock), language preference.
- Each major action shows toast/alert for success/errors and optionally reveals underlying JSON for technical users.
- Persist minimal state in Streamlit session_state; rely on FastAPI for data orchestration.

## 8. Data & State Management
- FastAPI maintains in-memory store for:
  - Active bearer token & expiry timestamp.
  - Cached lookups (recent clients, last search results) with TTL to reduce API chatter.
  - Activity log entries.
- Streamlit requests data from FastAPI endpoints via HTTP (e.g., `/api/clients/search`, `/api/booking/search`), enabling future separation of frontend/backend.
- For demo mode, FastAPI serves responses from JSON fixtures stored in `data/mock/*.json`.

## 9. Technical Architecture
- Python virtual environment managed with `venv`.
- Dependencies: `fastapi`, `uvicorn`, `httpx` (async client), `pydantic`, `python-dotenv`, `streamlit`, `streamlit-aggrid` (tabular UI), `loguru` (structured logging), `pytest` for tests.
- Backend (FastAPI):
  - Modular routers: `auth`, `crm`, `booking`, `quotes`, `mock`.
  - Central Travio client wrapper handling headers, retries, error parsing.
  - Background task to auto-refresh token close to expiry.
- Frontend (Streamlit):
  - Calls local FastAPI endpoints via `requests`/`httpx`.
  - Custom components for stepper visualization of booking flow.
- App entry script orchestrates both FastAPI server (run with Uvicorn) and Streamlit, or provides instructions for running them separately.

## 10. Non-Functional Requirements
- **Performance:** API calls should respond within 3s assuming Travio responsiveness; Streamlit UI should stay interactive (<200ms local processing).
- **Reliability:** Handle API errors gracefully (HTTP errors, validation issues, expired tokens); display actionable messages and allow retry.
- **Security:** Never persist credentials or tokens to disk; mask sensitive inputs; ensure HTTPS endpoint usage only.
- **Maintainability:** Code organized into clear modules with typing, docstrings, and unit/integration tests for Travio client and mock mode.
- **Accessibility:** Basic keyboard navigation and descriptive labels in Streamlit components.

## 11. Testing Strategy
- Unit tests for Travio client wrapper (request construction, error handling, mock responses).
- Integration tests leveraging mock mode fixtures to simulate full flows (auth → client search → booking).
- Manual QA checklist covering credential entry, CRM operations, property search, quote generation, and mock/live toggling.

## 12. Telemetry & Logging
- Local structured logs for all outbound Travio calls (endpoint, latency, status, correlation id).
- Surface log feed in UI for transparency; allow reset/clear.
- No external telemetry or analytics (local-only requirement).

## 13. Release Plan & Milestones
1. **MVP (Iteration 1)** – Auth flow, CRM search (read-only), property search basic results, mock mode scaffolding.
2. **Iteration 2** – CRM create/update, booking picks flow, cart management, quote placement.
3. **Iteration 3** – Quote email dispatch, activity log UI, polish (filters, localization header support).
4. **Hardening** – Automated tests, documentation (`README`, `.env.example`), packaging instructions.

## 14. Open Questions & Risks
- Confirm exact CRM endpoints, required fields, and filter syntax from Swagger (PDF omits details).
- Clarify token TTL and refresh best practices (implicit in PDF but no duration specified).
- Determine available quote templates and required template IDs for `POST /tools/print/...`.
- Need clarity on occupancy schema for multi-room searches (PDF references separate paragraph).
- Risk: Streamlit session restart may drop backend state; must ensure FastAPI persists token or provide reconnect UX.
- Risk: Without live credentials testers rely on mock mode—accuracy of mocks contingent on up-to-date fixtures.

## 15. Documentation Deliverables
- `README.md` detailing setup, environment variables, mock vs live usage, and Start commands.
- Schema diagrams for API request flow (optional appendix) once implementation begins.

