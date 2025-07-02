import re
import benchmarks.error_rate as error_rate
import benchmarks.throughput as throughput


def test_error_rate_main(monkeypatch, capsys):
    monkeypatch.setattr(error_rate, "DATA_SIZE", 10)
    monkeypatch.setattr(error_rate, "encode_base4_direct", lambda d: "A" * (len(d) * 4))
    monkeypatch.setattr(error_rate, "decode_base4_direct", lambda s: (b"\x00" * (len(s) // 4), None))
    monkeypatch.setattr(error_rate, "introduce_errors", lambda s, substitution_prob=0.0: s)
    error_rate.main()
    out = capsys.readouterr().out
    assert re.search(r"BER:", out)


def test_throughput_main(monkeypatch, capsys):
    monkeypatch.setattr(throughput, "DATA_SIZE", 10)
    monkeypatch.setattr(throughput, "encode_base4_direct", lambda d: "A" * (len(d) * 4))
    monkeypatch.setattr(throughput, "decode_base4_direct", lambda s: b"" )
    throughput.main()
    out = capsys.readouterr().out
    assert "encode:" in out and "decode:" in out
