from genecoder.core import _count_errors


def test_count_errors_large_sequences():
    base = "A" * 50_000

    sub_seq = base[:25_000] + "C" + base[25_001:]
    assert _count_errors(base, sub_seq) == (1, 0, 0)

    ins_seq = base[:25_000] + "C" + base[25_000:]
    assert _count_errors(base, ins_seq) == (0, 1, 0)

    del_seq = base[:25_000] + base[25_001:]
    assert _count_errors(base, del_seq) == (0, 0, 1)

