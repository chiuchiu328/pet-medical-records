from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app


@pytest.fixture
def client(tmp_path):
    settings = Settings(
        database_url=f"sqlite:///{tmp_path / 'test.db'}",
        upload_dir=tmp_path / "uploads",
    )
    app = create_app(settings)
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def momo_pet(client):
    response = client.post(
        "/pets",
        json={
            "name": "摸摸",
            "species": "cat",
            "breed": "米克斯",
            "sex": "female",
            "birth_date": "2021-03-12",
            "microchip_number": "900123456789012",
            "notes": "對某些藥物較敏感",
        },
    )
    assert response.status_code == 201
    return response.json()
