# Travio UI Bring-up Status

## Completed Changes
- **run.sh**: faster backend readiness (20 half-second probes) and simplified status parse to prevent hangs.
- **Environment setup**: added `.env.example` and resilient `.env.local` creation/updater so runner works even without the original example file.
- **Streamlit import fix**: `frontend/app.py` now supports both package and script execution; added `frontend/__init__.py`.
- **CRM API alignment**:
  - Backend now proxies Travio REST endpoints (`/rest/master-data`) with `data` wrappers for create/update.
  - `CRMSearchRequest` builds Travio-compatible filters (email/surname/code) and falls back to local filtering for phone.
  - Client-create/update flow now normalizes payloads (`name`/`surname`, contacts, defaults for profiles) so real Travio accepts submissions.
  - Mock client mimics REST responses, supports filters/pagination/contacts.
  - CRM route normalizes Travio responses into `items`, handles phone filtering, and records REST endpoints in activity log.
- **Booking flow guidance**: Streamlit now surfaces step-by-step pick templates (`date_idx` → `num` → `confirm`) based on the latest Travio response, and backend error surfaces include Travio's raw messages.
- **Geo lookup helper**: Booking form can search/multiselect from `geo_ids.csv` (type-ahead) and merges those selections with manual geo id input.
- **CRM-to-booking handoff**: Selecting/creating a CRM client marks it active; booking/quote tabs display that context, reuse Travio cart pax placeholders, and auto-prefill quote pax JSON (with unsupported fields stripped to avoid Travio validation errors).
- **Verification**: `./run.sh --mock --no-install --no-reload` and `--live` start up; direct auth + `/rest/master-data` calls succeed via httpx.

## Remaining Issues / Next Steps
- **Phone filtering still brittle**: remote API errors when querying nested phone data; currently filtered client-side. Need official field/filters from Travio docs.
- **Unknown Travio filter syntax**: existing filters (`filter[email]`) no longer valid; surrogate solution uses `field/operator/value` but may miss cases (e.g. phone).
- **Live data validation**: should confirm booking/cart/quote flows against real API, adjust payloads as needed.
- **Credential handling**: `.env.local` currently contains sample key; ensure production secrets managed securely.
- **Testing**: add automated tests/mocks for CRM filtering logic once API field definitions clarified.
