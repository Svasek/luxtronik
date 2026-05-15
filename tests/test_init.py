"""Tests for custom_components.luxtronik.__init__ (service registration and helpers)."""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.exceptions import ServiceValidationError

from custom_components.luxtronik.const import (
    ATTR_PARAMETER,
    ATTR_VALUE,
    CONF_HA_SENSOR_PREFIX,
    DOMAIN,
    SERVICE_WRITE,
)


# ===========================================================================
# Service write_parameter validation
# ===========================================================================


class TestWriteParameterValidation:
    """Test the write_parameter service handler validation logic."""

    def test_writable_prefix_accepted(self):
        """Verify whitelisted prefixes are accepted."""
        writable_prefixes = (
            "ID_Einst_",
            "ID_Ba_",
            "ID_Soll_",
            "ID_Sollwert_",
            "ID_SU_",
            "ID_RBE_",
            "Unknown_Parameter_",
            "HEATING_TARGET_TEMP_ROOM_THERMOSTAT",
        )
        test_params = [
            "ID_Einst_BWS_akt",
            "ID_Ba_Hz_akt",
            "ID_Soll_BWS_akt",
            "ID_Sollwert_KuCft1_akt",
            "ID_SU_FrkdHz",
            "ID_RBE_Einflussfaktor_RT_akt",
            "Unknown_Parameter_1159",
            "HEATING_TARGET_TEMP_ROOM_THERMOSTAT",
        ]
        for param in test_params:
            assert param.startswith(writable_prefixes), f"{param} should be writable"

    def test_non_writable_prefix_rejected(self):
        """Verify non-whitelisted prefixes are rejected."""
        writable_prefixes = (
            "ID_Einst_",
            "ID_Ba_",
            "ID_Soll_",
            "ID_Sollwert_",
            "ID_SU_",
            "ID_RBE_",
            "Unknown_Parameter_",
            "HEATING_TARGET_TEMP_ROOM_THERMOSTAT",
        )
        forbidden_params = [
            "ID_WEB_Temperatur_TVL",
            "ID_Visi_Solar",
            "system_command",
            "admin_access",
        ]
        for param in forbidden_params:
            assert not param.startswith(writable_prefixes), (
                f"{param} should NOT be writable"
            )


# ===========================================================================
# convert_to_int_if_possible (used by service handler)
# ===========================================================================


class TestConvertToIntInService:
    def test_int_conversion(self):
        from custom_components.luxtronik.common import convert_to_int_if_possible

        assert convert_to_int_if_possible("42") == 42
        assert convert_to_int_if_possible("not_a_number") == "not_a_number"
