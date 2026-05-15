"""Tests for custom_components.luxtronik.coordinator."""

from __future__ import annotations

import asyncio
from typing import Any
from unittest.mock import AsyncMock, MagicMock, PropertyMock, patch

import pytest

from homeassistant.const import CONF_HOST, CONF_PORT, CONF_TIMEOUT
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.update_coordinator import UpdateFailed
from packaging.version import Version

from custom_components.luxtronik.const import (
    CONF_MAX_DATA_LENGTH,
    DEFAULT_MAX_DATA_LENGTH,
    DEFAULT_TIMEOUT,
    DOMAIN,
    DeviceKey,
    LuxCalculation as LC,
    LuxMkTypes,
    LuxParameter as LP,
    LuxVisibility as LV,
)
from custom_components.luxtronik.coordinator import (
    LuxtronikConnectionError,
    LuxtronikCoordinator,
)
from custom_components.luxtronik.model import (
    LuxtronikCoordinatorData,
    LuxtronikEntityDescription,
)

from conftest import make_coordinator_data


# ===========================================================================
# Helpers
# ===========================================================================


def _make_coordinator(
    hass=None,
    parameters: dict[str, Any] | None = None,
    calculations: dict[str, Any] | None = None,
    visibilities: dict[str, Any] | None = None,
) -> LuxtronikCoordinator:
    """Build a coordinator with fake data for unit tests."""
    if hass is None:
        hass = MagicMock()
        hass.async_add_executor_job = AsyncMock(
            side_effect=lambda fn, *a, **kw: fn(*a, **kw)
        )

    client = MagicMock()
    data = make_coordinator_data(
        parameters=parameters or {},
        calculations=calculations or {},
        visibilities=visibilities or {},
    )
    client.parameters = data.parameters
    client.calculations = data.calculations
    client.visibilities = data.visibilities

    config = {
        CONF_HOST: "192.168.1.100",
        CONF_PORT: 8889,
    }

    with patch("homeassistant.helpers.frame.report_usage"):
        coordinator = LuxtronikCoordinator(hass=hass, client=client, config=config)
    coordinator.data = data
    return coordinator


# ===========================================================================
# LuxtronikCoordinator properties
# ===========================================================================


class TestCoordinatorProperties:
    def test_unique_id(self):
        coord = _make_coordinator(
            parameters={
                "ID_WP_SerienNummer_DATUM": 20230101,
                "ID_WP_SerienNummer_HEX": 255,
            }
        )
        uid = coord.unique_id
        assert isinstance(uid, str)
        assert "_" in uid  # serial_number_date-serial_number_hex

    def test_model(self):
        coord = _make_coordinator(calculations={"ID_WEB_Code_WP_akt": 27})
        assert coord.model == "27"

    def test_model_none(self):
        coord = _make_coordinator()
        # No model data → empty string
        assert coord.model == ""

    def test_manufacturer_novelan(self):
        coord = _make_coordinator(calculations={"ID_WEB_Code_WP_akt": "BW something"})
        assert coord.manufacturer == "Novelan"

    def test_manufacturer_alpha_innotec(self):
        coord = _make_coordinator(calculations={"ID_WEB_Code_WP_akt": "LWP 10"})
        assert coord.manufacturer == "Alpha Innotec"

    def test_manufacturer_unknown(self):
        coord = _make_coordinator(calculations={"ID_WEB_Code_WP_akt": "UNKNOWN"})
        assert coord.manufacturer is None

    def test_firmware_version(self):
        coord = _make_coordinator(calculations={"ID_WEB_SoftStand": "V3.90.1"})
        assert coord.firmware_version == "V3.90.1"

    def test_firmware_package_version(self):
        coord = _make_coordinator(calculations={"ID_WEB_SoftStand": "V3.90.1"})
        ver = coord.firmware_package_version
        assert isinstance(ver, Version)
        assert ver == Version("3.90.1")

    def test_firmware_package_version_invalid(self):
        coord = _make_coordinator(calculations={"ID_WEB_SoftStand": "invalid_firmware"})
        ver = coord.firmware_package_version
        assert ver == Version("0")

    def test_firmware_version_minor(self):
        coord = _make_coordinator(calculations={"ID_WEB_SoftStand": "V3.90.1"})
        minor = coord.firmware_version_minor
        assert minor == Version("90.1")

    def test_firmware_version_minor_short(self):
        coord = _make_coordinator(calculations={"ID_WEB_SoftStand": "V3.90"})
        minor = coord.firmware_version_minor
        assert minor == Version("90.0")

    def test_serial_number(self):
        coord = _make_coordinator(
            parameters={
                "ID_WP_SerienNummer_DATUM": 20230101,
                "ID_WP_SerienNummer_HEX": 255,
            }
        )
        sn = coord.serial_number
        assert "20230101" in sn
        assert "ff" in sn.lower()  # hex(255) = 0xff


# ===========================================================================
# device_key_active
# ===========================================================================


class TestDeviceKeyActive:
    def test_heatpump_always_active(self):
        coord = _make_coordinator()
        assert coord.device_key_active(DeviceKey.heatpump) is True

    def test_heating_active(self):
        coord = _make_coordinator(calculations={"ID_WEB_Zaehler_BetrZeitHz": 100})
        assert coord.device_key_active(DeviceKey.heating) is True

    def test_heating_inactive(self):
        coord = _make_coordinator(calculations={"ID_WEB_Zaehler_BetrZeitHz": 0})
        assert coord.device_key_active(DeviceKey.heating) is False

    def test_domestic_water_active(self):
        coord = _make_coordinator(calculations={"ID_WEB_Zaehler_BetrZeitBW": 100})
        assert coord.device_key_active(DeviceKey.domestic_water) is True

    def test_domestic_water_inactive(self):
        coord = _make_coordinator(calculations={"ID_WEB_Zaehler_BetrZeitBW": 0})
        assert coord.device_key_active(DeviceKey.domestic_water) is False

    def test_cooling_active(self):
        coord = _make_coordinator(calculations={"ID_WEB_Zaehler_BetrZeitKue": 100})
        assert coord.device_key_active(DeviceKey.cooling) is True

    def test_cooling_inactive(self):
        coord = _make_coordinator(calculations={"ID_WEB_Zaehler_BetrZeitKue": 0})
        assert coord.device_key_active(DeviceKey.cooling) is False

    def test_unknown_device_key_raises(self):
        coord = _make_coordinator()
        with pytest.raises(NotImplementedError):
            coord.device_key_active("unknown_key")


# ===========================================================================
# entity_visible
# ===========================================================================


class TestEntityVisible:
    def test_unset_visibility_always_visible(self):
        coord = _make_coordinator()
        desc = LuxtronikEntityDescription(key="test")
        assert coord.entity_visible(desc) is True

    def test_visibility_value_positive(self):
        coord = _make_coordinator(visibilities={"ID_Visi_Zirkulationspumpe": 1})
        desc = LuxtronikEntityDescription(
            key="test",
            visibility=LV.V0059_DHW_CIRCULATION_PUMP,
        )
        # This uses special detection logic for DHW pump
        result = coord.entity_visible(desc)
        assert isinstance(result, bool)

    def test_solar_visibility_no_solar(self):
        coord = _make_coordinator(
            visibilities={
                "ID_Visi_Solar": 0,
                "ID_Visi_Solar_Kollektor": 0,
                "ID_Visi_Solar_Puffer": 0,
            },
            parameters={"ID_Einst_SolBW_akt": 0},
        )
        desc = LuxtronikEntityDescription(
            key="test",
            visibility=LV.V0250_SOLAR,
        )
        assert coord.entity_visible(desc) is False

    def test_cooling_visibility(self):
        coord = _make_coordinator(
            visibilities={"ID_Visi_Kuhlung": 0},
            parameters={
                "ID_Einst_HzMKE1_akt": 0,
                "ID_Einst_HzMKE2_akt": 0,
                "ID_Einst_HzMKE3_akt": 0,
            },
        )
        desc = LuxtronikEntityDescription(
            key="test",
            visibility=LV.V0005_COOLING,
        )
        assert coord.entity_visible(desc) is False


# ===========================================================================
# entity_active
# ===========================================================================


class TestEntityActive:
    def test_version_incompatible(self):
        coord = _make_coordinator(calculations={"ID_WEB_SoftStand": "V3.90.1"})
        desc = LuxtronikEntityDescription(
            key="test",
            min_firmware_version=Version("4.0.0"),
        )
        assert coord.entity_active(desc) is False

    def test_version_compatible(self):
        coord = _make_coordinator(
            calculations={
                "ID_WEB_SoftStand": "V3.90.1",
                "ID_WEB_Zaehler_BetrZeitHz": 100,
            },
        )
        desc = LuxtronikEntityDescription(
            key="test",
            min_firmware_version=Version("3.0.0"),
        )
        assert coord.entity_active(desc) is True

    def test_max_version_exceeded(self):
        coord = _make_coordinator(calculations={"ID_WEB_SoftStand": "V3.90.1"})
        desc = LuxtronikEntityDescription(
            key="test",
            max_firmware_version=Version("3.0.0"),
        )
        assert coord.entity_active(desc) is False

    def test_device_key_inactive_disables_entity(self):
        coord = _make_coordinator(
            calculations={
                "ID_WEB_SoftStand": "V3.90.1",
                "ID_WEB_Zaehler_BetrZeitKue": 0,
            },
        )
        desc = LuxtronikEntityDescription(
            key="test",
            device_key=DeviceKey.cooling,
        )
        assert coord.entity_active(desc) is False

    def test_invisible_if_value_match(self):
        coord = _make_coordinator(
            calculations={
                "ID_WEB_SoftStand": "V3.90.1",
                "ID_WEB_Zaehler_BetrZeitHz": 100,
            },
            parameters={"ID_Ba_Hz_akt": "Off"},
        )
        desc = LuxtronikEntityDescription(
            key="test",
            luxtronik_key=LP.P0003_MODE_HEATING,
            invisible_if_value="Off",
        )
        assert coord.entity_active(desc) is False


# ===========================================================================
# get_value / get_sensor
# ===========================================================================


class TestCoordinatorGetValue:
    def test_get_value_existing(self):
        coord = _make_coordinator(calculations={"ID_WEB_Temperatur_TVL": 30.0})
        assert coord.get_value(LC.C0010_FLOW_IN_TEMPERATURE) == 30.0

    def test_get_value_missing(self):
        coord = _make_coordinator()
        assert coord.get_value("parameters.nonexistent") is None

    def test_get_sensor_by_id_invalid_format(self):
        coord = _make_coordinator()
        assert coord.get_sensor_by_id("no_dot_here") is None

    def test_get_sensor_existing(self):
        coord = _make_coordinator(parameters={"ID_Ba_Hz_akt": "Automatic"})
        sensor = coord.get_sensor("parameters", "ID_Ba_Hz_akt")
        assert sensor is not None
        assert sensor.value == "Automatic"

    def test_get_sensor_unknown_group(self):
        coord = _make_coordinator()
        assert coord.get_sensor("unknown_group", "some_key") is None


# ===========================================================================
# async operations
# ===========================================================================


class TestCoordinatorAsync:
    @pytest.mark.asyncio
    async def test_async_update_data(self):
        hass = MagicMock()
        hass.async_add_executor_job = AsyncMock(
            side_effect=lambda fn, *a, **kw: fn(*a, **kw)
        )

        client = MagicMock()
        from conftest import FakeSensorGroup

        client.parameters = FakeSensorGroup({"key1": "val1"})
        client.calculations = FakeSensorGroup({"key2": "val2"})
        client.visibilities = FakeSensorGroup({"key3": "val3"})

        with patch("homeassistant.helpers.frame.report_usage"):
            coord = LuxtronikCoordinator(
                hass=hass,
                client=client,
                config={CONF_HOST: "192.168.1.100", CONF_PORT: 8889},
            )

        data = await coord._async_update_data()
        assert data is not None
        client.read.assert_called_once()

    @pytest.mark.asyncio
    async def test_async_update_data_error(self):
        hass = MagicMock()
        hass.async_add_executor_job = AsyncMock(side_effect=OSError("connection lost"))

        client = MagicMock()
        with patch("homeassistant.helpers.frame.report_usage"):
            coord = LuxtronikCoordinator(
                hass=hass,
                client=client,
                config={CONF_HOST: "192.168.1.100", CONF_PORT: 8889},
            )

        with pytest.raises(UpdateFailed):
            await coord._async_update_data()

    @pytest.mark.asyncio
    async def test_async_shutdown(self):
        coord = _make_coordinator()
        coord.client = MagicMock()
        # Patch parent shutdown
        with patch.object(
            LuxtronikCoordinator.__bases__[0], "async_shutdown", new_callable=AsyncMock
        ):
            await coord.async_shutdown()
            # client should be deleted
            assert not hasattr(coord, "client") or coord.client is None


# ===========================================================================
# LuxtronikConnectionError
# ===========================================================================


class TestLuxtronikConnectionError:
    def test_error_message(self):
        err = LuxtronikConnectionError("192.168.1.100", 8889, TimeoutError("timeout"))
        assert "192.168.1.100" in str(err)
        assert "8889" in str(err)
        assert "TimeoutError" in str(err)
        assert err.host == "192.168.1.100"
        assert err.port == 8889


# ===========================================================================
# _is_version_not_compatible
# ===========================================================================


class TestIsVersionNotCompatible:
    def test_no_constraints(self):
        coord = _make_coordinator(calculations={"ID_WEB_SoftStand": "V3.90.1"})
        desc = LuxtronikEntityDescription(key="test")
        assert coord._is_version_not_compatible(desc) is False

    def test_min_version_met(self):
        coord = _make_coordinator(calculations={"ID_WEB_SoftStand": "V3.90.1"})
        desc = LuxtronikEntityDescription(
            key="test", min_firmware_version=Version("3.0.0")
        )
        assert coord._is_version_not_compatible(desc) is False

    def test_min_version_not_met(self):
        coord = _make_coordinator(calculations={"ID_WEB_SoftStand": "V3.90.1"})
        desc = LuxtronikEntityDescription(
            key="test", min_firmware_version=Version("4.0.0")
        )
        assert coord._is_version_not_compatible(desc) is True

    def test_max_version_met(self):
        coord = _make_coordinator(calculations={"ID_WEB_SoftStand": "V3.90.1"})
        desc = LuxtronikEntityDescription(
            key="test", max_firmware_version=Version("4.0.0")
        )
        assert coord._is_version_not_compatible(desc) is False

    def test_max_version_exceeded(self):
        coord = _make_coordinator(calculations={"ID_WEB_SoftStand": "V3.90.1"})
        desc = LuxtronikEntityDescription(
            key="test", max_firmware_version=Version("3.0.0")
        )
        assert coord._is_version_not_compatible(desc) is True

    def test_min_minor_version_met(self):
        coord = _make_coordinator(calculations={"ID_WEB_SoftStand": "V3.90.1"})
        desc = LuxtronikEntityDescription(
            key="test", min_firmware_version_minor=Version("80.0")
        )
        assert coord._is_version_not_compatible(desc) is False

    def test_min_minor_version_not_met(self):
        coord = _make_coordinator(calculations={"ID_WEB_SoftStand": "V3.90.1"})
        desc = LuxtronikEntityDescription(
            key="test", min_firmware_version_minor=Version("91.0")
        )
        assert coord._is_version_not_compatible(desc) is True

    def test_max_minor_version_exceeded(self):
        coord = _make_coordinator(calculations={"ID_WEB_SoftStand": "V3.90.1"})
        desc = LuxtronikEntityDescription(
            key="test", max_firmware_version_minor=Version("89.0")
        )
        assert coord._is_version_not_compatible(desc) is True


# ===========================================================================
# Detection methods
# ===========================================================================


class TestDetectionMethods:
    def test_detect_solar_not_present(self):
        coord = _make_coordinator(
            visibilities={
                "ID_Visi_Solar": 0,
                "ID_Visi_Solar_Kollektor": 0,
                "ID_Visi_Solar_Puffer": 0,
            },
            parameters={"ID_BSTD_Solar": 0},
        )
        assert coord._detect_solar_present() is False

    def test_detect_solar_by_visibility(self):
        coord = _make_coordinator(
            visibilities={"ID_Visi_Solar": 1},
        )
        assert coord._detect_solar_present() is True

    def test_detect_solar_by_operation_hours(self):
        coord = _make_coordinator(
            visibilities={"ID_Visi_Solar": 0},
            parameters={"ID_BSTD_Solar": 100.0},
        )
        assert coord._detect_solar_present() is True

    def test_detect_solar_by_collector_temp(self):
        coord = _make_coordinator(
            visibilities={
                "ID_Visi_Solar": 0,
                "ID_Visi_Temp_Solarkoll": 1,
            },
            parameters={"ID_BSTD_Solar": 0},
            calculations={"ID_WEB_Temperatur_TSK": 25.0},
        )
        assert coord._detect_solar_present() is True

    def test_detect_solar_by_buffer_temp(self):
        coord = _make_coordinator(
            visibilities={
                "ID_Visi_Solar": 0,
                "ID_Visi_Temp_Solarkoll": 0,
                "ID_Visi_Temp_Solarsp": 1,
            },
            parameters={"ID_BSTD_Solar": 0},
            calculations={
                "ID_WEB_Temperatur_TSK": 5.0,
                "ID_WEB_Temperatur_TSS": 50.0,
            },
        )
        assert coord._detect_solar_present() is True

    def test_detect_dhw_circulation_pump_present(self):
        coord = _make_coordinator(
            parameters={"ID_Einst_BWZIP_akt": 0},
        )
        assert coord._detect_dhw_circulation_pump_present() is True

    def test_detect_dhw_circulation_pump_not_present(self):
        coord = _make_coordinator(
            parameters={"ID_Einst_BWZIP_akt": 1},
        )
        assert coord._detect_dhw_circulation_pump_present() is False

    def test_detect_dhw_circulation_pump_none(self):
        coord = _make_coordinator()
        assert coord._detect_dhw_circulation_pump_present() is False

    def test_detect_cooling_present(self):
        coord = _make_coordinator(
            parameters={
                "ID_Einst_MK1Typ_akt": 3,  # LuxMkTypes.cooling.value
            },
        )
        assert coord.detect_cooling_present() is True

    def test_detect_cooling_not_present(self):
        coord = _make_coordinator(
            parameters={
                "ID_Einst_MK1Typ_akt": 0,
                "ID_Einst_MK2Typ_akt": 0,
                "ID_Einst_HzMKE3_akt": 0,
            },
        )
        assert coord.detect_cooling_present() is False

    def test_get_device_creates_info(self):
        coord = _make_coordinator(
            calculations={
                "ID_WEB_SoftStand": "V3.90.1",
                "ID_WEB_Code_WP_akt": "LWP 10",
            },
            parameters={
                "ID_WP_SerienNummer_DATUM": 20230101,
                "ID_WP_SerienNummer_HEX": 255,
            },
        )
        device = coord.get_device(DeviceKey.heatpump)
        assert device is not None
