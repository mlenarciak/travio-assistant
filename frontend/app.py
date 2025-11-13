"""Streamlit frontend for Travio API assistant."""

from __future__ import annotations

import ast
import json
from datetime import date
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, List, Optional

import pandas as pd
import streamlit as st
from st_aggrid import AgGrid, GridOptionsBuilder

try:
    from frontend.backend_client import BackendClient  # type: ignore[import]
except ModuleNotFoundError:
    import sys

    sys.path.append(str(Path(__file__).resolve().parent))
    from backend_client import BackendClient


def get_backend_client() -> BackendClient:
    """Retrieve a backend client configured from session state."""
    base_url: str = st.session_state.get("backend_url", "http://localhost:8000")
    return BackendClient(base_url=base_url)


@lru_cache(maxsize=1)
def load_geo_catalog() -> pd.DataFrame:
    """Load geo catalog from CSV if available."""
    csv_path = Path("geo_ids.csv")
    if not csv_path.exists():
        return pd.DataFrame(columns=["id", "name"])
    try:
        return pd.read_csv(csv_path)
    except Exception:
        return pd.DataFrame(columns=["id", "name"])


def parse_geo_name(raw: Any, language: str = "en") -> str:
    """Extract human-friendly name from stored dict/text representation."""
    if pd.isna(raw):
        return ""
    if isinstance(raw, str):
        try:
            data = ast.literal_eval(raw)
        except (ValueError, SyntaxError):
            return raw
        if isinstance(data, dict):
            for key in (language, "en", "it"):
                value = data.get(key)
                if value:
                    return value
            return next((value for value in data.values() if value), raw)
    return str(raw)


def build_geo_options(language: str = "en") -> Dict[int, str]:
    """Return mapping of geo id to formatted display label."""
    catalog = load_geo_catalog()
    if catalog.empty:
        return {}
    labels: Dict[int, str] = {}
    for row in catalog.itertuples():
        try:
            geo_id = int(row.id)
        except (TypeError, ValueError):
            continue
        name = parse_geo_name(row.name, language=language) or str(geo_id)
        labels[geo_id] = f"{name} ({geo_id})"
    return labels


def get_crm_clients() -> Dict[int, Dict[str, Any]]:
    """Return cached CRM clients dictionary."""
    clients = st.session_state.get("crm_clients")
    if not isinstance(clients, dict):
        clients = {}
        st.session_state["crm_clients"] = clients
    return clients


def format_client_label(client: Dict[str, Any], include_id: bool = False) -> str:
    """Return human readable label for a CRM client record."""
    name = (
        client.get("full_name")
        or client.get("name")
        or f"{client.get('firstname', '')} {client.get('lastname', '')}".strip()
    )
    label = name or f"Client {client.get('id')}"
    if include_id and client.get("id") is not None:
        label = f"{label} (ID {client['id']})"
    return label


def get_active_client() -> Optional[Dict[str, Any]]:
    """Return the currently selected CRM client, if any."""
    clients = get_crm_clients()
    active_id = st.session_state.get("active_client_id")
    if active_id in clients:
        return clients[active_id]
    return None


def render_active_client_selector(label: str = "Active CRM client") -> None:
    """Render selectbox for choosing active CRM client."""
    clients = get_crm_clients()
    if not clients:
        return
    option_ids = sorted(clients.keys())
    current_id = st.session_state.get("active_client_id")
    default_index = option_ids.index(current_id) if current_id in option_ids else 0
    selected_id = st.selectbox(
        label,
        option_ids,
        index=default_index,
        format_func=lambda cid: format_client_label(clients[cid], include_id=True),
    )
    st.session_state["active_client_id"] = selected_id


def extract_contact_detail(client: Dict[str, Any], field: str) -> Optional[str]:
    """Retrieve primary contact detail (email/phone) from client record."""
    contacts = client.get("contacts") or []
    for contact in contacts:
        values = contact.get(field)
        if isinstance(values, list) and values:
            return values[0]
        if isinstance(values, str) and values:
            return values
    value = client.get(field)
    if isinstance(value, list):
        return value[0] if value else None
    if isinstance(value, str) and value:
        return value
    return None


def build_cart_pax_prefill(
    cart_pax: Optional[List[Dict[str, Any]]],
    active_client: Optional[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """Produce pax payload suggestions derived from cart and CRM."""
    raw_pax = cart_pax or []
    pax_entries: List[Dict[str, Any]] = []

    for pax in raw_pax:
        if not isinstance(pax, dict):
            continue
        entry = {
            k: v
            for k, v in pax.items()
            if v not in (None, "", [], {})
            and k not in {"enabled", "room", "_age", "booking", "heading", "context"}
        }
        pax_entries.append(entry)

    if active_client:
        lead_data = {
            "name": active_client.get("firstname")
            or active_client.get("name")
            or active_client.get("full_name"),
            "surname": active_client.get("lastname") or active_client.get("surname"),
        }
        email = extract_contact_detail(active_client, "email")
        phone = extract_contact_detail(active_client, "phone")
        if email:
            lead_data["email"] = email
        if phone:
            lead_data["phone"] = phone
        if pax_entries:
            if lead_data.get("name"):
                pax_entries[0]["name"] = lead_data["name"]
            if lead_data.get("surname"):
                pax_entries[0]["surname"] = lead_data["surname"]
            if lead_data.get("email"):
                pax_entries[0]["email"] = lead_data["email"]
            if lead_data.get("phone"):
                pax_entries[0]["phone"] = lead_data["phone"]
            pax_entries[0].setdefault("id", active_client.get("id"))
        else:
            lead_entry = {k: v for k, v in lead_data.items() if v}
            lead_entry["id"] = active_client.get("id")
            pax_entries.append(lead_entry)

    cleaned = []
    for entry in pax_entries:
        cleaned.append({k: v for k, v in entry.items() if k not in {"enabled", "_age"}})
    return cleaned


def describe_item(item: Dict[str, Any]) -> str:
    """Format human friendly label for booking item."""
    name = item.get("name") or item.get("code") or f"Item {item.get('idx', '')}"
    price = item.get("price")
    currency = item.get("currency") or item.get("cost_currency")
    supplier = item.get("supplier")
    parts = [name]
    if price not in (None, 0):
        parts.append(f"{price:g} {currency or ''}".strip())
    if supplier:
        parts.append(f"provider: {supplier}")
    return " – ".join(parts)


def build_pick_samples(response: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Generate example picks payload based on latest booking response."""
    samples: List[Dict[str, Any]] = []
    if not isinstance(response, dict):
        return samples

    groups = response.get("groups") or []
    for group in groups:
        if not isinstance(group, dict):
            continue
        group_idx = group.get("idx")
        if group_idx is None:
            continue
        group_type = group.get("type")
        sample_entry: Dict[str, Any] = {"group": group_idx}
        if group_type == "confirm":
            sample_entry["confirm"] = True
            samples.append(sample_entry)
            continue

        items = group.get("items") or []
        if not items:
            continue
        first_item = items[0]
        pick_payload: Dict[str, Any] = {"idx": first_item.get("idx", 0)}
        if first_item.get("dates"):
            pick_payload["date_idx"] = 0
        if first_item.get("num") is not None:
            pick_payload["num"] = first_item.get("num") or 1
        sample_entry["picks"] = [pick_payload]
        samples.append(sample_entry)
    return samples


def render_booking_step_controls(
    flow: Dict[str, Any],
    client: BackendClient,
) -> None:
    """Render dynamic controls for current Travio booking step."""
    response: Dict[str, Any] = flow.get("response") or {}
    if not response:
        return
    search_id = flow.get("search_id") or response.get("search_id")
    if not search_id:
        st.warning("Missing search identifier in booking flow.")
        return
    step = response.get("step", 0)
    final = response.get("final", False)
    st.markdown(f"**Travio step {step}** {'(final)' if final else ''}")

    if response.get("warnings"):
        with st.expander("Warnings", expanded=False):
            show_json(response.get("warnings"))
    if response.get("errors"):
        with st.expander("Supplier errors", expanded=False):
            show_json(response.get("errors"))

    groups: List[Dict[str, Any]] = response.get("groups") or []
    picks_plan: List[Dict[str, Any]] = []
    issues: List[str] = []

    for group in groups:
        group_idx = group.get("idx")
        group_type = group.get("type")
        unique = group.get("unique") or f"group_{group_idx}"
        group_label = group.get("label") or f"Group {group_idx}"
        container = st.container()
        with container:
            st.markdown(f"_{group_label}_")

            if group_type == "pick":
                items = [item for item in group.get("items", []) if isinstance(item, dict)]
                if not items:
                    issues.append(f"No selectable items for group {group_idx}")
                    continue

                option_values = [item.get("idx") for item in items]
                label_map = {item.get("idx"): describe_item(item) for item in items}
                select_key = f"booking_step_{search_id}_{step}_{group_idx}_item"
                if select_key not in st.session_state:
                    st.session_state[select_key] = option_values[0]
                selected_idx = st.selectbox(
                    "Choose option",
                    option_values,
                    key=select_key,
                    format_func=lambda idx: label_map.get(idx, f"Idx {idx}"),
                )
                selected_item = next(
                    (item for item in items if item.get("idx") == selected_idx),
                    items[0],
                )
                pick_payload: Dict[str, Any] = {"idx": selected_item.get("idx", 0)}

                dates = selected_item.get("dates") or []
                if dates:
                    date_key = f"{select_key}_date"
                    if date_key not in st.session_state:
                        st.session_state[date_key] = 0

                    def _format_date(idx: int) -> str:
                        entry = dates[idx]
                        start = entry.get("from", {}).get("date")
                        end = entry.get("to", {}).get("date")
                        price = entry.get("price")
                        parts = [f"{start} → {end}"]
                        if price not in (None, 0):
                            parts.append(f"{price:g}")
                        return " • ".join(part for part in parts if part)

                    date_idx = st.selectbox(
                        "Travel dates",
                        options=list(range(len(dates))),
                        key=date_key,
                        format_func=_format_date,
                    )
                    pick_payload["date_idx"] = date_idx

                available_qty = selected_item.get("available_qty")
                base_num = selected_item.get("num")
                if available_qty and available_qty > 1:
                    num_key = f"{select_key}_num"
                    if num_key not in st.session_state:
                        st.session_state[num_key] = int(base_num or 1)
                    num_value = st.number_input(
                        "Quantity",
                        min_value=1,
                        max_value=int(available_qty),
                        key=num_key,
                        step=1,
                    )
                    pick_payload["num"] = int(num_value)
                elif base_num is not None:
                    pick_payload["num"] = int(base_num or 1)

                picks_plan.append({"group": group_idx, "picks": [pick_payload]})

            elif group_type == "confirm":
                confirm_key = f"booking_step_{search_id}_{step}_{group_idx}_confirm"
                if confirm_key not in st.session_state:
                    st.session_state[confirm_key] = True
                confirm_value = st.checkbox(
                    "Confirm selections",
                    key=confirm_key,
                )
                if confirm_value:
                    picks_plan.append({"group": group_idx, "confirm": True})
                else:
                    issues.append("Confirmation required to continue.")
            else:
                st.info(f"Unsupported group type: {group_type}")

    if final:
        st.success("Selections confirmed. You can proceed to cart operations.")
        if response.get("temp_cart"):
            with st.expander("Temporary cart preview", expanded=False):
                show_json(response.get("temp_cart"))
        if response.get("temp_cart_pax"):
            with st.expander("Temporary pax", expanded=False):
                show_json(response.get("temp_cart_pax"))
            st.session_state["temp_cart_pax"] = response.get("temp_cart_pax")
            st.session_state["cart_pax"] = response.get("temp_cart_pax")
        else:
            st.session_state.pop("temp_cart_pax", None)
        return

    disabled = not picks_plan or bool(issues)
    if issues:
        for msg in issues:
            st.warning(msg)

    if st.button("Submit picks for this step", disabled=disabled):
        payload_entries: List[Dict[str, Any]] = []
        for entry in picks_plan:
            if entry.get("confirm"):
                payload_entries.append({"group": entry["group"], "confirm": True})
            else:
                payload_entries.append(
                    {"group": entry["group"], "picks": entry.get("picks", [])}
                )
        body = {
            "search_id": search_id,
            "step": step,
            "picks": payload_entries,
        }
        try:
            result = client.post("/api/booking/picks", json=body)
            st.session_state["booking_picks_response"] = result
            st.session_state["booking_last_response"] = result
            st.session_state["booking_flow"] = {
                "search_id": search_id,
                "response": result,
                "temp_cart_pax": result.get("temp_cart_pax"),
            }
            st.session_state["latest_search_id"] = search_id
            st.success("Step submitted.")
        except Exception as err:  # noqa: BLE001
            st.error(f"Picks submission failed: {err}")


def render_table(data: List[Dict[str, Any]], height: int = 300) -> None:
    """Render a list of dictionaries using AgGrid."""
    if not data:
        st.info("No records to display.")
        return
    df = pd.json_normalize(data)
    builder = GridOptionsBuilder.from_dataframe(df)
    builder.configure_pagination(enabled=True, paginationAutoPageSize=True)
    builder.configure_default_column(
        resizable=True, sortable=True, filter=True, wrapText=True, autoHeight=True
    )
    grid_options = builder.build()
    AgGrid(
        df,
        gridOptions=grid_options,
        height=height,
        theme="streamlit",
    )


def extract_records(payload: Any) -> List[Dict[str, Any]]:
    """Attempt to extract record list from various payload shapes."""
    if isinstance(payload, list):
        return [item for item in payload if isinstance(item, dict)]
    if isinstance(payload, dict):
        for key in ("items", "data", "results", "list"):
            value = payload.get(key)
            if isinstance(value, list):
                return [item for item in value if isinstance(item, dict)]
    return []


def show_json(payload: Any) -> None:
    """Display payload as formatted JSON."""
    st.code(json.dumps(payload, indent=2, default=str), language="json")


def crm_search_tab() -> None:
    """Render CRM search and client management UI."""
    st.subheader("CRM Search")
    client = get_backend_client()

    with st.form("crm_search_form"):
        email = st.text_input("Email")
        phone = st.text_input("Phone")
        surname = st.text_input("Surname / Last Name")
        code = st.text_input("Client Code")
        page = st.number_input("Page", min_value=1, value=1, step=1)
        per_page = st.number_input("Per Page", min_value=1, value=20, step=1)
        unfold = st.text_input("Unfold (comma separated fields)", value="")
        submit = st.form_submit_button("Search CRM")

    if submit:
        filters: Dict[str, Any] = {}
        if email:
            filters["filter[email]"] = email
        if phone:
            filters["filter[phone]"] = phone
        if surname:
            filters["filter[surname]"] = surname
        if code:
            filters["filter[code]"] = code
        payload = {
            "filters": filters,
            "page": page,
            "per_page": per_page,
        }
        if unfold:
            payload["unfold"] = unfold
        try:
            response = client.post("/api/crm/search", json=payload)
            st.session_state["crm_last_response"] = response
            st.session_state["crm_last_filters"] = payload
            st.success("CRM search completed.")
        except Exception as err:  # noqa: BLE001
            st.error(f"CRM search failed: {err}")

    if "crm_last_response" in st.session_state:
        response = st.session_state["crm_last_response"]
        records = extract_records(response)
        st.markdown("**Search Results**")
        render_table(records)
        with st.expander("Raw response", expanded=False):
            show_json(response)
        clients_map = get_crm_clients()
        for record in records:
            client_id = record.get("id")
            if client_id is not None:
                clients_map[client_id] = record
    render_active_client_selector("Set active client")
    active = get_active_client()
    if active:
        st.caption(f"Active client: {format_client_label(active, include_id=True)}")

    st.subheader("Add New Client")
    with st.form("crm_create_form"):
        first_name = st.text_input("First Name")
        last_name = st.text_input("Last Name")
        email = st.text_input("Email Address", key="create_email")
        phone = st.text_input("Phone Number", key="create_phone")
        country = st.text_input("Country (ISO 3166-1 alpha-2)", value="IT")
        marketing = st.checkbox("Marketing Consent", value=False)
        extra_json = st.text_area("Additional JSON fields", value="{}")
        create_submit = st.form_submit_button("Create Client")

    if create_submit:
        client_payload: Dict[str, Any] = {
            "name": f"{first_name} {last_name}".strip(),
            "firstname": first_name,
            "lastname": last_name,
            "email": email,
            "phone": phone,
            "country": country,
            "marketing": marketing,
        }
        try:
            extra = json.loads(extra_json or "{}")
            if isinstance(extra, dict):
                client_payload.update(extra)
        except json.JSONDecodeError:
            st.warning("Invalid JSON in additional fields. Ignoring.")
        try:
            response = client.post("/api/crm", json={"data": client_payload})
            st.success(f"Client created with id {response.get('id')}")
            with st.expander("Create response"):
                show_json(response)
            new_id = response.get("id")
            if new_id is not None:
                clients_map = get_crm_clients()
                clients_map[new_id] = response
                st.session_state["active_client_id"] = new_id
        except Exception as err:  # noqa: BLE001
            st.error(f"Client creation failed: {err}")

    st.subheader("Update Existing Client")
    with st.form("crm_update_form"):
        client_id = st.text_input("Client ID", key="update_client_id")
        update_json = st.text_area(
            "Update JSON payload",
            value='{"email": "new-email@example.com"}',
        )
        update_submit = st.form_submit_button("Update Client")

    if update_submit:
        try:
            data = json.loads(update_json)
        except json.JSONDecodeError:
            st.error("Invalid JSON payload for update.")
        else:
            try:
                response = client.put(f"/api/crm/{client_id}", json={"data": data})
                st.success("Client updated successfully.")
                with st.expander("Update response"):
                    show_json(response)
                clients_map = get_crm_clients()
                if client_id:
                    clients_map[int(client_id)] = response
            except Exception as err:  # noqa: BLE001
                st.error(f"Client update failed: {err}")


def parse_children(children_str: str) -> Optional[List[int]]:
    """Parse comma separated children age string."""
    if not children_str:
        return None
    try:
        return [int(age.strip()) for age in children_str.split(",") if age.strip()]
    except ValueError:
        st.warning("Invalid children ages; please use comma separated integers.")
        return None


def booking_tab() -> None:
    """Render property search and booking flow."""
    st.subheader("Property Search")
    client = get_backend_client()
    geo_labels = build_geo_options()
    active_client = get_active_client()
    if active_client:
        st.caption(f"Active client: {format_client_label(active_client, include_id=True)}")

    with st.form("booking_search_form"):
        service_type = st.selectbox(
            "Service Type",
            options=[
                "hotels",
                "tours",
                "flights",
                "transfers",
                "rentals",
                "cruises",
                "ferries",
                "insurance",
                "activities",
                "packages",
            ],
            index=0,
        )
        check_in = st.date_input("Check-in", value=date.today())
        check_out = st.date_input("Check-out", value=date.today())
        if geo_labels:
            geo_default: List[int] = st.session_state.get("geo_selected_ids", [])
            geo_lookup = st.multiselect(
                "Geo lookup (type to search)",
                options=list(geo_labels.keys()),
                default=geo_default,
                format_func=lambda geo_id: geo_labels.get(geo_id, str(geo_id)),
                help="Results from geo_ids.csv; type part of a destination name to narrow choices.",
            )
            if geo_lookup != geo_default:
                st.session_state["geo_selected_ids"] = geo_lookup
        else:
            st.caption("geo_ids.csv not found. Add it to enable geo search helper.")
            geo_lookup = []
        geo_nodes = st.text_input("Geo IDs (comma separated)", value="")
        service_ids = st.text_input("Specific Service IDs (comma separated)", value="")
        service_codes = st.text_input("Service Codes (comma separated)", value="")
        rooms = st.number_input("Rooms", min_value=1, max_value=4, value=1, step=1)
        occupancy: List[Dict[str, Any]] = []
        for room_index in range(rooms):
            adults = st.number_input(
                f"Room {room_index + 1} adults",
                min_value=1,
                max_value=6,
                value=2 if room_index == 0 else 1,
                key=f"room_{room_index}_adults",
            )
            children_ages = st.text_input(
                f"Room {room_index + 1} children ages",
                help="Comma separated ages, leave empty if none.",
                key=f"room_{room_index}_children",
            )
            room_payload: Dict[str, Any] = {"adults": adults}
            parsed_children = parse_children(children_ages)
            if parsed_children:
                room_payload["children"] = parsed_children
            occupancy.append(room_payload)

        per_page = st.number_input("Results per page", min_value=1, value=10, step=1)
        client_country = st.text_input("Client Country ISO Code", value="")
        run_search = st.form_submit_button("Run Search")

    if run_search:
        payload: Dict[str, Any] = {
            "type": service_type,
            "from": check_in.strftime("%Y-%m-%d"),
            "to": check_out.strftime("%Y-%m-%d"),
            "occupancy": occupancy,
            "per_page": per_page,
        }
        geo_set = set(geo_lookup)
        if geo_nodes:
            try:
                manual_nodes = [
                    int(node.strip()) for node in geo_nodes.split(",") if node.strip()
                ]
                geo_set.update(manual_nodes)
            except ValueError:
                st.warning("Geo IDs must be integers. Check your manual entries.")
        if geo_set:
            payload["geo"] = sorted(geo_set)
        if service_ids:
            payload["ids"] = [item.strip() for item in service_ids.split(",") if item.strip()]
        if service_codes:
            payload["codes"] = [item.strip() for item in service_codes.split(",") if item.strip()]
        if client_country:
            payload["client_country"] = client_country
        try:
            response = client.post("/api/booking/search", json=payload)
            st.session_state["booking_search_response"] = response
            st.session_state["latest_search_id"] = response.get("search_id")
            st.session_state["booking_last_response"] = response
            st.session_state["booking_flow"] = {
                "search_id": response.get("search_id"),
                "response": response,
                "temp_cart_pax": response.get("temp_cart_pax"),
            }
            st.success("Booking search executed.")
        except Exception as err:  # noqa: BLE001
            st.error(f"Booking search failed: {err}")

    if "booking_search_response" in st.session_state:
        response = st.session_state["booking_search_response"]
        search_id = response.get("search_id")
        if search_id:
            st.info(f"Search ID: {search_id}")
        with st.expander("Search response", expanded=False):
            show_json(response)

    flow_state = st.session_state.get("booking_flow")
    if flow_state:
        render_booking_step_controls(flow_state, client)

    st.subheader("Booking Picks & Cart")
    latest_response = st.session_state.get("booking_last_response")
    if isinstance(latest_response, dict) and "groups" in latest_response:
        samples = build_pick_samples(latest_response)
        step_hint = latest_response.get("step")
        if samples:
            sample_key = f"{latest_response.get('search_id')}:{step_hint}"
            prev_key = st.session_state.get("booking_template_key")
            if sample_key != prev_key:
                st.session_state["booking_picks_template"] = json.dumps(samples, indent=2)
                st.session_state["booking_template_key"] = sample_key
            st.markdown(f"**Current step:** {step_hint}")
            st.code(json.dumps(samples, indent=2), language="json")
        else:
            st.info(f"Current step: {step_hint}. Awaiting selectable groups.")

    with st.expander("Advanced: manual picks JSON", expanded=False):
        default_picks = st.session_state.get(
            "booking_picks_template",
            '[{"group": 0, "picks": [{"idx": 0, "date_idx": 0}]}]',
        )
        with st.form("booking_picks_form"):
            search_id = st.text_input(
                "Search ID", value=st.session_state.get("latest_search_id", "")
            )
            step = st.number_input("Step", min_value=0, value=0, step=1)
            picks_json = st.text_area(
                "Picks payload",
                value=default_picks,
                help="Refer to Travio documentation for structure.",
            )
            run_picks = st.form_submit_button("Submit Picks")

        if run_picks:
            try:
                picks_payload = json.loads(picks_json)
            except json.JSONDecodeError:
                st.error("Invalid JSON for picks payload.")
            else:
                payload = {"search_id": search_id, "step": step, "picks": picks_payload}
                try:
                    response = client.post("/api/booking/picks", json=payload)
                    st.session_state["booking_picks_response"] = response
                    st.session_state["booking_last_response"] = response
                    st.session_state["booking_flow"] = {
                        "search_id": search_id,
                        "response": response,
                    }
                    st.success("Picks submitted successfully.")
                except Exception as err:  # noqa: BLE001
                    st.error(f"Submitting picks failed: {err}")

    if "booking_picks_response" in st.session_state:
        with st.expander("Picks response"):
            show_json(st.session_state["booking_picks_response"])

    st.subheader("Cart Operations")
    with st.form("cart_add_form"):
        search_id = st.text_input(
            "Search ID to add to cart", value=st.session_state.get("latest_search_id", "")
        )
        add_to_cart = st.form_submit_button("Add to Cart")
    if add_to_cart:
        try:
            response = client.put("/api/booking/cart", json={"search_id": search_id})
            st.session_state["cart_response"] = response
            cart_id = response.get("id") or response.get("cart_id")
            if cart_id:
                st.session_state["latest_cart_id"] = str(cart_id)
            cart_pax = response.get("pax") or st.session_state.get("temp_cart_pax", [])
            if cart_pax:
                st.session_state["cart_pax"] = cart_pax
            st.success("Search added to cart.")
        except Exception as err:  # noqa: BLE001
            st.error(f"Add to cart failed: {err}")

    with st.form("cart_get_form"):
        cart_id = st.text_input(
            "Cart ID", value=st.session_state.get("latest_cart_id", "")
        )
        fetch_cart = st.form_submit_button("Get Cart")
    if fetch_cart:
        try:
            response = client.get(f"/api/booking/cart/{cart_id}")
            st.session_state["cart_response"] = response
            if response.get("pax"):
                st.session_state["cart_pax"] = response.get("pax")
            st.success("Cart retrieved.")
        except Exception as err:  # noqa: BLE001
            st.error(f"Cart retrieval failed: {err}")

    if "cart_response" in st.session_state:
        with st.expander("Cart response", expanded=False):
            show_json(st.session_state["cart_response"])

    with st.form("cart_remove_form"):
        search_id = st.text_input(
            "Search ID to remove from cart",
            value=st.session_state.get("latest_search_id", ""),
        )
        remove = st.form_submit_button("Remove from Cart")
    if remove:
        try:
            response = client.delete("/api/booking/cart", json={"search_id": search_id})
            st.success("Removed from cart.")
            with st.expander("Remove response"):
                show_json(response)
        except Exception as err:  # noqa: BLE001
            st.error(f"Remove from cart failed: {err}")


def quote_tab() -> None:
    """Render quote placement and delivery flow."""
    st.subheader("Place Quote")
    client = get_backend_client()
    active_client = get_active_client()
    if active_client:
        st.caption(f"Active client: {format_client_label(active_client, include_id=True)}")
    else:
        st.caption("No active CRM client selected. Pick one from the CRM tab for auto-fill.")

    cart_id_default = st.session_state.get("latest_cart_id", "")
    cart_pax = st.session_state.get("cart_pax") or st.session_state.get("temp_cart_pax") or []
    active_id = st.session_state.get("active_client_id")
    pax_prefill = build_cart_pax_prefill(cart_pax, active_client)
    prefill_key = f"{cart_id_default}:{len(cart_pax)}:{active_id}"
    stored_key = st.session_state.get("quote_pax_key")
    if prefill_key != stored_key:
        st.session_state["quote_pax_prefill"] = json.dumps(pax_prefill or [], indent=2, default=str)
        st.session_state["quote_pax_key"] = prefill_key
    pax_default = st.session_state.get(
        "quote_pax_prefill", json.dumps(pax_prefill or [], indent=2, default=str)
    )

    with st.form("place_quote_form"):
        cart_id = st.text_input(
            "Cart ID",
            value=cart_id_default,
        )
        pax_json = st.text_area(
            "Pax JSON",
            value=pax_default,
            help="Defaults to cart pax placeholders. Update the primary entry with client details if needed.",
        )
        status = st.selectbox(
            "Reservation Status",
            options=[
                ("Quote", 0),
                ("Option", 1),
                ("Working / On Request", 2),
                ("Confirmed", 3),
            ],
            format_func=lambda item: item[0],
        )
        due_date = st.text_input(
            "Due date (YYYY-MM-DD hh:mm:ss, optional)",
            value="",
        )
        reference = st.text_input("Client reference", value="")
        description = st.text_input("Custom description", value="")
        request_payment_link = st.checkbox("Request payment link", value=False)
        notes_json = st.text_area(
            "Notes JSON",
            value='[{"type": "internal", "text": "Prepared via Streamlit"}]',
        )
        submit_place = st.form_submit_button("Place Quote")

    if submit_place:
        try:
            pax_data = json.loads(pax_json)
            notes_data = json.loads(notes_json) if notes_json else None
        except json.JSONDecodeError:
            st.error("Invalid JSON in pax or notes.")
        else:
            payload: Dict[str, Any] = {
                "pax": pax_data,
                "status": status[1],
            }
            if active_client and active_client.get("id"):
                payload["client_id"] = active_client["id"]
            if due_date:
                payload["due"] = due_date
            if reference:
                payload["reference"] = reference
            if description:
                payload["description"] = description
            if notes_data:
                payload["notes"] = notes_data
            if request_payment_link:
                payload["payment_link"] = True
            try:
                response = client.post(f"/api/quotes/place/{cart_id}", json=payload)
                st.session_state["quote_response"] = response
                reservation_id = response.get("id") or response.get("reservation_id")
                if reservation_id:
                    st.session_state["latest_reservation_id"] = reservation_id
                st.success("Quote placed successfully.")
            except Exception as err:  # noqa: BLE001
                st.error(f"Quote placement failed: {err}")

    if "quote_response" in st.session_state:
        with st.expander("Quote response"):
            show_json(st.session_state["quote_response"])

    st.subheader("Send Quote")
    with st.form("send_quote_form"):
        reservation_id = st.text_input(
            "Reservation ID",
            value=str(st.session_state.get("latest_reservation_id", "")),
        )
        last_template = st.session_state.get("quote_template_id", 2)
        template_id = st.number_input(
            "Template ID",
            min_value=1,
            value=last_template,
            step=1,
            help="Template 2 or 3 usually exist by default. Adjust if your Travio account has different templates.",
        )
        archive = st.checkbox("Archive PDF in reservation", value=False)
        send_email = st.checkbox("Send email to client", value=True)
        submit_send = st.form_submit_button("Send Quote")

    if submit_send:
        payload: Dict[str, Any] = {"template": template_id}
        if archive:
            payload["archive"] = True
        if send_email:
            payload["send"] = True
        try:
            response = client.post(f"/api/quotes/send/{reservation_id}", json=payload)
        except Exception as err:  # noqa: BLE001
            message = str(err)
            if "Template not found" in message and template_id != 2:
                fallback_payload = payload.copy()
                fallback_payload["template"] = 2
                st.warning(
                    "Selected template was not found. Retrying with template 2...",
                )
                try:
                    response = client.post(
                        f"/api/quotes/send/{reservation_id}",
                        json=fallback_payload,
                    )
                    st.session_state["quote_template_id"] = 2
                    st.success("Quote sent using template 2.")
                    with st.expander("Send quote response"):
                        show_json(response)
                except Exception as err2:  # noqa: BLE001
                    st.error(f"Send quote failed after fallback: {err2}")
            else:
                st.error(f"Send quote failed: {err}")
        else:
            st.session_state["quote_template_id"] = template_id
            st.success("Quote send request submitted.")
            with st.expander("Send quote response"):
                show_json(response)


def dashboard_tab() -> None:
    """Render dashboard overview."""
    st.subheader("Backend Status")
    client = get_backend_client()
    try:
        health = client.get("/api/system/health")
        st.success("Backend reachable.")
        st.json(health)
    except Exception as err:  # noqa: BLE001
        st.error(f"Unable to reach backend: {err}")

    st.subheader("Token Management")
    col1, col2 = st.columns(2)
    with col1:
        if st.button("Request Token"):
            try:
                response = client.post("/api/auth/token")
                st.session_state["last_token"] = response.get("token")
                st.success("Token refreshed.")
            except Exception as err:  # noqa: BLE001
                st.error(f"Token request failed: {err}")
    with col2:
        if st.button("Get Profile"):
            try:
                profile = client.get("/api/auth/profile")
                st.session_state["profile"] = profile
                st.success("Profile retrieved.")
            except Exception as err:  # noqa: BLE001
                st.error(f"Profile request failed: {err}")

    if "profile" in st.session_state:
        with st.expander("Profile data"):
            show_json(st.session_state["profile"])

    st.subheader("Session Activity")
    if st.button("Refresh Activity Log"):
        try:
            activity = client.get("/api/system/activity")
            st.session_state["activity_log"] = activity
        except Exception as err:  # noqa: BLE001
            st.error(f"Activity fetch failed: {err}")

    if st.button("Clear Activity Log"):
        try:
            client.delete("/api/system/activity")
            st.session_state.pop("activity_log", None)
            st.success("Activity log cleared.")
        except Exception as err:  # noqa: BLE001
            st.error(f"Failed to clear activity log: {err}")

    if "activity_log" in st.session_state:
        render_table(st.session_state["activity_log"], height=200)


def activity_tab() -> None:
    """Display live activity log."""
    st.subheader("Activity Log")
    client = get_backend_client()
    try:
        activity = client.get("/api/system/activity")
        render_table(activity, height=300)
    except Exception as err:  # noqa: BLE001
        st.error(f"Could not load activity log: {err}")


def settings_tab() -> None:
    """Render settings controls."""
    st.subheader("Connection Settings")
    backend_url = st.text_input(
        "Backend URL",
        value=st.session_state.get("backend_url", "http://localhost:8000"),
    )
    if backend_url != st.session_state.get("backend_url"):
        st.session_state["backend_url"] = backend_url
        st.success(f"Backend URL updated to {backend_url}")

    st.markdown(
        """
        **Usage Tips**
        - Start FastAPI backend: `uvicorn backend.app.main:app --reload`
        - Start Streamlit UI: `streamlit run frontend/app.py`
        - Provide Travio API credentials via `.env.local` or environment variables.
        - Use mock mode once fixtures are configured.
        """
    )


def main() -> None:
    """Application entry point."""
    st.set_page_config(page_title="Travio Assistant", layout="wide")
    if "backend_url" not in st.session_state:
        st.session_state["backend_url"] = "http://localhost:8000"

    tabs = st.tabs(
        [
            "Dashboard",
            "CRM Search",
            "Property Search",
            "Quote Builder",
            "Activity Log",
            "Settings",
        ]
    )
    with tabs[0]:
        dashboard_tab()
    with tabs[1]:
        crm_search_tab()
    with tabs[2]:
        booking_tab()
    with tabs[3]:
        quote_tab()
    with tabs[4]:
        activity_tab()
    with tabs[5]:
        settings_tab()


if __name__ == "__main__":
    main()
