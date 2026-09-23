import re

from fastapi.testclient import TestClient


def create_tenant(client: TestClient) -> str:
    response = client.post(
        "/tenants",
        json={"name": "Holzwerk", "email": "holzwerk@example.com"},
    )
    assert response.status_code == 201
    return response.json()["id"]


def test_owner_admin_and_employee_accounts(client: TestClient):
    tenant_id = create_tenant(client)

    owner_response = client.post(
        "/accounts",
        json={"name": "Owner", "email": "owner@example.com", "role": "OWNER"},
    )
    admin_response = client.post(
        "/accounts",
        json={"name": "Admin", "email": "admin@example.com", "role": "ADMIN"},
    )
    employee_response = client.post(
        "/accounts",
        json={"name": "Mitarbeiter", "role": "EMPLOYEE"},
    )

    for response, role in (
        (owner_response, "OWNER"),
        (admin_response, "ADMIN"),
        (employee_response, "EMPLOYEE"),
    ):
        assert response.status_code == 201
        payload = response.json()
        assert payload["tenant_id"] == tenant_id
        assert payload["role"] == role
        assert payload["password_change_required"] is True
        assert re.fullmatch(r"[A-Z]{2}-\d{6}", payload["account_id"])

    assert employee_response.json()["email"] is None


def test_generated_account_ids_are_unique(client: TestClient):
    create_tenant(client)

    first_response = client.post(
        "/accounts",
        json={"name": "Erster", "role": "EMPLOYEE"},
    )
    second_response = client.post(
        "/accounts",
        json={"name": "Zweiter", "role": "EMPLOYEE"},
    )

    assert first_response.status_code == 201
    assert second_response.status_code == 201
    assert first_response.json()["account_id"] != second_response.json()["account_id"]


def test_password_change_requirement_can_be_explicitly_disabled(client: TestClient):
    create_tenant(client)

    response = client.post(
        "/accounts",
        json={
            "name": "Owner",
            "email": "owner@example.com",
            "role": "OWNER",
            "password_change_required": False,
        },
    )

    assert response.status_code == 201
    assert response.json()["password_change_required"] is False


def test_invalid_account_roles_and_missing_privileged_email_are_rejected(client: TestClient):
    create_tenant(client)

    invalid_role_response = client.post(
        "/accounts",
        json={"name": "Unbekannt", "role": "MANAGER"},
    )
    missing_email_response = client.post(
        "/accounts",
        json={"name": "Owner", "role": "OWNER"},
    )

    assert invalid_role_response.status_code == 422
    assert missing_email_response.status_code == 422
