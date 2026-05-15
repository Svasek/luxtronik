"""Tests for custom_components.luxtronik.diagnostics."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from custom_components.luxtronik.diagnostics import _dump_items

from conftest import FakeSensorItem


class TestDumpItems:
    def test_empty_dict(self):
        result = _dump_items({})
        assert result == {}

    def test_single_item(self):
        items = {0: FakeSensorItem("test_param", 42)}
        result = _dump_items(items)
        assert len(result) == 1
        key = list(result.keys())[0]
        assert "0" in key
        assert "test_param" in key

    def test_multiple_items_sorted(self):
        items = {
            2: FakeSensorItem("param_c", 3),
            0: FakeSensorItem("param_a", 1),
            1: FakeSensorItem("param_b", 2),
        }
        result = _dump_items(items)
        assert len(result) == 3
        keys = list(result.keys())
        # Should be sorted by index
        assert "0" in keys[0]
        assert "1" in keys[1]
        assert "2" in keys[2]
