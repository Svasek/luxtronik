"""Tests for update.py — async_update and _request_available_firmware_version."""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

from conftest import make_coordinator_data
from homeassistant.const import CONF_HOST, CONF_PORT, CONF_TIMEOUT, STATE_UNAVAILABLE
import pytest

from custom_components.luxtronik2.const import (
    CONF_HA_SENSOR_PREFIX,
    CONF_MAX_DATA_LENGTH,
    DEFAULT_MAX_DATA_LENGTH,
    DEFAULT_PORT,
    DEFAULT_TIMEOUT,
    DOMAIN,
    LuxCalculation,
    SensorKey,
)
from custom_components.luxtronik2.model import LuxtronikUpdateEntityDescription
from custom_components.luxtronik2.update import (
    MIN_TIME_BETWEEN_UPDATES,
    LuxtronikUpdateEntity,
)

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
        data = make_coordinator_data(calculations={"ID_WEB_SoftStand": "V3.90.1"})
    coord = MagicMock()
    coord.data = data
    coord.entity_active.return_value = True
    coord.entity_visible.return_value = True
    coord.get_device.return_value = MagicMock()
    coord.model = "LWP 10"
    coord.manufacturer = "Alpha Innotec"
    return coord


def _make_update_entity(data=None):
    entry = _mock_entry()
    coord = _mock_coordinator(data)
    desc = LuxtronikUpdateEntityDescription(
        luxtronik_key=LuxCalculation.C0081_FIRMWARE_VERSION,
        key=SensorKey.FIRMWARE,
    )
    entity = LuxtronikUpdateEntity(entry=entry, coordinator=coord, description=desc)
    entity.hass = MagicMock()
    entity.hass.config.time_zone = "UTC"
    entity.hass.config.language = "en"
    entity.async_write_ha_state = MagicMock()
    entity.async_schedule_update_ha_state = MagicMock()
    return entity


# ===========================================================================
# async_setup_entry
# ===========================================================================


class TestUpdateAsyncSetupEntry:
    @pytest.mark.asyncio
    async def test_setup_creates_entity(self):
        from custom_components.luxtronik2.update import async_setup_entry

        data = make_coordinator_data(calculations={"ID_WEB_SoftStand": "V3.90.1"})
        coord = _mock_coordinator(data)
        entry = _mock_entry()
        entry.runtime_data = coord
        add = MagicMock()
        await async_setup_entry(MagicMock(), entry, add)
        add.assert_called_once()
        entities = add.call_args[0][0]
        assert len(entities) == 1
        assert isinstance(entities[0], LuxtronikUpdateEntity)


# ===========================================================================
# installed_version
# ===========================================================================


class TestInstalledVersion:
    def test_returns_attr_state(self):
        entity = _make_update_entity()
        entity._attr_state = "V3.90.1"
        assert entity.installed_version == "V3.90.1"

    def test_returns_none_when_no_state(self):
        entity = _make_update_entity()
        entity._attr_state = None
        assert entity.installed_version is None


# ===========================================================================
# async_update — throttle logic
# ===========================================================================


class TestAsyncUpdate:
    @pytest.mark.asyncio
    async def test_first_call_requests_firmware(self):
        entity = _make_update_entity()
        entity._attr_state = "V3.90.1"
        entity._LuxtronikUpdateEntity__firmware_version_available_last_request = None
        with patch.object(
            entity, "_request_available_firmware_version", new_callable=AsyncMock
        ) as mock_req:
            await entity.async_update()
            mock_req.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_skips_when_recently_requested(self):
        entity = _make_update_entity()
        entity._attr_state = "V3.90.1"
        entity._LuxtronikUpdateEntity__firmware_version_available_last_request = (
            datetime.now(UTC).timestamp()
        )
        with patch.object(
            entity, "_request_available_firmware_version", new_callable=AsyncMock
        ) as mock_req:
            await entity.async_update()
            mock_req.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_requests_when_expired(self):
        entity = _make_update_entity()
        entity._attr_state = "V3.90.1"
        entity._LuxtronikUpdateEntity__firmware_version_available_last_request = (
            datetime.now(UTC).timestamp()
            - MIN_TIME_BETWEEN_UPDATES.total_seconds()
            - 10
        )
        with patch.object(
            entity, "_request_available_firmware_version", new_callable=AsyncMock
        ) as mock_req:
            await entity.async_update()
            mock_req.assert_awaited_once()


# ===========================================================================
# _request_available_firmware_version
# ===========================================================================


class TestRequestAvailableFirmwareVersion:
    @pytest.mark.asyncio
    async def test_no_download_id_sets_unavailable(self):
        entity = _make_update_entity()
        entity._attr_state = "X99.0.0"  # Unknown prefix → no download ID
        await entity._request_available_firmware_version()
        assert (
            entity._LuxtronikUpdateEntity__firmware_version_available
            == STATE_UNAVAILABLE
        )

    @pytest.mark.asyncio
    async def test_successful_request(self):
        entity = _make_update_entity()
        entity._attr_state = "V3.90.1"

        mock_response_fw = AsyncMock()
        mock_response_fw.status = 200
        mock_response_fw.headers = {
            "Content-Disposition": "filename=wp2reg-V3.91.0_abc"
        }
        mock_response_fw.__aenter__ = AsyncMock(return_value=mock_response_fw)
        mock_response_fw.__aexit__ = AsyncMock(return_value=False)

        mock_response_cl = AsyncMock()
        mock_response_cl.status = 200
        mock_response_cl.text = AsyncMock(return_value="Bug fixes")
        mock_response_cl.__aenter__ = AsyncMock(return_value=mock_response_cl)
        mock_response_cl.__aexit__ = AsyncMock(return_value=False)

        mock_session = MagicMock()
        mock_session.get = MagicMock(side_effect=[mock_response_fw, mock_response_cl])

        with patch(
            "custom_components.luxtronik2.update.async_get_clientsession",
            return_value=mock_session,
        ):
            await entity._request_available_firmware_version()

        assert entity._LuxtronikUpdateEntity__firmware_version_available == "V3.91.0"
        assert entity._LuxtronikUpdateEntity__firmware_version_changelog == "Bug fixes"

    @pytest.mark.asyncio
    async def test_http_error_sets_unavailable(self):
        entity = _make_update_entity()
        entity._attr_state = "V3.90.1"

        mock_response = AsyncMock()
        mock_response.status = 500
        mock_response.__aenter__ = AsyncMock(return_value=mock_response)
        mock_response.__aexit__ = AsyncMock(return_value=False)

        mock_session = MagicMock()
        mock_session.get = MagicMock(return_value=mock_response)

        with patch(
            "custom_components.luxtronik2.update.async_get_clientsession",
            return_value=mock_session,
        ):
            await entity._request_available_firmware_version()

        assert (
            entity._LuxtronikUpdateEntity__firmware_version_available
            == STATE_UNAVAILABLE
        )

    @pytest.mark.asyncio
    async def test_connection_error_sets_unavailable(self):
        entity = _make_update_entity()
        entity._attr_state = "V3.90.1"

        mock_session = MagicMock()
        mock_session.get = MagicMock(side_effect=Exception("Connection refused"))

        with patch(
            "custom_components.luxtronik2.update.async_get_clientsession",
            return_value=mock_session,
        ):
            await entity._request_available_firmware_version()

        assert (
            entity._LuxtronikUpdateEntity__firmware_version_available
            == STATE_UNAVAILABLE
        )


# ===========================================================================
# release_notes
# ===========================================================================


class TestReleaseNotes:
    def test_returns_html_with_all_info(self):
        entity = _make_update_entity()
        entity._attr_state = "V3.90.1"
        entity._LuxtronikUpdateEntity__firmware_version_available = "V3.91.0"
        entity._LuxtronikUpdateEntity__firmware_version_changelog = "Bug fixes"
        result = entity.release_notes()
        assert result is not None
        assert "V3.91.0" in result
        assert "Bug fixes" in result
        assert "Alpha Innotec" in result

    def test_returns_none_for_unknown_prefix(self):
        entity = _make_update_entity()
        entity._attr_state = "X99.0.0"
        assert entity.release_notes() is None

    def test_german_language_uses_de_manual(self):
        entity = _make_update_entity()
        entity._attr_state = "V3.90.1"
        entity.hass.config.language = "de"
        entity._LuxtronikUpdateEntity__firmware_version_available = "V3.91.0"
        entity._LuxtronikUpdateEntity__firmware_version_changelog = "Fixes"
        result = entity.release_notes()
        assert result is not None
