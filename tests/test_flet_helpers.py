import pytest
from genecoder.flet_helpers import parse_int_input


@pytest.mark.parametrize(
    "value, default, min_value, expected",
    [
        ("10", 5, 1, 10),
        ("", 5, 1, 5),
        (None, 5, 1, 5),
        ("abc", 5, 1, 5),
    ],
)
def test_parse_int_input_valid_and_invalid(value, default, min_value, expected):
    assert parse_int_input(value, default, min_value) == expected


def test_parse_int_input_out_of_range():
    with pytest.raises(ValueError):
        parse_int_input("1", 5, min_value=2)
    with pytest.raises(ValueError):
        parse_int_input("-1", 5)
