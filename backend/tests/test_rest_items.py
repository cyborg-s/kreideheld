from fastapi.testclient import TestClient

from app.database import Base, engine
from app.main import app


def setup_function():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)


def test_rest_item_crud_flow():
    client = TestClient(app)

    tenant_response = client.post(
        "/tenants",
        json={"name": "Holzwerk", "email": "holz@example.com", "unit_preference": "mm", "is_active": True},
    )
    assert tenant_response.status_code == 201

    rest_type_response = client.post(
        "/rest-types",
        json={"name": "Massivholz", "measure_fields": ["length_mm", "width_mm", "height_mm"], "accepted_rotated_input": True},
    )
    assert rest_type_response.status_code == 201

    create_response = client.post(
        "/rest-items",
        json={
            "rest_type_id": rest_type_response.json()["id"],
            "chalk_number": "1234",
            "material_name": "Buche",
            "length_mm": 2000,
            "width_mm": 150,
            "height_mm": 25,
            "rest_meter_mm": 4000,
            "notes": "gut erhalten",
        },
    )
    assert create_response.status_code == 201
    item_id = create_response.json()["id"]

    get_response = client.get(f"/rest-items/{item_id}")
    assert get_response.status_code == 200

    update_response = client.put(
        f"/rest-items/{item_id}",
        json={
            "rest_type_id": rest_type_response.json()["id"],
            "chalk_number": "1235",
            "material_name": "Ahorn",
            "length_mm": 1800,
            "width_mm": 120,
            "height_mm": 20,
            "rest_meter_mm": 3000,
            "notes": "aktualisiert",
        },
    )
    assert update_response.status_code == 200

    delete_response = client.delete(f"/rest-items/{item_id}")
    assert delete_response.status_code == 204
