"""
Tests for model3_federation.correlation.engine
Tests deduplication, watchlist detection, cross-system correlation, and WebSocket dispatch.
"""

from datetime import datetime, timezone
from unittest.mock import MagicMock
from uuid import uuid4
import pytest

from model3_federation.bus.event_bus import FederationEventBus
from model3_federation.correlation.engine import CorrelationEngine, _normalize_plate
from model3_federation.schemas.models import FederatedEvent, WSMessage


def test_plate_normalization():
    assert _normalize_plate("GJ-01-AB-1234") == "GJ01AB1234"
    assert _normalize_plate(" gj 05 cd  5678 ") == "GJ05CD5678"
    assert _normalize_plate("") is None
    assert _normalize_plate(None) is None


@pytest.mark.asyncio
async def test_deduplication():
    bus = FederationEventBus(redis_url=None)
    ws_messages: list[WSMessage] = []

    async def mock_ws_broadcast(msg: WSMessage):
        ws_messages.append(msg)

    engine = CorrelationEngine(
        bus=bus,
        db_session_factory=None,
        ws_broadcast=mock_ws_broadcast,
    )

    now = datetime.now(timezone.utc)
    event1 = FederatedEvent(
        system_id="sys-police-01",
        system_name="Gujarat Police VMS (Milestone)",
        vendor="Milestone",
        camera_external_id="cam-pol-01",
        camera_name="Test Cam",
        event_type="vehicle_detection",
        detected_plate="GJ01DEDUP1",
        confidence=0.90,
        source_timestamp=now,
    )

    # First event is processed and broadcast
    await engine.on_event(event1)
    assert len(ws_messages) == 1
    assert ws_messages[0].type == "event"

    # Immediate duplicate from same camera and same plate within 60s
    event2 = FederatedEvent(
        system_id="sys-police-01",
        system_name="Gujarat Police VMS (Milestone)",
        vendor="Milestone",
        camera_external_id="cam-pol-01",
        camera_name="Test Cam",
        event_type="vehicle_detection",
        detected_plate="GJ01-DEDUP1",  # Different formatting, same normalized plate
        confidence=0.92,
        source_timestamp=now,
    )
    await engine.on_event(event2)
    # Deduplicated — no new message broadcast
    assert len(ws_messages) == 1


@pytest.mark.asyncio
async def test_watchlist_alert_with_db():
    bus = FederationEventBus(redis_url=None)
    ws_messages: list[WSMessage] = []

    async def mock_ws_broadcast(msg: WSMessage):
        ws_messages.append(msg)

    mock_session = MagicMock()
    # Mock watchlist query returning a match
    mock_session.execute.return_value.fetchone.side_effect = [
        (str(uuid4()),),  # cam_row
        (str(uuid4()),),  # wl_row (watchlist hit!)
        (str(uuid4()),),  # ev_row
        None,             # existing correlation query
    ]
    mock_session.execute.return_value.fetchall.return_value = []

    engine = CorrelationEngine(
        bus=bus,
        db_session_factory=lambda: mock_session,
        ws_broadcast=mock_ws_broadcast,
    )

    event = FederatedEvent(
        system_id="sys-police-01",
        system_name="Gujarat Police VMS (Milestone)",
        vendor="Milestone",
        camera_external_id="cam-pol-02",
        camera_name="SG Highway",
        event_type="vehicle_detection",
        detected_plate="GJ01AB1234",
        confidence=0.96,
        source_timestamp=datetime.now(timezone.utc),
    )

    await engine.on_event(event)

    # Verify event and alert were broadcast
    types = [m.type for m in ws_messages]
    assert "event" in types
    assert "alert" in types
    alert_msg = next(m for m in ws_messages if m.type == "alert")
    assert alert_msg.payload["plate_number"] == "GJ01AB1234"
    assert alert_msg.payload["severity"] == "high"


@pytest.mark.asyncio
async def test_cross_system_correlation_with_db():
    bus = FederationEventBus(redis_url=None)
    ws_messages: list[WSMessage] = []

    async def mock_ws_broadcast(msg: WSMessage):
        ws_messages.append(msg)

    mock_session = MagicMock()
    first_seen_time = datetime.now(timezone.utc)
    # other_rows from previous sighting in police VMS:
    # fe.id, fe.system_id, fe.camera_id, fe.received_at, fc.name, lat, lng
    previous_sighting = [
        (
            str(uuid4()),
            "sys-police-01",
            str(uuid4()),
            first_seen_time,
            "Iskcon Cross Road",
            23.0298,
            72.5067,
        )
    ]

    mock_session.execute.return_value.fetchone.side_effect = [
        (str(uuid4()),),  # cam_row
        None,             # wl_row (no watchlist hit)
        None,             # existing correlation check
    ]
    # First fetchall: other_rows. Second fetchall: system names query
    mock_session.execute.return_value.fetchall.side_effect = [
        previous_sighting,
        [("Gujarat Police VMS",), ("Gujarat RTO VMS",)],
    ]

    engine = CorrelationEngine(
        bus=bus,
        db_session_factory=lambda: mock_session,
        ws_broadcast=mock_ws_broadcast,
    )

    # Event in RTO VMS with same plate
    event_rto = FederatedEvent(
        system_id="sys-rto-01",
        system_name="Gujarat RTO Checkpoint System (HikCentral)",
        vendor="Hikvision",
        camera_external_id="cam-rto-01",
        camera_name="Subhash Bridge RTO",
        event_type="vehicle_detection",
        detected_plate="GJ01CROSS9",
        confidence=0.91,
        source_timestamp=datetime.now(timezone.utc),
    )

    await engine.on_event(event_rto)

    # Verify event and correlation were broadcast
    types = [m.type for m in ws_messages]
    assert "event" in types
    assert "correlation" in types
    corr_msg = next(m for m in ws_messages if m.type == "correlation")
    assert corr_msg.payload["plate_number"] == "GJ01CROSS9"
    assert "Gujarat Police VMS" in corr_msg.payload["systems_involved"]
    assert "Gujarat RTO VMS" in corr_msg.payload["systems_involved"]
