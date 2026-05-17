"""Tests for coordinator.py."""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

from homeassistant.helpers.update_coordinator import UpdateFailed
import pytest

from custom_components.luxtronik2.const import (
    DeviceKey,
    LuxMkTypes,
    LuxParameter as LP,
    LuxVisibility as LV,
)
from custom_components.luxtronik2.coordinator import (
    LuxtronikConnectionError,
    LuxtronikCoordinator,
    catch_luxtronik_errors,
)
from custom_components.luxtronik2.model import (
    LuxtronikCoordinatorData,
    LuxtronikEntityDescription,
)


def _make_coordinator(data=None):
    """Create a coordinator with mocked internals."""
    coord = object.__new__(LuxtronikCoordinator)
    coord._lock = asyncio.Lock()
    coord.hass = MagicMock()
    coord.client = MagicMock()
    coord._config = {"host": "1.2.3.4", "port": 8889}
    coord.device_infos = {}
    coord.update_reason_write = False
    coord.async_request_refresh = AsyncMock()
    coord.async_refresh = AsyncMock()
    if data is None:
        data = LuxtronikCoordinatorData(
            parameters={"ID_WEB_WP_BZ_akt": (0, 0)},
            calculations={"ID_WEB_WP_BZ_akt": (0, 0)},
            visibilities={"ID_WEB_Sichtbar_Solar": (0, 1)},
        )
    coord.data = data
    return coord


# ===========================================================================
# catch_luxtronik_errors decorator
# ===========================================================================


class TestCatchLuxtronikErrors:
    @pytest.mark.asyncio
    async def test_catches_exception_and_refreshes(self):
        @catch_luxtronik_errors
        async def failing_method(self):
            raise ValueError("test error")

        coord = _make_coordinator()
        await failing_method(coord)
        coord.async_request_refresh.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_calls_refresh_on_success(self):
        @catch_luxtronik_errors
        async def success_method(self):
            pass

        coord = _make_coordinator()
        await success_method(coord)
        coord.async_request_refresh.assert_awaited_once()


# ===========================================================================
# _async_update_data
# ===========================================================================


class TestAsyncUpdateData:
    @pytest.mark.asyncio
    async def test_successful_update(self):
        coord = _make_coordinator()
        coord.client.parameters = {"p1": 1}
        coord.client.calculations = {"c1": 2}
        coord.client.visibilities = {"v1": 3}
        coord.hass.async_add_executor_job = AsyncMock()
        result = await coord._async_update_data()
        assert result.parameters == {"p1": 1}

    @pytest.mark.asyncio
    async def test_update_raises_update_failed(self):
        coord = _make_coordinator()
        coord.hass.async_add_executor_job = AsyncMock(
            side_effect=Exception("read fail")
        )
        with pytest.raises(UpdateFailed):
            await coord._async_update_data()


# ===========================================================================
# async_write
# ===========================================================================


class TestAsyncWrite:
    @pytest.mark.asyncio
    async def test_successful_write(self):
        coord = _make_coordinator()
        coord.hass.async_add_executor_job = AsyncMock()

        # Make async_refresh update data
        async def fake_refresh():
            coord.data = LuxtronikCoordinatorData(
                parameters={"test_param": (0, 42)},
                calculations={},
                visibilities={},
            )

        coord.async_refresh = fake_refresh
        result = await coord.async_write("test_param", 42)
        assert result is not None

    @pytest.mark.asyncio
    async def test_write_error(self):
        coord = _make_coordinator()
        coord.hass.async_add_executor_job = AsyncMock(
            side_effect=Exception("write fail")
        )
        with pytest.raises(UpdateFailed):
            await coord.async_write("param", 1)


# ===========================================================================
# entity_visible
# ===========================================================================


class TestEntityVisible:
    def test_unset_visibility(self):
        coord = _make_coordinator()
        desc = MagicMock(spec=LuxtronikEntityDescription)
        desc.visibility = LV.UNSET
        assert coord.entity_visible(desc) is True

    def test_solar_collector_visibility(self):
        coord = _make_coordinator()
        coord._detect_solar_present = MagicMock(return_value=True)
        desc = MagicMock(spec=LuxtronikEntityDescription)
        desc.visibility = LV.V0038_SOLAR_COLLECTOR
        assert coord.entity_visible(desc) is True

    def test_solar_buffer_visibility(self):
        coord = _make_coordinator()
        coord._detect_solar_present = MagicMock(return_value=False)
        desc = MagicMock(spec=LuxtronikEntityDescription)
        desc.visibility = LV.V0039_SOLAR_BUFFER
        assert coord.entity_visible(desc) is False

    def test_solar_250_visibility(self):
        coord = _make_coordinator()
        coord._detect_solar_present = MagicMock(return_value=True)
        desc = MagicMock(spec=LuxtronikEntityDescription)
        desc.visibility = LV.V0250_SOLAR
        assert coord.entity_visible(desc) is True

    def test_dhw_circulation_pump(self):
        coord = _make_coordinator()
        coord._detect_dhw_circulation_pump_present = MagicMock(return_value=True)
        desc = MagicMock(spec=LuxtronikEntityDescription)
        desc.visibility = LV.V0059_DHW_CIRCULATION_PUMP
        assert coord.entity_visible(desc) is True

    def test_dhw_charging_pump(self):
        coord = _make_coordinator()
        coord._detect_dhw_circulation_pump_present = MagicMock(return_value=False)
        desc = MagicMock(spec=LuxtronikEntityDescription)
        desc.visibility = LV.V0059A_DHW_CHARGING_PUMP
        assert coord.entity_visible(desc) is True

    def test_cooling_visibility(self):
        coord = _make_coordinator()
        coord.detect_cooling_present = MagicMock(return_value=True)
        desc = MagicMock(spec=LuxtronikEntityDescription)
        desc.visibility = LV.V0005_COOLING
        assert coord.entity_visible(desc) is True

    def test_visibility_none_returns_true(self):
        coord = _make_coordinator()
        coord.get_value = MagicMock(return_value=None)
        desc = MagicMock(spec=LuxtronikEntityDescription)
        desc.visibility = LV.V0024_FLOW_OUT_TEMPERATURE_EXTERNAL
        assert coord.entity_visible(desc) is True

    def test_visibility_value_zero(self):
        coord = _make_coordinator()
        coord.get_value = MagicMock(return_value=0)
        desc = MagicMock(spec=LuxtronikEntityDescription)
        desc.visibility = LV.V0024_FLOW_OUT_TEMPERATURE_EXTERNAL
        assert coord.entity_visible(desc) is False

    def test_visibility_value_positive(self):
        coord = _make_coordinator()
        coord.get_value = MagicMock(return_value=1)
        desc = MagicMock(spec=LuxtronikEntityDescription)
        desc.visibility = LV.V0024_FLOW_OUT_TEMPERATURE_EXTERNAL
        assert coord.entity_visible(desc) is True


# ===========================================================================
# entity_active
# ===========================================================================


class TestEntityActive:
    def test_version_not_compatible(self):
        coord = _make_coordinator()
        coord._is_version_not_compatible = MagicMock(return_value=True)
        desc = MagicMock(spec=LuxtronikEntityDescription)
        assert coord.entity_active(desc) is False

    def test_mixing_circuit_cooling(self):
        coord = _make_coordinator()
        coord._is_version_not_compatible = MagicMock(return_value=False)
        coord.get_value = MagicMock(return_value=LuxMkTypes.cooling.value)
        desc = MagicMock(spec=LuxtronikEntityDescription)
        desc.visibility = LP.P0042_MIXING_CIRCUIT1_TYPE
        desc.device_key = DeviceKey.heatpump
        assert coord.entity_active(desc) is True

    def test_mixing_circuit_not_cooling(self):
        coord = _make_coordinator()
        coord._is_version_not_compatible = MagicMock(return_value=False)
        coord.get_value = MagicMock(return_value=0)
        desc = MagicMock(spec=LuxtronikEntityDescription)
        desc.visibility = LP.P0042_MIXING_CIRCUIT1_TYPE
        desc.device_key = DeviceKey.heatpump
        assert coord.entity_active(desc) is False

    def test_solar_visibility_active(self):
        coord = _make_coordinator()
        coord._is_version_not_compatible = MagicMock(return_value=False)
        coord._detect_solar_present = MagicMock(return_value=True)
        desc = MagicMock(spec=LuxtronikEntityDescription)
        desc.visibility = LV.V0038_SOLAR_COLLECTOR
        assert coord.entity_active(desc) is True

    def test_device_key_not_active(self):
        coord = _make_coordinator()
        coord._is_version_not_compatible = MagicMock(return_value=False)
        coord.device_key_active = MagicMock(return_value=False)
        desc = MagicMock(spec=LuxtronikEntityDescription)
        desc.visibility = LV.V0024_FLOW_OUT_TEMPERATURE_EXTERNAL
        desc.device_key = DeviceKey.heating
        assert coord.entity_active(desc) is False

    def test_invisible_if_value_matches(self):
        coord = _make_coordinator()
        coord._is_version_not_compatible = MagicMock(return_value=False)
        coord.device_key_active = MagicMock(return_value=True)
        coord.get_value = MagicMock(return_value=42)
        desc = MagicMock(spec=LuxtronikEntityDescription)
        desc.visibility = LV.V0024_FLOW_OUT_TEMPERATURE_EXTERNAL
        desc.device_key = DeviceKey.heatpump
        desc.invisible_if_value = 42
        desc.luxtronik_key = LP.P0001_HEATING_TARGET_CORRECTION
        assert coord.entity_active(desc) is False

    def test_invisible_if_value_no_match(self):
        coord = _make_coordinator()
        coord._is_version_not_compatible = MagicMock(return_value=False)
        coord.device_key_active = MagicMock(return_value=True)
        coord.get_value = MagicMock(return_value=99)
        desc = MagicMock(spec=LuxtronikEntityDescription)
        desc.visibility = LV.V0024_FLOW_OUT_TEMPERATURE_EXTERNAL
        desc.device_key = DeviceKey.heatpump
        desc.invisible_if_value = 42
        desc.luxtronik_key = LP.P0001_HEATING_TARGET_CORRECTION
        assert coord.entity_active(desc) is True


# ===========================================================================
# detect methods
# ===========================================================================


class TestDetectMethods:
    def test_detect_cooling_present_false(self):
        coord = _make_coordinator()
        coord._detect_cooling_mk = MagicMock(return_value=[])
        assert coord.detect_cooling_present() is False

    def test_detect_cooling_present_true(self):
        coord = _make_coordinator()
        coord._detect_cooling_mk = MagicMock(
            return_value=[LP.P0042_MIXING_CIRCUIT1_TYPE]
        )
        assert coord.detect_cooling_present() is True

    def test_detect_dhw_circulation_pump_none(self):
        coord = _make_coordinator()
        coord.get_value = MagicMock(return_value=None)
        assert coord._detect_dhw_circulation_pump_present() is False

    def test_detect_dhw_circulation_pump_is_1(self):
        coord = _make_coordinator()
        coord.get_value = MagicMock(return_value=1)
        assert coord._detect_dhw_circulation_pump_present() is False

    def test_detect_dhw_circulation_pump_not_1(self):
        coord = _make_coordinator()
        coord.get_value = MagicMock(return_value=0)
        assert coord._detect_dhw_circulation_pump_present() is True

    def test_detect_dhw_circulation_pump_exception(self):
        coord = _make_coordinator()
        coord.get_value = MagicMock(side_effect=Exception("err"))
        assert coord._detect_dhw_circulation_pump_present() is False


# ===========================================================================
# async_shutdown
# ===========================================================================


class TestAsyncShutdown:
    @pytest.mark.asyncio
    async def test_shutdown_with_client(self):
        coord = _make_coordinator()
        with patch(
            "homeassistant.helpers.update_coordinator.DataUpdateCoordinator.async_shutdown",
            new_callable=AsyncMock,
        ):
            await coord.async_shutdown()
        assert not hasattr(coord, "client")

    @pytest.mark.asyncio
    async def test_shutdown_without_client(self):
        coord = _make_coordinator()
        del coord.client
        with patch(
            "homeassistant.helpers.update_coordinator.DataUpdateCoordinator.async_shutdown",
            new_callable=AsyncMock,
        ):
            await coord.async_shutdown()


# ===========================================================================
# LuxtronikConnectionError
# ===========================================================================


class TestLuxtronikConnectionError:
    def test_attributes(self):
        err = LuxtronikConnectionError("1.2.3.4", 8889, Exception("refused"))
        assert err.host == "1.2.3.4"
        assert err.port == 8889
        assert "1.2.3.4:8889" in str(err)
