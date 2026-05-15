"""Tests for custom_components.luxtronik.water_heater constants and mappings."""

from __future__ import annotations

from homeassistant.components.water_heater import (
    STATE_ELECTRIC,
    STATE_HEAT_PUMP,
    STATE_PERFORMANCE,
)
from homeassistant.const import STATE_OFF

from custom_components.luxtronik.const import (
    DeviceKey,
    LuxMode,
    LuxOperationMode,
)
from custom_components.luxtronik.water_heater import (
    OPERATION_MAPPING,
    WATER_HEATERS,
)


class TestOperationMapping:
    def test_off(self):
        assert OPERATION_MAPPING[LuxMode.off] == STATE_OFF

    def test_automatic(self):
        assert OPERATION_MAPPING[LuxMode.automatic] == STATE_HEAT_PUMP

    def test_second_heatsource(self):
        assert OPERATION_MAPPING[LuxMode.second_heatsource] == STATE_ELECTRIC

    def test_party(self):
        assert OPERATION_MAPPING[LuxMode.party] == STATE_PERFORMANCE

    def test_holidays(self):
        assert OPERATION_MAPPING[LuxMode.holidays] == STATE_HEAT_PUMP


class TestWaterHeaterDescriptions:
    def test_water_heaters_count(self):
        assert len(WATER_HEATERS) == 2  # old firmware + new firmware

    def test_all_domestic_water(self):
        for wh in WATER_HEATERS:
            assert wh.device_key == DeviceKey.heatpump  # default
            assert wh.luxtronik_action_heating == LuxOperationMode.domestic_water

    def test_firmware_version_split(self):
        """First WH is for firmware < 88.3, second for >= 88.3."""
        from packaging.version import Version

        old = WATER_HEATERS[0]
        new = WATER_HEATERS[1]
        assert old.max_firmware_version_minor == Version("88.2")
        assert new.min_firmware_version_minor == Version("88.3")
