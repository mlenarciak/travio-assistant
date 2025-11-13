# Travio Assistant

A local playground for the Travio platform that pairs a FastAPI backend with a Streamlit UI. It lets you exercise CRM lookups, live booking flows, cart management, quote creation, and quote delivery end‑to‑end against either Travio’s sandbox (mock mode) or the live API.

## Highlights

- **Guided booking wizard** – Search, iterate through Travio’s step sequence, and add the result to a cart with only a few clicks.
- **CRM ↔ booking hand‑off** – Select or create a client once; the booking and quote screens auto-fill the pax payloads and Travio client id.
- **Geo id helper** – Type-ahead search powered by `geo_ids.csv` to discover the right destination ids while you fill the booking form.
- **Quote builder + sender** – Place reservations from the cart, then trigger PDF/email delivery (with automatic fallback if a template is missing).
- **Activity timeline** – Every API hop is recorded so you can inspect the raw request/response bodies when debugging.

## Quick start

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
```

Copy `.env.example` to `.env.local` and supply real credentials if you plan to hit Travio:

```bash
cp .env.example .env.local
# edit TRAVIO_ID / TRAVIO_KEY / USE_MOCK_DATA as needed
```

### One-shot run script

Launch both services with the bundled runner:

```bash
./run.sh --mock            # default: mock data, auto reload
./run.sh --live --id 13 --key YOUR_KEY
```

Common flags:

- `--mock` / `--live` – seed `.env.local` with the desired `USE_MOCK_DATA` default.
- `--id` / `--key` / `--lang` – write Travio credentials into `.env.local` on first run.
- `--backend-port` / `--frontend-port` – override default ports.
- `--no-reload` – run the backend without the autoreloader if you prefer a quieter console.

### Manual launch

```bash
# backend
source .venv/bin/activate
uvicorn backend.app.main:app --reload

# in a second shell
source .venv/bin/activate
streamlit run frontend/app.py
```

Navigate to <http://localhost:8501> (or your chosen port). If you changed the backend port, update it in the **Settings** tab of the UI.

## Key workflows

| Tab | Capabilities |
| --- | --- |
| **Dashboard** | Ping the backend, mint a Travio token, and review the request/response history. |
| **CRM Search** | Query Travio master data, inspect results, create/update clients, and designate the “active” client that will be reused in bookings/quotes. |
| **Property Search** | Enter travel parameters, pick destination ids via type-ahead, step through Travio’s booking workflow with auto-generated picks payloads, and add the final result to a cart. |
| **Quote Builder** | Prefilled cart id and pax JSON (merged with the active client). Submit the quote/reservation, then send the PDF/email using your preferred template. Missing templates automatically fall back to template `2`. |
| **Activity Log** | View the recorded request/response history for the current session. |

## Geo id catalogue

`frontend` uses `geo_ids.csv` for the multiselect helper. The file in the repo was generated via:

```bash
python - <<'PY'
import csv, httpx, os
ID = int(os.environ['TRAVIO_ID'])
KEY = os.environ['TRAVIO_KEY']
LANG = os.environ.get('TRAVIO_LANGUAGE', 'en')
with httpx.Client(base_url='https://api.travio.it', timeout=30.0) as client:
    token = client.post('/auth', json={'id': ID, 'key': KEY}).json()['token']
    headers = {'Authorization': f'Bearer {token}', 'X-Lang': LANG}
    rows, page, pages = [], 1, 1
    while page <= pages:
        resp = client.get('/rest/geo', headers=headers, params={'page': page, 'per_page': 200})
        resp.raise_for_status()
        data = resp.json()
        pages = data.get('pages', pages)
        rows.extend((item['id'], item['name']) for item in data.get('list', []))
        page += 1
with open('geo_ids.csv', 'w', newline='', encoding='utf-8') as fh:
    writer = csv.writer(fh)
    writer.writerow(['id', 'name'])
    writer.writerows(rows)
PY
```

Regenerate it whenever Travio adds new destinations.

## Tests

All tests run in mock mode and therefore require no network access:

```bash
pytest
```

## Repository layout

```
backend/    FastAPI application (settings, routers, Travio clients, mock data)
frontend/   Streamlit UI
data/       Optional fixtures (currently unused)
tests/      Pytest suite covering mock-mode flows
run.sh      Bootstrapper that wires up the entire stack
status.md   Running changelog / status notes
```

## Housekeeping

- `logs/` is ignored — fresh logs are created when services start.
- `.env.local` is only used locally; don’t commit credentials.
- Large Travio reference PDFs have been removed to keep the repo lean. Consult Travio’s official docs for deeper reference material.

## Next ideas

- Surface paginated booking “results” pages with a next/prev UX.
- Persist activity logs to disk (toggle) for audit or demo recordings.
- Allow multi-room pax assignment by mapping CRM search results onto the Travio-generated pax ids.
