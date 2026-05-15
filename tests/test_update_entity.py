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


if __name__ == "__main__":
    unittest.main()
