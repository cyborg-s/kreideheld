from fastapi.testclient import TestClient

from app.database import Base, engine
from app.main import app


def setup_function():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)


def test_login_with_created_tenant():
    client = TestClient(app)

    tenant_payload = {
        "name": "Test Betrieb",
        "email": "test@example.com",
        "unit_preference": "mm",
        "is_active": True,
    }

    tenant_response = client.post("/tenants", json=tenant_payload)
    assert tenant_response.status_code == 201

    login_response = client.post(
        "/auth/login",
        json={"email": tenant_payload["email"], "password": "demo123"},
    )

    assert login_response.status_code == 200
    payload = login_response.json()
    assert payload["tenant_id"] == tenant_response.json()["id"]
    assert payload["email"] == tenant_payload["email"]
