# Developer Notes

This file captures the non-obvious behaviour and edge cases we uncovered while wiring the Travio flows. Future refactors (for example, migrating the UI to Next.js) should keep these in mind to avoid re-learning the hard lessons.

## Booking / Cart Flow

- **Sequential steps are mandatory**: Travio rejects out-of-order picks. The UI must submit step `0` (service/date), then step `1` (room with `num`), then step `2` (confirm). Even if the user picks everything in one screen, the code must still make three API calls.
- **Cart lookups are transient**: `POST /booking/search` + picks produce a temporary search id. If the cart isn’t confirmed (step 2), `PUT /booking/cart` returns “Search not found”. Always store the `search_id` from the latest successful step.
- **Geo ids are complex**: the destination tree is large and multilingual. We generated `geo_ids.csv` using `/rest/geo`. Re-create that periodically or build a proper lookup from the API before requiring the user to know ids.

## Pax & Client Handling

- **Pax IDs come from Travio**: `GET /booking/cart/{id}` may return placeholder pax such as `{id: 4063…, enabled: true}`. When sending `POST /booking/place`, reuse that `id`; replacing it with a CRM id causes “Specified pax does not exist”. Instead, merge CRM name/email/phone onto the existing pax entry.
- **Client id is required**: Travio expects a numeric `client` value in the reservation payload. Passing `{"client": {"id": …}}` returns “client must be a number”. We now send `client: <master-data id>`.
- **CRM updates don’t echo phone/email**: The REST `/rest/master-data` endpoint sometimes omits `phone` from responses; the mock client mirrors this by storing contact details inside `contacts`. Consumers should read both `phone` and `contacts[].phone`.

## Quote Placement & Delivery

- `POST /booking/place/{cart_id}` fails unless both pax ids and client id are correct (see above). Handle the 400 errors in the UI; they contain helpful strings.
- **Template discovery isn’t documented**: There is no `GET /tools/templates` route. Template ids are account-specific. We found that template `2` always exists in our tenant, so the UI falls back to it when the user’s choice 404s (“Template not found”). Build similar fallback or surface the error clearly.
- **Multiple send attempts**: The first call may 424 (“No document found”) if the quote isn’t ready. Retrying usually succeeds; the current UI surfaces Travio’s raw message so users know whether to retry.

## Miscellaneous

- Travio’s OpenAPI spec is missing several routes and understates field requirements. Trust the live responses more than the spec.
- During tests, we run in mock mode (`USE_MOCK_DATA=true`) so the suite doesn’t hit the network. If you extend tests, prefer mocking the live client; Travio rate limits aggressively.

Keep this list updated as more quirks surface.
