"""Tests for custom_components.luxtronik.base (LuxtronikEntity)."""

from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timedelta
from typing import Any
from unittest.mock import AsyncMock, MagicMock, PropertyMock, patch

import pytest
from homeassistant.const import UnitOfTemperature, UnitOfTime

from custom_components.luxtronik.const import (
    DeviceKey,
    LuxCalculation as LC,
    LuxMode,
    LuxOperationMode,
    LuxParameter as LP,
    SensorAttrFormat,
    SensorAttrKey as SA,
)
from custom_components.luxtronik.model import (
    LuxtronikBinarySensorEntityDescription,
    LuxtronikEntityAttributeDescription,
    LuxtronikEntityDescription,
    LuxtronikSwitchDescription,
)

from conftest import make_coordinator_data


# ===========================================================================
# Helpers
# ===========================================================================


def _make_mock_coordinator(data=None):
    """Build a mock coordinator with data."""
    if data is None:
        data = make_coordinator_data()
    coord = MagicMock()
    coord.data = data
    coord.entity_visible.return_value = True
    coord.get_device.return_value = MagicMock()
    return coord


# ===========================================================================
# compute_is_on (tested via base mixin)
# ===========================================================================


class TestComputeIsOn:
    """Test compute_is_on logic from LuxtronikEntity."""

    def _make_entity_with_description(
        self, on_state=True, on_states=None, off_state=False, inverted=False
    ):
        """Create a minimal entity with a given description for compute_is_on testing."""
        from custom_components.luxtronik.base import LuxtronikEntity

        coord = _make_mock_coordinator()
        desc = LuxtronikBinarySensorEntityDescription(
            key="test_compute",
            on_state=on_state,
            on_states=on_states,
            off_state=off_state,
            inverted=inverted,
        )

        # We need to test compute_is_on directly without full entity init
        # So create a minimal mock that has entity_description
        entity = MagicMock()
        entity.entity_description = desc
        entity.compute_is_on = LuxtronikEntity.compute_is_on.__get__(entity)
        return entity

    def test_bool_state_true_matches(self):
        entity = self._make_entity_with_description(on_state=True)
        assert entity.compute_is_on(True) is True

    def test_bool_state_false_not_matches(self):
        entity = self._make_entity_with_description(on_state=True)
        assert entity.compute_is_on(False) is False

    def test_string_state_matches(self):
        entity = self._make_entity_with_description(on_state="active")
        assert entity.compute_is_on("active") is True

    def test_string_state_not_matches(self):
        entity = self._make_entity_with_description(on_state="active")
        assert entity.compute_is_on("inactive") is False

    def test_on_states_list(self):
        entity = self._make_entity_with_description(
            on_state="active", on_states=["active", "running"]
        )
        assert entity.compute_is_on("running") is True

    def test_inverted(self):
        entity = self._make_entity_with_description(on_state=True, inverted=True)
        assert entity.compute_is_on(True) is False
        assert entity.compute_is_on(False) is True

    def test_none_state_with_bool_on_state(self):
        entity = self._make_entity_with_description(on_state=True)
        # None state: bool(None) raises issue but compute_is_on handles it
        # on_state is bool and state is not None check → state is None so no coercion
        assert entity.compute_is_on(None) is False

    def test_int_state_as_bool(self):
        entity = self._make_entity_with_description(on_state=True)
        assert entity.compute_is_on(1) is True
        assert entity.compute_is_on(0) is False


# ===========================================================================
# formatted_data
# ===========================================================================


class TestFormattedData:
    """Test formatted_data method."""

    def _make_entity_for_formatting(self, data):
        """Create a mock entity with _get_value using the given data."""
        from custom_components.luxtronik.base import LuxtronikEntity

        entity = MagicMock()
        entity.entity_description = LuxtronikEntityDescription(key="test")
        entity.hass = MagicMock()
        entity.hass.config.time_zone = "UTC"

        def get_value(key):
            from custom_components.luxtronik.common import get_sensor_data

            return get_sensor_data(data, key)

        entity._get_value = get_value
        entity.formatted_data = LuxtronikEntity.formatted_data.__get__(entity)
        entity._attr_state = None
        return entity

    def test_none_value_returns_empty(self):
        data = make_coordinator_data()
        entity = self._make_entity_for_formatting(data)
        attr = LuxtronikEntityAttributeDescription(
            key=SA.LUXTRONIK_KEY,
            luxtronik_key=LP.UNSET,
        )
        result = entity.formatted_data(attr)
        assert result == ""

    def test_no_format_returns_str(self):
        data = make_coordinator_data(parameters={"ID_Ba_Hz_akt": "Automatic"})
        entity = self._make_entity_for_formatting(data)
        attr = LuxtronikEntityAttributeDescription(
            key=SA.LUXTRONIK_KEY,
            luxtronik_key=LP.P0003_MODE_HEATING,
            format=None,
        )
        result = entity.formatted_data(attr)
        assert result == "Automatic"

    def test_hour_minute_format(self):
        # 7200 seconds = 2 hours
        data = make_coordinator_data(parameters={"ID_Ba_Hz_akt": 7200})
        entity = self._make_entity_for_formatting(data)
        attr = LuxtronikEntityAttributeDescription(
            key=SA.LUXTRONIK_KEY,
            luxtronik_key=LP.P0003_MODE_HEATING,
            format=SensorAttrFormat.HOUR_MINUTE,
        )
        result = entity.formatted_data(attr)
        assert UnitOfTime.HOURS in result

    def test_celsius_tenth_format(self):
        data = make_coordinator_data(parameters={"ID_Ba_Hz_akt": 255})
        entity = self._make_entity_for_formatting(data)
        attr = LuxtronikEntityAttributeDescription(
            key=SA.LUXTRONIK_KEY,
            luxtronik_key=LP.P0003_MODE_HEATING,
            format=SensorAttrFormat.CELSIUS_TENTH,
        )
        result = entity.formatted_data(attr)
        assert UnitOfTemperature.CELSIUS in result
        assert "25.5" in result

    def test_datetime_value_returns_str(self):
        dt = datetime(2024, 1, 1, 12, 0)
        data = make_coordinator_data(parameters={"ID_Ba_Hz_akt": dt})
        entity = self._make_entity_for_formatting(data)
        attr = LuxtronikEntityAttributeDescription(
            key=SA.LUXTRONIK_KEY,
            luxtronik_key=LP.P0003_MODE_HEATING,
            format=None,
        )
        result = entity.formatted_data(attr)
        assert "2024" in result


# ===========================================================================
# should_update
# ===========================================================================


class TestShouldUpdate:
    def _make_entity_with_update_interval(self, interval):
        from custom_components.luxtronik.base import LuxtronikEntity

        entity = MagicMock()
        entity.entity_description = MagicMock()
        entity.entity_description.update_interval = interval
        entity.next_update = None
        entity.should_update = LuxtronikEntity.should_update.__get__(entity)
        return entity

    def test_no_interval_always_updates(self):
        entity = self._make_entity_with_update_interval(None)
        assert entity.should_update() is True

    def test_with_interval_and_no_next_update(self):
        entity = self._make_entity_with_update_interval(timedelta(minutes=5))
        assert entity.should_update() is True

    def test_with_interval_future_next_update(self):
        from homeassistant.util.dt import utcnow

        entity = self._make_entity_with_update_interval(timedelta(minutes=5))
        entity.next_update = utcnow() + timedelta(hours=1)
        assert entity.should_update() is False

    def test_with_interval_past_next_update(self):
        from homeassistant.util.dt import utcnow

        entity = self._make_entity_with_update_interval(timedelta(minutes=5))
        entity.next_update = utcnow() - timedelta(hours=1)
        assert entity.should_update() is True
