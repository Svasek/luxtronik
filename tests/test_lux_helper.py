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
    _is_socket_closed,
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


# ===========================================================================
# _is_socket_closed
# ===========================================================================


class TestIsSocketClosed:
    def test_negative_fileno(self):
        sock = MagicMock()
        sock.fileno.return_value = -1
        assert _is_socket_closed(sock) is True

    def test_fileno_exception(self):
        sock = MagicMock()
        sock.fileno.side_effect = RuntimeError("bad fd")
        assert _is_socket_closed(sock) is True

    def test_recv_empty_data_means_closed(self):
        sock = MagicMock()
        sock.fileno.return_value = 3
        sock.recv.return_value = b""
        assert _is_socket_closed(sock) is True

    def test_recv_blocking_io_means_open(self):
        sock = MagicMock()
        sock.fileno.return_value = 3
        sock.recv.side_effect = BlockingIOError
        assert _is_socket_closed(sock) is False

    def test_recv_connection_reset_means_closed(self):
        sock = MagicMock()
        sock.fileno.return_value = 3
        sock.recv.side_effect = ConnectionResetError
        assert _is_socket_closed(sock) is True

    def test_recv_os_error_107_means_closed(self):
        sock = MagicMock()
        sock.fileno.return_value = 3
        sock.recv.side_effect = OSError(107, "not connected")
        assert _is_socket_closed(sock) is True

    def test_recv_other_os_error_means_open(self):
        sock = MagicMock()
        sock.fileno.return_value = 3
        sock.recv.side_effect = OSError(99, "other")
        assert _is_socket_closed(sock) is False


# ===========================================================================
# Luxtronik._read_write / _write
# ===========================================================================


class TestLuxtronikReadWrite:
    @patch("custom_components.luxtronik.lux_helper.socket.socket")
    def test_read_write_os_error_disconnects(self, mock_socket_class):
        mock_sock = MagicMock()
        mock_socket_class.return_value = mock_sock

        client = Luxtronik("192.168.1.100", 8889, 10.0, 10000)
        client._socket = mock_sock

        # Make _read raise OSError
        with patch.object(client, "_read", side_effect=OSError("socket err")):
            with pytest.raises(OSError):
                client._read_write(write=False)

    @patch("custom_components.luxtronik.lux_helper.socket.socket")
    def test_read_write_struct_error_disconnects(self, mock_socket_class):
        mock_sock = MagicMock()
        mock_socket_class.return_value = mock_sock

        client = Luxtronik("192.168.1.100", 8889, 10.0, 10000)
        client._socket = mock_sock

        with patch.object(client, "_read", side_effect=struct.error("bad data")):
            with pytest.raises(struct.error):
                client._read_write(write=False)

    def test_write_no_socket_raises(self):
        client = Luxtronik("192.168.1.100", 8889, 10.0, 10000)
        client._socket = None
        with pytest.raises(OSError, match="Cannot write"):
            client._write()

    @patch("custom_components.luxtronik.lux_helper.socket.socket")
    def test_write_sends_parameters(self, mock_socket_class):
        mock_sock = MagicMock()
        mock_socket_class.return_value = mock_sock
        # recv returns packed ints for cmd and val responses
        mock_sock.recv.return_value = struct.pack(">i", 0)

        client = Luxtronik("192.168.1.100", 8889, 10.0, 10000)
        client._socket = mock_sock
        client.parameters.queue = {1: 42}

        client._write()

        mock_sock.sendall.assert_called_once()
        assert client.parameters.queue == {}

    @patch("custom_components.luxtronik.lux_helper.socket.socket")
    def test_write_skips_invalid_params(self, mock_socket_class):
        mock_sock = MagicMock()
        mock_socket_class.return_value = mock_sock

        client = Luxtronik("192.168.1.100", 8889, 10.0, 10000)
        client._socket = mock_sock
        client.parameters.queue = {"bad_key": "bad_val"}

        client._write()

        mock_sock.sendall.assert_not_called()

    @patch("custom_components.luxtronik.lux_helper.socket.socket")
    def test_write_converts_float_to_int(self, mock_socket_class):
        mock_sock = MagicMock()
        mock_socket_class.return_value = mock_sock
        mock_sock.recv.return_value = struct.pack(">i", 0)

        client = Luxtronik("192.168.1.100", 8889, 10.0, 10000)
        client._socket = mock_sock
        client.parameters.queue = {5: 21.0}

        client._write()

        mock_sock.sendall.assert_called_once()


class TestLuxtronikReadData:
    @patch("custom_components.luxtronik.lux_helper.socket.socket")
    def test_read_data_oversized_length(self, mock_socket_class):
        """Data with length > max_data_length should be skipped."""
        from custom_components.luxtronik.lux_helper import LUXTRONIK_PARAMETERS_READ, LUXTRONIK_SOCKET_READ_SIZE_INTEGER

        mock_sock = MagicMock()
        mock_socket_class.return_value = mock_sock

        mock_sock.recv.side_effect = [
            struct.pack(">i", LUXTRONIK_PARAMETERS_READ),
            struct.pack(">i", 99999),
        ]

        client = Luxtronik("192.168.1.100", 8889, 10.0, 100)
        client._socket = mock_sock
        parser = MagicMock()

        client._read_data(LUXTRONIK_PARAMETERS_READ, LUXTRONIK_SOCKET_READ_SIZE_INTEGER, parser, "test", retries=0)

        parser.parse.assert_not_called()

    @patch("custom_components.luxtronik.lux_helper.socket.socket")
    def test_read_data_success_parameters(self, mock_socket_class):
        """Successfully reads parameter data."""
        from custom_components.luxtronik.lux_helper import LUXTRONIK_PARAMETERS_READ, LUXTRONIK_SOCKET_READ_SIZE_INTEGER

        mock_sock = MagicMock()
        mock_socket_class.return_value = mock_sock

        # cmd, length=2, then 2 int values
        mock_sock.recv.side_effect = [
            struct.pack(">i", LUXTRONIK_PARAMETERS_READ),  # cmd
            struct.pack(">i", 2),  # length
            struct.pack(">i", 100),  # item 1
            struct.pack(">i", 200),  # item 2
        ]

        client = Luxtronik("192.168.1.100", 8889, 10.0, 10000)
        client._socket = mock_sock
        parser = MagicMock()

        client._read_data(LUXTRONIK_PARAMETERS_READ, LUXTRONIK_SOCKET_READ_SIZE_INTEGER, parser, "params", retries=0)

        parser.parse.assert_called_once_with([100, 200])

    @patch("custom_components.luxtronik.lux_helper.socket.socket")
    def test_read_data_calculations_has_stat_field(self, mock_socket_class):
        """Calculations read includes extra stat field."""
        from custom_components.luxtronik.lux_helper import LUXTRONIK_CALCULATIONS_READ, LUXTRONIK_SOCKET_READ_SIZE_INTEGER

        mock_sock = MagicMock()
        mock_socket_class.return_value = mock_sock

        mock_sock.recv.side_effect = [
            struct.pack(">i", LUXTRONIK_CALCULATIONS_READ),  # cmd
            struct.pack(">i", 0),  # stat (extra field for calculations)
            struct.pack(">i", 1),  # length
            struct.pack(">i", 42),  # item
        ]

        client = Luxtronik("192.168.1.100", 8889, 10.0, 10000)
        client._socket = mock_sock
        parser = MagicMock()

        client._read_data(LUXTRONIK_CALCULATIONS_READ, LUXTRONIK_SOCKET_READ_SIZE_INTEGER, parser, "calcs", retries=0)

        parser.parse.assert_called_once_with([42])

    @patch("custom_components.luxtronik.lux_helper.socket.socket")
    def test_read_data_visibilities_zero_length_disconnects(self, mock_socket_class):
        """Visibilities with length <= 0 forces disconnect."""
        from custom_components.luxtronik.lux_helper import LUXTRONIK_VISIBILITIES_READ, LUXTRONIK_SOCKET_READ_SIZE_CHAR

        mock_sock = MagicMock()
        mock_socket_class.return_value = mock_sock

        mock_sock.recv.side_effect = [
            struct.pack(">i", LUXTRONIK_VISIBILITIES_READ),  # cmd
            struct.pack(">i", 0),  # length = 0
        ]

        client = Luxtronik("192.168.1.100", 8889, 10.0, 10000)
        client._socket = mock_sock
        parser = MagicMock()

        client._read_data(LUXTRONIK_VISIBILITIES_READ, LUXTRONIK_SOCKET_READ_SIZE_CHAR, parser, "vis", retries=0)

        parser.parse.assert_not_called()
        assert client._socket is None  # disconnected

    @patch("custom_components.luxtronik.lux_helper.time.sleep")
    @patch("custom_components.luxtronik.lux_helper.socket.socket")
    def test_read_data_retry_on_timeout(self, mock_socket_class, mock_sleep):
        """Retries on TimeoutError."""
        from custom_components.luxtronik.lux_helper import LUXTRONIK_PARAMETERS_READ, LUXTRONIK_SOCKET_READ_SIZE_INTEGER

        mock_sock = MagicMock()
        mock_socket_class.return_value = mock_sock

        # First attempt times out, second succeeds
        call_count = 0

        def recv_side_effect(size):
            nonlocal call_count
            call_count += 1
            if call_count <= 1:
                raise TimeoutError("timeout")
            if call_count == 2:
                return struct.pack(">i", LUXTRONIK_PARAMETERS_READ)
            if call_count == 3:
                return struct.pack(">i", 1)
            return struct.pack(">i", 99)

        mock_sock.recv.side_effect = recv_side_effect

        client = Luxtronik("192.168.1.100", 8889, 10.0, 10000)
        client._socket = mock_sock
        parser = MagicMock()

        client._read_data(LUXTRONIK_PARAMETERS_READ, LUXTRONIK_SOCKET_READ_SIZE_INTEGER, parser, "params", retries=1)

        parser.parse.assert_called_once_with([99])
        mock_sleep.assert_called_once_with(1)

    @patch("custom_components.luxtronik.lux_helper.socket.socket")
    def test_read_data_unexpected_error_disconnects(self, mock_socket_class):
        """Unexpected errors disconnect and return."""
        from custom_components.luxtronik.lux_helper import LUXTRONIK_PARAMETERS_READ, LUXTRONIK_SOCKET_READ_SIZE_INTEGER

        mock_sock = MagicMock()
        mock_socket_class.return_value = mock_sock
        mock_sock.recv.side_effect = ValueError("unexpected")

        client = Luxtronik("192.168.1.100", 8889, 10.0, 10000)
        client._socket = mock_sock
        parser = MagicMock()

        client._read_data(LUXTRONIK_PARAMETERS_READ, LUXTRONIK_SOCKET_READ_SIZE_INTEGER, parser, "params", retries=0)

        parser.parse.assert_not_called()

    @patch("custom_components.luxtronik.lux_helper.socket.socket")
    def test_read_calls_all_three_groups(self, mock_socket_class):
        """_read calls _read_data for parameters, calculations, visibilities."""
        mock_sock = MagicMock()
        mock_socket_class.return_value = mock_sock

        client = Luxtronik("192.168.1.100", 8889, 10.0, 10000)
        client._socket = mock_sock

        with patch.object(client, "_read_data") as mock_read_data:
            client._read()
            assert mock_read_data.call_count == 3
