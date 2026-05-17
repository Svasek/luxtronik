"""Tests for custom_components.luxtronik2.climate constants and mappings."""

from __future__ import annotations

from homeassistant.components.climate import (
    PRESET_AWAY,
    PRESET_BOOST,
    PRESET_COMFORT,
    PRESET_NONE,
    HVACAction,
    HVACMode,
)

from custom_components.luxtronik2.climate import (
    HVAC_ACTION_MAPPING_COOL,
    HVAC_ACTION_MAPPING_HEAT,
    HVAC_MODE_MAPPING_COOL,
    HVAC_MODE_MAPPING_HEAT,
    HVAC_PRESET_MAPPING,
    MAX_TEMPERATURE,
    MIN_TEMPERATURE,
    THERMOSTATS,
    LuxtronikClimateExtraStoredData,
)
from custom_components.luxtronik2.const import (
    DeviceKey,
    LuxMode,
    LuxOperationMode,
)


class TestHVACMappings:
    def test_heat_action_mapping_complete(self):
        """All LuxOperationMode values are mapped for heating."""
        for mode in LuxOperationMode:
            assert mode in HVAC_ACTION_MAPPING_HEAT, f"Missing: {mode}"

    def test_cool_action_mapping_complete(self):
        """All LuxOperationMode values are mapped for cooling."""
        for mode in LuxOperationMode:
            assert mode in HVAC_ACTION_MAPPING_COOL, f"Missing: {mode}"

    def test_heating_maps_to_heating_action(self):
        assert (
            HVAC_ACTION_MAPPING_HEAT[LuxOperationMode.heating]
            == HVACAction.HEATING.value
        )

    def test_cooling_maps_to_cooling_action(self):
        assert (
            HVAC_ACTION_MAPPING_COOL[LuxOperationMode.cooling]
            == HVACAction.COOLING.value
        )

    def test_no_request_maps_to_idle(self):
        assert (
            HVAC_ACTION_MAPPING_HEAT[LuxOperationMode.no_request]
            == HVACAction.IDLE.value
        )
        assert (
            HVAC_ACTION_MAPPING_COOL[LuxOperationMode.no_request]
            == HVACAction.IDLE.value
        )

    def test_evu_maps_to_idle(self):
        assert HVAC_ACTION_MAPPING_HEAT[LuxOperationMode.evu] == HVACAction.IDLE.value

    def test_heat_mode_mapping(self):
        assert HVAC_MODE_MAPPING_HEAT[LuxMode.off] == HVACMode.OFF.value
        assert HVAC_MODE_MAPPING_HEAT[LuxMode.automatic] == HVACMode.HEAT.value
        assert HVAC_MODE_MAPPING_HEAT[LuxMode.party] == HVACMode.HEAT.value

    def test_cool_mode_mapping(self):
        assert HVAC_MODE_MAPPING_COOL[LuxMode.off] == HVACMode.OFF.value
        assert HVAC_MODE_MAPPING_COOL[LuxMode.automatic] == HVACMode.COOL.value


class TestHVACPresetMapping:
    def test_off_preset(self):
        assert HVAC_PRESET_MAPPING[LuxMode.off] == PRESET_NONE

    def test_automatic_preset(self):
        assert HVAC_PRESET_MAPPING[LuxMode.automatic] == PRESET_NONE

    def test_party_preset(self):
        assert HVAC_PRESET_MAPPING[LuxMode.party] == PRESET_COMFORT

    def test_holidays_preset(self):
        assert HVAC_PRESET_MAPPING[LuxMode.holidays] == PRESET_AWAY

    def test_second_heatsource_preset(self):
        assert HVAC_PRESET_MAPPING[LuxMode.second_heatsource] == PRESET_BOOST


class TestThermostats:
    def test_thermostat_count(self):
        assert len(THERMOSTATS) >= 3  # heating new, heating old, cooling

    def test_heating_thermostat_exists(self):
        heating = [t for t in THERMOSTATS if t.device_key == DeviceKey.heating]
        assert len(heating) >= 1

    def test_cooling_thermostat_exists(self):
        cooling = [t for t in THERMOSTATS if t.device_key == DeviceKey.cooling]
        assert len(cooling) == 1

    def test_temperature_bounds(self):
        assert MIN_TEMPERATURE == 8
        assert MAX_TEMPERATURE == 28


class TestClimateExtraStoredData:
    def test_as_dict(self):
        data = LuxtronikClimateExtraStoredData(
            _attr_target_temperature=21.0,
            _attr_hvac_mode=HVACMode.HEAT,
            _attr_preset_mode=PRESET_NONE,
        )
        d = data.as_dict()
        assert d["_attr_target_temperature"] == 21.0
        assert d["_attr_hvac_mode"] == HVACMode.HEAT
        assert d["_attr_preset_mode"] == PRESET_NONE

    def test_defaults(self):
        data = LuxtronikClimateExtraStoredData()
        d = data.as_dict()
        assert d["_attr_target_temperature"] is None
        assert d["_attr_hvac_mode"] is None
        assert d["last_hvac_mode_before_preset"] is None
