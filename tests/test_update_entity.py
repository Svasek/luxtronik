"""Tests for custom_components.luxtronik.update (firmware update entity)."""

import re
import unittest

from packaging.version import Version

from custom_components.luxtronik.update import LuxtronikUpdateEntity


class TestFirmwareVersionExtraction(unittest.TestCase):
    """Tests for extract_firmware_version static method."""

    def test_extract_standard_version(self):
        assert (
            LuxtronikUpdateEntity.extract_firmware_version("wp2reg-V3.91.0_d0dc76bb")
            == "V3.91.0"
        )

    def test_extract_version_with_build_number(self):
        assert (
            LuxtronikUpdateEntity.extract_firmware_version("wp2reg-V2.88.1-9086")
            == "V2.88.1-9086"
        )

    def test_extract_version_dot_separated(self):
        assert (
            LuxtronikUpdateEntity.extract_firmware_version("wpreg.V1.88.3-9717")
            == "V1.88.3-9717"
        )

    def test_extract_version_other_prefix(self):
        assert (
            LuxtronikUpdateEntity.extract_firmware_version("otherprefix-V2.99.2-1234")
            == "V2.99.2-1234"
        )

    def test_extract_version_with_moretext(self):
        assert (
            LuxtronikUpdateEntity.extract_firmware_version("something-V3.91.0_moretext")
            == "V3.91.0"
        )

    def test_no_version_in_filename(self):
        assert (
            LuxtronikUpdateEntity.extract_firmware_version("nofirmwarehere.txt") is None
        )

    def test_none_filename(self):
        assert LuxtronikUpdateEntity.extract_firmware_version(None) is None

    def test_empty_filename(self):
        assert LuxtronikUpdateEntity.extract_firmware_version("") is None

    def test_b_prefix_version(self):
        """Versions can also start with B prefix."""
        result = LuxtronikUpdateEntity.extract_firmware_version("wp2reg-B1.0.0")
        assert result == "B1.0.0"


class TestVersionIsNewer:
    """Tests for version comparison logic."""

    def _make_entity(self):
        """Create a minimal entity instance for testing instance methods."""
        from unittest.mock import MagicMock

        entity = MagicMock(spec=LuxtronikUpdateEntity)
        entity.version_is_newer = LuxtronikUpdateEntity.version_is_newer.__get__(entity)
        return entity

    def test_newer_major(self):
        entity = self._make_entity()
        assert entity.version_is_newer("V4.0.0", "V3.90.1") is True

    def test_newer_minor(self):
        entity = self._make_entity()
        assert entity.version_is_newer("V3.91.0", "V3.90.1") is True

    def test_same_version(self):
        entity = self._make_entity()
        assert entity.version_is_newer("V3.90.1", "V3.90.1") is False

    def test_older_version(self):
        entity = self._make_entity()
        assert entity.version_is_newer("V3.89.0", "V3.90.1") is False

    def test_invalid_version(self):
        entity = self._make_entity()
        assert entity.version_is_newer("invalid", "V3.90.1") is False


class TestLatestVersion:
    def _make_entity(self):
        from unittest.mock import MagicMock, PropertyMock

        entity = MagicMock(spec=LuxtronikUpdateEntity)
        entity.latest_version = LuxtronikUpdateEntity.latest_version.fget.__get__(entity)
        entity.update_available = LuxtronikUpdateEntity.update_available.fget.__get__(entity)
        return entity

    def test_latest_version_none_when_no_available(self):
        entity = self._make_entity()
        entity._LuxtronikUpdateEntity__firmware_version_available = None
        entity._attr_state = "V3.90.1"
        # Access property through fget
        result = LuxtronikUpdateEntity.latest_version.fget(entity)
        assert result is None

    def test_latest_version_none_when_no_installed(self):
        entity = self._make_entity()
        entity._LuxtronikUpdateEntity__firmware_version_available = "V3.91.0"
        entity._attr_state = None
        # installed_version returns _attr_state
        type(entity).installed_version = property(lambda s: s._attr_state)
        result = LuxtronikUpdateEntity.latest_version.fget(entity)
        assert result is None

    def test_latest_version_strips_build_number(self):
        entity = self._make_entity()
        entity._LuxtronikUpdateEntity__firmware_version_available = "V3.91.0-9086"
        entity._attr_state = "V3.90.1"
        type(entity).installed_version = property(lambda s: s._attr_state)
        result = LuxtronikUpdateEntity.latest_version.fget(entity)
        assert result == "V3.91.0"


class TestReleaseNotes:
    def test_release_notes_none_when_no_download_id(self):
        from unittest.mock import MagicMock

        entity = MagicMock(spec=LuxtronikUpdateEntity)
        entity._attr_state = "X99.0.0"  # Unknown prefix → no download ID
        type(entity).installed_version = property(lambda s: s._attr_state)
        result = LuxtronikUpdateEntity.release_notes(entity)
        assert result is None

    def test_release_notes_returns_html(self):
        from unittest.mock import MagicMock

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


if __name__ == "__main__":
    unittest.main()
