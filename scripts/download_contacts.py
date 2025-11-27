#!/usr/bin/env python3
"""Download Travio contacts into a local SQLite database.

The script authenticates against the Travio API, walks the paginated
`/rest/master-data` endpoint, unfolds contact information, and stores the
results in two tables:

* `clients` — one row per master-data record.
* `contacts` — one row per contact, linked to its client.

Credentials are read from CLI flags or `TRAVIO_ID` / `TRAVIO_KEY`
environment variables. The optional `TRAVIO_LANGUAGE` flag controls the
`X-Lang` header sent to the API.
"""

from __future__ import annotations

import argparse
import json
import os
import sqlite3
from typing import Any, Dict, Iterable, Iterator, Tuple

import httpx
from dotenv import load_dotenv


def parse_args() -> argparse.Namespace:
    """Configure CLI arguments."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--env-file",
        default=".env.local",
        help="Path to the dotenv file with Travio credentials (default: %(default)s)",
    )
    parser.add_argument(
        "--travio-id",
        type=int,
        help="Travio account id (falls back to TRAVIO_ID env var)",
    )
    parser.add_argument(
        "--travio-key",
        help="Travio API key (falls back to TRAVIO_KEY env var)",
    )
    parser.add_argument(
        "--language",
        default=None,
        help="Preferred language code for X-Lang header (default: TRAVIO_LANGUAGE env var or 'en')",
    )
    parser.add_argument(
        "--base-url",
        default="https://api.travio.it",
        help="Travio API base url (default: %(default)s)",
    )
    parser.add_argument(
        "--db-path",
        default="contacts.db",
        help="Destination SQLite database path (default: %(default)s)",
    )
    parser.add_argument(
        "--per-page",
        type=int,
        default=200,
        help="Number of items per API page (default: %(default)s)",
    )
    parser.add_argument(
        "--max-pages",
        type=int,
        default=None,
        help="Optional cap on pages to download (default: fetch all pages)",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=30.0,
        help="HTTP request timeout in seconds (default: %(default)s)",
    )
    return parser.parse_args()


def load_credentials(args: argparse.Namespace) -> Tuple[int, str, str]:
    """Resolve Travio credentials and language preference."""
    if args.env_file and os.path.exists(args.env_file):
        load_dotenv(args.env_file, override=False)

    travio_id = args.travio_id or os.getenv("TRAVIO_ID")
    travio_key = args.travio_key or os.getenv("TRAVIO_KEY")
    language = args.language or os.getenv("TRAVIO_LANGUAGE") or "en"

    if not travio_id or not travio_key:
        raise SystemExit("Missing Travio credentials. Provide --travio-id/--travio-key or set TRAVIO_ID/TRAVIO_KEY.")

    return int(travio_id), travio_key, language


def get_token(client: httpx.Client, account_id: int, api_key: str) -> str:
    """Authenticate with the Travio API and return a bearer token."""
    response = client.post("/auth", json={"id": account_id, "key": api_key})
    response.raise_for_status()
    payload = response.json()
    token = payload.get("token")
    if not token:
        raise RuntimeError("Authentication succeeded but no token was returned.")
    return token


def iter_master_data(
    client: httpx.Client,
    headers: Dict[str, str],
    per_page: int,
    max_pages: int | None,
) -> Iterator[Dict[str, Any]]:
    """Yield master-data records page by page."""
    page = 1
    pages = 1
    while page <= pages:
        if max_pages is not None and page > max_pages:
            break
        params = {"page": page, "per_page": per_page, "unfold": "contacts"}
        response = client.get("/rest/master-data", headers=headers, params=params)
        response.raise_for_status()
        data = response.json()
        items = data.get("list") or data.get("items") or []
        for item in items:
            yield item
        pages = data.get("pages") or pages
        page += 1


def ensure_schema(connection: sqlite3.Connection) -> None:
    """Create the target tables if they do not exist."""
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS clients (
            id INTEGER PRIMARY KEY,
            code TEXT,
            name TEXT,
            surname TEXT,
            profile_type TEXT,
            language TEXT,
            vat_country TEXT,
            raw_json TEXT NOT NULL
        )
        """
    )
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS contacts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            client_id INTEGER NOT NULL,
            contact_id INTEGER,
            name TEXT,
            emails TEXT,
            phones TEXT,
            fax_numbers TEXT,
            raw_json TEXT NOT NULL,
            FOREIGN KEY (client_id) REFERENCES clients (id) ON DELETE CASCADE
        )
        """
    )
    connection.commit()


def upsert_client(connection: sqlite3.Connection, record: Dict[str, Any]) -> None:
    """Insert or update a master-data record."""
    connection.execute(
        """
        INSERT OR REPLACE INTO clients (id, code, name, surname, profile_type, language, vat_country, raw_json)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            record.get("id"),
            record.get("code"),
            record.get("name") or record.get("firstname"),
            record.get("surname") or record.get("lastname"),
            record.get("profile_type"),
            record.get("language"),
            record.get("vat_country"),
            json.dumps(record, ensure_ascii=False),
        ),
    )


def replace_contacts(
    connection: sqlite3.Connection,
    client_id: int,
    contacts: Iterable[Dict[str, Any]],
) -> int:
    """Replace contacts for the given client and return the number of inserted rows."""
    connection.execute("DELETE FROM contacts WHERE client_id = ?", (client_id,))
    inserted = 0
    for contact in contacts:
        connection.execute(
            """
            INSERT INTO contacts (client_id, contact_id, name, emails, phones, fax_numbers, raw_json)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                client_id,
                contact.get("id"),
                contact.get("name"),
                json.dumps(contact.get("email") or [], ensure_ascii=False),
                json.dumps(contact.get("phone") or [], ensure_ascii=False),
                json.dumps(contact.get("fax") or [], ensure_ascii=False),
                json.dumps(contact, ensure_ascii=False),
            ),
        )
        inserted += 1
    return inserted


def main() -> None:
    args = parse_args()
    account_id, api_key, language = load_credentials(args)

    connection = sqlite3.connect(args.db_path)
    try:
        ensure_schema(connection)
        with httpx.Client(base_url=args.base_url, timeout=args.timeout) as client:
            token = get_token(client, account_id, api_key)
            headers = {"Authorization": f"Bearer {token}", "X-Lang": language}
            total_clients = 0
            total_contacts = 0
            for record in iter_master_data(client, headers, args.per_page, args.max_pages):
                client_id = record.get("id")
                if client_id is None:
                    continue
                upsert_client(connection, record)
                contacts = record.get("contacts") or []
                total_contacts += replace_contacts(connection, client_id, contacts)
                total_clients += 1
            connection.commit()
    finally:
        connection.close()

    print(f"Stored {total_contacts} contacts across {total_clients} clients in {args.db_path}.")


if __name__ == "__main__":
    main()

