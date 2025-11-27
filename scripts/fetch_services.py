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

def fetch_services(limit, token):
    url = f"{TRAVIO_BASE_URL}/rest/services"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }
    
    # Unfold geo to get city name if possible, though 'geo' field is complex.
    # We'll just fetch the list first.
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
        print(f"Error fetching services: {e}")
        return []

def get_multilang_str(field, lang="en"):
    if isinstance(field, dict):
        return field.get(lang) or field.get("it") or str(field)
    return str(field) if field else ""

def main():
    parser = argparse.ArgumentParser(description="Fetch services from Travio API.")
    parser.add_argument("--limit", type=int, default=100, help="Number of services to fetch (default: 100)")
    parser.add_argument("--output", type=str, default="services.csv", help="Output CSV file path")
    
    args = parser.parse_args()
    
    print("Authenticating...")
    token = get_auth_token()
    
    print(f"Fetching {args.limit} services...")
    services = fetch_services(args.limit, token)
    
    if not services:
        print("No services found.")
        return

    fieldnames = ["id", "name", "code", "type", "classification", "city", "description_snippet"]
    
    with open(args.output, mode='w', newline='', encoding='utf-8') as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        writer.writeheader()
        
        for srv in services:
            # Extract description snippet
            desc_snippet = ""
            descriptions = srv.get("descriptions", [])
            if descriptions:
                # Try to find english or italian
                target_desc = next((d for d in descriptions if d.get("lang") == "en"), None)
                if not target_desc:
                    target_desc = next((d for d in descriptions if d.get("lang") == "it"), None)
                
                if target_desc and target_desc.get("paragraphs"):
                    # Get first paragraph text
                    desc_snippet = target_desc.get("paragraphs")[0].get("text", "")[:100] + "..."

            # Extract city from location or geo if available (simplified)
            # The 'geo' field in list response might be just IDs or a summary.
            # 'location' has lat/lng.
            # We'll leave city empty for now unless we fetch details, but let's check if 'geo' is useful.
            city = ""
            
            row = {
                "id": srv.get("id"),
                "name": get_multilang_str(srv.get("name")),
                "code": srv.get("code"),
                "type": srv.get("type"),
                "classification": srv.get("classification"),
                "city": city, 
                "description_snippet": desc_snippet
            }
            writer.writerow(row)
            
    print(f"Done. Fetched {len(services)} services. Saved to {args.output}")

if __name__ == "__main__":
    main()
