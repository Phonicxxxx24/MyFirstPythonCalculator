"""
Tests for model3_federation.schemas.models
Validates Pydantic model serialization, validation constraints, and defaults.
"""

from datetime import datetime, timezone

from model3_federation.schemas.models import (
    CorrelationResult,
    FederatedAlert,
    FederatedCamera,
    FederatedEvent,
    FederatedSystem,
    WSMessage,
)


def test_federated_event_creation_and_defaults():
    now = datetime.now(timezone.utc)
    event = FederatedEvent(
        system_id="sys-police-01",
        system_name="Gujarat Police VMS",
        vendor="milestone",
        camera_external_id="cam-pol-01",
        camera_name="Iskcon Cross Road, Ahmedabad",
        event_type="vehicle_detection",
        detected_plate="GJ01AB1234",
        confidence=0.95,
        vehicle_type="car",
        source_timestamp=now,
    )

    assert isinstance(event.id, str)
    assert event.system_id == "sys-police-01"
    assert event.detected_plate == "GJ01AB1234"
    assert event.confidence == 0.95
    assert event.received_at <= datetime.now(timezone.utc)
    assert event.raw_payload == {}


def test_federated_event_serialization():
    event = FederatedEvent(
        system_id="sys-rto-01",
        system_name="Gujarat RTO VMS",
        vendor="hikvision",
        camera_external_id="cam-rto-01",
        camera_name="Subhash Bridge RTO, Ahmedabad",
        event_type="vehicle_detection",
        detected_plate="GJ27X1234",
        confidence=0.91,
        vehicle_type="truck",
        source_timestamp=datetime(2026, 9, 10, 10, 0, 0, tzinfo=timezone.utc),
    )

    json_data = event.model_dump_json()
    assert "GJ27X1234" in json_data
    assert "hikvision" in json_data
    parsed = FederatedEvent.model_validate_json(json_data)
    assert parsed.id == event.id
    assert parsed.detected_plate == "GJ27X1234"


def test_federated_camera_schema():
    cam = FederatedCamera(
        external_id="cam-mun-01",
        name="SG Highway Near Vaishnodevi Circle",
        system_name="Gujarat Municipal VMS",
        vendor="dahua",
        department="Municipal",
        lat=23.1256,
        lng=72.5342,
        location_label="SG Highway, Ahmedabad",
        is_active=True,
    )

    assert cam.lat == 23.1256
    assert cam.lng == 72.5342
    assert cam.is_active is True
    assert cam.department == "Municipal"


def test_correlation_result_schema():
    now = datetime.now(timezone.utc)
    corr = CorrelationResult(
        plate_number="GJ01AB1234",
        systems_involved=["sys-police-01", "sys-rto-01"],
        first_seen=now,
        last_seen=now,
        travel_time_secs=12,
        camera_sequence=[
            {"system": "sys-police-01", "camera": "cam-pol-01", "time": now.isoformat()},
            {"system": "sys-rto-01", "camera": "cam-rto-01", "time": now.isoformat()},
        ],
        is_watchlisted=True,
    )

    assert corr.plate_number == "GJ01AB1234"
    assert len(corr.systems_involved) == 2
    assert corr.is_watchlisted is True
    assert corr.travel_time_secs == 12


def test_federated_alert_schema():
    alert = FederatedAlert(
        event_id="evt-1234",
        plate_number="GJ01AB1234",
        system_name="Gujarat Police VMS",
        camera_name="Iskcon Cross Road",
        severity="critical",
    )

    assert alert.severity == "critical"
    assert alert.plate_number == "GJ01AB1234"
    assert alert.acknowledged is False


def test_ws_message_schema():
    msg = WSMessage(
        type="event",
        payload={"plate": "GJ01AB1234", "camera": "cam-pol-01"},
    )
    assert msg.type == "event"
    assert msg.payload["plate"] == "GJ01AB1234"
