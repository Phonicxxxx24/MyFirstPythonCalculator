"""
Tests for model3_federation.bus.event_bus
Validates pub/sub, in-process queue fallback, and subscriber loop.
"""

import asyncio
from datetime import datetime, timezone
import pytest

from model3_federation.bus.event_bus import FederationEventBus
from model3_federation.schemas.models import FederatedEvent


@pytest.mark.asyncio
async def test_event_bus_fallback_queue():
    bus = FederationEventBus(redis_url="redis://127.0.0.1:9999/0")

    sample_event = FederatedEvent(
        system_id="sys-police-01",
        system_name="Gujarat Police VMS (Milestone)",
        vendor="Milestone",
        camera_external_id="cam-pol-01",
        camera_name="Test Camera",
        event_type="vehicle_detection",
        detected_plate="GJ01TEST1",
        confidence=0.99,
        source_timestamp=datetime.now(timezone.utc),
    )

    await bus.publish(sample_event)
    assert bus._fallback_queue.qsize() == 1

    dequeued = await bus._fallback_queue.get()
    assert dequeued.detected_plate == "GJ01TEST1"


@pytest.mark.asyncio
async def test_event_bus_subscriber():
    bus = FederationEventBus(redis_url="redis://127.0.0.1:9999/0")
    received: list[FederatedEvent] = []

    async def handler(evt: FederatedEvent):
        received.append(evt)

    sub_task = asyncio.create_task(bus.subscribe(handler))

    sample_event = FederatedEvent(
        system_id="sys-rto-01",
        system_name="Gujarat RTO Checkpoint System (HikCentral)",
        vendor="Hikvision",
        camera_external_id="cam-rto-01",
        camera_name="RTO Camera",
        event_type="vehicle_detection",
        detected_plate="GJ02TEST2",
        confidence=0.88,
        source_timestamp=datetime.now(timezone.utc),
    )

    await bus.publish(sample_event)
    # Give the subscriber loop a moment to drain the queue
    for _ in range(10):
        if received:
            break
        await asyncio.sleep(0.05)

    assert len(received) == 1
    assert received[0].detected_plate == "GJ02TEST2"

    sub_task.cancel()
    try:
        await sub_task
    except asyncio.CancelledError:
        pass
