"""Tests for __init__.py — migration, setup, unload, service registration."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

from homeassistant.const import CONF_HOST, CONF_PORT, CONF_TIMEOUT, Platform as P
from homeassistant.exceptions import ConfigEntryNotReady
import pytest

from custom_components.luxtronik2 import (
    _async_update_config_entry,
    _fix_select_entity_unique_ids,
    _identifiers_exists,
    _up_many,
    async_migrate_entry,
    async_setup_entry,
    async_unload_entry,
    setup_hass_services,
    update_listener,
)
from custom_components.luxtronik2.const import (
    CONF_HA_SENSOR_PREFIX,
    CONF_MAX_DATA_LENGTH,
    CONFIG_ENTRY_VERSION,
    DEFAULT_MAX_DATA_LENGTH,
    DEFAULT_PORT,
    DEFAULT_TIMEOUT,
    DOMAIN,
    SERVICE_WRITE,
    SensorKey as SK,
)

_ENTRY_DATA = {
    CONF_HOST: "192.168.1.100",
    CONF_PORT: DEFAULT_PORT,
    CONF_TIMEOUT: DEFAULT_TIMEOUT,
    CONF_MAX_DATA_LENGTH: DEFAULT_MAX_DATA_LENGTH,
    CONF_HA_SENSOR_PREFIX: DOMAIN,
}


def _mock_entry(version=CONFIG_ENTRY_VERSION):
    entry = MagicMock()
    entry.data = _ENTRY_DATA.copy()
    entry.entry_id = "test_entry_id"
    entry.version = version
    entry.options = {}
    entry.async_on_unload = MagicMock()
    entry.add_update_listener = MagicMock()
    return entry


# ===========================================================================
# _identifiers_exists
# ===========================================================================


class TestIdentifiersExists:
    def test_match(self):
        idents_list = [{(DOMAIN, "abc")}, {(DOMAIN, "def")}]
        assert _identifiers_exists(idents_list, {(DOMAIN, "abc")}) is True

    def test_no_match(self):
        idents_list = [{(DOMAIN, "abc")}]
        assert _identifiers_exists(idents_list, {(DOMAIN, "xyz")}) is False

    def test_empty_list(self):
        assert _identifiers_exists([], {(DOMAIN, "abc")}) is False


# ===========================================================================
# _async_update_config_entry
# ===========================================================================


class TestAsyncUpdateConfigEntry:
    @pytest.mark.asyncio
    async def test_updates_entry(self):
        hass = MagicMock()
        entry = _mock_entry()
        await _async_update_config_entry(hass, entry, {"key": "val"}, 5)
        hass.config_entries.async_update_entry.assert_called_once_with(
            entry, data={"key": "val"}, version=5
        )


# ===========================================================================
# _up_many
# ===========================================================================


class TestUpMany:
    @pytest.mark.asyncio
    async def test_rename_success(self):
        hass = MagicMock()
        entry = _mock_entry()
        ent_reg = MagicMock()
        with patch("custom_components.luxtronik2.async_get", return_value=ent_reg):
            await _up_many(
                hass,
                entry,
                {P.SENSOR: [("old_key", SK.FLOW_OUT_TEMPERATURE)]},
            )
        ent_reg.async_update_entity.assert_called_once()

    @pytest.mark.asyncio
    async def test_rename_key_error(self):
        hass = MagicMock()
        entry = _mock_entry()
        ent_reg = MagicMock()
        ent_reg.async_update_entity.side_effect = KeyError("not found")
        with patch("custom_components.luxtronik2.async_get", return_value=ent_reg):
            # Should not raise
            await _up_many(
                hass,
                entry,
                {P.SENSOR: [("old_key", SK.FLOW_OUT_TEMPERATURE)]},
            )

    @pytest.mark.asyncio
    async def test_rename_value_error(self):
        hass = MagicMock()
        entry = _mock_entry()
        ent_reg = MagicMock()
        ent_reg.async_update_entity.side_effect = ValueError("conflict")
        with patch("custom_components.luxtronik2.async_get", return_value=ent_reg):
            await _up_many(
                hass,
                entry,
                {P.SENSOR: [("old_key", SK.FLOW_OUT_TEMPERATURE)]},
            )

    @pytest.mark.asyncio
    async def test_rename_generic_exception(self):
        hass = MagicMock()
        entry = _mock_entry()
        ent_reg = MagicMock()
        ent_reg.async_update_entity.side_effect = RuntimeError("unexpected")
        with patch("custom_components.luxtronik2.async_get", return_value=ent_reg):
            await _up_many(
                hass,
                entry,
                {P.SENSOR: [("old_key", SK.FLOW_OUT_TEMPERATURE)]},
            )


# ===========================================================================
# _fix_select_entity_unique_ids
# ===========================================================================


class TestFixSelectEntityUniqueIds:
    @pytest.mark.asyncio
    async def test_migrates_old_unique_id(self):
        hass = MagicMock()
        entry = _mock_entry()
        ent_reg = MagicMock()
        ent_reg.async_get_entity_id.return_value = "select.luxtronik2_old"
        with patch("custom_components.luxtronik2.async_get", return_value=ent_reg):
            await _fix_select_entity_unique_ids(hass, entry)
        assert ent_reg.async_update_entity.call_count == 3  # 3 select keys

    @pytest.mark.asyncio
    async def test_skips_when_no_old_entity(self):
        hass = MagicMock()
        entry = _mock_entry()
        ent_reg = MagicMock()
        ent_reg.async_get_entity_id.return_value = None
        with patch("custom_components.luxtronik2.async_get", return_value=ent_reg):
            await _fix_select_entity_unique_ids(hass, entry)
        ent_reg.async_update_entity.assert_not_called()

    @pytest.mark.asyncio
    async def test_handles_value_error(self):
        hass = MagicMock()
        entry = _mock_entry()
        ent_reg = MagicMock()
        ent_reg.async_get_entity_id.return_value = "select.luxtronik2_old"
        ent_reg.async_update_entity.side_effect = ValueError("conflict")
        with patch("custom_components.luxtronik2.async_get", return_value=ent_reg):
            await _fix_select_entity_unique_ids(hass, entry)


# ===========================================================================
# async_migrate_entry
# ===========================================================================


class TestAsyncMigrateEntry:
    @pytest.mark.asyncio
    async def test_already_at_latest_version(self):
        hass = MagicMock()
        entry = _mock_entry(version=CONFIG_ENTRY_VERSION)
        result = await async_migrate_entry(hass, entry)
        assert result is True

    @pytest.mark.asyncio
    async def test_migration_from_v3_to_v4(self):
        hass = MagicMock()
        hass.config_entries.async_entries.return_value = []
        entry = _mock_entry(version=3)
        # Set version to 3 so we migrate 3->4->...->9
        entry.version = 3
        entry.data = {**_ENTRY_DATA}

        with (
            patch(
                "custom_components.luxtronik2._async_update_config_entry",
                new_callable=AsyncMock,
            ) as mock_update,
            patch(
                "custom_components.luxtronik2._rename_entities",
                new_callable=AsyncMock,
            ),
            patch(
                "custom_components.luxtronik2._rename_cooling_entities",
                new_callable=AsyncMock,
            ),
            patch(
                "custom_components.luxtronik2._rename_curve_entities",
                new_callable=AsyncMock,
            ),
            patch(
                "custom_components.luxtronik2._fix_select_entity_unique_ids",
                new_callable=AsyncMock,
            ),
        ):
            result = await async_migrate_entry(hass, entry)

        assert result is True
        # Should have been called for versions 4, 5, 6, 7, 8, 9
        assert mock_update.call_count == 6

    @pytest.mark.asyncio
    async def test_migration_v3_adds_prefix(self):
        hass = MagicMock()
        hass.config_entries.async_entries.return_value = []
        entry = _mock_entry(version=3)
        entry.data = {CONF_HOST: "1.2.3.4", CONF_PORT: 8889}

        with (
            patch(
                "custom_components.luxtronik2._async_update_config_entry",
                new_callable=AsyncMock,
            ),
            patch(
                "custom_components.luxtronik2._rename_entities",
                new_callable=AsyncMock,
            ),
            patch(
                "custom_components.luxtronik2._rename_cooling_entities",
                new_callable=AsyncMock,
            ),
            patch(
                "custom_components.luxtronik2._rename_curve_entities",
                new_callable=AsyncMock,
            ),
            patch(
                "custom_components.luxtronik2._fix_select_entity_unique_ids",
                new_callable=AsyncMock,
            ),
        ):
            result = await async_migrate_entry(hass, entry)

        assert result is True


# ===========================================================================
# update_listener
# ===========================================================================


class TestUpdateListener:
    @pytest.mark.asyncio
    async def test_reloads_entry(self):
        hass = MagicMock()
        hass.config_entries.async_reload = AsyncMock()
        entry = _mock_entry()
        await update_listener(hass, entry)
        hass.config_entries.async_reload.assert_awaited_once_with(entry.entry_id)


# ===========================================================================
# async_unload_entry
# ===========================================================================


class TestAsyncUnloadEntry:
    @pytest.mark.asyncio
    async def test_unload_removes_service_when_last_entry(self):
        hass = MagicMock()
        hass.config_entries.async_unload_platforms = AsyncMock(return_value=True)
        hass.config_entries.async_entries.return_value = []
        entry = _mock_entry()
        entry.runtime_data = MagicMock()
        entry.runtime_data.async_shutdown = AsyncMock()
        result = await async_unload_entry(hass, entry)
        assert result is True
        hass.services.async_remove.assert_called_once_with(DOMAIN, SERVICE_WRITE)

    @pytest.mark.asyncio
    async def test_unload_keeps_service_when_other_entries_remain(self):
        hass = MagicMock()
        hass.config_entries.async_unload_platforms = AsyncMock(return_value=True)
        other_entry = MagicMock()
        other_entry.entry_id = "other_entry"
        hass.config_entries.async_entries.return_value = [other_entry]
        entry = _mock_entry()
        entry.runtime_data = MagicMock()
        entry.runtime_data.async_shutdown = AsyncMock()
        result = await async_unload_entry(hass, entry)
        assert result is True
        hass.services.async_remove.assert_not_called()


# ===========================================================================
# setup_hass_services
# ===========================================================================


class TestSetupHassServices:
    def test_skips_when_already_registered(self):
        hass = MagicMock()
        hass.services.has_service.return_value = True
        entry = _mock_entry()
        setup_hass_services(hass, entry)
        hass.services.async_register.assert_not_called()

    def test_registers_service(self):
        hass = MagicMock()
        hass.services.has_service.return_value = False
        entry = _mock_entry()
        setup_hass_services(hass, entry)
        hass.services.async_register.assert_called_once()


# ===========================================================================
# async_setup_entry
# ===========================================================================


class TestAsyncSetupEntry:
    @pytest.mark.asyncio
    async def test_raises_config_entry_not_ready_on_failure(self):
        hass = MagicMock()
        hass.config_entries.async_forward_entry_setups = AsyncMock()
        hass.services.has_service.return_value = False
        entry = _mock_entry()
        with (
            patch(
                "custom_components.luxtronik2.connect_and_get_coordinator",
                new_callable=AsyncMock,
                side_effect=Exception("Connection failed"),
            ),
            pytest.raises(ConfigEntryNotReady),
        ):
            await async_setup_entry(hass, entry)

    @pytest.mark.asyncio
    async def test_successful_setup(self):
        hass = MagicMock()
        hass.config_entries.async_forward_entry_setups = AsyncMock()
        hass.services.has_service.return_value = False
        entry = _mock_entry()

        coordinator = MagicMock()
        coordinator.manufacturer = "Alpha Innotec"
        coordinator.async_config_entry_first_refresh = AsyncMock()

        with patch(
            "custom_components.luxtronik2.connect_and_get_coordinator",
            new_callable=AsyncMock,
            return_value=coordinator,
        ):
            result = await async_setup_entry(hass, entry)

        assert result is True
        assert entry.runtime_data == coordinator

    @pytest.mark.asyncio
    async def test_setup_no_manufacturer(self):
        hass = MagicMock()
        hass.config_entries.async_forward_entry_setups = AsyncMock()
        hass.services.has_service.return_value = False
        entry = _mock_entry()

        coordinator = MagicMock()
        coordinator.manufacturer = None
        coordinator.async_config_entry_first_refresh = AsyncMock()

        with patch(
            "custom_components.luxtronik2.connect_and_get_coordinator",
            new_callable=AsyncMock,
            return_value=coordinator,
        ):
            result = await async_setup_entry(hass, entry)

        assert result is True
        # Title should start with "Luxtronik @"
        call_args = hass.config_entries.async_update_entry.call_args
        assert "Luxtronik @" in call_args.kwargs.get(
            "title", call_args[1].get("title", "")
        )
