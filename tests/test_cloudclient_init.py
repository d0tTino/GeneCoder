import genecoder
import pytest

httpx = pytest.importorskip("httpx")


def test_cloudclient_lazy_import() -> None:
    cls = genecoder.CloudClient
    assert isinstance(cls, type)
    assert cls.__name__ == "CloudClient"
