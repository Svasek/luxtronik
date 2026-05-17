"""Tests for custom_components.luxtronik2.update (firmware update entity)."""

from unittest.mock import MagicMock

import pytest

from custom_components.luxtronik2.update import LuxtronikUpdateEntity

# ===========================================================================
# extract_firmware_version
# ===========================================================================


@pytest.mark.parametrize(
    ("filename", "expected"),
    [
        ("wp2reg-V3.91.0_d0dc76bb", "V3.91.0"),
        ("wp2reg-V2.88.1-9086", "V2.88.1-9086"),
        ("wpreg.V1.88.3-9717", "V1.88.3-9717"),
        ("otherprefix-V2.99.2-1234", "V2.99.2-1234"),
        ("something-V3.91.0_moretext", "V3.91.0"),
        ("nofirmwarehere.txt", None),
        (None, None),
        ("", None),
        ("wp2reg-B1.0.0", "B1.0.0"),
    ],
)
def test_extract_firmware_version(filename, expected):
    assert LuxtronikUpdateEntity.extract_firmware_version(filename) == expected


# ===========================================================================
# version_is_newer
# ===========================================================================


def _make_version_entity():
    entity = MagicMock(spec=LuxtronikUpdateEntity)
    entity.version_is_newer = LuxtronikUpdateEntity.version_is_newer.__get__(entity)
    return entity


@pytest.mark.parametrize(
    ("available", "installed", "expected"),
    [
        ("V4.0.0", "V3.90.1", True),
        ("V3.91.0", "V3.90.1", True),
        ("V3.90.1", "V3.90.1", False),
        ("V3.89.0", "V3.90.1", False),
        ("invalid", "V3.90.1", False),
    ],
)
def test_version_is_newer(available, installed, expected):
    entity = _make_version_entity()
    assert entity.version_is_newer(available, installed) is expected


# ===========================================================================
# latest_version
# ===========================================================================


def _make_latest_entity():
    entity = MagicMock(spec=LuxtronikUpdateEntity)
    entity.latest_version = LuxtronikUpdateEntity.latest_version.fget.__get__(entity)
    entity.update_available = LuxtronikUpdateEntity.update_available.fget.__get__(
        entity
    )
    return entity


def test_latest_version_none_when_no_available():
    entity = _make_latest_entity()
    entity._LuxtronikUpdateEntity__firmware_version_available = None
    entity._attr_state = "V3.90.1"
    result = LuxtronikUpdateEntity.latest_version.fget(entity)
    assert result is None


def test_latest_version_none_when_no_installed():
    entity = _make_latest_entity()
    entity._LuxtronikUpdateEntity__firmware_version_available = "V3.91.0"
    entity._attr_state = None
    type(entity).installed_version = property(lambda s: s._attr_state)
    result = LuxtronikUpdateEntity.latest_version.fget(entity)
    assert result is None


def test_latest_version_strips_build_number():
    entity = _make_latest_entity()
    entity._LuxtronikUpdateEntity__firmware_version_available = "V3.91.0-9086"
    entity._attr_state = "V3.90.1"
    type(entity).installed_version = property(lambda s: s._attr_state)
    result = LuxtronikUpdateEntity.latest_version.fget(entity)
    assert result == "V3.91.0"


# ===========================================================================
# release_notes
# ===========================================================================


def test_release_notes_none_when_no_download_id():
    entity = MagicMock(spec=LuxtronikUpdateEntity)
    entity._attr_state = "X99.0.0"
    type(entity).installed_version = property(lambda s: s._attr_state)
    result = LuxtronikUpdateEntity.release_notes(entity)
    assert result is None


def test_release_notes_returns_html():
    entity = MagicMock(spec=LuxtronikUpdateEntity)
    entity._attr_state = "V3.90.1"
    type(entity).installed_version = property(lambda s: s._attr_state)
    entity.coordinator = MagicMock()
    entity.coordinator.model = "LWP 10"
    entity.coordinator.manufacturer = "Alpha Innotec"
    entity._LuxtronikUpdateEntity__firmware_version_available = "V3.91.0"
    entity._LuxtronikUpdateEntity__firmware_version_changelog = "Bug fixes"
    entity.hass = MagicMock()
    entity.hass.config.language = "en"
    result = LuxtronikUpdateEntity.release_notes(entity)
    assert result is not None
    assert "V3.91.0" in result
    assert "Bug fixes" in result


# ===========================================================================
# update.py — update_available, manual_url (lines 113-115)
# ===========================================================================


def _make_full_update_entity():
    """Create a real LuxtronikUpdateEntity for integration-level tests."""
    from conftest import make_coordinator_data
    from homeassistant.const import CONF_HOST, CONF_PORT, CONF_TIMEOUT

    from custom_components.luxtronik2.const import (
        CONF_HA_SENSOR_PREFIX,
        CONF_MAX_DATA_LENGTH,
        DEFAULT_MAX_DATA_LENGTH,
        DEFAULT_PORT,
        DEFAULT_TIMEOUT,
        DOMAIN,
        DeviceKey,
        LuxCalculation as LC,
        SensorKey,
    )
    from custom_components.luxtronik2.model import LuxtronikUpdateEntityDescription
    from custom_components.luxtronik2.update import LuxtronikUpdateEntity

    desc = LuxtronikUpdateEntityDescription(
        key=SensorKey.FIRMWARE,
        luxtronik_key=LC.C0081_FIRMWARE_VERSION,
        device_key=DeviceKey.heatpump,
    )
    data = make_coordinator_data()
    coord = MagicMock()
    coord.data = data
    coord.entity_active.return_value = True
    coord.entity_visible.return_value = True
    coord.get_device.return_value = MagicMock()
    coord.model = "LW"
    coord.manufacturer = "Alpha Innotec"
    entry = MagicMock()
    entry.data = {
        CONF_HOST: "192.168.1.100",
        CONF_PORT: DEFAULT_PORT,
        CONF_TIMEOUT: DEFAULT_TIMEOUT,
        CONF_MAX_DATA_LENGTH: DEFAULT_MAX_DATA_LENGTH,
        CONF_HA_SENSOR_PREFIX: DOMAIN,
    }
    entity = LuxtronikUpdateEntity(entry, coord, desc)
    entity.hass = MagicMock()
    entity.hass.config.time_zone = "UTC"
    entity.async_write_ha_state = MagicMock()
    entity.async_schedule_update_ha_state = MagicMock()
    return entity


def test_update_available_true():
    entity = _make_full_update_entity()
    entity._LuxtronikUpdateEntity__firmware_version_available = "V3.91.0"
    entity._attr_state = "V3.90.1"
    assert entity.update_available is True


def test_update_available_false_no_latest():
    entity = _make_full_update_entity()
    entity._LuxtronikUpdateEntity__firmware_version_available = None
    entity._attr_state = "V3.90.1"
    assert entity.update_available is False


def test_manual_url_german():
    from custom_components.luxtronik2.update import FIRMWARE_UPDATE_MANUAL_DE, LANG_DE

    entity = _make_full_update_entity()
    entity._LuxtronikUpdateEntity__firmware_version_available = "V3.91.0"
    entity._attr_state = "V3.90.1"
    entity.hass.config.language = LANG_DE
    notes = entity.release_notes()
    assert FIRMWARE_UPDATE_MANUAL_DE in notes


def test_manual_url_english():
    from custom_components.luxtronik2.update import FIRMWARE_UPDATE_MANUAL_EN

    entity = _make_full_update_entity()
    entity._LuxtronikUpdateEntity__firmware_version_available = "V3.91.0"
    entity._attr_state = "V3.90.1"
    entity.hass.config.language = "en"
    notes = entity.release_notes()
    assert FIRMWARE_UPDATE_MANUAL_EN in notes
