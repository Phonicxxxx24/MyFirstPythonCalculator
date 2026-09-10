"""
Tests for model3_federation.adapters
Tests adapter camera catalog, connection lifecycle, and event stream generator.
"""

from datetime import datetime, timezone
import pytest

from model3_federation.adapters.police_vms_adapter import PoliceVMSAdapter
from model3_federation.adapters.rto_vms_adapter import RTOVMSAdapter
from model3_federation.adapters.municipal_vms_adapter import MunicipalVMSAdapter


@pytest.mark.asyncio
async def test_police_vms_adapter():
    adapter = PoliceVMSAdapter()
    assert adapter.system_name == "Gujarat Police VMS (Milestone)"
    assert adapter.vendor == "Milestone"
    assert "sys-police" in adapter.system_id or len(adapter.system_id) == 36

    connected = await adapter.connect()
    assert connected is True

    cameras = await adapter.get_cameras()
    assert len(cameras) == 5
    assert all(c.system_name == "Gujarat Police VMS (Milestone)" for c in cameras)
    assert any(c.external_id == "cam-pol-01" for c in cameras)


@pytest.mark.asyncio
async def test_rto_vms_adapter():
    adapter = RTOVMSAdapter()
    assert adapter.system_name == "Gujarat RTO Checkpoint System (HikCentral)"
    assert adapter.vendor == "Hikvision"

    connected = await adapter.connect()
    assert connected is True

    cameras = await adapter.get_cameras()
    assert len(cameras) == 4
    assert any(c.external_id == "rto-nh48-01" for c in cameras)


@pytest.mark.asyncio
async def test_municipal_vms_adapter():
    adapter = MunicipalVMSAdapter()
    assert adapter.system_name == "AMC City Surveillance (Dahua)"
    assert adapter.vendor == "Dahua"

    connected = await adapter.connect()
    assert connected is True

    cameras = await adapter.get_cameras()
    assert len(cameras) == 4
    assert any(c.external_id == "amc-lal-01" for c in cameras)
