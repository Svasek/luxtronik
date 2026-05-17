"""Tests for async_get_mac_address in common.py."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from custom_components.luxtronik2.common import async_get_mac_address


class TestAsyncGetMacAddress:
    @pytest.mark.asyncio
    async def test_ipv4_address(self):
        hass = MagicMock()
        hass.async_add_executor_job = AsyncMock(return_value="aa:bb:cc:dd:ee:ff")
        result = await async_get_mac_address(hass, "192.168.1.100")
        assert result == "aa:bb:cc:dd:ee:ff"

    @pytest.mark.asyncio
    async def test_ipv6_address(self):
        hass = MagicMock()
        hass.async_add_executor_job = AsyncMock(return_value="aa:bb:cc:dd:ee:ff")
        result = await async_get_mac_address(hass, "::1")
        assert result == "aa:bb:cc:dd:ee:ff"

    @pytest.mark.asyncio
    async def test_hostname(self):
        hass = MagicMock()
        hass.async_add_executor_job = AsyncMock(return_value="aa:bb:cc:dd:ee:ff")
        result = await async_get_mac_address(hass, "heatpump.local")
        assert result == "aa:bb:cc:dd:ee:ff"

    @pytest.mark.asyncio
    async def test_no_mac_returns_none(self):
        hass = MagicMock()
        hass.async_add_executor_job = AsyncMock(return_value=None)
        result = await async_get_mac_address(hass, "192.168.1.100")
        assert result is None

    @pytest.mark.asyncio
    async def test_empty_mac_returns_none(self):
        hass = MagicMock()
        hass.async_add_executor_job = AsyncMock(return_value="")
        result = await async_get_mac_address(hass, "192.168.1.100")
        assert result is None
