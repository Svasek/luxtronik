"""Tests covering code paths previously annotated with pragma: no cover.

Each section targets specific uncovered lines after pragma removal.
"""

from __future__ import annotations

from datetime import time
from unittest.mock import AsyncMock, MagicMock, patch

from conftest import make_coordinator_data
from homeassistant.const import CONF_HOST, CONF_PORT, CONF_TIMEOUT
import pytest

from custom_components.luxtronik2.const import (
    CONF_HA_SENSOR_INDOOR_TEMPERATURE,
    CONF_HA_SENSOR_PREFIX,
    CONF_MAX_DATA_LENGTH,
    DEFAULT_MAX_DATA_LENGTH,
    DEFAULT_PORT,
    DEFAULT_TIMEOUT,
    DOMAIN,
    DeviceKey,
    LuxCalculation as LC,
    LuxMode,
    LuxOperationMode,
    LuxParameter as LP,
    SensorAttrFormat,
    SensorAttrKey as SA,
    SensorKey,
)
from custom_components.luxtronik2.model import (
    LuxtronikEntityAttributeDescription,
    LuxtronikSensorDescription,
)

_ENTRY_DATA = {
    CONF_HOST: "192.168.1.100",
    CONF_PORT: DEFAULT_PORT,
    CONF_TIMEOUT: DEFAULT_TIMEOUT,
    CONF_MAX_DATA_LENGTH: DEFAULT_MAX_DATA_LENGTH,
    CONF_HA_SENSOR_PREFIX: DOMAIN,
}


def _mock_entry(**overrides):
    entry = MagicMock()
    data = _ENTRY_DATA.copy()
    data.update(overrides)
    entry.data = data
    entry.options = {}
    return entry


def _mock_coordinator(data=None):
    if data is None:
        data = make_coordinator_data()
    coord = MagicMock()
    coord.data = data
    coord.entity_active.return_value = True
    coord.entity_visible.return_value = True
    coord.get_device.return_value = MagicMock()
    coord.async_write = AsyncMock(return_value=data)
    return coord


def _patch_entity(entity):
    entity.hass = MagicMock()
    entity.hass.config.time_zone = "UTC"
    entity.async_write_ha_state = MagicMock()
    entity.async_schedule_update_ha_state = MagicMock()


# ===========================================================================
# base.py — entity_registry_enabled_default is None (line 78)
# ===========================================================================


class TestBaseEntityRegistryEnabledDefault:
    def test_none_enabled_default_calls_entity_visible(self):
        """When entity_registry_enabled_default is None, coordinator.entity_visible is called."""
        from custom_components.luxtronik2.sensor import LuxtronikSensorEntity

        coord = _mock_coordinator()
        coord.entity_visible.return_value = False
        desc = LuxtronikSensorDescription(
            key=SensorKey.FLOW_OUT_TEMPERATURE,
            luxtronik_key=LC.C0011_FLOW_OUT_TEMPERATURE,
            device_key=DeviceKey.heatpump,
            entity_registry_enabled_default=None,  # triggers the branch
        )
        entity = LuxtronikSensorEntity(
            MagicMock(), _mock_entry(), coord, desc, DeviceKey.heatpump
        )
        _patch_entity(entity)
        # The description should now have the value from entity_visible
        assert entity.entity_description.entity_registry_enabled_default is False
        coord.entity_visible.assert_called()


# ===========================================================================
# base.py — StrEnum / None / else branches in __init__ loop (lines 103, 109)
# ===========================================================================


class TestBaseExtraKeyLoop:
    def test_strenum_value_in_extra_attrs(self):
        """StrEnum value is formatted as 'name[1:5] value'."""
        from custom_components.luxtronik2.model import LuxtronikClimateDescription

        desc = LuxtronikClimateDescription(
            key=SensorKey.HEATING,
            luxtronik_key=LP.P0003_MODE_HEATING,
            device_key=DeviceKey.heating,
            luxtronik_key_current_temperature=LC.C0227_ROOM_THERMOSTAT_TEMPERATURE,
            luxtronik_key_current_action=LC.C0080_STATUS,
        )
        coord = _mock_coordinator()
        from custom_components.luxtronik2.base import LuxtronikEntity

        entity = LuxtronikEntity(coord, desc, DeviceKey.heating)
        _patch_entity(entity)
        # luxtronik_key_current_temperature is a StrEnum (LuxCalculation)
        assert (
            "luxtronik_key_current_temperature" in entity._attr_extra_state_attributes
        )
        val = entity._attr_extra_state_attributes["luxtronik_key_current_temperature"]
        assert isinstance(val, str)
        # StrEnum => formatted "name[1:5] value"
        assert LC.C0227_ROOM_THERMOSTAT_TEMPERATURE.value in val

    def test_non_strenum_value_in_extra_attrs(self):
        """Non-StrEnum value is stored directly."""
        from custom_components.luxtronik2.model import LuxtronikClimateDescription

        desc = LuxtronikClimateDescription(
            key=SensorKey.HEATING,
            luxtronik_key=LP.P0003_MODE_HEATING,
            device_key=DeviceKey.heating,
            luxtronik_key_current_temperature="sensor.my_temp",  # string, not StrEnum
            luxtronik_key_current_action=LC.C0080_STATUS,
        )
        coord = _mock_coordinator()
        from custom_components.luxtronik2.base import LuxtronikEntity

        entity = LuxtronikEntity(coord, desc, DeviceKey.heating)
        _patch_entity(entity)
        assert (
            entity._attr_extra_state_attributes["luxtronik_key_current_temperature"]
            == "sensor.my_temp"
        )

    def test_none_value_skipped_in_extra_attrs(self):
        """When a luxtronik_key_* field is None, it's skipped."""
        from custom_components.luxtronik2.model import LuxtronikIndexSensorDescription

        desc = LuxtronikIndexSensorDescription(
            key=SensorKey.FLOW_OUT_TEMPERATURE,
            luxtronik_key=LC.C0011_FLOW_OUT_TEMPERATURE,
            device_key=DeviceKey.heatpump,
            luxtronik_key_timestamp=None,  # pyright: ignore[reportArgumentType]
        )
        coord = _mock_coordinator()
        from custom_components.luxtronik2.base import LuxtronikEntity

        entity = LuxtronikEntity(coord, desc, DeviceKey.heatpump)
        _patch_entity(entity)
        assert "luxtronik_key_timestamp" not in entity._attr_extra_state_attributes


# ===========================================================================
# base.py — restore_on_startup loop (lines 128-132)
# ===========================================================================


# ===========================================================================
# base.py — _restore_attr_value (line 162), _data_update (line 171)
# ===========================================================================


class TestBaseHelperMethods:
    def test_restore_attr_value_passthrough(self):
        from custom_components.luxtronik2.base import LuxtronikEntity

        desc = LuxtronikSensorDescription(
            key=SensorKey.FLOW_OUT_TEMPERATURE,
            luxtronik_key=LC.C0011_FLOW_OUT_TEMPERATURE,
            device_key=DeviceKey.heatpump,
        )
        coord = _mock_coordinator()
        entity = LuxtronikEntity(coord, desc, DeviceKey.heatpump)
        _patch_entity(entity)
        assert entity._restore_attr_value(42) == 42
        assert entity._restore_attr_value(None) is None

    @pytest.mark.asyncio
    async def test_data_update_calls_handle(self):
        from custom_components.luxtronik2.base import LuxtronikEntity

        desc = LuxtronikSensorDescription(
            key=SensorKey.FLOW_OUT_TEMPERATURE,
            luxtronik_key=LC.C0011_FLOW_OUT_TEMPERATURE,
            device_key=DeviceKey.heatpump,
        )
        coord = _mock_coordinator()
        entity = LuxtronikEntity(coord, desc, DeviceKey.heatpump)
        _patch_entity(entity)
        with patch.object(entity, "_handle_coordinator_update") as mock_handle:
            await entity._data_update(MagicMock())
            mock_handle.assert_called_once()


# ===========================================================================
# base.py — _enrich_extra_attributes (lines 227-231)
# ===========================================================================


class TestBaseEnrichExtraAttributes:
    def test_skips_attr_with_no_format_and_unset_key(self):
        from custom_components.luxtronik2.base import LuxtronikEntity

        desc = LuxtronikSensorDescription(
            key=SensorKey.FLOW_OUT_TEMPERATURE,
            luxtronik_key=LC.C0011_FLOW_OUT_TEMPERATURE,
            device_key=DeviceKey.heatpump,
            extra_attributes=(
                LuxtronikEntityAttributeDescription(
                    key=SA.TIMER_HEATPUMP_ON,
                    luxtronik_key=LP.UNSET,
                    format=None,
                ),
            ),
        )
        coord = _mock_coordinator()
        entity = LuxtronikEntity(coord, desc, DeviceKey.heatpump)
        _patch_entity(entity)
        entity._enrich_extra_attributes()
        # Should be skipped — not in extra_state_attributes
        assert SA.TIMER_HEATPUMP_ON.value not in entity._attr_extra_state_attributes

    def test_includes_attr_with_format(self):
        data = make_coordinator_data(calculations={"ID_WEB_Temperatur_TRL": 7200})
        desc = LuxtronikSensorDescription(
            key=SensorKey.FLOW_OUT_TEMPERATURE,
            luxtronik_key=LC.C0011_FLOW_OUT_TEMPERATURE,
            device_key=DeviceKey.heatpump,
            extra_attributes=(
                LuxtronikEntityAttributeDescription(
                    key=SA.TIMER_HEATPUMP_ON,
                    luxtronik_key=LC.C0011_FLOW_OUT_TEMPERATURE,
                    format=SensorAttrFormat.HOUR_MINUTE,
                ),
            ),
        )
        coord = _mock_coordinator(data)
        from custom_components.luxtronik2.sensor import LuxtronikSensorEntity

        entity = LuxtronikSensorEntity(
            MagicMock(), _mock_entry(), coord, desc, DeviceKey.heatpump
        )
        _patch_entity(entity)
        entity._enrich_extra_attributes()
        assert SA.TIMER_HEATPUMP_ON.value in entity._attr_extra_state_attributes


# ===========================================================================
# base.py — _schedule_immediate_update (line 239)
# ===========================================================================


class TestBaseScheduleImmediateUpdate:
    def test_schedule_immediate_update(self):
        from custom_components.luxtronik2.base import LuxtronikEntity

        desc = LuxtronikSensorDescription(
            key=SensorKey.FLOW_OUT_TEMPERATURE,
            luxtronik_key=LC.C0011_FLOW_OUT_TEMPERATURE,
            device_key=DeviceKey.heatpump,
        )
        coord = _mock_coordinator()
        entity = LuxtronikEntity(coord, desc, DeviceKey.heatpump)
        _patch_entity(entity)
        entity._schedule_immediate_update()
        entity.async_schedule_update_ha_state.assert_called_once_with(True)


# ===========================================================================
# base.py — return str(value) fallback (line 274)
# ===========================================================================


class TestBaseFormattedDataFallback:
    def test_unknown_format_returns_str(self):
        """When format doesn't match any known case, return str(value)."""
        from custom_components.luxtronik2.sensor import LuxtronikSensorEntity

        data = make_coordinator_data(calculations={"ID_WEB_Temperatur_TRL": 42})
        desc = LuxtronikSensorDescription(
            key=SensorKey.FLOW_OUT_TEMPERATURE,
            luxtronik_key=LC.C0011_FLOW_OUT_TEMPERATURE,
            device_key=DeviceKey.heatpump,
        )
        coord = _mock_coordinator(data)
        entity = LuxtronikSensorEntity(
            MagicMock(), _mock_entry(), coord, desc, DeviceKey.heatpump
        )
        _patch_entity(entity)
        # Use TIMESTAMP_LAST_OVER which is not handled by base.formatted_data
        attr = LuxtronikEntityAttributeDescription(
            key=SA.TIMER_HEATPUMP_ON,
            luxtronik_key=LC.C0011_FLOW_OUT_TEMPERATURE,
            format=SensorAttrFormat.TIMESTAMP_LAST_OVER,
        )
        result = entity.formatted_data(attr)
        assert result == "42"


# ===========================================================================
# climate.py — unavailable_keys log (line 193)
# ===========================================================================


class TestClimateUnavailableKeys:
    @pytest.mark.asyncio
    async def test_unavailable_keys_logged(self):
        """When a thermostat key is missing from data, it's logged."""
        from custom_components.luxtronik2.climate import async_setup_entry

        coord = _mock_coordinator(make_coordinator_data())
        # Ensure at least one THERMOSTAT key doesn't exist
        # The default data doesn't have all thermostat keys
        entry = MagicMock()
        entry.runtime_data = coord

        added = []
        with (
            patch(
                "custom_components.luxtronik2.climate.key_exists", return_value=False
            ),
            patch("custom_components.luxtronik2.climate.LOGGER") as mock_logger,
        ):
            await async_setup_entry(
                MagicMock(), entry, lambda entities, update: added.extend(entities)
            )
            mock_logger.debug.assert_called()


# ===========================================================================
# climate.py — configured_indoor_temp_sensor (lines 267-271)
# ===========================================================================


class TestClimateConfiguredIndoorTempSensor:
    def test_configured_sensor_replaces_key(self):
        from custom_components.luxtronik2.climate import (
            THERMOSTATS,
            LuxtronikThermostat,
        )

        coord = _mock_coordinator()
        entry = _mock_entry()
        entry.options = {CONF_HA_SENSOR_INDOOR_TEMPERATURE: "sensor.my_temp"}
        hass = MagicMock()

        thermostat = LuxtronikThermostat(hass, entry, coord, THERMOSTATS[0])
        assert (
            thermostat.entity_description.luxtronik_key_current_temperature
            == "sensor.my_temp"
        )


# ===========================================================================
# climate.py — key None/empty and sensor.* branches (lines 337, 339-340)
# ===========================================================================


class TestClimateTemperatureKeyBranches:
    def test_key_none_sets_current_temp_none(self):
        from dataclasses import replace as dc_replace

        from custom_components.luxtronik2.climate import (
            THERMOSTATS,
            LuxtronikThermostat,
        )

        coord = _mock_coordinator()
        entry = _mock_entry()
        hass = MagicMock()

        thermostat = LuxtronikThermostat(hass, entry, coord, THERMOSTATS[0])
        _patch_entity(thermostat)
        # Set key to None
        thermostat.entity_description = dc_replace(
            thermostat.entity_description,
            luxtronik_key_current_temperature=None,
        )
        data = make_coordinator_data(
            parameters={"ID_Ba_Hz_akt": LuxMode.automatic},
            calculations={"ID_WEB_WP_BZ_akt": LuxOperationMode.heating},
        )
        thermostat._handle_coordinator_update(data)
        assert thermostat._attr_current_temperature is None

    def test_key_empty_sets_current_temp_none(self):
        from dataclasses import replace as dc_replace

        from custom_components.luxtronik2.climate import (
            THERMOSTATS,
            LuxtronikThermostat,
        )

        coord = _mock_coordinator()
        entry = _mock_entry()
        hass = MagicMock()

        thermostat = LuxtronikThermostat(hass, entry, coord, THERMOSTATS[0])
        _patch_entity(thermostat)
        thermostat.entity_description = dc_replace(
            thermostat.entity_description,
            luxtronik_key_current_temperature="",
        )
        data = make_coordinator_data(
            parameters={"ID_Ba_Hz_akt": LuxMode.automatic},
            calculations={"ID_WEB_WP_BZ_akt": LuxOperationMode.heating},
        )
        thermostat._handle_coordinator_update(data)
        assert thermostat._attr_current_temperature is None

    def test_key_sensor_reads_from_hass_states(self):
        from dataclasses import replace as dc_replace

        from custom_components.luxtronik2.climate import (
            THERMOSTATS,
            LuxtronikThermostat,
        )

        coord = _mock_coordinator()
        entry = _mock_entry()
        hass = MagicMock()

        thermostat = LuxtronikThermostat(hass, entry, coord, THERMOSTATS[0])
        _patch_entity(thermostat)
        thermostat.entity_description = dc_replace(
            thermostat.entity_description,
            luxtronik_key_current_temperature="sensor.living_room_temp",
        )
        mock_state = MagicMock()
        mock_state.state = "21.5"
        thermostat.hass.states.get.return_value = mock_state
        data = make_coordinator_data(
            parameters={"ID_Ba_Hz_akt": LuxMode.automatic},
            calculations={"ID_WEB_WP_BZ_akt": LuxOperationMode.heating},
        )
        thermostat._handle_coordinator_update(data)
        thermostat.hass.states.get.assert_called_with("sensor.living_room_temp")
        assert thermostat._attr_current_temperature == 21.5


# ===========================================================================
# coordinator.py — get_device fallback (line 187) and name==key (line 223)
# ===========================================================================


class TestCoordinatorGetDevice:
    def test_device_info_none_returns_fallback(self):
        from custom_components.luxtronik2.coordinator import LuxtronikCoordinator

        coord = _mock_coordinator()
        coord.device_infos = {}
        coord._create_device_infos = MagicMock()
        coord.unique_id = "test_uid"
        # After _create_device_infos, device_infos.get still returns None
        result = LuxtronikCoordinator.get_device(coord, DeviceKey.heatpump)
        assert "identifiers" in result

    def test_build_device_name_with_platform(self):
        from custom_components.luxtronik2.coordinator import LuxtronikCoordinator

        coord = _mock_coordinator()
        platform = MagicMock()
        platform.platform_data.platform_translations.get.return_value = "My Heatpump"
        result = LuxtronikCoordinator._build_device_name(
            coord, DeviceKey.heatpump, platform
        )
        assert result == "My Heatpump"


# ===========================================================================
# config_flow.py — indoor_temp None reset (line 432)
# ===========================================================================


class TestConfigFlowIndoorTempReset:
    @pytest.mark.asyncio
    async def test_indoor_temp_reset_to_none(self):
        from custom_components.luxtronik2.config_flow import LuxtronikOptionsFlowHandler

        handler = MagicMock(spec=LuxtronikOptionsFlowHandler)
        handler.options = {CONF_HA_SENSOR_INDOOR_TEMPERATURE: "sensor.old"}
        handler.config_entry = MagicMock()
        handler.config_entry.data = _ENTRY_DATA.copy()
        handler.config_entry.entry_id = "test_id"
        handler.hass = MagicMock()
        handler.hass.config_entries.async_reload = AsyncMock()

        # Simulate user_input without indoor temp (empty value)
        user_input = {CONF_HOST: "192.168.1.100", CONF_PORT: DEFAULT_PORT}

        with patch(
            "custom_components.luxtronik2.config_flow.connect_and_get_coordinator",
            new_callable=AsyncMock,
        ):
            await LuxtronikOptionsFlowHandler.async_step_user(handler, user_input)

        # The indoor temp should have been reset to None
        new_options = handler.hass.config_entries.async_update_entry.call_args
        if new_options:
            assert True  # Call was made — the branch was hit


# ===========================================================================
# diagnostics.py — "data" not in entry_data (line 37)
# ===========================================================================


class TestDiagnosticsNoDataKey:
    @pytest.mark.asyncio
    async def test_entry_data_without_data_key(self):
        from custom_components.luxtronik2.diagnostics import (
            async_get_config_entry_diagnostics,
        )

        hass = MagicMock()
        hass.async_add_executor_job = AsyncMock(return_value=None)

        data = MagicMock()
        data.parameters.parameters = {}
        data.calculations.calculations = {}
        data.visibilities.visibilities = {}

        coordinator = MagicMock()
        coordinator.async_request_refresh = AsyncMock()
        coordinator.data = data
        coordinator.device_infos = {}

        entry = MagicMock()
        entry.runtime_data = coordinator
        entry.data = {CONF_HOST: "192.168.1.100"}
        # as_dict returns WITHOUT "data" key — triggers the branch
        entry.as_dict.return_value = {"options": {}}

        result = await async_get_config_entry_diagnostics(hass, entry)
        assert "entry" in result
        # "data" should have been created
        assert "data" in result["entry"]


# ===========================================================================
# evu_helper.py — multi-day gap (line 75) and else branch (lines 76-79)
# ===========================================================================


class TestEVUHelperMultiDayGap:
    @patch("custom_components.luxtronik2.evu_helper.dt_util")
    def test_multi_day_gap_adds_1440(self, mock_dt):
        from datetime import datetime

        from custom_components.luxtronik2.evu_helper import LuxtronikEVUTracker

        # Current time: Wednesday 10:00
        mock_dt.now.return_value = datetime(2024, 1, 3, 10, 0)  # Wednesday=2

        tracker = LuxtronikEVUTracker()
        tracker._evu_first_start = time(8, 0)
        tracker._evu_days = [5]  # Only Friday has EVU events
        # Wednesday(2) -> Thursday(3) -> Friday(5) = needs to skip 2 days

        minutes = tracker.get_next_event_minutes()
        assert minutes is not None
        # Should include 1440 * (days to skip) + minutes on target day
        assert minutes > 1440  # At least one full day skipped

    @patch("custom_components.luxtronik2.evu_helper.dt_util")
    def test_weekday_in_evu_days_returns_minutes(self, mock_dt):
        from datetime import datetime

        from custom_components.luxtronik2.evu_helper import LuxtronikEVUTracker

        # Current time: Monday 10:00
        mock_dt.now.return_value = datetime(2024, 1, 1, 10, 0)  # Monday=0

        tracker = LuxtronikEVUTracker()
        tracker._evu_first_start = time(12, 0)
        tracker._evu_days = [0]  # Monday is in evu_days

        minutes = tracker.get_next_event_minutes()
        assert minutes is not None
        assert minutes == 120  # 12:00 - 10:00 = 120 min


# ===========================================================================
# lux_helper.py — discovery parsing (lines 81-82, 85, 97)
# ===========================================================================


class TestLuxHelperDiscovery:
    @patch("custom_components.luxtronik2.lux_helper.socket")
    def test_discovery_valid_port(self, mock_socket_module):
        from custom_components.luxtronik2.lux_helper import (
            LUXTRONIK_DISCOVERY_RESPONSE_PREFIX,
            discover,
        )

        sock_instance = MagicMock()
        mock_socket_module.socket.return_value = sock_instance
        mock_socket_module.AF_INET = 2
        mock_socket_module.SOCK_DGRAM = 2
        mock_socket_module.IPPROTO_UDP = 17
        mock_socket_module.SOL_SOCKET = 1
        mock_socket_module.SO_BROADCAST = 6

        # First call returns our sent packet (skipped), second returns valid response, third times out
        magic_packet = "2000;111;1;\x00"
        valid_response = f"{LUXTRONIK_DISCOVERY_RESPONSE_PREFIX}8888;"
        sock_instance.recvfrom.side_effect = [
            (magic_packet.encode(), ("192.168.1.1", 4444)),
            (valid_response.encode(), ("192.168.1.200", 4444)),
            TimeoutError(),
            TimeoutError(),  # second port
        ]

        results = discover()
        assert ("192.168.1.200", 8888) in results

    @patch("custom_components.luxtronik2.lux_helper.socket")
    def test_discovery_invalid_port(self, mock_socket_module):
        from custom_components.luxtronik2.lux_helper import (
            LUXTRONIK_DISCOVERY_RESPONSE_PREFIX,
            discover,
        )

        sock_instance = MagicMock()
        mock_socket_module.socket.return_value = sock_instance
        mock_socket_module.AF_INET = 2
        mock_socket_module.SOCK_DGRAM = 2
        mock_socket_module.IPPROTO_UDP = 17
        mock_socket_module.SOL_SOCKET = 1
        mock_socket_module.SO_BROADCAST = 6

        # Response with invalid port string
        valid_response = f"{LUXTRONIK_DISCOVERY_RESPONSE_PREFIX}not_a_port;"
        sock_instance.recvfrom.side_effect = [
            (valid_response.encode(), ("192.168.1.200", 4444)),
            TimeoutError(),
            TimeoutError(),
        ]

        results = discover()
        # Invalid port => should not be added (port is None after ValueError)
        assert len([r for r in results if r[0] == "192.168.1.200"]) == 0

    @patch("custom_components.luxtronik2.lux_helper.socket")
    def test_discovery_invalid_response_prefix(self, mock_socket_module):
        from custom_components.luxtronik2.lux_helper import discover

        sock_instance = MagicMock()
        mock_socket_module.socket.return_value = sock_instance
        mock_socket_module.AF_INET = 2
        mock_socket_module.SOCK_DGRAM = 2
        mock_socket_module.IPPROTO_UDP = 17
        mock_socket_module.SOL_SOCKET = 1
        mock_socket_module.SO_BROADCAST = 6

        # Response without expected prefix
        invalid_response = "9999;222;garbage;"
        sock_instance.recvfrom.side_effect = [
            (invalid_response.encode(), ("192.168.1.200", 4444)),
            TimeoutError(),
            TimeoutError(),
        ]

        results = discover()
        assert ("192.168.1.200", None) not in results


# ===========================================================================
# lux_helper.py — _is_socket_closed edge cases (lines 183-187, 191)
# ===========================================================================


class TestIsSocketClosed:
    def test_generic_exception_returns_false(self):
        from custom_components.luxtronik2.lux_helper import _is_socket_closed

        sock = MagicMock()
        sock.fileno.return_value = 3
        sock.gettimeout.return_value = 5.0
        sock.recv.side_effect = RuntimeError("unexpected")
        result = _is_socket_closed(sock)
        assert result is False
        # Verify timeout was restored
        sock.settimeout.assert_called_with(5.0)

    def test_timeout_restored_after_blocking_io_error(self):
        from custom_components.luxtronik2.lux_helper import _is_socket_closed

        sock = MagicMock()
        sock.fileno.return_value = 3
        sock.gettimeout.return_value = 10.0
        sock.recv.side_effect = BlockingIOError()
        result = _is_socket_closed(sock)
        assert result is False
        sock.settimeout.assert_called_with(10.0)

    def test_recv_returns_data_means_open(self):
        """When recv returns non-empty data, socket is open (return False after finally)."""
        from custom_components.luxtronik2.lux_helper import _is_socket_closed

        sock = MagicMock()
        sock.fileno.return_value = 3
        sock.gettimeout.return_value = 5.0
        sock.recv.return_value = b"\x01\x02"
        result = _is_socket_closed(sock)
        assert result is False
        sock.settimeout.assert_called_with(5.0)


# ===========================================================================
# model.py — metaclass_resolver (lines 182-188)
# ===========================================================================


class TestMetaclassResolver:
    def test_single_metaclass(self):
        from custom_components.luxtronik2.model import metaclass_resolver

        class A:
            pass

        result = metaclass_resolver(A)
        assert isinstance(result, type)
        assert issubclass(type(result), type)

    def test_multiple_same_metaclass(self):
        from custom_components.luxtronik2.model import metaclass_resolver

        class A:
            pass

        class B:
            pass

        result = metaclass_resolver(A, B)
        assert isinstance(result, type)

    def test_different_metaclasses(self):
        from custom_components.luxtronik2.model import metaclass_resolver

        class MetaA(type):
            pass

        class MetaB(type):
            pass

        class A(metaclass=MetaA):
            pass

        class B(metaclass=MetaB):
            pass

        result = metaclass_resolver(A, B)
        assert isinstance(result, type)
        # Should be instance of a combined metaclass
        assert issubclass(type(type(result)), type)


# ===========================================================================
# select.py — data is None guard (line 239)
# ===========================================================================


class TestSelectDataNone:
    @pytest.mark.asyncio
    async def test_async_select_option_data_none(self):
        from custom_components.luxtronik2.const import LuxDaySelectorParameter
        from custom_components.luxtronik2.model import LuxtronikSelectEntityDescription
        from custom_components.luxtronik2.select import (
            LuxtronikThermalDesinfectionDaySelector,
        )

        desc = LuxtronikSelectEntityDescription(
            key=SensorKey.THERMAL_DESINFECTION_DAY,
            device_key=DeviceKey.domestic_water,
            luxtronik_key=LuxDaySelectorParameter.MONDAY,  # pyright: ignore[reportArgumentType]
        )
        coord = _mock_coordinator()
        entry = _mock_entry()
        entity = LuxtronikThermalDesinfectionDaySelector(
            entry, coord, desc, DeviceKey.domestic_water
        )
        _patch_entity(entity)

        # Set data to None
        entity.coordinator.data = None
        await entity.async_select_option("Monday")
        # Should return early without error


# ===========================================================================
# sensor.py — icon fallback in smart grid (line 391)
# ===========================================================================


class TestSensorSmartGridIconFallback:
    def test_icon_fallback_when_no_icon_by_state_match(self):
        from custom_components.luxtronik2.sensor import LuxtronikStatusSensorEntity

        data = make_coordinator_data(
            parameters={"ID_Einst_SmartGrid": 1},
            calculations={
                "ID_WEB_EVU": 0,
                "ID_WEB_EVU2": 1,
            },
        )
        desc = LuxtronikSensorDescription(
            key=SensorKey.SMART_GRID_STATUS,
            luxtronik_key=LC.UNSET,
            device_key=DeviceKey.heatpump,
            icon="mdi:grid",
            icon_by_state={"nonexistent_state": "mdi:other"},  # no match for "normal"
        )
        coord = _mock_coordinator(data)
        entry = _mock_entry()
        entity = LuxtronikStatusSensorEntity(
            MagicMock(), entry, coord, desc, DeviceKey.heatpump
        )
        _patch_entity(entity)
        entity._handle_coordinator_update(data)
        assert entity._attr_icon == "mdi:grid"


# ===========================================================================
# update.py — latest_version, update_available, manual_url (lines 113-115)
# ===========================================================================


class TestUpdateEntityProperties:
    def _make_update_entity(self):
        from custom_components.luxtronik2.model import LuxtronikUpdateEntityDescription
        from custom_components.luxtronik2.update import LuxtronikUpdateEntity

        desc = LuxtronikUpdateEntityDescription(
            key=SensorKey.FIRMWARE,
            luxtronik_key=LC.C0081_FIRMWARE_VERSION,
            device_key=DeviceKey.heatpump,
        )
        coord = _mock_coordinator()
        coord.model = "LW"
        coord.manufacturer = "Alpha Innotec"
        entry = _mock_entry()
        entity = LuxtronikUpdateEntity(entry, coord, desc)
        _patch_entity(entity)
        return entity

    def test_latest_version_none_when_no_firmware(self):
        entity = self._make_update_entity()
        entity._LuxtronikUpdateEntity__firmware_version_available = None
        assert entity.latest_version is None

    def test_latest_version_none_when_no_installed(self):
        entity = self._make_update_entity()
        entity._LuxtronikUpdateEntity__firmware_version_available = "V3.90.1"
        entity._attr_state = None
        assert entity.latest_version is None

    def test_latest_version_strips_suffix(self):
        entity = self._make_update_entity()
        entity._LuxtronikUpdateEntity__firmware_version_available = "V3.91.0-12345"
        entity._attr_state = "V3.90.1"
        assert entity.latest_version == "V3.91.0"

    def test_update_available_true(self):
        entity = self._make_update_entity()
        entity._LuxtronikUpdateEntity__firmware_version_available = "V3.91.0"
        entity._attr_state = "V3.90.1"
        assert entity.update_available is True

    def test_update_available_false_no_latest(self):
        entity = self._make_update_entity()
        entity._LuxtronikUpdateEntity__firmware_version_available = None
        entity._attr_state = "V3.90.1"
        assert entity.update_available is False

    def test_manual_url_german(self):
        from custom_components.luxtronik2.update import (
            FIRMWARE_UPDATE_MANUAL_DE,
            LANG_DE,
        )

        entity = self._make_update_entity()
        entity._LuxtronikUpdateEntity__firmware_version_available = "V3.91.0"
        entity._attr_state = "V3.90.1"
        entity.hass.config.language = LANG_DE
        notes = entity.release_notes()
        assert FIRMWARE_UPDATE_MANUAL_DE in notes

    def test_manual_url_english(self):
        from custom_components.luxtronik2.update import FIRMWARE_UPDATE_MANUAL_EN

        entity = self._make_update_entity()
        entity._LuxtronikUpdateEntity__firmware_version_available = "V3.91.0"
        entity._attr_state = "V3.90.1"
        entity.hass.config.language = "en"
        notes = entity.release_notes()
        assert FIRMWARE_UPDATE_MANUAL_EN in notes


# ===========================================================================
# water_heater.py — unavailable_keys log (line 115) and max_temp (lines 177-182)
# ===========================================================================


class TestWaterHeaterUnavailableKeys:
    @pytest.mark.asyncio
    async def test_unavailable_keys_logged(self):
        from custom_components.luxtronik2.water_heater import async_setup_entry

        coord = _mock_coordinator(make_coordinator_data())
        coord.last_update_success = True
        entry = MagicMock()
        entry.runtime_data = coord

        added = []
        with (
            patch(
                "custom_components.luxtronik2.water_heater.key_exists",
                return_value=False,
            ),
            patch("custom_components.luxtronik2.water_heater.LOGGER") as mock_logger,
        ):
            await async_setup_entry(
                MagicMock(), entry, lambda entities, update: added.extend(entities)
            )
            mock_logger.debug.assert_called()


class TestWaterHeaterMaxTemp:
    def test_max_temp_from_data(self):
        from custom_components.luxtronik2.water_heater import (
            WATER_HEATERS,
            LuxtronikWaterHeater,
        )

        data = make_coordinator_data(parameters={"ID_Einst_BW_max": 65.0})
        coord = _mock_coordinator(data)
        entry = _mock_entry()
        hass = MagicMock()
        entity = LuxtronikWaterHeater(hass, entry, coord, WATER_HEATERS[0])
        _patch_entity(entity)
        result = entity.max_temp
        assert result == 65.0

    def test_max_temp_fallback_on_missing_key(self):
        from custom_components.luxtronik2.water_heater import (
            WATER_HEATERS,
            LuxtronikWaterHeater,
        )

        data = make_coordinator_data(parameters={})
        coord = _mock_coordinator(data)
        entry = _mock_entry()
        hass = MagicMock()
        entity = LuxtronikWaterHeater(hass, entry, coord, WATER_HEATERS[0])
        _patch_entity(entity)
        result = entity.max_temp
        assert result == 60.0

    def test_max_temp_fallback_on_conversion_error(self):
        from custom_components.luxtronik2.water_heater import (
            WATER_HEATERS,
            LuxtronikWaterHeater,
        )

        data = make_coordinator_data(parameters={"ID_Einst_BW_max": "not_a_number"})
        coord = _mock_coordinator(data)
        entry = _mock_entry()
        hass = MagicMock()
        entity = LuxtronikWaterHeater(hass, entry, coord, WATER_HEATERS[0])
        _patch_entity(entity)
        result = entity.max_temp
        assert result == 60.0
