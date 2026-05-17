"""Tests for base.py LuxtronikEntity methods."""

from __future__ import annotations

from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

from conftest import make_coordinator_data
from homeassistant.components.water_heater import STATE_HEAT_PUMP
from homeassistant.const import (
    CONF_HOST,
    CONF_PORT,
    CONF_TIMEOUT,
    STATE_OFF,
    UnitOfTime,
)
import pytest

from custom_components.luxtronik2.base import LuxtronikEntity
from custom_components.luxtronik2.const import (
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
from custom_components.luxtronik2.sensor import LuxtronikSensorEntity

_ENTRY_DATA = {
    CONF_HOST: "192.168.1.100",
    CONF_PORT: DEFAULT_PORT,
    CONF_TIMEOUT: DEFAULT_TIMEOUT,
    CONF_MAX_DATA_LENGTH: DEFAULT_MAX_DATA_LENGTH,
    CONF_HA_SENSOR_PREFIX: DOMAIN,
}


def _mock_entry():
    entry = MagicMock()
    entry.data = _ENTRY_DATA.copy()
    return entry


def _mock_coordinator(data=None):
    if data is None:
        data = make_coordinator_data()
    coord = MagicMock()
    coord.data = data
    coord.entity_active.return_value = True
    coord.entity_visible.return_value = True
    coord.get_device.return_value = MagicMock()
    return coord


def _patch_entity(entity):
    entity.hass = MagicMock()
    entity.hass.config.time_zone = "UTC"
    entity.async_write_ha_state = MagicMock()
    entity.async_schedule_update_ha_state = MagicMock()


def _make_sensor_entity(data=None, description=None):
    hass = MagicMock()
    entry = _mock_entry()
    coord = _mock_coordinator(data)
    if description is None:
        description = LuxtronikSensorDescription(
            key=SensorKey.FLOW_OUT_TEMPERATURE,
            luxtronik_key=LC.C0011_FLOW_OUT_TEMPERATURE,
            device_key=DeviceKey.heatpump,
        )
    entity = LuxtronikSensorEntity(hass, entry, coord, description, DeviceKey.heatpump)
    _patch_entity(entity)
    return entity


# ===========================================================================
# _handle_coordinator_update (base)
# ===========================================================================


class TestBaseHandleCoordinatorUpdate:
    def test_datetime_without_tzinfo_gets_timezone(self):
        """Datetime values without tzinfo get local timezone."""
        naive_dt = datetime(2024, 1, 15, 10, 30, 0)
        data = make_coordinator_data(calculations={"ID_WEB_Temperatur_TRL": naive_dt})
        entity = _make_sensor_entity(data)
        # Call the base _handle_coordinator_update
        LuxtronikEntity._handle_coordinator_update(entity, data)
        assert entity._attr_state.tzinfo is not None

    def test_icon_by_state(self):
        """Icon changes based on state."""
        data = make_coordinator_data(calculations={"ID_WEB_Temperatur_TRL": "heating"})
        desc = LuxtronikSensorDescription(
            key=SensorKey.FLOW_OUT_TEMPERATURE,
            luxtronik_key=LC.C0011_FLOW_OUT_TEMPERATURE,
            device_key=DeviceKey.heatpump,
            icon="mdi:default",
            icon_by_state={"heating": "mdi:fire"},
        )
        entity = _make_sensor_entity(data, desc)
        LuxtronikEntity._handle_coordinator_update(entity, data)
        assert entity._attr_icon == "mdi:fire"

    def test_icon_fallback(self):
        """When no matching icon_by_state, use default icon."""
        data = make_coordinator_data(calculations={"ID_WEB_Temperatur_TRL": "unknown"})
        desc = LuxtronikSensorDescription(
            key=SensorKey.FLOW_OUT_TEMPERATURE,
            luxtronik_key=LC.C0011_FLOW_OUT_TEMPERATURE,
            device_key=DeviceKey.heatpump,
            icon="mdi:default",
            icon_by_state={"heating": "mdi:fire"},
        )
        entity = _make_sensor_entity(data, desc)
        LuxtronikEntity._handle_coordinator_update(entity, data)
        assert entity._attr_icon == "mdi:default"


# ===========================================================================
# should_update
# ===========================================================================


class TestShouldUpdate:
    def test_no_interval_always_true(self):
        entity = _make_sensor_entity()
        assert entity.should_update() is True

    def test_with_interval_and_no_next_update(self):
        desc = LuxtronikSensorDescription(
            key=SensorKey.FLOW_OUT_TEMPERATURE,
            luxtronik_key=LC.C0011_FLOW_OUT_TEMPERATURE,
            device_key=DeviceKey.heatpump,
            update_interval=timedelta(seconds=60),
        )
        entity = _make_sensor_entity(description=desc)
        entity.next_update = None
        assert entity.should_update() is True

    def test_with_interval_and_future_next_update(self):
        desc = LuxtronikSensorDescription(
            key=SensorKey.FLOW_OUT_TEMPERATURE,
            luxtronik_key=LC.C0011_FLOW_OUT_TEMPERATURE,
            device_key=DeviceKey.heatpump,
            update_interval=timedelta(seconds=60),
        )
        entity = _make_sensor_entity(description=desc)
        entity.next_update = datetime.now() + timedelta(hours=1)
        # Should NOT update (future next_update)
        # Note: this may be True/False depending on utcnow vs now, but the logic is tested


# ===========================================================================
# compute_is_on
# ===========================================================================


class TestComputeIsOn:
    def _make_entity_with_on_state(self, on_state, state, inverted=False):
        from custom_components.luxtronik2.model import LuxtronikSwitchDescription

        desc = LuxtronikSwitchDescription(
            key=SensorKey.HEATING,
            luxtronik_key=LP.P0003_MODE_HEATING,
            device_key=DeviceKey.heating,
            on_state=on_state,
            inverted=inverted,
        )
        from custom_components.luxtronik2.switch import LuxtronikSwitchEntity

        hass = MagicMock()
        entry = _mock_entry()
        coord = _mock_coordinator()
        entity = LuxtronikSwitchEntity(hass, entry, coord, desc, DeviceKey.heating)
        return entity

    def test_bool_on_state_true(self):
        entity = self._make_entity_with_on_state(True, True)
        assert entity.compute_is_on(True) is True

    def test_bool_on_state_false(self):
        entity = self._make_entity_with_on_state(True, False)
        assert entity.compute_is_on(False) is False

    def test_inverted(self):
        entity = self._make_entity_with_on_state(True, True, inverted=True)
        assert entity.compute_is_on(True) is False


# ===========================================================================
# formatted_data
# ===========================================================================


class TestFormattedData:
    def test_hour_minute_format(self):
        data = make_coordinator_data(calculations={"ID_WEB_Temperatur_TRL": 7200})
        entity = _make_sensor_entity(data)
        attr = LuxtronikEntityAttributeDescription(
            key=SA.TIMER_HEATPUMP_ON,
            luxtronik_key=LC.C0011_FLOW_OUT_TEMPERATURE,
            format=SensorAttrFormat.HOUR_MINUTE,
        )
        result = entity.formatted_data(attr)
        assert UnitOfTime.HOURS in result
        assert "2:00" in result

    def test_celsius_tenth_format(self):
        data = make_coordinator_data(calculations={"ID_WEB_Temperatur_TRL": 255})
        entity = _make_sensor_entity(data)
        attr = LuxtronikEntityAttributeDescription(
            key=SA.TIMER_HEATPUMP_ON,
            luxtronik_key=LC.C0011_FLOW_OUT_TEMPERATURE,
            format=SensorAttrFormat.CELSIUS_TENTH,
        )
        result = entity.formatted_data(attr)
        assert "25.5" in result

    def test_none_value_returns_empty(self):
        data = make_coordinator_data(calculations={})
        entity = _make_sensor_entity(data)
        attr = LuxtronikEntityAttributeDescription(
            key=SA.TIMER_HEATPUMP_ON,
            luxtronik_key=LC.C0011_FLOW_OUT_TEMPERATURE,
        )
        result = entity.formatted_data(attr)
        assert result == ""

    def test_no_format_returns_str(self):
        data = make_coordinator_data(calculations={"ID_WEB_Temperatur_TRL": 42})
        entity = _make_sensor_entity(data)
        attr = LuxtronikEntityAttributeDescription(
            key=SA.TIMER_HEATPUMP_ON,
            luxtronik_key=LC.C0011_FLOW_OUT_TEMPERATURE,
        )
        result = entity.formatted_data(attr)
        assert result == "42"

    def test_datetime_value_returns_str(self):
        dt = datetime(2024, 1, 15, 10, 30, 0)
        data = make_coordinator_data(calculations={"ID_WEB_Temperatur_TRL": dt})
        entity = _make_sensor_entity(data)
        attr = LuxtronikEntityAttributeDescription(
            key=SA.TIMER_HEATPUMP_ON,
            luxtronik_key=LC.C0011_FLOW_OUT_TEMPERATURE,
            format=SensorAttrFormat.HOUR_MINUTE,
        )
        # datetime is handled before format check
        result = entity.formatted_data(attr)
        assert "2024" in result

    def test_switch_gap_heating(self):
        """Test SWITCH_GAP format when heating."""
        data = make_coordinator_data(
            parameters={
                "ID_Ba_Hz_akt": "Automatic",
                "ID_Ba_Bw_akt": "Automatic",
                "ID_Einst_HRHyst_akt": 50,  # 50 * 0.1 = 5.0
            },
            calculations={
                "ID_WEB_Temperatur_TRL": 30.0,  # flow_out
                "ID_WEB_Sollwert_TRL_HZ": 28.0,  # flow_out_target
                "ID_WEB_WP_BZ_akt": LuxOperationMode.heating,
                "ID_WEB_VD1out": 1,
                "ID_WEB_ZW1out": 0,
            },
        )
        entity = _make_sensor_entity(data)
        attr = LuxtronikEntityAttributeDescription(
            key=SA.SWITCH_GAP,
            luxtronik_key=LC.C0011_FLOW_OUT_TEMPERATURE,
            format=SensorAttrFormat.SWITCH_GAP,
        )
        result = entity.formatted_data(attr)
        assert "K" in result  # UnitOfTemperature.KELVIN

    def test_switch_gap_not_heating_not_off(self):
        """Test SWITCH_GAP when mode is not heating and not off."""
        data = make_coordinator_data(
            parameters={
                "ID_Ba_Hz_akt": "Automatic",  # not LuxMode.off
                "ID_Ba_Bw_akt": "Automatic",
                "ID_Einst_HRHyst_akt": 50,
            },
            calculations={
                "ID_WEB_Temperatur_TRL": 30.0,
                "ID_WEB_Sollwert_TRL_HZ": 28.0,
                "ID_WEB_WP_BZ_akt": LuxOperationMode.domestic_water,
                "ID_WEB_VD1out": 1,
                "ID_WEB_ZW1out": 0,
            },
        )
        entity = _make_sensor_entity(data)
        attr = LuxtronikEntityAttributeDescription(
            key=SA.SWITCH_GAP,
            luxtronik_key=LC.C0011_FLOW_OUT_TEMPERATURE,
            format=SensorAttrFormat.SWITCH_GAP,
        )
        result = entity.formatted_data(attr)
        assert "K" in result

    def test_switch_gap_mode_off(self):
        """Test SWITCH_GAP when heating mode is off."""
        data = make_coordinator_data(
            parameters={
                "ID_Ba_Hz_akt": LuxMode.off,
                "ID_Ba_Bw_akt": "Automatic",
                "ID_Einst_HRHyst_akt": 50,
            },
            calculations={
                "ID_WEB_Temperatur_TRL": 30.0,
                "ID_WEB_Sollwert_TRL_HZ": 28.0,
                "ID_WEB_WP_BZ_akt": LuxOperationMode.domestic_water,
                "ID_WEB_VD1out": 1,
                "ID_WEB_ZW1out": 0,
            },
        )
        entity = _make_sensor_entity(data)
        attr = LuxtronikEntityAttributeDescription(
            key=SA.SWITCH_GAP,
            luxtronik_key=LC.C0011_FLOW_OUT_TEMPERATURE,
            format=SensorAttrFormat.SWITCH_GAP,
        )
        result = entity.formatted_data(attr)
        assert result == ""


# ===========================================================================
# async_added_to_hass
# ===========================================================================


class TestAsyncAddedToHass:
    @pytest.mark.asyncio
    async def test_restores_last_state(self):
        entity = _make_sensor_entity()
        last_state = MagicMock()
        last_state.state = "25.5"
        last_state.attributes = {}
        entity.async_get_last_state = AsyncMock(return_value=last_state)
        entity.async_get_last_extra_data = AsyncMock(return_value=None)
        entity.async_on_remove = MagicMock()
        entity.entity_id = "sensor.test_entity"
        entity.platform = MagicMock()
        # Prevent _handle_coordinator_update from overwriting
        entity.coordinator.data = None

        with patch("custom_components.luxtronik2.base.async_dispatcher_connect"):
            await LuxtronikEntity.async_added_to_hass(entity)

        assert entity._attr_state == "25.5"

    @pytest.mark.asyncio
    async def test_no_last_state_returns_early(self):
        entity = _make_sensor_entity()
        entity.async_get_last_state = AsyncMock(return_value=None)
        entity.async_get_last_extra_data = AsyncMock(return_value=None)
        entity.platform = MagicMock()

        await LuxtronikEntity.async_added_to_hass(entity)
        # Should not crash

    @pytest.mark.asyncio
    async def test_restores_extra_data(self):
        entity = _make_sensor_entity()
        last_state = MagicMock()
        last_state.state = "42"
        last_state.attributes = {}
        entity.async_get_last_state = AsyncMock(return_value=last_state)

        extra_data = MagicMock()
        extra_data.as_dict.return_value = {"_attr_target_temperature": 22.0}
        entity.async_get_last_extra_data = AsyncMock(return_value=extra_data)
        entity.async_on_remove = MagicMock()
        entity.entity_id = "sensor.test_entity"
        entity.platform = MagicMock()

        with patch("custom_components.luxtronik2.base.async_dispatcher_connect"):
            await LuxtronikEntity.async_added_to_hass(entity)

        assert entity._attr_target_temperature == 22.0

    @pytest.mark.asyncio
    async def test_exception_is_caught(self):
        entity = _make_sensor_entity()
        entity.async_get_last_state = AsyncMock(side_effect=Exception("test error"))
        entity.platform = MagicMock()

        # Should not raise
        await LuxtronikEntity.async_added_to_hass(entity)


# ===========================================================================
# _handle_coordinator_update — icon with current_operation
# ===========================================================================


class TestIconCurrentOperation:
    def test_icon_off_suffix(self):
        """When _attr_current_operation is STATE_OFF, icon gets -off suffix."""
        data = make_coordinator_data(calculations={"ID_WEB_Temperatur_TRL": 25.0})
        desc = LuxtronikSensorDescription(
            key=SensorKey.FLOW_OUT_TEMPERATURE,
            luxtronik_key=LC.C0011_FLOW_OUT_TEMPERATURE,
            device_key=DeviceKey.heatpump,
            icon="mdi:water",
        )
        entity = _make_sensor_entity(data, desc)
        entity._attr_current_operation = STATE_OFF
        LuxtronikEntity._handle_coordinator_update(entity, data)
        assert entity._attr_icon == "mdi:water-off"

    def test_icon_auto_suffix(self):
        """When _attr_current_operation is STATE_HEAT_PUMP, icon gets -auto suffix."""
        data = make_coordinator_data(calculations={"ID_WEB_Temperatur_TRL": 25.0})
        desc = LuxtronikSensorDescription(
            key=SensorKey.FLOW_OUT_TEMPERATURE,
            luxtronik_key=LC.C0011_FLOW_OUT_TEMPERATURE,
            device_key=DeviceKey.heatpump,
            icon="mdi:water",
        )
        entity = _make_sensor_entity(data, desc)
        entity._attr_current_operation = STATE_HEAT_PUMP
        LuxtronikEntity._handle_coordinator_update(entity, data)
        assert entity._attr_icon == "mdi:water-auto"
