"""Tests for __init__.py functions using direct calls (bypassing HA loader)."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

from conftest import make_coordinator_data
from homeassistant.const import CONF_HOST, CONF_PORT, CONF_TIMEOUT
from homeassistant.exceptions import ConfigEntryNotReady, ServiceValidationError
import pytest

from custom_components.luxtronik2 import (
    async_setup_entry,
    async_unload_entry,
    setup_hass_services,
)
from custom_components.luxtronik2.const import (
    ATTR_PARAMETER,
    ATTR_VALUE,
    CONF_HA_SENSOR_PREFIX,
    CONF_MAX_DATA_LENGTH,
    DEFAULT_MAX_DATA_LENGTH,
    DEFAULT_PORT,
    DEFAULT_TIMEOUT,
    DOMAIN,
    PLATFORMS,
    SERVICE_WRITE,
)


def _mock_entry():
    entry = MagicMock()
    entry.data = {
        CONF_HOST: "192.168.1.100",
        CONF_PORT: DEFAULT_PORT,
        CONF_TIMEOUT: DEFAULT_TIMEOUT,
        CONF_MAX_DATA_LENGTH: DEFAULT_MAX_DATA_LENGTH,
        CONF_HA_SENSOR_PREFIX: DOMAIN,
    }
    entry.options = {}
    entry.entry_id = "test_entry_id"
    entry.add_update_listener = MagicMock(return_value=MagicMock())
    entry.async_on_unload = MagicMock()
    return entry


def _mock_coordinator(hass):
    coord = MagicMock()
    coord.hass = hass
    coord.data = make_coordinator_data()
    coord.manufacturer = "Alpha Innotec"
    coord.model = "LWP 10"
    coord.async_config_entry_first_refresh = AsyncMock()
    coord.async_shutdown = AsyncMock()
    coord.async_write = AsyncMock()
    return coord


class TestAsyncSetupEntry:
    @pytest.mark.asyncio
    async def test_success(self):
        hass = MagicMock()
        hass.config_entries.async_forward_entry_setups = AsyncMock()
        hass.config_entries.async_update_entry = MagicMock()
        hass.services.has_service = MagicMock(return_value=True)
        entry = _mock_entry()
        coord = _mock_coordinator(hass)

        with patch(
            "custom_components.luxtronik2.connect_and_get_coordinator",
            return_value=coord,
        ):
            result = await async_setup_entry(hass, entry)

        assert result is True
        coord.async_config_entry_first_refresh.assert_awaited_once()
        hass.config_entries.async_forward_entry_setups.assert_awaited_once_with(
            entry, PLATFORMS
        )

    @pytest.mark.asyncio
    async def test_connection_failure_raises_not_ready(self):
        hass = MagicMock()
        entry = _mock_entry()

        with (
            patch(
                "custom_components.luxtronik2.connect_and_get_coordinator",
                side_effect=ConnectionRefusedError("refused"),
            ),
            pytest.raises(ConfigEntryNotReady),
        ):
            await async_setup_entry(hass, entry)

    @pytest.mark.asyncio
    async def test_title_without_manufacturer(self):
        hass = MagicMock()
        hass.config_entries.async_forward_entry_setups = AsyncMock()
        hass.config_entries.async_update_entry = MagicMock()
        hass.services.has_service = MagicMock(return_value=True)
        entry = _mock_entry()
        coord = _mock_coordinator(hass)
        coord.manufacturer = None

        with patch(
            "custom_components.luxtronik2.connect_and_get_coordinator",
            return_value=coord,
        ):
            await async_setup_entry(hass, entry)

        call_args = hass.config_entries.async_update_entry.call_args
        title = call_args.kwargs.get("title", "")
        assert "Luxtronik @" in title


class TestAsyncUnloadEntry:
    @pytest.mark.asyncio
    async def test_unload_success(self):
        hass = MagicMock()
        hass.config_entries.async_unload_platforms = AsyncMock(return_value=True)
        hass.config_entries.async_entries = MagicMock(return_value=[])
        hass.services.async_remove = MagicMock()
        entry = _mock_entry()
        entry.runtime_data = _mock_coordinator(hass)

        result = await async_unload_entry(hass, entry)

        assert result is True
        entry.runtime_data.async_shutdown.assert_awaited_once()
        hass.services.async_remove.assert_called_once_with(DOMAIN, SERVICE_WRITE)

    @pytest.mark.asyncio
    async def test_unload_with_remaining_entries(self):
        hass = MagicMock()
        hass.config_entries.async_unload_platforms = AsyncMock(return_value=True)
        other_entry = MagicMock()
        other_entry.entry_id = "other_entry"
        hass.config_entries.async_entries = MagicMock(return_value=[other_entry])
        hass.services.async_remove = MagicMock()
        entry = _mock_entry()
        entry.runtime_data = _mock_coordinator(hass)

        await async_unload_entry(hass, entry)

        hass.services.async_remove.assert_not_called()


class TestSetupHassServices:
    def test_service_already_registered(self):
        hass = MagicMock()
        hass.services.has_service = MagicMock(return_value=True)
        entry = _mock_entry()

        setup_hass_services(hass, entry)

        hass.services.async_register.assert_not_called()

    def test_service_registered(self):
        hass = MagicMock()
        hass.services.has_service = MagicMock(return_value=False)
        entry = _mock_entry()

        setup_hass_services(hass, entry)

        hass.services.async_register.assert_called_once()


class TestWriteParameterService:
    @pytest.mark.asyncio
    async def test_write_valid_parameter(self):
        hass = MagicMock()
        hass.services.has_service = MagicMock(return_value=False)
        entry = _mock_entry()

        setup_hass_services(hass, entry)
        handler = hass.services.async_register.call_args[0][2]

        from homeassistant.config_entries import ConfigEntryState

        mock_entry = MagicMock()
        mock_entry.state = ConfigEntryState.LOADED
        mock_entry.runtime_data = _mock_coordinator(hass)
        hass.config_entries.async_entries = MagicMock(return_value=[mock_entry])

        service = MagicMock()
        service.data = {
            ATTR_PARAMETER: "ID_Einst_BWS_akt",
            ATTR_VALUE: "42",
        }

        await handler(service)

        mock_entry.runtime_data.async_write.assert_awaited_once_with(
            "ID_Einst_BWS_akt", 42
        )

    @pytest.mark.asyncio
    async def test_write_rejected_parameter(self):
        hass = MagicMock()
        hass.services.has_service = MagicMock(return_value=False)
        entry = _mock_entry()

        setup_hass_services(hass, entry)
        handler = hass.services.async_register.call_args[0][2]

        service = MagicMock()
        service.data = {
            ATTR_PARAMETER: "ID_Forbidden_param",
            ATTR_VALUE: "42",
        }

        with pytest.raises(ServiceValidationError):
            await handler(service)

    @pytest.mark.asyncio
    async def test_write_invalid_parameter_name(self):
        hass = MagicMock()
        hass.services.has_service = MagicMock(return_value=False)
        entry = _mock_entry()

        setup_hass_services(hass, entry)
        handler = hass.services.async_register.call_args[0][2]

        service = MagicMock()
        service.data = {
            ATTR_PARAMETER: None,
            ATTR_VALUE: "42",
        }

        with pytest.raises(ServiceValidationError):
            await handler(service)
