import os
import argparse
import requests
import sys
import json
from datetime import datetime, timedelta
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

def check_availability(token, from_date, to_date, adults, geo_id=None, service_ids=None):
    url = f"{TRAVIO_BASE_URL}/booking/search"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }
    
    search_params = {
        "type": "hotels", # Defaulting to hotels for now
        "from": from_date,
        "to": to_date,
        "occupancy": [{"adults": adults}]
    }
    
    if geo_id:
        search_params["geo"] = [geo_id]
    
    if service_ids:
        search_params["ids"] = service_ids

    payload = {
        "search": [search_params]
    }
    
    print(f"Sending search request: {json.dumps(payload, indent=2)}")
    
    try:
        response = requests.post(url, headers=headers, json=payload)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        print(f"Error checking availability: {e}")
        if hasattr(e, 'response') and e.response is not None:
             print(f"Response: {e.response.text}")
        return None

def main():
    parser = argparse.ArgumentParser(description="Check availability on Travio API.")
    parser.add_argument("--from-date", type=str, required=True, help="Check-in date (YYYY-MM-DD)")
    parser.add_argument("--to-date", type=str, required=True, help="Check-out date (YYYY-MM-DD)")
    parser.add_argument("--adults", type=int, default=2, help="Number of adults (default: 2)")
    parser.add_argument("--geo-id", type=int, help="Destination ID to search in")
    parser.add_argument("--service-ids", type=str, help="Comma-separated list of service IDs to search for")
    
    args = parser.parse_args()
    
    print("Authenticating...")
    token = get_auth_token()
    
    service_ids_list = [int(x) for x in args.service_ids.split(",")] if args.service_ids else None
    
    print("Checking availability...")
    result = check_availability(token, args.from_date, args.to_date, args.adults, args.geo_id, service_ids_list)
    
    if result:
        print("\nSearch Results:")
        # The response structure is complex (booking flow). 
        # We need to look at 'groups' -> 'items'.
        if "groups" in result:
            for group in result["groups"]:
                print(f"\nGroup Type: {group.get('type')}")
                for item in group.get("items", []):
                    # Item structure depends on what's returned.
                    # Usually contains service info, price, etc.
                    # Let's print a summary.
                    print("-" * 40)
                    # Note: The item structure in 'search' response might be minimal or just a 'next step' indicator.
                    # But typically for hotels it lists available hotels.
                    # Let's dump the item keys to see what we have.
                    # print(item.keys())
                    
                    # Try to extract common fields
                    name = item.get("name", "Unknown")
                    # Price might be in 'price' object
                    price_info = item.get("price", {})
                    gross_price = price_info.get("gross", "N/A")
                    currency = price_info.get("currency", {}).get("code", "")
                    
                    print(f"Service: {name}")
                    print(f"Price: {gross_price} {currency}")
                    
                    # If there are sub-items (like rooms), they might be in 'items' of this item or we need to 'pick' it.
                    # For a simple search list, this should be enough.
        else:
            print("No groups found in response.")
            print(json.dumps(result, indent=2))

if __name__ == "__main__":
    main()
