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
