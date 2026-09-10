"""
Tests for model3_federation.api.router
Tests REST endpoints and WebSocket functionality using FastAPI TestClient.
"""

from datetime import datetime, timezone
from unittest.mock import MagicMock
from uuid import uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from model3_federation.api.router import router, _events_per_min, _adapters, _bus
from model3_federation.adapters.police_vms_adapter import PoliceVMSAdapter
from model3_federation.bus.event_bus import FederationEventBus
from shared.db.session import get_db


@pytest.fixture
def app_with_federation():
    app = FastAPI()
    app.include_router(router)
    return app


def test_get_federated_systems_endpoint(app_with_federation):
    mock_session = MagicMock()
    # Return 1 system row: id, name, vendor, status, camera_count, last_heartbeat, protocol, dept_name
    mock_session.execute.return_value.fetchall.return_value = [
        (
            "sys-police-01",
            "Gujarat Police VMS",
            "milestone",
            "online",
            5,
            datetime.now(timezone.utc),
            "ONVIF Profile S",
            "Police",
        )
    ]

    app_with_federation.dependency_overrides[get_db] = lambda: mock_session
    client = TestClient(app_with_federation)

    response = client.get("/api/v3/systems")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["name"] == "Gujarat Police VMS"
    assert data[0]["vendor"] == "milestone"
    assert data[0]["camera_count"] == 5


def test_get_federated_cameras_endpoint(app_with_federation):
    mock_session = MagicMock()
    # id, system_id, external_id, name, location_label, is_active, lat, lng, system_name, vendor
    mock_session.execute.return_value.fetchall.return_value = [
        (
            str(uuid4()),
            "sys-police-01",
            "cam-pol-01",
            "Iskcon Cross Road, Ahmedabad",
            "SG Highway, Ahmedabad",
            True,
            23.0298,
            72.5067,
            "Gujarat Police VMS",
            "milestone",
        )
    ]

    app_with_federation.dependency_overrides[get_db] = lambda: mock_session
    client = TestClient(app_with_federation)

    response = client.get("/api/v3/cameras?system_id=sys-police-01")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["external_id"] == "cam-pol-01"
    assert data[0]["lat"] == 23.0298
    assert data[0]["lng"] == 72.5067


def test_get_federated_events_endpoint(app_with_federation):
    mock_session = MagicMock()
    # id, system_id, event_type, detected_plate, confidence, vehicle_type, received_at, source_timestamp, sys_name, vendor, cam_name
    mock_session.execute.return_value.fetchall.return_value = [
        (
            str(uuid4()),
            "sys-police-01",
            "vehicle_detection",
            "GJ01AB1234",
            0.95,
            "car",
            datetime.now(timezone.utc),
            datetime.now(timezone.utc),
            "Gujarat Police VMS",
            "milestone",
            "Iskcon Cross Road",
        )
    ]

    app_with_federation.dependency_overrides[get_db] = lambda: mock_session
    client = TestClient(app_with_federation)

    response = client.get("/api/v3/events?limit=10")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["detected_plate"] == "GJ01AB1234"
    assert data[0]["confidence"] == 0.95


def test_events_stats_endpoint(app_with_federation):
    mock_session = MagicMock()
    mock_session.execute.return_value.fetchall.return_value = [
        ("sys-police-01", "Gujarat Police VMS", "milestone")
    ]

    app_with_federation.dependency_overrides[get_db] = lambda: mock_session
    client = TestClient(app_with_federation)

    response = client.get("/api/v3/events/stats")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["system_name"] == "Gujarat Police VMS"
    assert "events_per_min" in data[0]


def test_acknowledge_alert_endpoint(app_with_federation):
    mock_session = MagicMock()
    alert_id = str(uuid4())
    mock_session.execute.return_value.fetchone.return_value = (alert_id,)

    app_with_federation.dependency_overrides[get_db] = lambda: mock_session
    client = TestClient(app_with_federation)

    response = client.post(f"/api/v3/alerts/{alert_id}/acknowledge")
    assert response.status_code == 200
    assert response.json()["status"] == "acknowledged"


def test_websocket_federation(app_with_federation):
    client = TestClient(app_with_federation)
    with client.websocket_connect("/api/v3/ws/federation") as ws:
        msg = ws.receive_json()
        assert msg["type"] == "heartbeat"
        assert "Federation WebSocket connected" in msg["payload"]["message"]
