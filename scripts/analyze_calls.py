import asyncio
import csv
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

from loguru import logger

# Add project root to path so we can import backend modules
sys.path.append(str(Path(__file__).parent.parent))

from backend.app.config import Settings
from backend.app.services.travio_client import TravioClient

async def analyze_calls(csv_path: str):
    """
    Reads call records from CSV and links them to Travio CRM data.
    """
    settings = Settings()
    
    # Ensure we have a valid path
    input_path = Path(csv_path)
    if not input_path.exists():
        logger.error(f"File not found: {csv_path}")
        return

    logger.info(f"Reading call records from {csv_path}...")
    
    calls = []
    try:
        with open(input_path, mode='r', encoding='utf-8-sig') as f:
            reader = csv.DictReader(f)
            for row in reader:
                calls.append(row)
    except Exception as e:
        logger.error(f"Failed to read CSV: {e}")
        return

    logger.info(f"Found {len(calls)} call records. Starting analysis...")

    async with TravioClient(settings).lifespan() as client:
        # Authenticate first
        try:
            await client.authenticate()
        except Exception as e:
            logger.error(f"Authentication failed: {e}")
            return

        stats = {
            "total_calls": len(calls),
            "linked_calls": 0,
            "revenue_on_call_day": 0.0,
            "new_clients_on_call_day": 0,
            "existing_clients_before_call": 0
        }

        for call in calls:
            # Extract phone number - try 'clean number' first, then 'Number Ext'
            phone = call.get('clean number') or call.get('Number Ext')
            if not phone:
                continue
            
            # Clean up phone number for search (remove + if needed, or keep it depending on API)
            # Assuming API might want exact match or partial. 
            # Let's try to search by the number as is.
            
            # Search for client
            # Note: The filter field for phone might be 'contacts.phone' or just 'phone' depending on implementation.
            # We will try a filter that seems most likely based on standard Travio patterns.
            # If 'contacts.phone' is the path, we might need a specific operator or just '='.
            
            # Search for pax by phone
            # Pax repository has a 'phone' field which is a string.
            filters = json.dumps([
                {"field": "phone", "operator": "LIKE", "value": phone} 
            ])
            
            try:
                # Search in 'pax' repository
                result = await client._request("GET", "/rest/pax", params={"filters": filters})
                
                pax_list = result.get("list", [])
                if not pax_list:
                    # Try removing '+' if present
                    if phone.startswith('+'):
                        phone_no_plus = phone[1:]
                        filters_retry = json.dumps([
                            {"field": "phone", "operator": "LIKE", "value": phone_no_plus}
                        ])
                        result = await client._request("GET", "/rest/pax", params={"filters": filters_retry})
                        pax_list = result.get("list", [])

                if pax_list:
                    # We found a pax!
                    # Get the reservation ID
                    # We might have multiple pax records for the same person (different trips).
                    # We should check all of them or the most recent?
                    # For "revenue on call day", we should check if any reservation matches the call date.
                    
                    stats["linked_calls"] += 1
                    
                    # Track unique clients found to avoid double counting stats if multiple pax records point to same client
                    # But here we are iterating calls.
                    
                    for pax in pax_list:
                        reservation_id = pax.get("reservation")
                        if not reservation_id:
                            continue
                            
                        # Fetch reservation
                        try:
                            res = await client._request("GET", f"/rest/reservations/{reservation_id}")
                            res_data = res.get("data", {})
                            
                            # Check reservation date
                            res_date_str = res_data.get("date") # Booking date
                            if res_date_str:
                                res_date = datetime.fromisoformat(res_date_str.replace('Z', '+00:00')).date()
                                
                                call_date_str = call.get("calldate")
                                if call_date_str:
                                    call_date = datetime.strptime(call_date_str, "%Y-%m-%d %H:%M:%S").date()
                                    
                                    if res_date == call_date:
                                        # Match!
                                        price = res_data.get("price", {})
                                        gross = price.get("gross", 0)
                                        stats["revenue_on_call_day"] += gross
                                        
                                        # Check if client is new
                                        client_id = res_data.get("client")
                                        if client_id:
                                            full_client = await client.get_client(client_id)
                                            full_client_data = full_client.get("data", {})
                                            client_created_str = full_client_data.get("created_at") or full_client_data.get("_meta", {}).get("creation_date")
                                            
                                            if client_created_str:
                                                # Handle "0000-00-00 00:00:00" case seen in debug output
                                                if client_created_str.startswith("0000"):
                                                    pass
                                                else:
                                                    try:
                                                        client_created = datetime.fromisoformat(client_created_str.replace('Z', '+00:00')).date()
                                                        if client_created == call_date:
                                                            stats["new_clients_on_call_day"] += 1
                                                        elif client_created < call_date:
                                                            stats["existing_clients_before_call"] += 1
                                                    except ValueError:
                                                        pass
                                        
                                        # Break after finding a match for this call to avoid double counting revenue for same call?
                                        # Actually, one call might discuss multiple reservations, but usually one.
                                        # But if we find multiple pax records, they might be for the same reservation.
                                        # We should probably track processed reservation IDs per call to avoid duplicates.
                                        break 

                        except Exception as e:
                            logger.error(f"Error fetching reservation {reservation_id}: {e}")

            except Exception as e:
                logger.error(f"Error processing call {phone}: {e}")
                continue

            except Exception as e:
                logger.error(f"Error processing call {phone}: {e}")
                continue

    # Output Report
    print("\n" + "="*40)
    print("CALL ANALYSIS REPORT")
    print("="*40)
    print(f"Total Calls Analyzed: {stats['total_calls']}")
    print(f"Calls Linked to Clients: {stats['linked_calls']}")
    print(f"Existing Clients (Before Call): {stats['existing_clients_before_call']}")
    print(f"New Clients (Created on Call Day): {stats['new_clients_on_call_day']}")
    print(f"Revenue Generated on Call Day: €{stats['revenue_on_call_day']:.2f}")
    print("="*40 + "\n")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python scripts/analyze_calls.py <path_to_csv>")
        sys.exit(1)
    
    asyncio.run(analyze_calls(sys.argv[1]))
