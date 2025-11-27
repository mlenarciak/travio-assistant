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

def get_client_list(start_id, limit, token):
    """Fetches a list of client IDs starting from start_id downwards."""
    url = f"{TRAVIO_BASE_URL}/rest/master-data"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }
    
    # Filter: id <= start_id
    filters = [{"field": "id", "operator": "<=", "value": start_id}]
    
    # Sort: id DESC
    sort_by = [["id", "DESC"]]
    
    params = {
        "filters": json.dumps(filters),
        "sort_by": json.dumps(sort_by),
        "per_page": limit,
        "page": 1
    }
    
    try:
        response = requests.get(url, headers=headers, params=params)
        response.raise_for_status()
        data = response.json()
        return data.get("list", [])
    except requests.exceptions.RequestException as e:
        print(f"Error fetching client list: {e}")
        return []

def fetch_client_details(client_id, token):
    """Fetches full details for a single client."""
    url = f"{TRAVIO_BASE_URL}/rest/master-data/{client_id}"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }
    
    try:
        response = requests.get(url, headers=headers)
        if response.status_code == 404:
            return None
        response.raise_for_status()
        return response.json().get("data", {})
    except requests.exceptions.RequestException as e:
        print(f"Error fetching client {client_id}: {e}")
        return None

def main():
    parser = argparse.ArgumentParser(description="Fetch client data from Travio API.")
    parser.add_argument("--start-id", type=int, default=390550, help="Client ID to start counting down from (default: 390550)")
    parser.add_argument("--limit", type=int, default=100, help="Number of clients to fetch (default: 100)")
    parser.add_argument("--output", type=str, default="clients_enhanced.csv", help="Output CSV file path")
    
    args = parser.parse_args()
    
    print("Authenticating...")
    token = get_auth_token()
    print("Authentication successful.")
    
    print(f"Fetching list of {args.limit} clients starting from ID {args.start_id} downwards...")
    client_list = get_client_list(args.start_id, args.limit, token)
    
    if not client_list:
        print("No clients found.")
        return

    print(f"Found {len(client_list)} clients in list. Fetching details...")
    
    fieldnames = [
        "id", "name", "surname", "company_name", "full_name", 
        "email", "phone", "vat_number", "tax_code", 
        "address", "postal_code", "city", "province", "country",
        "gender", "birth_date"
    ]
    
    with open(args.output, mode='w', newline='', encoding='utf-8') as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        writer.writeheader()
        
        count = 0
        for client_summary in client_list:
            client_id = client_summary.get("id")
            print(f"Fetching details for client {client_id}...", end='\r')
            
            client_data = fetch_client_details(client_id, token)
            
            if client_data:
                # Extract address info (taking the first address found)
                address_info = {}
                if client_data.get("addresses"):
                    addr = client_data.get("addresses")[0]
                    address_info = {
                        "address": addr.get("address"),
                        "postal_code": addr.get("postal_code"),
                        "city": addr.get("legacy", {}).get("city"),
                        "province": addr.get("legacy", {}).get("province"),
                        "country": addr.get("legacy", {}).get("country")
                    }
                
                # Extract contact info
                email = ""
                phone = ""
                if client_data.get("contacts"):
                    contact = client_data.get("contacts")[0]
                    email = ", ".join(contact.get("email", [])) if contact.get("email") else ""
                    phone = ", ".join(contact.get("phone", [])) if contact.get("phone") else ""

                row = {
                    "id": client_data.get("id"),
                    "name": client_data.get("name"),
                    "surname": client_data.get("surname"),
                    "company_name": client_data.get("company_name"),
                    "full_name": client_data.get("full_name"),
                    "email": email,
                    "phone": phone,
                    "vat_number": client_data.get("vat_number"),
                    "tax_code": client_data.get("tax_code"),
                    "address": address_info.get("address"),
                    "postal_code": address_info.get("postal_code"),
                    "city": address_info.get("city"),
                    "province": address_info.get("province"),
                    "country": address_info.get("country"),
                    "gender": client_data.get("gender"),
                    "birth_date": client_data.get("birth")
                }
                writer.writerow(row)
                count += 1
            
    print(f"\nDone. Fetched {count} clients. Saved to {args.output}")

if __name__ == "__main__":
    main()
