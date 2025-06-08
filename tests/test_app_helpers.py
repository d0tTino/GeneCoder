import re

from genecoder.app_helpers import EncodeOptions, perform_encoding, perform_decoding


def test_roundtrip_base4_direct_hamming():
    data = b"Hello GeneCoder"
    opts = EncodeOptions(
        method="Base-4 Direct",
        add_parity=True,
        k_value=7,
        fec_method="Hamming(7,4)",
    )
    enc = perform_encoding(data, opts)
    header_line = enc.fasta.splitlines()[0]
    assert "fec=hamming_7_4" in header_line
    assert any("Hamming(7,4) FEC applied." in m for m in enc.info_messages)
    assert any("Add Parity" in m for m in enc.info_messages)

    corrected = enc.fasta.replace("method=base_4_direct", "method=base4_direct")
    dec = perform_decoding(corrected)
    assert dec.decoded_bytes == data
    assert re.search(r"Hamming\(7,4\) FEC: \d+ corrected", dec.status_message)
