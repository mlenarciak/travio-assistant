import os
import csv
import argparse
import requests
import sys
import json
from dotenv import load_dotenv

# Load environment variables
script_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(script_dir)
load_dotenv(os.path.join(project_root, '.env.local'))

TRAVIO_ID = os.getenv("TRAVIO_ID")
TRAVIO_KEY = os.getenv("TRAVIO_KEY")
TRAVIO_BASE_URL = os.getenv("TRAVIO_BASE_URL", "https://api.travio.it")

def get_auth_token():
    """Authenticates with Travio API and returns the Bearer token."""
    if not TRAVIO_ID or not TRAVIO_KEY:
        print("Error: TRAVIO_ID and TRAVIO_KEY must be set in environment or .env.local")
        sys.exit(1)

    url = f"{TRAVIO_BASE_URL}/auth"
    payload = {
        "id": int(TRAVIO_ID),
        "key": TRAVIO_KEY
    }
    
    try:
        response = requests.post(url, json=payload)
        response.raise_for_status()
        return response.json().get("token")
    except requests.exceptions.RequestException as e:
        print(f"Authentication failed: {e}")
        sys.exit(1)

def fetch_destinations(limit, token):
    url = f"{TRAVIO_BASE_URL}/rest/geo"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }
    
    params = {
        "per_page": limit,
        "page": 1,
        "sort_by": json.dumps([["name", "ASC"]])
    }
    
    try:
        response = requests.get(url, headers=headers, params=params)
        response.raise_for_status()
        return response.json().get("list", [])
    except requests.exceptions.RequestException as e:
        print(f"Error fetching destinations: {e}")
        return []

def get_multilang_str(field, lang="en"):
    if isinstance(field, dict):
        return field.get(lang) or field.get("it") or str(field)
    return str(field) if field else ""

def main():
    parser = argparse.ArgumentParser(description="Fetch destinations from Travio API.")
    parser.add_argument("--limit", type=int, default=100, help="Number of destinations to fetch (default: 100)")
    parser.add_argument("--output", type=str, default="destinations.csv", help="Output CSV file path")
    
    args = parser.parse_args()
    
    print("Authenticating...")
    token = get_auth_token()
    
    print(f"Fetching {args.limit} destinations...")
    destinations = fetch_destinations(args.limit, token)
    
    if not destinations:
        print("No destinations found.")
        return

    fieldnames = ["id", "name", "type", "parent_id"]
    
    with open(args.output, mode='w', newline='', encoding='utf-8') as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        writer.writeheader()
        
        for dest in destinations:
            row = {
                "id": dest.get("id"),
                "name": get_multilang_str(dest.get("name")),
                "type": dest.get("type"),
                "parent_id": dest.get("parent")
            }
            writer.writerow(row)
            
    print(f"Done. Fetched {len(destinations)} destinations. Saved to {args.output}")

if __name__ == "__main__":
    main()
