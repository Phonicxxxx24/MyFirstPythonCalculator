"""
Live End-to-End Integration Tests for Model 3 Federation
Runs against live Docker containers: PostgreSQL PostGIS and Redis.
"""

import asyncio
from datetime import datetime, timezone
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from model3_federation.api.router import router, _adapters, _bus
from model3_federation.bus.event_bus import FederationEventBus
from model3_federation.correlation.engine import CorrelationEngine
from model3_federation.schemas.models import FederatedEvent, WSMessage
from shared.db.session import get_db, init_engine

DATABASE_URL = "postgresql://sentinel:sentinel_dev@localhost:5432/sentinel"
REDIS_URL = "redis://localhost:6379"


@pytest.fixture(scope="module")
def real_db_session_factory():
    engine = create_engine(DATABASE_URL, pool_pre_ping=True)
    SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)
    init_engine(DATABASE_URL)
    return SessionLocal


@pytest.fixture(scope="module")
def app_with_real_db(real_db_session_factory):
    app = FastAPI()
    app.include_router(router)

    def override_get_db():
        db = real_db_session_factory()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    return app


def test_live_db_systems_and_cameras(app_with_real_db):
    client = TestClient(app_with_real_db)

    # 1. Systems endpoint
    res_sys = client.get("/api/v3/systems")
    assert res_sys.status_code == 200
    systems = res_sys.json()
    assert len(systems) == 3
    system_names = [s["name"] for s in systems]
    assert "Gujarat Police VMS (Milestone)" in system_names
    assert "Gujarat RTO Checkpoint System (HikCentral)" in system_names
    assert "AMC City Surveillance (Dahua)" in system_names

    # 2. Cameras endpoint
    res_cam = client.get("/api/v3/cameras")
    assert res_cam.status_code == 200
    cameras = res_cam.json()
    assert len(cameras) == 13
    assert all(c["lat"] is not None and c["lng"] is not None for c in cameras)


def test_live_db_events_and_correlations(app_with_real_db):
    client = TestClient(app_with_real_db)

    # 3. Events endpoint
    res_events = client.get("/api/v3/events?limit=10")
    assert res_events.status_code == 200
    events = res_events.json()
    assert len(events) >= 1

    # 4. Correlations endpoint
    res_corr = client.get("/api/v3/correlations")
    assert res_corr.status_code == 200
    corrs = res_corr.json()
    assert len(corrs) >= 2


@pytest.mark.asyncio
async def test_live_redis_bus_and_correlation_engine(real_db_session_factory):
    bus = FederationEventBus(redis_url=REDIS_URL)
    ws_messages: list[WSMessage] = []

    async def mock_ws_broadcast(msg: WSMessage):
        ws_messages.append(msg)

    engine = CorrelationEngine(
        bus=bus,
        db_session_factory=real_db_session_factory,
        ws_broadcast=mock_ws_broadcast,
    )

    # Start subscriber loop
    sub_task = asyncio.create_task(bus.subscribe(engine.on_event))
    await asyncio.sleep(0.1)

    # Retrieve valid camera IDs from PostgreSQL
    session = real_db_session_factory()
    police_cam = session.execute(text(
        "SELECT external_id, system_id, name FROM federated_cameras WHERE external_id = 'cam-pol-01' LIMIT 1"
    )).fetchone()
    rto_cam = session.execute(text(
        "SELECT external_id, system_id, name FROM federated_cameras WHERE external_id = 'rto-nh48-01' LIMIT 1"
    )).fetchone()
    session.close()

    assert police_cam is not None
    assert rto_cam is not None

    test_plate = f"GJ01LIVE{int(datetime.now().timestamp()) % 10000:04d}"

    # Publish Event 1 from Police VMS
    event1 = FederatedEvent(
        system_id=str(police_cam[1]),
        system_name="Gujarat Police VMS",
        vendor="milestone",
        camera_external_id=police_cam[0],
        camera_name=police_cam[2],
        event_type="vehicle_detection",
        detected_plate=test_plate,
        confidence=0.97,
        source_timestamp=datetime.now(timezone.utc),
    )
    await bus.publish(event1)
    await asyncio.sleep(0.3)

    # Publish Event 2 from RTO VMS (same plate -> triggers correlation!)
    event2 = FederatedEvent(
        system_id=str(rto_cam[1]),
        system_name="Gujarat RTO VMS",
        vendor="hikvision",
        camera_external_id=rto_cam[0],
        camera_name=rto_cam[2],
        event_type="vehicle_detection",
        detected_plate=test_plate,
        confidence=0.93,
        source_timestamp=datetime.now(timezone.utc),
    )
    await bus.publish(event2)
    await asyncio.sleep(0.5)

    sub_task.cancel()
    try:
        await sub_task
    except asyncio.CancelledError:
        pass

    # Verify event and correlation were written to the real DB
    db = real_db_session_factory()
    saved_events = db.execute(text(
        "SELECT count(*) FROM federated_events WHERE detected_plate = :p"
    ), {"p": test_plate}).fetchone()[0]
    assert saved_events >= 2

    saved_corr = db.execute(text(
        "SELECT id, plate_number, system_ids, travel_time_secs FROM correlation_results WHERE plate_number = :p"
    ), {"p": test_plate}).fetchone()
    assert saved_corr is not None
    assert saved_corr[1] == test_plate
    assert len(saved_corr[2]) == 2
    db.close()
