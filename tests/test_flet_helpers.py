from genecoder.flet_helpers import parse_int_input


def test_parse_int_input_basic():
    assert parse_int_input("10", 5) == 10
    assert parse_int_input("", 5) == 5
    assert parse_int_input("abc", 5) == 5
    assert parse_int_input("-1", 5) == 5
    assert parse_int_input("2", 5, min_value=2) == 2
    assert parse_int_input("1", 5, min_value=2) == 5
