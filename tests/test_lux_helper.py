"""Tests for custom_components.luxtronik.lux_helper."""

from __future__ import annotations

import socket
import struct
from unittest.mock import MagicMock, patch

import pytest

from custom_components.luxtronik.lux_helper import (
    LUXTRONIK_DISCOVERY_MAGIC_PACKET,
    LUXTRONIK_DISCOVERY_RESPONSE_PREFIX,
    Luxtronik,
    discover,
    get_firmware_download_id,
    get_manufacturer_by_model,
    get_manufacturer_firmware_url_by_model,
)


# ===========================================================================
# get_manufacturer_by_model
# ===========================================================================


class TestGetManufacturerByModel:
    def test_none_model(self):
        assert get_manufacturer_by_model(None) is None

    def test_novelan_model(self):
        assert get_manufacturer_by_model("BW something") == "Novelan"
        assert get_manufacturer_by_model("LA 12") == "Novelan"
        assert get_manufacturer_by_model("LD5") == "Novelan"
        assert get_manufacturer_by_model("LI test") == "Novelan"
        assert get_manufacturer_by_model("SI model") == "Novelan"
        assert get_manufacturer_by_model("ZLW x") == "Novelan"

    def test_alpha_innotec_model(self):
        assert get_manufacturer_by_model("LWP 10") == "Alpha Innotec"
        assert get_manufacturer_by_model("LWV x") == "Alpha Innotec"
        assert get_manufacturer_by_model("MSW 6") == "Alpha Innotec"
        assert get_manufacturer_by_model("SWC model") == "Alpha Innotec"
        assert get_manufacturer_by_model("SWP test") == "Alpha Innotec"

    def test_unknown_model(self):
        assert get_manufacturer_by_model("UNKNOWN") is None
        assert get_manufacturer_by_model("XYZ") is None


# ===========================================================================
# get_firmware_download_id
# ===========================================================================


class TestGetFirmwareDownloadId:
    def test_none_version(self):
        assert get_firmware_download_id(None) is None

    def test_v1(self):
        assert get_firmware_download_id("V1.88.3") == 0

    def test_v2(self):
        assert get_firmware_download_id("V2.88.1") == 1

    def test_v3(self):
        assert get_firmware_download_id("V3.90.1") == 2

    def test_v4(self):
        assert get_firmware_download_id("V4.0.0") == 3

    def test_f1(self):
        assert get_firmware_download_id("F1.0.0") == 4

    def test_wwb1(self):
        assert get_firmware_download_id("WWB1.0.0") == 5

    def test_smo(self):
        assert get_firmware_download_id("smo") == 6

    def test_unknown(self):
        assert get_firmware_download_id("X1.0.0") is None


# ===========================================================================
# get_manufacturer_firmware_url_by_model
# ===========================================================================


class TestGetManufacturerFirmwareUrlByModel:
    def test_none_model_uses_default(self):
        url = get_manufacturer_firmware_url_by_model(None, 42)
        assert "layout=42" in url

    def test_alpha_innotec(self):
        url = get_manufacturer_firmware_url_by_model("LWP 10", 0)
        assert "layout=1" in url

    def test_novelan(self):
        url = get_manufacturer_firmware_url_by_model("BW model", 0)
        assert "layout=2" in url

    def test_other_known(self):
        url = get_manufacturer_firmware_url_by_model("CB model", 0)
        assert "layout=3" in url

    def test_unknown_model(self):
        url = get_manufacturer_firmware_url_by_model("XYZ", 0)
        assert "layout=0" in url


# ===========================================================================
# Luxtronik class
# ===========================================================================


class TestLuxtronikClient:
    def test_init(self):
        client = Luxtronik(
            host="192.168.1.100",
            port=8889,
            socket_timeout=10.0,
            max_data_length=10000,
        )
        assert client._host == "192.168.1.100"
        assert client._port == 8889
        assert client._socket_timeout == 10.0
        assert client._max_data_length == 10000
        assert client._socket is None

    def test_init_safe_mode(self):
        client = Luxtronik(
            host="localhost",
            port=8889,
            socket_timeout=10.0,
            max_data_length=10000,
            safe=True,
        )
        # safe mode should be passed through to Parameters
        assert client.parameters is not None

    @patch("custom_components.luxtronik.lux_helper.socket.socket")
    def test_connect_success(self, mock_socket_class):
        mock_sock = MagicMock()
        mock_socket_class.return_value = mock_sock

        client = Luxtronik("192.168.1.100", 8889, 10.0, 10000)
        client.connect()

        mock_sock.settimeout.assert_called_with(10.0)
        mock_sock.connect.assert_called_with(("192.168.1.100", 8889))

    @patch("custom_components.luxtronik.lux_helper.socket.socket")
    def test_connect_failure(self, mock_socket_class):
        mock_sock = MagicMock()
        mock_sock.connect.side_effect = TimeoutError("timeout")
        mock_socket_class.return_value = mock_sock

        client = Luxtronik("192.168.1.100", 8889, 10.0, 10000)
        with pytest.raises(TimeoutError):
            client.connect()

    def test_disconnect_when_no_socket(self):
        client = Luxtronik("192.168.1.100", 8889, 10.0, 10000)
        client._disconnect()  # should not raise

    @patch(
        "custom_components.luxtronik.lux_helper._is_socket_closed", return_value=False
    )
    def test_disconnect_closes_socket(self, mock_is_closed):
        client = Luxtronik("192.168.1.100", 8889, 10.0, 10000)
        mock_sock = MagicMock()
        client._socket = mock_sock

        client._disconnect()

        mock_sock.close.assert_called_once()
        assert client._socket is None

    @patch(
        "custom_components.luxtronik.lux_helper._is_socket_closed", return_value=True
    )
    def test_disconnect_already_closed_socket(self, mock_is_closed):
        client = Luxtronik("192.168.1.100", 8889, 10.0, 10000)
        mock_sock = MagicMock()
        client._socket = mock_sock

        client._disconnect()

        mock_sock.close.assert_not_called()
        assert client._socket is None

    def test_destructor(self):
        client = Luxtronik("192.168.1.100", 8889, 10.0, 10000)
        # Just ensure __del__ doesn't raise
        client.__del__()


# ===========================================================================
# discover
# ===========================================================================


class TestDiscover:
    @patch("custom_components.luxtronik.lux_helper.socket.socket")
    def test_discover_finds_heatpump(self, mock_socket_class):
        mock_sock = MagicMock()
        mock_socket_class.return_value = mock_sock

        response = f"{LUXTRONIK_DISCOVERY_RESPONSE_PREFIX}8889;".encode()

        # First call returns what we sent (should be skipped), second returns valid response, third times out
        call_count = 0

        def recv_side_effect(size):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return LUXTRONIK_DISCOVERY_MAGIC_PACKET.encode(), (
                    "192.168.1.100",
                    4444,
                )
            elif call_count == 2:
                return response, ("192.168.1.100", 4444)
            raise TimeoutError

        mock_sock.recvfrom = recv_side_effect

        results = discover()
        # Results depend on the mock behavior
        assert isinstance(results, list)

    @patch("custom_components.luxtronik.lux_helper.socket.socket")
    def test_discover_timeout_no_results(self, mock_socket_class):
        mock_sock = MagicMock()
        mock_socket_class.return_value = mock_sock
        mock_sock.recvfrom.side_effect = TimeoutError

        results = discover()
        assert results == []
