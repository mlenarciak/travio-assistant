import os

os.environ.setdefault("USE_MOCK_DATA", "true")
os.environ.setdefault("TRAVIO_ID", "13")
os.environ.setdefault("TRAVIO_KEY", "mock-key")
os.environ.setdefault("TRAVIO_BASE_URL", "https://api.travio.it")

from fastapi.testclient import TestClient  # noqa: E402

from backend.app.main import app  # noqa: E402

import pytest  # noqa: E402


@pytest.fixture()
def client():
    with TestClient(app) as c:
        yield c


def test_health_endpoint(client):
    response = client.get("/api/system/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["use_mock_data"] is True


def test_auth_and_profile(client):
    token_response = client.post("/api/auth/token")
    assert token_response.status_code == 200
    profile_response = client.get("/api/auth/profile")
    assert profile_response.status_code == 200
    profile = profile_response.json()
    assert profile["user"]["name"] == "Mock User"


def test_crm_search_and_create_update(client):
    search_response = client.post(
        "/api/crm/search",
        json={"filters": {"filter[email]": "alice"}},
    )
    assert search_response.status_code == 200
    results = search_response.json()
    assert results["total"] >= 1

    create_response = client.post(
        "/api/crm",
        json={"data": {"name": "Charlie Tester", "email": "charlie@example.com"}},
    )
    assert create_response.status_code == 200
    created = create_response.json()
    client_id = created["id"]

    update_response = client.put(
        f"/api/crm/{client_id}",
        json={"data": {"phone": "+3900009999"}},
    )
    assert update_response.status_code == 200
    updated = update_response.json()
    if "phone" in updated:
        assert updated["phone"] == "+3900009999"
    else:
        contacts = updated.get("contacts", [])
        assert any(
            "+3900009999" in (contact.get("phone") or [])
            for contact in contacts
        )


def test_booking_flow_and_quote(client):
    search_payload = {
        "type": "hotels",
        "from": "2024-08-01",
        "to": "2024-08-05",
        "occupancy": [{"adults": 2}],
    }
    search_response = client.post("/api/booking/search", json=search_payload)
    assert search_response.status_code == 200
    search_data = search_response.json()
    search_id = search_data["search_id"]

    picks_response = client.post(
        "/api/booking/picks",
        json={"search_id": search_id, "step": 0, "picks": [{"group": 0, "picks": [{"idx": 0}]}]},
    )
    assert picks_response.status_code == 200

    cart_response = client.put("/api/booking/cart", json={"search_id": search_id})
    assert cart_response.status_code == 200
    cart_data = cart_response.json()
    cart_id = cart_data["id"]

    place_payload = {
        "pax": [{"id": 1, "name": "John", "surname": "Doe"}],
        "status": 0,
        "reference": "REF123",
    }
    place_response = client.post(f"/api/quotes/place/{cart_id}", json=place_payload)
    assert place_response.status_code == 200
    reservation = place_response.json()
    reservation_id = reservation["id"]

    send_response = client.post(
        f"/api/quotes/send/{reservation_id}",
        json={"template": 1, "send": True},
    )
    assert send_response.status_code == 200
    send_data = send_response.json()
    assert send_data["reservation_id"] == reservation_id
