import pytest

from custom_components.luxtronik2.update import LuxtronikUpdateEntity


@pytest.mark.parametrize(
    ("filename", "expected"),
    [
        ("wp2reg-V3.91.0_d0dc76bb", "V3.91.0"),
        ("wp2reg-V2.88.1-9086", "V2.88.1-9086"),
        ("wpreg.V1.88.3-9717", "V1.88.3-9717"),
        ("otherprefix-V2.99.2-1234", "V2.99.2-1234"),
        ("something-V3.91.0_moretext", "V3.91.0"),
        ("nofirmwarehere.txt", None),
    ],
)
def test_extract_firmware_version(filename: str, expected: str | None):
    assert LuxtronikUpdateEntity.extract_firmware_version(filename) == expected
